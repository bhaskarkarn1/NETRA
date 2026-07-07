"""
NETRA Dashboard Router — Metrics & Threat Feed

All metrics are computed from database aggregations, not hardcoded.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, Case, Simulation, GraphNode, AuditLog

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- Schemas ----------

class DashboardMetrics(BaseModel):
    total_cases_analyzed: int
    total_scams_detected: int
    average_confidence: float
    total_simulations_run: int
    simulations_intervened: int
    total_graph_nodes: int
    total_graph_edges: int
    most_common_scam_type: str | None
    agent_calls_total: int
    agent_fallback_count: int


class ThreatFeedItem(BaseModel):
    id: str
    type: str  # 'case' or 'simulation'
    title: str
    detail: str
    risk_level: str
    timestamp: str


# ---------- Endpoints ----------

@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
):
    """Dashboard statistics — all computed from database, nothing hardcoded."""

    # Cases
    total_cases = await db.scalar(select(func.count(Case.id))) or 0
    total_scams = await db.scalar(
        select(func.count(Case.id)).where(Case.scam_type.is_not(None))
    ) or 0
    avg_conf = await db.scalar(
        select(func.avg(Case.confidence)).where(Case.confidence.is_not(None))
    ) or 0.0

    # Most common scam type
    most_common_stmt = (
        select(Case.scam_type, func.count(Case.id).label("cnt"))
        .where(Case.scam_type.is_not(None))
        .group_by(Case.scam_type)
        .order_by(func.count(Case.id).desc())
        .limit(1)
    )
    result = await db.execute(most_common_stmt)
    row = result.first()
    most_common_scam = row[0] if row else None

    # Simulations
    total_sims = await db.scalar(select(func.count(Simulation.id))) or 0
    sims_intervened = await db.scalar(
        select(func.count(Simulation.id)).where(Simulation.intervention_triggered == True)
    ) or 0

    # Graph
    total_nodes = await db.scalar(select(func.count(GraphNode.id))) or 0
    # Count edges via a raw count since we'd need the GraphEdge import
    from app.database import GraphEdge
    total_edges = await db.scalar(select(func.count(GraphEdge.id))) or 0

    # Audit
    total_agent_calls = await db.scalar(select(func.count(AuditLog.id))) or 0
    fallback_count = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.status == "fallback")
    ) or 0

    return DashboardMetrics(
        total_cases_analyzed=total_cases,
        total_scams_detected=total_scams,
        average_confidence=round(float(avg_conf), 3),
        total_simulations_run=total_sims,
        simulations_intervened=sims_intervened,
        total_graph_nodes=total_nodes,
        total_graph_edges=total_edges,
        most_common_scam_type=most_common_scam,
        agent_calls_total=total_agent_calls,
        agent_fallback_count=fallback_count,
    )


@router.get("/threat-feed", response_model=list[ThreatFeedItem])
async def get_threat_feed(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Recent threat activity feed — pulled from cases and simulations."""
    items: list[ThreatFeedItem] = []

    # Recent cases
    stmt = select(Case).order_by(Case.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    cases = result.scalars().all()

    for c in cases:
        items.append(ThreatFeedItem(
            id=str(c.id),
            type="case",
            title=f"Scam Detected: {c.scam_type or 'Unknown'}",
            detail=c.input_text[:120] + ("..." if len(c.input_text) > 120 else ""),
            risk_level=c.risk_level or "unknown",
            timestamp=c.created_at.isoformat() if c.created_at else "",
        ))

    # Recent simulations
    stmt = select(Simulation).order_by(Simulation.started_at.desc()).limit(limit)
    result = await db.execute(stmt)
    sims = result.scalars().all()

    for s in sims:
        items.append(ThreatFeedItem(
            id=str(s.id),
            type="simulation",
            title=f"Simulation: {s.scenario_type} ({s.status})",
            detail=f"{s.total_turns or 0} turns, intervention: {'Yes' if s.intervention_triggered else 'No'}",
            risk_level="high" if s.intervention_triggered else "medium",
            timestamp=s.started_at.isoformat() if s.started_at else "",
        ))

    # Sort by timestamp descending
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:limit]
