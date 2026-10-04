"""ESPN pregame NHL probable-starter adapter.

ESPN's public scoreboard is used only to identify the probable/confirmed goalie.
Frozen goalie performance remains sourced from MoneyPuck. Any parse ambiguity
fails closed and leaves the game without an admissible starter.
"""
import json
from datetime import datetime,timezone
from urllib.request import Request,urlopen

URL="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={date}"

def _goalie(comp):
    # ESPN competition competitor objects can expose probable starters under
    # probableStarter; accept only explicit goalie objects with an athlete id.
    p=comp.get("probableStarter") or comp.get("probableStartingGoalie")
    if not isinstance(p,dict): return None
    athlete=p.get("athlete") if isinstance(p.get("athlete"),dict) else p
    gid=athlete.get("id")
    if not gid:return None
    status=str(p.get("status") or p.get("type") or "probable").lower()
    confirmed="confirm" in status
    return {"goalie_id":int(gid),"status":"confirmed" if confirmed else "probable",
            "name":athlete.get("displayName") or athlete.get("fullName")}

def fetch_date(day):
    date=day.strftime("%Y%m%d")
    with urlopen(Request(URL.format(date=date),headers={"User-Agent":"EVResearchCollector/1.0"}),timeout=15) as r:
        obj=json.loads(r.read())
    observed=datetime.now(timezone.utc).isoformat()
    games=[]
    for event in obj.get("events",[]):
        for c in event.get("competitions",[]):
            teams=c.get("competitors",[])
            h=next((x for x in teams if x.get("homeAway")=="home"),None)
            a=next((x for x in teams if x.get("homeAway")=="away"),None)
            if not h or not a:continue
            hg,ag=_goalie(h),_goalie(a)
            if not hg or not ag:continue
            games.append({"espn_event_id":str(event.get("id")),"start":event.get("date"),
              "home_abbrev":h.get("team",{}).get("abbreviation"),"away_abbrev":a.get("team",{}).get("abbreviation"),
              "home_goalie_id":hg["goalie_id"],"away_goalie_id":ag["goalie_id"],
              "status":"confirmed" if hg["status"]=="confirmed" and ag["status"]=="confirmed" else "probable",
              "observed_at":observed,"source":"ESPN probable starter scoreboard",
              "home_goalie_name":hg["name"],"away_goalie_name":ag["name"]})
    return games

def match_to_nhl(games,nhl_games):
    out=[]
    for n in nhl_games:
        m=[g for g in games if g["home_abbrev"]==n["home"] and g["away_abbrev"]==n["away"]]
        if len(m)!=1:continue
        x=dict(m[0]);x["game_id"]=str(n["id"]);out.append(x)
    return {"games":out}
