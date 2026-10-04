import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from urllib.error import HTTPError
import worker as w

GAME={'id':'123','home':'VAN','away':'CGY','start':'2026-10-05T02:00:00Z','state':'FUT'}
META={'requested_at':'2026-10-05T01:45:01+00:00','received_at':'2026-10-05T01:45:02+00:00'}

class WorkerTests(unittest.TestCase):
    def test_team_download_filters_season_and_playoffs(self):
        csv=b'season,playoffGame,team,gameDate\n2025,0,VAN,20260401\n2026,1,VAN,20261001\n2026,0,VAN,20261002\n'
        with tempfile.TemporaryDirectory() as d,patch('worker.urlopen',return_value=io.BytesIO(csv)):
            result=w.Collector(Path(d)).refresh_teams(2026)
            self.assertEqual(result['rows'],1)
            self.assertEqual(result['latest_game_date'],'20261002')

    def test_no_current_season_cannot_pass(self):
        csv=b'season,playoffGame,team,gameDate\n2025,0,VAN,20260401\n'
        with tempfile.TemporaryDirectory() as d,patch('worker.urlopen',return_value=io.BytesIO(csv)):
            self.assertEqual(w.Collector(Path(d)).refresh_teams(2026)['status'],'BLOCKED')

    def test_book_scope(self):
        self.assertEqual(w.BOOKS,('fanduel','draftkings','proline_ca_on'))\n        self.assertEqual(w.MANUAL_BOOKS,('bet365',))

    def test_schedule_excludes_preseason(self):
        item={'id':123,'gameType':1,'homeTeam':{'abbrev':'VAN'},'awayTeam':{'abbrev':'CGY'},'startTimeUTC':GAME['start']}
        self.assertEqual(w.schedule_games({'gameWeek':[{'games':[item]}]}),[])

    def test_three_outcomes_invalid_and_later_quote_visible(self):
        e={'id':'abc','home_team':'Vancouver Canucks','away_team':'Calgary Flames','commence_time':GAME['start'],
           'bookmakers':[{'key':'fanduel','markets':[{'key':'h2h','last_update':'2026-10-05T01:46:00Z',
           'outcomes':[{'name':'Vancouver Canucks','price':110},{'name':'Calgary Flames','price':-120},{'name':'Draw','price':300}]}]}]}
        audit=w.audit_market([e],GAME,META)
        self.assertEqual(audit['books']['fanduel']['status'],'INVALID_OUTCOMES')
        self.assertEqual(audit['books']['fanduel']['quote_age_at_target_seconds'],-60)
        self.assertFalse(audit['ready_for_prediction'])

    def test_wrong_start_rejected(self):
        e={'home_team':'Vancouver Canucks','away_team':'Calgary Flames','commence_time':'2026-10-05T03:00:00Z'}
        self.assertEqual(w.audit_market([e],GAME,META)['event_matches'],0)

    def test_no_secret_in_errors(self):
        with patch('worker.urlopen',side_effect=HTTPError('https://example/?apiKey=SECRET',403,'SECRET',{},None)):
            with self.assertRaisesRegex(RuntimeError,'^HTTP_403$'):w.fetch('https://example',{'apiKey':'SECRET'})

    def test_missing_key_does_not_use_network(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ODDS_API_KEY':''}),patch('worker.fetch') as f:
            with self.assertRaisesRegex(RuntimeError,'ODDS_API_KEY_MISSING'):w.Collector(Path(d)).capture([GAME])
            f.assert_not_called()

    def test_capture_is_not_repeated_after_restart(self):
        with tempfile.TemporaryDirectory() as d,patch('worker.now',return_value=datetime(2026,10,5,1,45,1,tzinfo=timezone.utc)):
            c=w.Collector(Path(d));c.games=[GAME];c.last_schedule=w.time.monotonic()
            with patch.object(c,'capture') as f:c.tick();f.assert_called_once()
            c=w.Collector(Path(d));c.games=[GAME];c.last_schedule=w.time.monotonic()
            with patch.object(c,'capture') as f:c.tick();f.assert_not_called()

    def test_late_restart_records_missed_no_odds_call(self):
        with tempfile.TemporaryDirectory() as d,patch('worker.now',return_value=datetime(2026,10,5,1,50,tzinfo=timezone.utc)):
            c=w.Collector(Path(d));c.games=[GAME];c.last_schedule=w.time.monotonic()
            with patch.object(c,'capture') as f:c.tick();f.assert_not_called()
            self.assertEqual(json.loads((Path(d)/'evaluations/123.json').read_text())['status'],'MISSED_OR_NOT_PREGAME')

if __name__=='__main__': unittest.main()
