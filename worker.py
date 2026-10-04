"""Read-only NHL data/odds collector. No wagers or progression mutations.

Uses only Python's standard library. All fetched inputs are evidence awaiting
validation; successful collection does not assert model readiness.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from zoneinfo import ZoneInfo
import feature_engine

BOOKS = ('fanduel', 'draftkings', 'bet365', 'proline_ca_on')
UTC = timezone.utc
TEAMS = 'ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split()

def now(): return datetime.now(UTC)
def stamp(t): return t.isoformat()
def parse(t):
    d = datetime.fromisoformat(t.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d.astimezone(UTC)

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, indent=2, allow_nan=False))
    temp.replace(path)

def fetch(url, params=None):
    # Never log the URL or exception string: odds credentials are query params.
    requested = now()
    query = url + ('?' + urlencode(params) if params else '')
    try:
        with urlopen(Request(query, headers={'User-Agent':'EVResearchCollector/1.0'}), timeout=20) as r:
            payload = r.read(24 * 1024 * 1024 + 1)
            if len(payload) > 24 * 1024 * 1024: raise ValueError('Response too large')
            return payload, {'requested_at':stamp(requested), 'received_at':stamp(now()),
                'http_status':r.status, 'sha256':hashlib.sha256(payload).hexdigest(),
                'credits_remaining':r.headers.get('x-requests-remaining')}
    except HTTPError as e:
        raise RuntimeError(f'HTTP_{e.code}') from None
    except Exception as e:
        raise RuntimeError(type(e).__name__) from None

def archive(root, label, body, meta):
    path = root / 'raw' / (label + '.gz')
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_bytes(gzip.compress(body)); temp.replace(path)
    write_json(root/'raw'/(label+'.meta.json'), meta)

def schedule_games(payload):
    games = {}
    for day in payload.get('gameWeek', []):
        for g in day.get('games', []):
            if g.get('gameType') != 2: continue
            games[str(g['id'])] = {'id':str(g['id']), 'start':g['startTimeUTC'],
                'home':g['homeTeam']['abbrev'], 'away':g['awayTeam']['abbrev'],
                'state':g.get('gameState'), 'season':g.get('season')}
    return list(games.values())

def audit_market(events, game, metadata):
    # Match abbreviations using official name mapping; require start-time equality.
    names = json.loads((Path(__file__).parent/'team_names.json').read_text())
    matches = [e for e in events if e.get('home_team') == names.get(game['home'])
        and e.get('away_team') == names.get(game['away'])
        and parse(e['commence_time']) == parse(game['start'])]
    result = {'event_matches':len(matches), 'books':{}, 'ready_for_prediction':False}
    if len(matches) != 1: return result
    event = matches[0]; result['provider_event_id'] = event['id']
    target = parse(game['start']) - timedelta(minutes=15)
    result['request_offset_seconds'] = (parse(metadata['requested_at'])-target).total_seconds()
    result['receipt_offset_seconds'] = (parse(metadata['received_at'])-target).total_seconds()
    by_book = {b['key']:b for b in event.get('bookmakers', [])}
    for key in BOOKS:
        book = by_book.get(key)
        if not book:
            result['books'][key] = {'status':'MISSING'}; continue
        markets = [m for m in book.get('markets',[]) if m.get('key')=='h2h']
        if len(markets)!=1:
            result['books'][key]={'status':'INVALID_MARKET'}; continue
        market=markets[0]; outcomes=market.get('outcomes',[])
        valid = len(outcomes)==2 and {o.get('name') for o in outcomes} == {event['home_team'],event['away_team']}
        valid = valid and all(type(o.get('price')) in (int,float) and abs(o['price'])>=100 and float(o['price']).is_integer() for o in outcomes)
        updated = market.get('last_update',book.get('last_update'))
        result['books'][key] = {'status':'STRUCTURE_OK' if valid else 'INVALID_OUTCOMES',
            'outcomes':outcomes, 'provider_updated_at':updated,
            'quote_age_at_target_seconds':(target-parse(updated)).total_seconds() if updated else None}
    result['blockers']=['GOALIE_HISTORY_NOT_VALIDATED','STARTERS_NOT_CONFIRMED',
                        'LIVE_FEATURE_REFRESH_NOT_PROMOTED','CAPTURE_TIMING_REQUIRES_REVIEW']
    return result

class Collector:
    def __init__(self, root):
        self.root=root; root.mkdir(parents=True,exist_ok=True)
        self.path=root/'collector_state.json'
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {'processed':{},'calls':{}}
        self.games=[]; self.last_schedule=0; self.next_schedule_try=0

    def save(self): write_json(self.path,self.state)

    def refresh_schedule(self):
        date=now().astimezone(ZoneInfo('America/Toronto')).date().isoformat()
        body,meta=fetch('https://api-web.nhle.com/v1/schedule/'+date)
        games=schedule_games(json.loads(body))
        archive(self.root,'schedule/'+stamp(now()).replace(':','-'),body,meta)
        self.games=games; self.last_schedule=time.monotonic()
        return {'games':len(games),'status':'FETCHED'}

    def refresh_teams(self, season):
        # Published MoneyPuck bulk file. Stream once: preserve the current-season
        # evidence while also feeding all 2015+ history to the exact recovered
        # expanding-state feature builder.
        url='https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv'
        requested=now(); results={}
        try:
            with urlopen(Request(url,headers={'User-Agent':'EVResearchCollector/1.0'}),timeout=60) as response:
                reader=csv.DictReader(io.TextIOWrapper(response,encoding='utf-8-sig'))
                output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=reader.fieldnames);writer.writeheader()
                history=io.StringIO(); hist_writer=csv.DictWriter(history,fieldnames=reader.fieldnames);hist_writer.writeheader()
                count=0;seen=set();latest=None;seasons=set()
                for row in reader:
                    s=int(row['season']);seasons.add(s)
                    if s>=2015 and str(row.get('playoffGame'))=='0': hist_writer.writerow(row)
                    if s!=season or str(row.get('playoffGame'))!='0':continue
                    writer.writerow(row);count+=1;seen.add(row['team'])
                    date=row.get('gameDate',row.get('date'))
                    latest=max(latest or date,date)
            if not count: raise ValueError('NO_CURRENT_SEASON_ROWS; available_max='+str(max(seasons)))
            body=output.getvalue().encode()
            meta={'source':url,'requested_at':stamp(requested),'received_at':stamp(now()),
                  'sha256':hashlib.sha256(body).hexdigest(),'filtered_to_regular_season':season,
                  'rows':count,'latest_game_date':latest,'source_bytes_preserved':False}
            archive(self.root,f'teams/{season}/current_teams',body,meta)
            history_body=history.getvalue().encode()
            feature_rows=feature_engine.from_csv_bytes(history_body,self.games)
            feature_path=self.root/'features'/f'nhl_v1c_live_features_{season}_{season+1}.csv'
            feature_engine.write_csv(feature_path,feature_rows)
            ready=sum(bool(x['ready_for_v1c']) for x in feature_rows)
            feature_meta={'generated_at':stamp(now()),'games':len(feature_rows),'ready':ready,
                'blocked':len(feature_rows)-ready,'source_sha256':hashlib.sha256(history_body).hexdigest(),
                'method':'V1c recovered expanding arithmetic means since 2015-16; strictly pregame'}
            write_json(self.root/'features'/'latest.json',feature_meta)
            results={'status':'FETCHED_FEATURES_BUILT','rows':count,'teams':sorted(seen),
                'latest_game_date':latest,'feature_games':len(feature_rows),'feature_ready':ready}
        except HTTPError as e:results={'status':'BLOCKED','error':f'HTTP_{e.code}'}
        except Exception as e:results={'status':'BLOCKED','error':str(e)}
        write_json(self.root/'team_refresh.json',results)
        return results

    def collect_goalies(self):
        # Official player landing pages contain career/season evidence. Their
        # aggregation is NOT automatically treated as the frozen career contract.
        seed=json.loads((Path(__file__).parent/'seed/opening_state.json').read_text())
        results={}
        def collect(gid):
            try:
                body,meta=fetch(f'https://api-web.nhle.com/v1/player/{gid}/landing')
                obj=json.loads(body)
                if int(obj.get('playerId',-1))!=int(gid): raise ValueError('Player mismatch')
                archive(self.root,f'goalies/{gid}',body,meta)
                results[gid]={'status':'FETCHED_REQUIRES_CAREER_REPLAY'}
            except Exception as e: results[gid]={'status':'BLOCKED','error':str(e)}
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(collect,seed['goalies']))
        write_json(self.root/'goalie_refresh.json',results)
        return results

    def capture(self, games):
        key=os.environ.get('ODDS_API_KEY','')
        day=now().date().isoformat()
        calls=self.state['calls'].get(day,0)
        cap=int(os.environ.get('MAX_ODDS_CALLS_PER_DAY','20'))
        if not key: raise RuntimeError('ODDS_API_KEY_MISSING')
        if calls>=cap: raise RuntimeError('DAILY_ODDS_CALL_CAP')
        # Count before request so crashes cannot cause unlimited retries.
        self.state['calls'][day]=calls+1; self.save()
        body,meta=fetch('https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds',
            {'apiKey':key,'bookmakers':','.join(BOOKS),'markets':'h2h','oddsFormat':'american'})
        events=json.loads(body)
        if not isinstance(events,list): raise ValueError('Unexpected odds response')
        archive(self.root,'odds/'+stamp(now()).replace(':','-'),body,meta)
        for g in games:
            audit=audit_market(events,g,meta)
            write_json(self.root/'evaluations'/(g['id']+'.json'),{'game':g,'status':'DRY_RUN_BLOCKED','audit':audit})
        return meta

    def tick(self):
        t=now(); due=[]
        if time.monotonic()-self.last_schedule>900:
            return
        for g in self.games:
            token=g['id']+'@'+g['start']
            if token in self.state['processed']: continue
            target=parse(g['start'])-timedelta(minutes=15)
            if t<target: continue
            lag=(t-target).total_seconds()
            # 60s is a collection attempt window, NOT an accepted betting tolerance.
            if lag>60 or g['state'] not in ('FUT','PRE'):
                self.state['processed'][token]='MISSED_OR_NOT_PREGAME'
                write_json(self.root/'evaluations'/(g['id']+'.json'),
                    {'game':g,'status':'MISSED_OR_NOT_PREGAME','lag_seconds':lag})
            else: due.append(g)
        if due:
            try: self.capture(due); status='CAPTURED_FOR_REVIEW'
            except Exception as e: status='BLOCKED_'+str(e)
            for g in due: self.state['processed'][g['id']+'@'+g['start']]=status
            print(json.dumps({'event':'capture','games':[g['id'] for g in due],'status':status}),flush=True)
        self.save()

    def run(self):
        print(json.dumps({'event':'worker_started','mode':'READ_ONLY_COLLECTION','books':BOOKS}),flush=True)
        threading.Thread(target=self.maintenance, daemon=True).start()
        while True:
            try:
                if time.monotonic()>=self.next_schedule_try and (not self.last_schedule or time.monotonic()-self.last_schedule>300):
                    self.next_schedule_try=time.monotonic()+300
                    print(json.dumps({'event':'schedule','result':self.refresh_schedule()}),flush=True)
                self.tick()
            except Exception as e:
                print(json.dumps({'event':'error','type':type(e).__name__,'reason':str(e)}),flush=True)
            time.sleep(1)

    def maintenance(self):
        # Independent from the T-15 loop; slow downloads must not delay capture.
        marker=self.root/'maintenance.json'
        while True:
            try:
                previous=json.loads(marker.read_text()) if marker.exists() else {}
                local_now=now().astimezone(ZoneInfo('America/Toronto'))
                day=local_now.date().isoformat()
                season=int(os.environ.get('NHL_SEASON','2026'))
                # MoneyPuck updates nightly, but the exact publish time can vary.
                # Refresh every four hours so an early-morning pre-update fetch
                # cannot leave the live state stale for the entire betting day.
                last_team=parse(previous['team_refreshed_at']) if previous.get('team_refreshed_at') else None
                team_due=last_team is None or (now()-last_team).total_seconds() >= 4*3600
                goalie_due=previous.get('goalie_day') != day
                teams={'status':'NOT_DUE'}
                goalies={}
                if team_due:
                    teams=self.refresh_teams(season)
                    previous['team_refreshed_at']=stamp(now())
                    previous['team_data_status']=teams['status']
                    previous['team_latest_game_date']=teams.get('latest_game_date')
                if goalie_due:
                    goalies=self.collect_goalies()
                    previous['goalie_day']=day
                    previous['goalies_fetched']=sum(v['status'].startswith('FETCHED') for v in goalies.values())
                previous['day']=day
                previous['status']='AUTO_REFRESH_ACTIVE'
                write_json(marker,previous)
                if team_due or goalie_due:
                    print(json.dumps({'event':'automatic_refresh','result':previous}),flush=True)
                for folder,days in [('schedule',7),('odds',60)]:
                    for file in (self.root/'raw'/folder).glob('*'):
                        if file.is_file() and time.time()-file.stat().st_mtime>days*86400: file.unlink()
            except Exception as e:
                print(json.dumps({'event':'maintenance_error','type':type(e).__name__}),flush=True)
            time.sleep(3600)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['run','preflight','teams','goalies','odds-test'])
    p.add_argument('--season',type=int,default=2026); args=p.parse_args()
    c=Collector(Path(os.environ.get('DATA_DIR','./runtime')))
    if args.command=='run': c.run()
    elif args.command=='teams': print(json.dumps(c.refresh_teams(args.season)))
    elif args.command=='goalies': print(json.dumps(c.collect_goalies()))
    elif args.command=='odds-test': print(json.dumps(c.capture([])))
    else:
        result={'mode':'READ_ONLY','key_present':bool(os.environ.get('ODDS_API_KEY'))}
        try: result['schedule']=c.refresh_schedule()
        except Exception as e: result['schedule']={'status':'BLOCKED','reason':str(e)}
        write_json(c.root/'preflight.json',result); print(json.dumps(result))
