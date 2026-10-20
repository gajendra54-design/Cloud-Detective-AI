import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.security import role
from app.db import (
    Incident,
    Evidence,
    Investigation,
    Remediation,
    AuditEvent,
    TimelineEvent,
)
from app.api.routes import row_dict
from app.services.telemetry import observe
from app.services.investigation import investigate, sanitize
from app.services.recovery import approved, fingerprint, verify, utc, restart_demo

router = APIRouter(prefix="/api/v1")


def audit(session, actor, event, subject, details=None):
    session.add(
        AuditEvent(
            id=str(uuid4()),
            actor=actor,
            event=event,
            subject=subject,
            details=details or {},
        )
    )


def timeline(session, incident_id, kind, **details):
    session.add(
        TimelineEvent(
            id=str(uuid4()), incident_id=incident_id, details={"type": kind, **details}
        )
    )


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["auto", "restart_service", "rollback_demo"] = "auto"


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint: str = Field(min_length=64, max_length=64)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(
        pattern="^(healthy|errors|latency|cpu|memory|dependency_timeout|database|deployment)$"
    )
    duration_seconds: int = Field(default=60, ge=1, le=120)


@router.get("/demo/scenario")
async def scenario_state():
    config = settings()
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(
                config.checkout_url + "/control/scenario",
                headers={"X-Demo-Token": config.control_token},
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Demo controls unavailable") from None


@router.post("/demo/scenario")
async def set_scenario(
    body: ScenarioRequest, request: Request, actor=Depends(role("investigator"))
):
    config = settings()
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.post(
                config.checkout_url + "/control/scenario",
                headers={"X-Demo-Token": config.control_token},
                json=body.model_dump(),
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            503, "Demo change failed or outcome unknown; inspect current scenario"
        ) from None
    with request.app.state.sessions() as session, session.begin():
        audit(session, actor, "demo_scenario_changed", "checkout", body.model_dump())
    return result


@router.post("/demo/traffic")
async def traffic(actor=Depends(role("investigator"))):
    config = settings()
    results = []
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        for _ in range(5):
            try:
                response = await client.post(
                    config.checkout_url + "/api/checkout", json={"product_id": "book"}
                )
                results.append(response.status_code)
            except httpx.HTTPError:
                results.append(0)
    return {"request_count": 5, "statuses": results, "simulated_orders": True}


@router.post("/incidents/{incident_id}/investigate")
async def start_investigation(
    incident_id: str, request: Request, actor=Depends(role("investigator"))
):
    config = settings()
    with request.app.state.sessions() as session:
        incident = session.get(Incident, incident_id)
        if not incident:
            raise HTTPException(404, "Incident not found")
        target = incident.service_id
    evidence = []
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        observation = await observe(config, target, client)
        evidence.append(
            {
                "id": str(uuid4()),
                "kind": "observation",
                "source": "Prometheus + health endpoints",
                "data": observation.model_dump(),
            }
        )
        for route, kind in [
            ("/control/scenario", "scenario"),
            ("/control/evidence", "demo_records"),
        ]:
            try:
                response = await client.get(
                    config.targets[target] + route,
                    headers={"X-Demo-Token": config.control_token},
                )
                response.raise_for_status()
                data = sanitize(response.json())
            except (httpx.HTTPError, ValueError):
                data = {"status": "unavailable"}
            evidence.append(
                {
                    "id": str(uuid4()),
                    "kind": kind,
                    "source": f"{target}{route}",
                    "data": data,
                }
            )
    finding, provider = await investigate(evidence)
    try:
        with request.app.state.sessions() as session, session.begin():
            for item in evidence:
                session.add(Evidence(incident_id=incident_id, **item))
            row = session.scalar(
                select(Investigation).where(Investigation.incident_id == incident_id)
            )
            if row is None:
                row = Investigation(id=str(uuid4()), incident_id=incident_id)
                session.add(row)
            row.provider = provider
            row.findings = finding.model_dump()
            row.created_at = datetime.now(timezone.utc)
            timeline(session, incident_id, "investigated", provider=provider)
            audit(session, actor, "investigated", incident_id, {"provider": provider})
        return {"provider": provider, "findings": finding.model_dump()}
    except IntegrityError:
        raise HTTPException(409, "Investigation already in progress; refresh") from None


@router.get("/incidents/{incident_id}/investigation")
def get_investigation(incident_id: str, request: Request):
    with request.app.state.sessions() as session:
        row = session.scalar(
            select(Investigation).where(Investigation.incident_id == incident_id)
        )
        if row is None:
            raise HTTPException(404, "No investigation yet")
        return row_dict(row)


@router.post("/incidents/{incident_id}/propose")
async def propose(
    incident_id: str,
    request: Request,
    body: ProposalRequest = ProposalRequest(),
    actor=Depends(role("investigator")),
):
    config = settings()
    with request.app.state.sessions() as session:
        incident = session.get(Incident, incident_id)
        investigation = session.scalar(
            select(Investigation).where(Investigation.incident_id == incident_id)
        )
        if not incident:
            raise HTTPException(404, "Incident not found")
        if incident.status != "OPEN" or not investigation:
            raise HTTPException(409, "An open investigated incident is required")
        target, version = incident.service_id, incident.version
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(
                config.targets[target] + "/control/scenario",
                headers={"X-Demo-Token": config.control_token},
            )
            response.raise_for_status()
            state = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Cannot verify action preconditions") from None
    action_type = "health_check" if state["name"] == "healthy" else "disable_failure"
    parameters = {"expected_revision": state["revision"], "scenario": state["name"]}
    if body.action == "rollback_demo":
        if (
            state.get("deployment_version") != "demo-v2"
            or state.get("previous_version") != "demo-v1"
            or state["name"] != "deployment"
        ):
            raise HTTPException(
                409,
                "No active versioned demo regression with a recorded previous release",
            )
        action_type = "rollback_demo"
        parameters.update(
            expected_version="demo-v2",
            target_version="demo-v1",
            impact="Restores bundled demo behavior; does not roll back a container image",
        )
    if body.action == "restart_service":
        if not state.get("restart_enabled") or not state.get("boot_id"):
            raise HTTPException(409, "Target does not support controlled restart")
        action_type = "restart_service"
        parameters["expected_boot_id"] = state["boot_id"]
        parameters["impact"] = (
            "Brief outage; ephemeral orders, logs, traces and metric counters are lost"
        )
    action = Remediation(
        id=str(uuid4()),
        incident_id=incident_id,
        target=target,
        action=action_type,
        parameters=parameters,
        incident_version=version,
        fingerprint=fingerprint(action_type, target, parameters, version),
        status="PENDING_APPROVAL",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    with request.app.state.sessions() as session, session.begin():
        # Serialize competing proposals per incident in PostgreSQL, then recheck
        # the incident after upstream precondition collection.
        locked_incident = session.scalar(
            select(Incident).where(Incident.id == incident_id).with_for_update()
        )
        if (
            not locked_incident
            or locked_incident.status != "OPEN"
            or locked_incident.version != version
        ):
            raise HTTPException(
                409, "Incident changed while collecting action preconditions"
            )
        existing = session.scalar(
            select(Remediation).where(
                Remediation.incident_id == incident_id,
                Remediation.status.in_(
                    ["PENDING_APPROVAL", "APPROVED", "EXECUTING", "VERIFYING"]
                ),
            )
        )
        if existing and utc(existing.expires_at) > datetime.now(timezone.utc):
            if existing.action != action_type:
                raise HTTPException(
                    409,
                    "Reject the existing proposal before selecting a different action",
                )
            return row_dict(existing)
        session.add(action)
        session.flush()
        audit(
            session, actor, "proposed", action.id, {"fingerprint": action.fingerprint}
        )
        timeline(session, incident_id, "proposed", action_id=action.id)
        result = row_dict(action)
    return result


@router.get("/remediations")
def actions(request: Request):
    with request.app.state.sessions() as session:
        return [
            row_dict(r)
            for r in session.scalars(
                select(Remediation).order_by(Remediation.created_at.desc()).limit(100)
            )
        ]


@router.post("/remediations/{action_id}/approve")
def approve(
    action_id: str, body: Approval, request: Request, actor=Depends(role("approver"))
):
    with request.app.state.sessions() as session, session.begin():
        action = session.get(Remediation, action_id)
        if not action:
            raise HTTPException(404, "Action not found")
        incident = session.get(Incident, action.incident_id)
        if (
            body.fingerprint != action.fingerprint
            or incident.version != action.incident_version
            or incident.status != "OPEN"
        ):
            raise HTTPException(409, "Proposal changed or incident is stale")
        if utc(action.expires_at) <= datetime.now(timezone.utc):
            raise HTTPException(409, "Proposal expired")
        result = session.execute(
            update(Remediation)
            .where(
                Remediation.id == action_id, Remediation.status == "PENDING_APPROVAL"
            )
            .values(
                status="APPROVED",
                approved_by=actor,
                approved_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Action is not pending approval")
        audit(session, actor, "approved", action_id, {"fingerprint": body.fingerprint})
        timeline(session, action.incident_id, "approved", action_id=action_id)
    return {"status": "APPROVED"}


@router.post("/remediations/{action_id}/reject")
def reject(action_id: str, request: Request, actor=Depends(role("approver"))):
    with request.app.state.sessions() as session, session.begin():
        result = session.execute(
            update(Remediation)
            .where(
                Remediation.id == action_id,
                Remediation.status.in_(["PENDING_APPROVAL", "APPROVED"]),
            )
            .values(status="REJECTED")
        )
        if result.rowcount != 1:
            raise HTTPException(409, "Action cannot be rejected in its current state")
        audit(session, actor, "rejected", action_id)
    return {"status": "REJECTED"}


@router.post("/remediations/{action_id}/execute")
async def execute(action_id: str, request: Request, actor=Depends(role("approver"))):
    config = settings()
    with request.app.state.sessions() as session, session.begin():
        action = session.get(Remediation, action_id)
        if not action:
            raise HTTPException(404, "Action not found")
        if action.status in {"EXECUTING", "VERIFYING", "SUCCEEDED", "FAILED"}:
            return row_dict(action)  # Retry is a read; never executes twice.
        incident = session.get(Incident, action.incident_id)
        if not approved(action, incident) or action.target not in config.targets:
            raise HTTPException(409, "Approval expired, stale or invalid")
        claimed = session.execute(
            update(Remediation)
            .where(Remediation.id == action_id, Remediation.status == "APPROVED")
            .values(status="EXECUTING")
        )
        if claimed.rowcount != 1:
            raise HTTPException(409, "Execution already claimed")
        target, parameters, incident_id, action_type = (
            action.target,
            action.parameters,
            action.incident_id,
            action.action,
        )
        audit(session, actor, "execution_started", action_id)
        timeline(session, incident_id, "executing", action_id=action_id)
    result = {
        "passed": False,
        "reason": "Execution failed or timed out; recovery is not established",
    }
    try:
        async with asyncio.timeout(35 if action_type == "restart_service" else 20):
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                restart_result = None
                if action_type == "restart_service":
                    restart_result = await restart_demo(
                        config, target, parameters, client
                    )
                elif action_type == "rollback_demo":
                    response = await client.post(
                        config.targets[target] + "/control/rollback",
                        headers={"X-Demo-Token": config.control_token},
                        json={
                            key: parameters[key]
                            for key in (
                                "expected_revision",
                                "expected_version",
                                "target_version",
                            )
                        },
                    )
                    response.raise_for_status()
                    rollback_response = response.json()
                    if rollback_response.get("version") != parameters["target_version"]:
                        raise ValueError("Rollback target not established")
                elif action_type == "disable_failure":
                    response = await client.post(
                        config.targets[target] + "/control/scenario",
                        headers={"X-Demo-Token": config.control_token},
                        json={
                            "name": "healthy",
                            "duration_seconds": 1,
                            "expected_revision": parameters["expected_revision"],
                        },
                    )
                    response.raise_for_status()
                else:
                    response = await client.get(
                        config.targets[target] + "/control/scenario",
                        headers={"X-Demo-Token": config.control_token},
                    )
                    response.raise_for_status()
                    if response.json()["revision"] != parameters["expected_revision"]:
                        raise ValueError("Scenario changed since approval")
                with request.app.state.sessions() as session, session.begin():
                    session.execute(
                        update(Remediation)
                        .where(Remediation.id == action_id)
                        .values(status="VERIFYING")
                    )
                    timeline(session, incident_id, "verifying", action_id=action_id)
                result = await verify(config, target, client)
                if restart_result:
                    result["restart"] = restart_result
                if action_type == "rollback_demo":
                    result["rollback"] = rollback_response
    except (httpx.HTTPError, TimeoutError, ValueError):
        pass
    with request.app.state.sessions() as session, session.begin():
        action = session.get(Remediation, action_id)
        action.result = result
        action.status = "SUCCEEDED" if result["passed"] else "FAILED"
        incident = session.get(Incident, incident_id)
        if result["passed"]:
            incident.status = "RESOLVED"
            incident.open_key = None
            incident.version += 1
        timeline(
            session,
            incident_id,
            "verification_completed",
            action_id=action_id,
            passed=result["passed"],
        )
        audit(session, actor, "verification_completed", action_id, result)
        session.flush()
        response = row_dict(action)
    return response


@router.get("/remediations/{action_id}/verification")
def verification(action_id: str, request: Request):
    with request.app.state.sessions() as session:
        row = session.get(Remediation, action_id)
        if not row:
            raise HTTPException(404, "Action not found")
        return {"status": row.status, "verification": row.result}


@router.get("/audit-events")
def audits(request: Request):
    with request.app.state.sessions() as session:
        return [
            row_dict(r)
            for r in session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)
            )
        ]
