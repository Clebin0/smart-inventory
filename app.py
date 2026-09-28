from __future__ import annotations
from datetime import datetime, timezone
from io import BytesIO
from enum import Enum
import qrcode
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, DateTime, ForeignKey, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

engine=create_engine("sqlite:///inventory.db",connect_args={"check_same_thread":False})
class Base(DeclarativeBase): pass
class Asset(Base):
    __tablename__="assets"
    id:Mapped[int]=mapped_column(primary_key=True)
    tag:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    name:Mapped[str]=mapped_column(String(160))
    category:Mapped[str]=mapped_column(String(80))
    location:Mapped[str]=mapped_column(String(120),default="Estoque")
    status:Mapped[str]=mapped_column(String(40),default="available")
class Movement(Base):
    __tablename__="movements"
    id:Mapped[int]=mapped_column(primary_key=True)
    asset_id:Mapped[int]=mapped_column(ForeignKey("assets.id"),index=True)
    action:Mapped[str]=mapped_column(String(40))
    actor:Mapped[str]=mapped_column(String(120))
    destination:Mapped[str|None]=mapped_column(String(120),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
Base.metadata.create_all(engine)

class Action(str,Enum):
    check_out="check_out"; check_in="check_in"; transfer="transfer"; maintenance="maintenance"
class AssetIn(BaseModel):
    tag:str=Field(min_length=2,max_length=80); name:str; category:str; location:str="Estoque"
class MovementIn(BaseModel):
    action:Action; actor:str=Field(min_length=2); destination:str|None=None
def db():
    with Session(engine) as s: yield s

app=FastAPI(title="Smart Inventory",version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/assets",status_code=201)
def create_asset(body:AssetIn,s:Session=Depends(db)):
    if s.scalar(select(Asset).where(Asset.tag==body.tag)): raise HTTPException(409,"Asset tag already exists")
    a=Asset(**body.model_dump()); s.add(a); s.commit(); s.refresh(a); return a
@app.get("/assets")
def assets(s:Session=Depends(db)): return s.scalars(select(Asset).order_by(Asset.id.desc())).all()
@app.get("/assets/{asset_id}")
def asset(asset_id:int,s:Session=Depends(db)):
    a=s.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Asset not found")
    return a
@app.post("/assets/{asset_id}/movements",status_code=201)
def move(asset_id:int,body:MovementIn,s:Session=Depends(db)):
    a=s.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Asset not found")
    if body.action=="check_out": a.status="in_use"
    elif body.action=="check_in": a.status="available"
    elif body.action=="maintenance": a.status="maintenance"
    if body.destination: a.location=body.destination
    m=Movement(asset_id=asset_id,**body.model_dump()); s.add(m); s.commit(); s.refresh(m); return m
@app.get("/assets/{asset_id}/movements")
def history(asset_id:int,s:Session=Depends(db)):
    return s.scalars(select(Movement).where(Movement.asset_id==asset_id).order_by(Movement.created_at.desc())).all()
@app.get("/assets/{asset_id}/qr")
def qr(asset_id:int,s:Session=Depends(db)):
    if not s.get(Asset,asset_id): raise HTTPException(404,"Asset not found")
    img=qrcode.make(f"smart-inventory://asset/{asset_id}"); buf=BytesIO(); img.save(buf,format="PNG"); buf.seek(0)
    return StreamingResponse(buf,media_type="image/png")
@app.get("/dashboard")
def dashboard(s:Session=Depends(db)):
    total=s.scalar(select(func.count()).select_from(Asset)) or 0
    rows=s.execute(select(Asset.status,func.count()).group_by(Asset.status)).all()
    return {"total_assets":total,"by_status":dict(rows)}
