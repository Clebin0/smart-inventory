from __future__ import annotations
from datetime import datetime, timezone

def score_asset(asset, movement_count:int=0, last_movement=None):
    score=0
    reasons=[]
    if getattr(asset,"status",None)=="maintenance":
        score+=35; reasons.append("asset currently in maintenance")
    if getattr(asset,"status",None)=="in_use" and not getattr(asset,"assigned_to",None):
        score+=30; reasons.append("in-use asset without assigned person")
    if not getattr(asset,"serial_number",None):
        score+=10; reasons.append("missing serial number")
    if not getattr(asset,"location",None):
        score+=10; reasons.append("missing location")
    created=getattr(asset,"created_at",None)
    if created:
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        created_naive=created.replace(tzinfo=None) if getattr(created,"tzinfo",None) else created
        age_days=(now-created_naive).days
        if age_days>1095:
            score+=15; reasons.append("asset record older than three years")
    if movement_count>=12:
        score+=10; reasons.append("high movement frequency")
    if last_movement:
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        lm=last_movement.replace(tzinfo=None) if getattr(last_movement,"tzinfo",None) else last_movement
        if getattr(asset,"status",None)=="maintenance" and (now-lm).days>14:
            score+=25; reasons.append("maintenance state older than 14 days")
    score=min(score,100)
    level="high" if score>=60 else "medium" if score>=30 else "low"
    return {"score":score,"level":level,"reasons":reasons or ["no obvious lifecycle risk signals"]}
