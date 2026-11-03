from __future__ import annotations

import csv
import hmac
import io
import os
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO

import qrcode
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import DateTime, ForeignKey, String, create_engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from risk_engine import score_asset

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///inventory.db")
APP_TOKEN = os.getenv("APP_TOKEN", "").strip()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


class Base(DeclarativeBase):
    pass


class AssetStatus(str, Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"
    retired = "retired"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80), index=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str] = mapped_column(String(120), default="Estoque", index=True)
    status: Mapped[str] = mapped_column(String(40), default="available", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Movement(Base):
    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )


Base.metadata.create_all(engine)


class Action(str, Enum):
    check_out = "check_out"
    check_in = "check_in"
    transfer = "transfer"
    maintenance = "maintenance"
    retire = "retire"


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class AssetIn(InputModel):
    tag: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    serial_number: str | None = Field(default=None, max_length=120)
    location: str = Field(default="Estoque", min_length=2, max_length=120)
    status: AssetStatus = AssetStatus.available
    assigned_to: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_assignee_matches_status(self):
        if self.status == AssetStatus.in_use and not self.assigned_to:
            raise ValueError("An in-use asset must have an assigned person")
        if self.status != AssetStatus.in_use and self.assigned_to:
            raise ValueError("Only in-use assets can have an assigned person")
        return self


class MovementIn(InputModel):
    action: Action
    actor: str = Field(min_length=2, max_length=120)
    destination: str | None = Field(default=None, max_length=120)
    assigned_to: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_action_requirements(self):
        if self.action == Action.transfer and not self.destination:
            raise ValueError("A destination is required for a transfer")
        if self.action == Action.check_out and not self.assigned_to:
            raise ValueError("An assignee is required when checking out an asset")
        return self


def db():
    with Session(engine) as session:
        yield session


def guard(x_app_token: str | None = Header(default=None)):
    if not APP_TOKEN:
        raise HTTPException(503, "Application token is not configured")
    if not x_app_token or not hmac.compare_digest(x_app_token, APP_TOKEN):
        raise HTTPException(401, "Invalid application token")


app = FastAPI(title="Smart Inventory", version="2.2.0")


@app.get("/", response_class=HTMLResponse)
def home():
    with open("frontend.html", "r", encoding="utf-8") as file:
        return file.read()


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.2.0"}


@app.get("/assets", dependencies=[Depends(guard)])
def list_assets(
    q: str = "",
    status: str = "",
    category: str = "",
    location: str = "",
    session: Session = Depends(db),
):
    statement = select(Asset).order_by(Asset.id.desc())
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(
                Asset.tag.ilike(like),
                Asset.name.ilike(like),
                Asset.serial_number.ilike(like),
                Asset.assigned_to.ilike(like),
            )
        )
    if status:
        statement = statement.where(Asset.status == status)
    if category:
        statement = statement.where(Asset.category == category)
    if location:
        statement = statement.where(Asset.location == location)
    return session.scalars(statement).all()


@app.post("/assets", status_code=201, dependencies=[Depends(guard)])
def create_asset(body: AssetIn, session: Session = Depends(db)):
    asset = Asset(**body.model_dump())
    session.add(asset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Asset tag already exists") from exc
    session.refresh(asset)
    return asset


@app.get("/assets/{asset_id}", dependencies=[Depends(guard)])
def get_asset(asset_id: int, session: Session = Depends(db)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset


@app.put("/assets/{asset_id}", dependencies=[Depends(guard)])
def update_asset(asset_id: int, body: AssetIn, session: Session = Depends(db)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")

    if body.status.value != asset.status or body.assigned_to != asset.assigned_to:
        raise HTTPException(
            409,
            "Status and assignee changes must use the movements endpoint to preserve history",
        )

    duplicate = session.scalar(
        select(Asset).where(Asset.tag == body.tag, Asset.id != asset_id)
    )
    if duplicate:
        raise HTTPException(409, "Asset tag already exists")

    data = body.model_dump(exclude={"status", "assigned_to"})
    for key, value in data.items():
        setattr(asset, key, value)
    session.commit()
    session.refresh(asset)
    return asset


@app.post(
    "/assets/{asset_id}/movements",
    status_code=201,
    dependencies=[Depends(guard)],
)
def move(asset_id: int, body: MovementIn, session: Session = Depends(db)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")

    current_status = AssetStatus(asset.status)

    if current_status == AssetStatus.retired:
        raise HTTPException(409, "Retired assets cannot be moved")

    if body.action == Action.check_out:
        if current_status != AssetStatus.available:
            raise HTTPException(409, "Only available assets can be checked out")
        asset.status = AssetStatus.in_use.value
        asset.assigned_to = body.assigned_to

    elif body.action == Action.check_in:
        if current_status != AssetStatus.in_use:
            raise HTTPException(409, "Only in-use assets can be checked in")
        asset.status = AssetStatus.available.value
        asset.assigned_to = None

    elif body.action == Action.transfer:
        asset.location = body.destination

    elif body.action == Action.maintenance:
        asset.status = AssetStatus.maintenance.value
        asset.assigned_to = None

    elif body.action == Action.retire:
        asset.status = AssetStatus.retired.value
        asset.assigned_to = None

    if body.destination and body.action != Action.transfer:
        asset.location = body.destination

    movement = Movement(
        asset_id=asset_id,
        action=body.action.value,
        actor=body.actor,
        destination=asset.location,
        assigned_to=asset.assigned_to,
        notes=body.notes,
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return movement


@app.get("/assets/{asset_id}/movements", dependencies=[Depends(guard)])
def history(asset_id: int, session: Session = Depends(db)):
    if not session.get(Asset, asset_id):
        raise HTTPException(404, "Asset not found")
    return session.scalars(
        select(Movement)
        .where(Movement.asset_id == asset_id)
        .order_by(Movement.created_at.desc(), Movement.id.desc())
    ).all()


@app.get("/assets/{asset_id}/qr")
def qr(asset_id: int, session: Session = Depends(db)):
    if not session.get(Asset, asset_id):
        raise HTTPException(404, "Asset not found")
    image = qrcode.make(f"SMARTINV:{asset_id}")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@app.get("/dashboard", dependencies=[Depends(guard)])
def dashboard(session: Session = Depends(db)):
    total = session.scalar(select(func.count()).select_from(Asset)) or 0
    by_status = dict(
        session.execute(select(Asset.status, func.count()).group_by(Asset.status)).all()
    )
    by_category = dict(
        session.execute(select(Asset.category, func.count()).group_by(Asset.category)).all()
    )
    by_location = dict(
        session.execute(select(Asset.location, func.count()).group_by(Asset.location)).all()
    )
    recent = session.scalars(
        select(Movement)
        .order_by(Movement.created_at.desc(), Movement.id.desc())
        .limit(8)
    ).all()
    return {
        "total_assets": total,
        "by_status": by_status,
        "by_category": by_category,
        "by_location": by_location,
        "recent_movements": recent,
    }


@app.get("/meta", dependencies=[Depends(guard)])
def meta(session: Session = Depends(db)):
    return {
        "categories": session.scalars(select(Asset.category).distinct()).all(),
        "locations": session.scalars(select(Asset.location).distinct()).all(),
    }


@app.get("/insights", dependencies=[Depends(guard)])
def insights(session: Session = Depends(db)):
    total = session.scalar(select(func.count()).select_from(Asset)) or 0
    maintenance = (
        session.scalar(
            select(func.count()).select_from(Asset).where(
                Asset.status == AssetStatus.maintenance.value
            )
        )
        or 0
    )
    unassigned = (
        session.scalar(
            select(func.count()).select_from(Asset).where(
                Asset.status == AssetStatus.in_use.value,
                Asset.assigned_to.is_(None),
            )
        )
        or 0
    )
    retired = (
        session.scalar(
            select(func.count()).select_from(Asset).where(
                Asset.status == AssetStatus.retired.value
            )
        )
        or 0
    )

    tips = []
    if maintenance:
        tips.append(f"{maintenance} asset(s) in maintenance: review downtime and owner.")
    if unassigned:
        tips.append(f"{unassigned} asset(s) in use without an assigned person.")
    if retired and total and retired / total > 0.15:
        tips.append("More than 15 percent of assets are retired; review lifecycle planning.")
    if not tips:
        tips.append("No obvious operational anomalies in the current inventory.")

    return {"engine": "rules-v1", "human_review_required": True, "insights": tips}


@app.get("/risk", dependencies=[Depends(guard)])
def risk_dashboard(session: Session = Depends(db)):
    assets = session.scalars(select(Asset).order_by(Asset.id.desc())).all()
    rows = []
    for asset in assets:
        movements = session.scalars(
            select(Movement)
            .where(Movement.asset_id == asset.id)
            .order_by(Movement.created_at.desc(), Movement.id.desc())
        ).all()
        risk = score_asset(
            asset,
            len(movements),
            movements[0].created_at if movements else None,
        )
        rows.append(
            {
                "asset_id": asset.id,
                "tag": asset.tag,
                "name": asset.name,
                "status": asset.status,
                **risk,
            }
        )

    rows.sort(key=lambda item: item["score"], reverse=True)
    return {
        "engine": "interpretable-lifecycle-risk-v1",
        "note": "Operational risk score based on explicit rules; not a predictive ML probability.",
        "high_risk": sum(1 for row in rows if row["level"] == "high"),
        "assets": rows,
    }


@app.get("/export.csv", dependencies=[Depends(guard)])
def export_csv(session: Session = Depends(db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "tag",
            "name",
            "category",
            "serial_number",
            "location",
            "status",
            "assigned_to",
            "created_at",
        ]
    )
    for asset in session.scalars(select(Asset).order_by(Asset.id)).all():
        writer.writerow(
            [
                asset.id,
                asset.tag,
                asset.name,
                asset.category,
                asset.serial_number or "",
                asset.location,
                asset.status,
                asset.assigned_to or "",
                asset.created_at.isoformat(),
            ]
        )
    data = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return StreamingResponse(
        data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=smart-inventory.csv"},
    )
