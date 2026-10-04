"""Confirmed-starter adapter for the frozen V1c goalie feature.

Automatic providers can POST/serve the documented JSON schema via STARTER_FEED_URL.
A local /var/data/confirmed_starters.json file is the manual fallback. Only
records explicitly marked confirmed are accepted; projected/probable is blocked.
"""
import csv,gzip,json,os
from pathlib import Path
from urllib.request import Request,urlopen
PRIOR_SV=0.91239041; PRIOR_SHOTS=600.0

def load_starters(root):
    source=None
    url=os.environ.get("STARTER_FEED_URL")
    if url:
        with urlopen(Request(url,headers={"User-Agent":"EVResearchCollector/1.0"}),timeout=15) as r:
            source=json.loads(r.read())
    else:
        p=Path(root)/"confirmed_starters.json"
        if p.exists(): source=json.loads(p.read_text())
    if not source:return {}
    out={}
    for x in source.get("games",[]):
        if x.get("status")!="confirmed":continue
        if not x.get("home_goalie_id") or not x.get("away_goalie_id"):continue
        out[str(x["game_id"])]=x
    return out

def goalie_shrunk(root,gid):
    p=Path(root)/"goalie_state.json"
    if not p.exists(): return None
    state=json.loads(p.read_text()).get("goalies",{})
    x=state.get(str(gid))
    return float(x["career_sv_shrunk"]) if x and x.get("career_sv_shrunk") is not None else None

