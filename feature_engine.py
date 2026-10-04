"""Prospective V1c live feature-state builder.

Builds the 11 exactly recovered MoneyPuck team features plus schedule-derived
home_ice/rest/B2B inputs. It deliberately leaves Elo and confirmed-starting-
goalie inputs blocked until their frozen live states are supplied; it never
fabricates those values.
"""
import csv, io, json, math
from collections import defaultdict
from datetime import datetime

SPECS = {
 "home_xgf60_5v5_prior_diff": ("5on5", lambda r: ratio(r,"xGoalsFor","iceTime",3600)),
 "home_xga60_5v5_prior_diff": ("5on5", lambda r: ratio(r,"xGoalsAgainst","iceTime",3600)),
 "home_xgf_pct_5v5_prior_diff": ("5on5", lambda r: num(r,"xGoalsPercentage")),
 "home_corsi_pct_5v5_prior_diff": ("5on5", lambda r: num(r,"corsiPercentage")),
 "home_fenwick_pct_5v5_prior_diff": ("5on5", lambda r: num(r,"fenwickPercentage")),
 "home_shoot_5v5_prior_diff": ("5on5", lambda r: ratio(r,"goalsFor","shotsOnGoalFor")),
 # Frozen V1c coding quirk: numerator is savedShotsOnGoalFor, not Against.
 "home_save_5v5_prior_diff": ("5on5", lambda r: ratio(r,"savedShotsOnGoalFor","shotsOnGoalAgainst")),
 "home_pp_xgf60_prior_diff": ("5on4", lambda r: ratio(r,"xGoalsFor","iceTime",3600)),
 "home_pk_xga60_prior_diff": ("4on5", lambda r: ratio(r,"xGoalsAgainst","iceTime",3600)),
 "home_all_shoot_prior_diff": ("all", lambda r: ratio(r,"goalsFor","shotsOnGoalFor")),
 "home_all_save_prior_diff": ("all", lambda r: ratio(r,"savedShotsOnGoalFor","shotsOnGoalAgainst")),
}
FEATURE_ORDER = ["home_ice","home_elo_pre_diff",*SPECS,
 "home_rest_days_diff","home_b2b_diff","goalie_career_sv_shrunk_diff"]

def num(r,k):
    try:
        v=float(r[k]); return v if math.isfinite(v) else None
    except (KeyError,TypeError,ValueError): return None

def ratio(r,a,b,m=1.0):
    x,y=num(r,a),num(r,b)
    return None if x is None or y in (None,0) else x/y*m

def parse_day(v):
    s=str(v).strip()
    for f in ("%Y%m%d","%Y-%m-%d"):
        try:return datetime.strptime(s[:10],f).date()
        except ValueError:pass
    raise ValueError("Unsupported gameDate")

def build_state(rows, min_season=2015):
    sums=defaultdict(float); counts=defaultdict(int); last={}
    for r in rows:
        try:
            if int(r["season"]) < min_season or str(r.get("playoffGame"))!="0": continue
        except (KeyError,ValueError): continue
        team=r.get("team"); situation=r.get("situation")
        if not team: continue
        if situation=="all":
            d=parse_day(r.get("gameDate",r.get("date")))
            if team not in last or d>last[team]: last[team]=d
        for feature,(need,fn) in SPECS.items():
            if situation!=need: continue
            v=fn(r)
            if v is not None:
                sums[(team,feature)]+=v; counts[(team,feature)]+=1
    means={k:sums[k]/counts[k] for k in counts}
    return means,last,counts

def live_rows(rows, games, elo=None, goalie=None):
    means,last,counts=build_state(rows); out=[]
    elo=elo or {}; goalie=goalie or {}
    for g in games:
        h,a=g["home"],g["away"]; start=datetime.fromisoformat(g["start"].replace("Z","+00:00")).date()
        x={"gameId":g["id"],"date":start.isoformat(),"home_team":h,"away_team":a,"home_ice":1.0}
        blockers=[]
        x["home_elo_pre_diff"]=(elo[h]-elo[a]) if h in elo and a in elo else None
        if x["home_elo_pre_diff"] is None: blockers.append("ELO_STATE_MISSING")
        for feature in SPECS:
            hv,av=means.get((h,feature)),means.get((a,feature))
            x[feature]=hv-av if hv is not None and av is not None else None
            if x[feature] is None: blockers.append("TEAM_HISTORY_MISSING:"+feature)
        hr=(start-last[h]).days-1 if h in last else None
        ar=(start-last[a]).days-1 if a in last else None
        x["home_rest_days_diff"]=hr-ar if hr is not None and ar is not None else None
        x["home_b2b_diff"]=(int(hr==0)-int(ar==0)) if hr is not None and ar is not None else None
        if hr is None or ar is None: blockers.append("REST_HISTORY_MISSING")
        x["goalie_career_sv_shrunk_diff"]=goalie.get(str(g["id"]))
        if x["goalie_career_sv_shrunk_diff"] is None: blockers.append("CONFIRMED_STARTER_GOALIE_FEATURE_MISSING")
        x["ready_for_v1c"]=not blockers
        x["blockers"]=";".join(blockers)
        out.append(x)
    return out

def from_csv_bytes(body,games,elo=None,goalie=None):
    rows=csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    return live_rows(rows,games,elo,goalie)

def write_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=["gameId","date","home_team","away_team",*FEATURE_ORDER,"ready_for_v1c","blockers"]
    temp=path.with_suffix(path.suffix+".tmp")
    with temp.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
    temp.replace(path)
