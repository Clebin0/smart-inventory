from __future__ import annotations
import csv
import io
import os
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO

import qrcode
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, create_engine, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from risk_engine import score_asset

DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///inventory.db")
APP_TOKEN=os.getenv("APP_TOKEN","demo-token")
connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {}
engine=create_engine(DATABASE_URL,connect_args=connect_args)

class Base(DeclarativeBase): pass

class Asset(Base):
    __tablename__="assets"
    id:Mapped[int]=mapped_column(primary_key=True)
    tag:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(160))
    category:Mapped[str]=mapped_column(String(80),index=True)
    serial_number:Mapped[str|None]=mapped_column(String(120),nullable=True)
    location:Mapped[str]=mapped_column(String(120),default="Estoque",index=True)
    status:Mapped[str]=mapped_column(String(40),default="available",index=True)
    assigned_to:Mapped[str|None]=mapped_column(String(160),nullable=True)
    notes:Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))

class Movement(Base):
    __tablename__="movements"
    id:Mapped[int]=mapped_column(primary_key=True)
    asset_id:Mapped[int]=mapped_column(ForeignKey("assets.id"),index=True)
    action:Mapped[str]=mapped_column(String(40))
    actor:Mapped[str]=mapped_column(String(120))
    destination:Mapped[str|None]=mapped_column(String(120),nullable=True)
    assigned_to:Mapped[str|None]=mapped_column(String(160),nullable=True)
    notes:Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc),index=True)

Base.metadata.create_all(engine)

class Action(str,Enum):
    check_out="check_out"
    check_in="check_in"
    transfer="transfer"
    maintenance="maintenance"
    retire="retire"

class AssetIn(BaseModel):
    tag:str=Field(min_length=2,max_length=80)
    name:str=Field(min_length=2,max_length=160)
    category:str=Field(min_length=2,max_length=80)
    serial_number:str|None=None
    location:str="Estoque"
    status:str="available"
    assigned_to:str|None=None
    notes:str|None=None

class MovementIn(BaseModel):
    action:Action
    actor:str=Field(min_length=2,max_length=120)
    destination:str|None=None
    assigned_to:str|None=None
    notes:str|None=None

def db():
    with Session(engine) as s:
        yield s

def guard(x_app_token:str|None=Header(default=None)):
    if APP_TOKEN and x_app_token!=APP_TOKEN:
        raise HTTPException(401,"Invalid application token")

app=FastAPI(title="Smart Inventory",version="2.1.0")

@app.get("/",response_class=HTMLResponse)
def home():
    with open("frontend.html","r",encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health():
    return {"status":"ok","version":"2.1.0"}

@app.get("/assets",dependencies=[Depends(guard)])
def list_assets(q:str="",status:str="",category:str="",location:str="",s:Session=Depends(db)):
    stmt=select(Asset).order_by(Asset.id.desc())
    if q:
        like=f"%{q}%"
        stmt=stmt.where(or_(Asset.tag.ilike(like),Asset.name.ilike(like),Asset.serial_number.ilike(like),Asset.assigned_to.ilike(like)))
    if status:
        stmt=stmt.where(Asset.status==status)
    if category:
        stmt=stmt.where(Asset.category==category)
    if location:
        stmt=stmt.where(Asset.location==location)
    return s.scalars(stmt).all()

@app.post("/assets",status_code=201,dependencies=[Depends(guard)])
def create_asset(body:AssetIn,s:Session=Depends(db)):
    if s.scalar(select(Asset).where(Asset.tag==body.tag)):
        raise HTTPException(409,"Asset tag already exists")
    a=Asset(**body.model_dump())
    s.add(a); s.commit(); s.refresh(a)
    return a

@app.get("/assets/{asset_id}",dependencies=[Depends(guard)])
def get_asset(asset_id:int,s:Session=Depends(db)):
    a=s.get(Asset,asset_id)
    if not a:
        raise HTTPException(404,"Asset not found")
    return a

@app.put("/assets/{asset_id}",dependencies=[Depends(guard)])
def update_asset(asset_id:int,body:AssetIn,s:Session=Depends(db)):
    a=s.get(Asset,asset_id)
    if not a:
        raise HTTPException(404,"Asset not found")
    duplicate=s.scalar(select(Asset).where(Asset.tag==body.tag,Asset.id!=asset_id))
    if duplicate:
        raise HTTPException(409,"Asset tag already exists")
    for key,value in body.model_dump().items():
        setattr(a,key,value)
    s.commit(); s.refresh(a)
    return a

@app.post("/assets/{asset_id}/movements",status_code=201,dependencies=[Depends(guard)])
def move(asset_id:int,body:MovementIn,s:Session=Depends(db)):
    a=s.get(Asset,asset_id)
    if not a:
        raise HTTPException(404,"Asset not found")
    if body.action=="check_out":
        a.status="in_use"
    elif body.action=="check_in":
        a.status="available"; a.assigned_to=None
    elif body.action=="maintenance":
        a.status="maintenance"
    elif body.action=="retire":
        a.status="retired"
    if body.destination:
        a.location=body.destination
    if body.assigned_to is not None:
        a.assigned_to=body.assigned_to
    m=Movement(asset_id=asset_id,action=body.action.value,actor=body.actor,destination=body.destination,assigned_to=body.assigned_to,notes=body.notes)
    s.add(m); s.commit(); s.refresh(m)
    return m

@app.get("/assets/{asset_id}/movements",dependencies=[Depends(guard)])
def history(asset_id:int,s:Session=Depends(db)):
    return s.scalars(select(Movement).where(Movement.asset_id==asset_id).order_by(Movement.created_at.desc())).all()

@app.get("/assets/{asset_id}/qr")
def qr(asset_id:int,s:Session=Depends(db)):
    if not s.get(Asset,asset_id):
        raise HTTPException(404,"Asset not found")
    img=qrcode.make(f"SMARTINV:{asset_id}")
    buf=BytesIO(); img.save(buf,format="PNG"); buf.seek(0)
    return StreamingResponse(buf,media_type="image/png")

@app.get("/dashboard",dependencies=[Depends(guard)])
def dashboard(s:Session=Depends(db)):
    total=s.scalar(select(func.count()).select_from(Asset)) or 0
    by_status=dict(s.execute(select(Asset.status,func.count()).group_by(Asset.status)).all())
    by_category=dict(s.execute(select(Asset.category,func.count()).group_by(Asset.category)).all())
    by_location=dict(s.execute(select(Asset.location,func.count()).group_by(Asset.location)).all())
    recent=s.scalars(select(Movement).order_by(Movement.created_at.desc()).limit(8)).all()
    return {"total_assets":total,"by_status":by_status,"by_category":by_category,"by_location":by_location,"recent_movements":recent}

@app.get("/meta",dependencies=[Depends(guard)])
def meta(s:Session=Depends(db)):
    return {"categories":s.scalars(select(Asset.category).distinct()).all(),"locations":s.scalars(select(Asset.location).distinct()).all()}

@app.get("/insights",dependencies=[Depends(guard)])
def insights(s:Session=Depends(db)):
    total=s.scalar(select(func.count()).select_from(Asset)) or 0
    maint=s.scalar(select(func.count()).select_from(Asset).where(Asset.status=="maintenance")) or 0
    unassigned=s.scalar(select(func.count()).select_from(Asset).where(Asset.status=="in_use",Asset.assigned_to.is_(None))) or 0
    retired=s.scalar(select(func.count()).select_from(Asset).where(Asset.status=="retired")) or 0
    tips=[]
    if maint:
        tips.append(f"{maint} asset(s) in maintenance: review downtime and owner.")
    if unassigned:
        tips.append(f"{unassigned} asset(s) in use without an assigned person.")
    if retired and total and retired/total>.15:
        tips.append("More than 15 percent of assets are retired; review lifecycle planning.")
    if not tips:
        tips.append("No obvious operational anomalies in the current inventory.")
    return {"engine":"rules-v1","human_review_required":True,"insights":tips}


@app.get("/risk",dependencies=[Depends(guard)])
def risk_dashboard(s:Session=Depends(db)):
    assets=s.scalars(select(Asset).order_by(Asset.id.desc())).all()
    rows=[]
    for a in assets:
        movements=s.scalars(select(Movement).where(Movement.asset_id==a.id).order_by(Movement.created_at.desc())).all()
        risk=score_asset(a,len(movements),movements[0].created_at if movements else None)
        rows.append({"asset_id":a.id,"tag":a.tag,"name":a.name,"status":a.status,**risk})
    rows.sort(key=lambda x:x["score"],reverse=True)
    return {
      "engine":"interpretable-lifecycle-risk-v1",
      "note":"Operational risk score based on explicit rules; not a predictive ML probability.",
      "high_risk":sum(1 for r in rows if r["level"]=="high"),
      "assets":rows
    }

@app.get("/export.csv",dependencies=[Depends(guard)])
def export_csv(s:Session=Depends(db)):
    out=io.StringIO()
    w=csv.writer(out)
    w.writerow(["id","tag","name","category","serial_number","location","status","assigned_to","created_at"])
    for a in s.scalars(select(Asset).order_by(Asset.id)).all():
        w.writerow([a.id,a.tag,a.name,a.category,a.serial_number or "",a.location,a.status,a.assigned_to or "",a.created_at.isoformat()])
    data=io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return StreamingResponse(data,media_type="text/csv",headers={"Content-Disposition":"attachment; filename=smart-inventory.csv"})
