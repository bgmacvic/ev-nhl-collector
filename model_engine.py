"""Frozen EV Martingale v1.1 probability and decision layer. Pure Python."""
import math
FEATURES=["home_ice","home_elo_pre_diff","home_xgf60_5v5_prior_diff","home_xga60_5v5_prior_diff",
"home_xgf_pct_5v5_prior_diff","home_corsi_pct_5v5_prior_diff","home_fenwick_pct_5v5_prior_diff",
"home_shoot_5v5_prior_diff","home_save_5v5_prior_diff","home_pp_xgf60_prior_diff",
"home_pk_xga60_prior_diff","home_all_shoot_prior_diff","home_all_save_prior_diff",
"home_rest_days_diff","home_b2b_diff","goalie_career_sv_shrunk_diff"]
COEF=[0.0,0.27859706673471996,-0.059108412462639016,0.054001752179166876,0.12654885712856795,
0.10947890690998052,-0.12974609276595814,-0.0034664211942101366,0.054343271674296076,
0.060565005644064966,0.011111428361863355,0.04763246683898953,0.0589801086797086,
0.03833301580344778,-0.11527346868600323,0.05816354574047821]
MEAN=[1.0,-0.9883738364406981,-0.00035143898867946597,0.001157153715695322,-0.0001964411619982904,
-0.0001012461624711822,-0.00012356399980659869,-0.0001094817903039928,-0.0004960246802512289,
-0.006282253994465723,0.0037360417349339616,-0.0001390804964707807,-0.0004994351450477628,
0.6108196721311475,-0.1168032786885246,0.00043982690110794134]
SCALE=[1.0,93.50971884138416,0.254670298194005,0.19845992274367544,0.033579199191834386,
0.03003027580943162,0.03009034414939426,0.010737976778806531,0.12534973192277404,
2.0486706185975483,2.625689025177832,0.011521510770086193,0.11082828647705391,
12.509780343641944,0.45145986585858716,0.006876898283052004]
INTERCEPT=0.16826876532961402
PLATT_A=1.0614084412823295; PLATT_B=-0.025296588715599658
LADDER={1:0.20,2:0.25,4:0.30,8:0.35,16:0.40,32:0.45,64:0.50,128:0.55}

def sigmoid(x):
    if x>=0: return 1/(1+math.exp(-x))
    e=math.exp(x); return e/(1+e)
def probability(row):
    missing=[k for k in FEATURES if row.get(k) is None]
    if missing: raise ValueError("MISSING_FEATURES:"+",".join(missing))
    z=INTERCEPT+sum(c*((float(row[k])-m)/s) for k,c,m,s in zip(FEATURES,COEF,MEAN,SCALE))
    raw=sigmoid(z); logit=math.log(raw/(1-raw)); cal=sigmoid(PLATT_A*logit+PLATT_B)
    return raw,cal
def decimal_odds(american):
    a=float(american); return 1+a/100 if a>0 else 1+100/abs(a)
def evaluate(row,home_odds,away_odds,stake):
    raw,p=probability(row); probs={"home":p,"away":1-p}; out=[]
    for side,odds in (("home",home_odds),("away",away_odds)):
        if odds is None: continue
        ev=probs[side]*decimal_odds(odds)-1
        out.append({"side":side,"american_odds":odds,"p_cal":probs[side],"ev":ev,
          "qualifies":float(odds)>=100 and ev>=0.20 and probs[side]>=LADDER[int(stake)]})
    return {"p_raw_home":raw,"p_cal_home":p,"candidates":out}
