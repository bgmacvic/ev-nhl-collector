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
    p=Path(root)/"raw"/"goalies"/(str(gid)+".gz")
    if not p.exists(): return None
    obj=json.loads(gzip.decompress(p.read_bytes()))
    c=(obj.get("careerTotals") or {}).get("regularSeason") or {}
    sv=c.get("savePctg",c.get("savePercentage")); shots=c.get("shotsAgainst")
    if sv is None or shots is None:return None
    sv=float(sv); shots=float(shots)
    return (sv*shots+PRIOR_SV*PRIOR_SHOTS)/(shots+PRIOR_SHOTS)

def patch_feature_csv(root,path):
    path=Path(path)
    if not path.exists():return {"status":"NO_FEATURE_TABLE"}
    starters=load_starters(root)
    with path.open(newline="") as f: rows=list(csv.DictReader(f))
    patched=0
    for r in rows:
        s=starters.get(str(r["gameId"]))
        blockers=[x for x in r.get("blockers","").split(";") if x]
        blockers=[x for x in blockers if x!="CONFIRMED_STARTER_GOALIE_FEATURE_MISSING"]
        if s:
            h=goalie_shrunk(root,s["home_goalie_id"]); a=goalie_shrunk(root,s["away_goalie_id"])
            if h is not None and a is not None:
                r["goalie_career_sv_shrunk_diff"]=str(h-a); patched+=1
            else:blockers.append("GOALIE_CAREER_STATS_MISSING")
        else:blockers.append("CONFIRMED_STARTER_GOALIE_FEATURE_MISSING")
        r["blockers"]=";".join(dict.fromkeys(blockers))
        r["ready_for_v1c"]=str(not bool(blockers))
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    tmp.replace(path)
    return {"status":"PATCHED","confirmed_games":len(starters),"patched_rows":patched}
