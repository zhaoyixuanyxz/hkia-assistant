from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DataUpdateJob, MarketIndicator
from app.schemas import DataUpdateJobOut
from app.schemas import MarketIndicatorOut
from app.stub_data import load_market_stubs

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/indicators", response_model=list[MarketIndicatorOut])
def indicators(db: Session = Depends(get_db)) -> list[MarketIndicatorOut]:
    rows = db.scalars(
        select(MarketIndicator).order_by(MarketIndicator.updated_at.desc(), MarketIndicator.id.asc())
    ).all()
    if rows:
        return [
            MarketIndicatorOut(
                id=r.id,
                name=r.name,
                value=r.value_text,
                explanation=r.explanation,
                source_url=r.source_url,
                updated_at=r.updated_at.isoformat() + "Z",
                trend_note=r.trend_note,
            )
            for r in rows
        ]
    stubs = load_market_stubs()
    return [MarketIndicatorOut.model_validate(r) for r in stubs]


@router.get("/updates", response_model=list[DataUpdateJobOut])
def updates(db: Session = Depends(get_db)) -> list[DataUpdateJob]:
    rows = db.scalars(
        select(DataUpdateJob)
        .where(DataUpdateJob.job_type == "market_refresh")
        .order_by(DataUpdateJob.id.desc())
        .limit(20)
    ).all()
    return list(rows)


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)) -> dict:
    job = DataUpdateJob(job_type="market_refresh", status="pending")
    db.add(job)
    db.flush()
    try:
        now = datetime.utcnow()
        stubs = load_market_stubs()
        for item in stubs:
            row = db.get(MarketIndicator, str(item.get("id")))
            if row is None:
                row = MarketIndicator(id=str(item.get("id")))
                db.add(row)
            row.name = str(item.get("name", ""))
            row.value_text = str(item.get("value", ""))
            row.explanation = str(item.get("explanation", ""))
            row.source_url = str(item.get("source_url", ""))
            row.trend_note = str(item.get("trend_note", ""))
            row.updated_at = now
        job.status = "success"
        job.finished_at = now
        job.detail_json = {"updated_count": len(stubs)}
        message = "市场指标更新完成"
        ok = True
    except Exception as exc:
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.error_message = str(exc)
        message = "市场指标更新失败"
        ok = False
    db.commit()
    return {
        "ok": ok,
        "message": message,
        "job_id": job.id,
        "status": job.status,
        "updated_at": job.finished_at.isoformat() + "Z" if job.finished_at else "",
    }
