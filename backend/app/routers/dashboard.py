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


# ---------- Analytics ----------

class ChartDataPoint(BaseModel):
    label: str
    value: int
    color: str | None = None


class DailyTrend(BaseModel):
    date: str
    cases: int
    scams: int


class AnalyticsResponse(BaseModel):
    scam_type_distribution: list[ChartDataPoint]
    risk_level_breakdown: list[ChartDataPoint]
    daily_trend: list[DailyTrend]
    entity_type_breakdown: list[ChartDataPoint]
    top_entities: list[dict]


SCAM_COLORS = {
    "Digital Arrest": "#ef4444",
    "KYC Fraud": "#f97316",
    "Investment Scam": "#eab308",
    "Phishing": "#3b82f6",
    "OTP Fraud": "#8b5cf6",
    "Fake Lottery": "#ec4899",
    "Tech Support Scam": "#14b8a6",
    "Job Fraud": "#06b6d4",
    "Loan Scam": "#f59e0b",
}

RISK_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#22c55e",
    "unknown": "#6b7280",
}

ENTITY_COLORS = {
    "phone": "#3b82f6",
    "bank_account": "#f59e0b",
    "upi_id": "#8b5cf6",
    "email": "#14b8a6",
    "url": "#a855f7",
    "person": "#f43f5e",
    "organization": "#6366f1",
    "location": "#10b981",
    "case": "#06b6d4",
    "amount": "#eab308",
}


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
):
    """Chart-ready analytics data for the Command Center dashboard."""
    from app.database import GraphEdge
    from datetime import datetime, timedelta, timezone

    # 1. Scam type distribution
    scam_dist_stmt = (
        select(Case.scam_type, func.count(Case.id).label("cnt"))
        .where(Case.scam_type.is_not(None))
        .group_by(Case.scam_type)
        .order_by(func.count(Case.id).desc())
    )
    scam_dist = await db.execute(scam_dist_stmt)
    scam_type_distribution = [
        ChartDataPoint(
            label=row[0],
            value=row[1],
            color=SCAM_COLORS.get(row[0], "#6b7280"),
        )
        for row in scam_dist.all()
    ]

    # 2. Risk level breakdown
    risk_stmt = (
        select(Case.risk_level, func.count(Case.id).label("cnt"))
        .group_by(Case.risk_level)
        .order_by(func.count(Case.id).desc())
    )
    risk_result = await db.execute(risk_stmt)
    risk_level_breakdown = [
        ChartDataPoint(
            label=row[0] or "unknown",
            value=row[1],
            color=RISK_COLORS.get(row[0] or "unknown", "#6b7280"),
        )
        for row in risk_result.all()
    ]

    # 3. Daily trend (last 14 days)
    fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
    daily_stmt = (
        select(
            func.date(Case.created_at).label("day"),
            func.count(Case.id).label("total"),
            func.count(Case.id).filter(Case.scam_type.is_not(None)).label("scams"),
        )
        .where(Case.created_at >= fourteen_days_ago)
        .group_by(func.date(Case.created_at))
        .order_by(func.date(Case.created_at))
    )
    daily_result = await db.execute(daily_stmt)
    daily_trend = [
        DailyTrend(
            date=str(row[0]),
            cases=row[1],
            scams=row[2],
        )
        for row in daily_result.all()
    ]

    # 4. Entity type breakdown
    entity_stmt = (
        select(GraphNode.node_type, func.count(GraphNode.id).label("cnt"))
        .where(GraphNode.node_type != "case")
        .group_by(GraphNode.node_type)
        .order_by(func.count(GraphNode.id).desc())
    )
    entity_result = await db.execute(entity_stmt)
    entity_type_breakdown = [
        ChartDataPoint(
            label=row[0],
            value=row[1],
            color=ENTITY_COLORS.get(row[0], "#6b7280"),
        )
        for row in entity_result.all()
    ]

    # 5. Top risky entities
    top_stmt = (
        select(GraphNode)
        .where(GraphNode.risk_score > 0.5, GraphNode.node_type != "case")
        .order_by(GraphNode.risk_score.desc())
        .limit(10)
    )
    top_result = await db.execute(top_stmt)
    top_entities = [
        {
            "label": n.label,
            "type": n.node_type,
            "risk_score": round(n.risk_score, 3) if n.risk_score else 0,
        }
        for n in top_result.scalars().all()
    ]

    return AnalyticsResponse(
        scam_type_distribution=scam_type_distribution,
        risk_level_breakdown=risk_level_breakdown,
        daily_trend=daily_trend,
        entity_type_breakdown=entity_type_breakdown,
        top_entities=top_entities,
    )


# ---------- Geospatial Intelligence ----------

class GeoPoint(BaseModel):
    lat: float
    lng: float
    label: str
    state: str
    is_hotspot: bool
    risk_score: float
    case_count: int
    scam_types: list[str]
    data_source: str = "case_data"  # 'case_data' or 'ncrb_reference'


class GeospatialResponse(BaseModel):
    points: list[GeoPoint]
    total_locations: int
    hotspot_count: int


@router.get("/geospatial", response_model=GeospatialResponse)
async def get_geospatial_data(db: AsyncSession = Depends(get_db)):
    """
    Returns geocoded scam origin locations from the fraud graph.
    Location nodes are geocoded using local Indian city/state lookup.
    """
    from app.database import GraphEdge
    from app.services.geocoding import geocode_location

    # Fetch all location-type nodes
    loc_stmt = select(GraphNode).where(GraphNode.node_type == "location")
    loc_result = await db.execute(loc_stmt)
    location_nodes = loc_result.scalars().all()

    # Also extract locations mentioned in case text via existing graph edges
    # For each location node, find connected case nodes to get scam types
    points: list[GeoPoint] = []
    seen_locations: dict[str, GeoPoint] = {}

    for node in location_nodes:
        geo = geocode_location(node.label)
        if not geo:
            continue

        loc_key = geo["matched"]
        if loc_key in seen_locations:
            # Increment case count for duplicates
            seen_locations[loc_key].case_count += 1
            continue

        # Find connected cases to attribute scam types
        edge_stmt = select(GraphEdge).where(
            (GraphEdge.source_id == node.id) | (GraphEdge.target_id == node.id)
        )
        edge_result = await db.execute(edge_stmt)
        edges = edge_result.scalars().all()

        # Get case nodes connected to this location
        connected_ids = set()
        for e in edges:
            connected_ids.add(e.source_id)
            connected_ids.add(e.target_id)
        connected_ids.discard(node.id)

        scam_types = []
        if connected_ids:
            case_node_stmt = select(GraphNode).where(
                GraphNode.id.in_(list(connected_ids)),
                GraphNode.node_type == "case",
            )
            case_result = await db.execute(case_node_stmt)
            case_nodes = case_result.scalars().all()

            for cn in case_nodes:
                # Case node label is the case ID — look up the actual case
                case_stmt = select(Case).where(Case.id == cn.label)
                try:
                    cr = await db.execute(case_stmt)
                    actual_case = cr.scalar_one_or_none()
                    if actual_case and actual_case.scam_type:
                        scam_types.append(actual_case.scam_type)
                except Exception:
                    pass

        point = GeoPoint(
            lat=geo["lat"],
            lng=geo["lng"],
            label=node.label,
            state=geo["state"],
            is_hotspot=geo["is_hotspot"],
            risk_score=round(node.risk_score or 0.0, 3),
            case_count=1,
            scam_types=list(set(scam_types)) if scam_types else ["Unknown"],
            data_source="case_data",
        )
        seen_locations[loc_key] = point
        points.append(point)

    # Add NCRB reference hotspot overlay — clearly labeled as reference data
    # Source: NCRB Cybercrime Statistics 2024, CBI Press Releases
    from app.services.geocoding import INDIA_GEOCODE
    for name, (lat, lng, state, is_hotspot) in INDIA_GEOCODE.items():
        if is_hotspot and name not in seen_locations:
            point = GeoPoint(
                lat=lat,
                lng=lng,
                label=f"{name.title()} (NCRB Reference)",
                state=state,
                is_hotspot=True,
                risk_score=0.7,  # Base risk from NCRB cybercrime corridor data
                case_count=0,
                scam_types=["NCRB Reference — Known Cybercrime Corridor"],
                data_source="ncrb_reference",
            )
            points.append(point)

    return GeospatialResponse(
        points=points,
        total_locations=len(points),
        hotspot_count=sum(1 for p in points if p.is_hotspot),
    )


