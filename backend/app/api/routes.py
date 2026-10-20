from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select, and_, or_
from app.db import Service, Incident, TimelineEvent, Evidence, TelemetrySample

router = APIRouter(prefix="/api/v1")


def row_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get("/services")
def services(request: Request):
    with request.app.state.sessions() as session:
        result = []
        for service in session.scalars(select(Service)):
            sample = session.scalar(
                select(TelemetrySample)
                .where(TelemetrySample.service_id == service.id)
                .order_by(TelemetrySample.created_at.desc())
                .limit(1)
            )
            result.append(
                {**row_dict(service), "observation": sample.data if sample else None}
            )
        return result


@router.get("/telemetry")
def telemetry(request: Request, limit: int = Query(default=120, ge=1, le=720)):
    with request.app.state.sessions() as session:
        rows = list(
            session.scalars(
                select(TelemetrySample)
                .order_by(TelemetrySample.created_at.desc())
                .limit(limit)
            )
        )
        return {
            "status": request.app.state.monitor_status,
            "samples": [row.data for row in reversed(rows)],
        }


@router.get("/incidents")
def incidents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    with request.app.state.sessions() as session:
        return [
            row_dict(row)
            for row in session.scalars(
                select(Incident)
                .order_by(Incident.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ]


@router.get("/incidents/{incident_id}")
def incident(incident_id: str, request: Request):
    with request.app.state.sessions() as session:
        row = session.get(Incident, incident_id)
        if row is None:
            raise HTTPException(404, "Incident not found")
        return row_dict(row)


def history_page(session, model, incident_id, limit, before):
    if not session.get(Incident, incident_id):
        raise HTTPException(404, "Incident not found")
    query = select(model).where(model.incident_id == incident_id)
    if before:
        cursor = session.get(model, before)
        if cursor is None or cursor.incident_id != incident_id:
            raise HTTPException(404, "History cursor not found for this incident")
        query = query.where(
            or_(
                model.created_at < cursor.created_at,
                and_(model.created_at == cursor.created_at, model.id < cursor.id),
            )
        )
    rows = list(
        session.scalars(
            query.order_by(model.created_at.desc(), model.id.desc()).limit(limit)
        )
    )
    return [row_dict(row) for row in reversed(rows)]


@router.get("/incidents/{incident_id}/timeline")
def timeline(
    incident_id: str,
    request: Request,
    limit: int = Query(default=200, ge=1, le=200),
    before: str | None = None,
):
    with request.app.state.sessions() as session:
        return history_page(session, TimelineEvent, incident_id, limit, before)


@router.get("/incidents/{incident_id}/evidence")
def evidence(
    incident_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    before: str | None = None,
):
    with request.app.state.sessions() as session:
        return history_page(session, Evidence, incident_id, limit, before)


@router.get("/incidents/{incident_id}/evidence/{evidence_id}")
def evidence_record(incident_id: str, evidence_id: str, request: Request):
    with request.app.state.sessions() as session:
        row = session.get(Evidence, evidence_id)
        if row is None or row.incident_id != incident_id:
            raise HTTPException(404, "Evidence not found for this incident")
        return row_dict(row)
