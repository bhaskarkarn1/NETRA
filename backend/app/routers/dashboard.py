"""
NETRA Dashboard Router — Metrics & Threat Feed

All metrics are computed from database aggregations, not hardcoded.
Uses 30-second in-memory cache to reduce DB round-trips on Railway/Neon.
"""

import asyncio
import logging
import time
from typing import Any

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, Case, Simulation, GraphNode, AuditLog, DisruptionAction, ScamPattern

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------- In-Memory Cache (30s TTL) ----------
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 60  # seconds — increased from 30 to reduce DB pressure on Railway/Neon


def _get_cached(key: str) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


# ---------- Schemas ----------

class DisruptionActionFeed(BaseModel):
    id: str
    action_type: str
    target_entity: str
    target_institution: str
    status: str
    confidence: float
    created_at: str


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
    # NEW: Command Center fields
    threat_level: str  # 'CRITICAL', 'HIGH', 'ELEVATED', 'NORMAL'
    estimated_financial_loss_prevented: float  # In INR
    active_disruption_actions: int
    recent_disruptions: list[DisruptionActionFeed]


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
    """Dashboard statistics — all computed from database, nothing hardcoded.

    Optimized: queries are batched into concurrent groups via asyncio.gather()
    to reduce total DB round-trip time from ~12 sequential queries to ~3 parallel batches.
    """

    # Cache-first: return cached data if fresh
    cached = _get_cached("metrics")
    if cached is not None:
        return cached

    from app.database import GraphEdge
    from sqlalchemy import and_

    # --- Batch 1: Simple count queries (all independent, run concurrently) ---
    async def _case_counts():
        total = await db.scalar(select(func.count(Case.id))) or 0
        scams = await db.scalar(
            select(func.count(Case.id)).where(Case.scam_type.is_not(None))
        ) or 0
        avg_conf = await db.scalar(
            select(func.avg(Case.confidence)).where(Case.confidence.is_not(None))
        ) or 0.0
        return total, scams, avg_conf

    async def _most_common_scam():
        stmt = (
            select(Case.scam_type, func.count(Case.id).label("cnt"))
            .where(Case.scam_type.is_not(None))
            .group_by(Case.scam_type)
            .order_by(func.count(Case.id).desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        return row[0] if row else None

    async def _sim_counts():
        total_sims = await db.scalar(select(func.count(Simulation.id))) or 0
        sims_int = await db.scalar(
            select(func.count(Simulation.id)).where(Simulation.intervention_triggered == True)
        ) or 0
        return total_sims, sims_int

    async def _graph_counts():
        nodes = await db.scalar(select(func.count(GraphNode.id))) or 0
        edges = await db.scalar(select(func.count(GraphEdge.id))) or 0
        return nodes, edges

    async def _audit_counts():
        total = await db.scalar(select(func.count(AuditLog.id))) or 0
        fallbacks = await db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.status == "fallback")
        ) or 0
        return total, fallbacks

    # Run all count queries concurrently
    (
        (total_cases, total_scams, avg_conf),
        most_common_scam,
        (total_sims, sims_intervened),
        (total_nodes, total_edges),
        (total_agent_calls, fallback_count),
    ) = await asyncio.gather(
        _case_counts(),
        _most_common_scam(),
        _sim_counts(),
        _graph_counts(),
        _audit_counts(),
    )

    # --- Batch 2: Threat level + financial loss + disruptions (run concurrently) ---
    async def _threat_level():
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        high_risk_24h = await db.scalar(
            select(func.count(Case.id)).where(
                and_(
                    Case.risk_level.in_(["critical", "high"]),
                    Case.created_at >= cutoff,
                )
            )
        ) or 0

        if high_risk_24h == 0:
            high_risk_total = await db.scalar(
                select(func.count(Case.id)).where(
                    Case.risk_level.in_(["critical", "high"])
                )
            ) or 0
        else:
            high_risk_total = high_risk_24h

        if high_risk_24h >= 5:
            return "CRITICAL"
        elif high_risk_24h >= 2:
            return "HIGH"
        elif high_risk_24h >= 1 or high_risk_total >= 3:
            return "ELEVATED"
        elif high_risk_total >= 1:
            return "ELEVATED"
        return "NORMAL"

    async def _financial_loss():
        """Single pass: fetch scam counts AND pattern avg_loss in one go (no N+1)."""
        if total_scams == 0:
            return 0.0

        # Get scam type counts
        scam_counts_stmt = (
            select(Case.scam_type, func.count(Case.id).label("cnt"))
            .where(Case.scam_type.is_not(None))
            .group_by(Case.scam_type)
        )
        scam_counts_result = await db.execute(scam_counts_stmt)
        scam_counts = {row[0]: row[1] for row in scam_counts_result.all()}

        # Fetch ALL pattern avg_loss_inr in a single query (eliminates N+1)
        pattern_stmt = select(ScamPattern.name, ScamPattern.avg_loss_inr).where(
            ScamPattern.name.in_(list(scam_counts.keys()))
        )
        pattern_result = await db.execute(pattern_stmt)
        avg_losses = {row[0]: row[1] for row in pattern_result.all() if row[1]}

        total_loss = 0.0
        for stype, count in scam_counts.items():
            if stype in avg_losses:
                total_loss += avg_losses[stype] * count
        return total_loss

    async def _disruptions():
        active = await db.scalar(select(func.count(DisruptionAction.id))) or 0
        stmt = (
            select(DisruptionAction)
            .order_by(DisruptionAction.created_at.desc())
            .limit(10)
        )
        rd_result = await db.execute(stmt)
        rd_rows = rd_result.scalars().all()
        recent = [
            DisruptionActionFeed(
                id=str(d.id),
                action_type=d.action_type,
                target_entity=d.target_entity,
                target_institution=d.target_institution or "",
                status=d.status or "simulated",
                confidence=d.confidence or 0,
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            for d in rd_rows
        ]
        return active, recent

    # Run batch 2 concurrently
    threat_level, financial_loss_prevented, (active_disruptions, recent_disruptions) = await asyncio.gather(
        _threat_level(),
        _financial_loss(),
        _disruptions(),
    )

    result = DashboardMetrics(
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
        threat_level=threat_level,
        estimated_financial_loss_prevented=round(financial_loss_prevented, 2),
        active_disruption_actions=active_disruptions,
        recent_disruptions=recent_disruptions,
    )

    _set_cached("metrics", result)
    return result


@router.get("/threat-feed", response_model=list[ThreatFeedItem])
async def get_threat_feed(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Recent threat activity feed — pulled from cases and simulations."""
    cached = _get_cached(f"threat-feed-{limit}")
    if cached is not None:
        return cached
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
    result = items[:limit]
    _set_cached(f"threat-feed-{limit}", result)
    return result


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
    cached = _get_cached("analytics")
    if cached is not None:
        return cached

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

    result = AnalyticsResponse(
        scam_type_distribution=scam_type_distribution,
        risk_level_breakdown=risk_level_breakdown,
        daily_trend=daily_trend,
        entity_type_breakdown=entity_type_breakdown,
        top_entities=top_entities,
    )
    _set_cached("analytics", result)
    return result


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
    Cached for 60 seconds since geo data changes infrequently.
    """
    cached = _get_cached("geospatial")
    if cached is not None:
        return cached

    from app.database import GraphEdge
    from app.services.geocoding import geocode_location

    # Fetch all location-type nodes
    loc_stmt = select(GraphNode).where(GraphNode.node_type == "location")
    loc_result = await db.execute(loc_stmt)
    location_nodes = loc_result.scalars().all()

    # Only fetch edges connected to location nodes (not ALL edges in DB)
    location_ids = [n.id for n in location_nodes]
    if location_ids:
        from sqlalchemy import or_
        edges_stmt = select(GraphEdge).where(
            or_(
                GraphEdge.source_id.in_(location_ids),
                GraphEdge.target_id.in_(location_ids),
            )
        )
        edges_result = await db.execute(edges_stmt)
        relevant_edges = edges_result.scalars().all()
    else:
        relevant_edges = []

    # Build adjacency map: node_id -> set of connected node_ids
    adjacency: dict[str, set[str]] = {}
    for e in relevant_edges:
        adjacency.setdefault(str(e.source_id), set()).add(str(e.target_id))
        adjacency.setdefault(str(e.target_id), set()).add(str(e.source_id))

    # Pre-fetch all case nodes and their corresponding Case records
    case_nodes_stmt = select(GraphNode).where(GraphNode.node_type == "case")
    case_nodes_result = await db.execute(case_nodes_stmt)
    case_nodes_map = {str(cn.id): cn.label for cn in case_nodes_result.scalars().all()}

    # Pre-fetch all cases for scam_type lookup
    all_case_ids = list(case_nodes_map.values())
    cases_by_id: dict[str, str] = {}
    if all_case_ids:
        try:
            import uuid as _uuid
            valid_uuids = []
            for cid in all_case_ids:
                try:
                    valid_uuids.append(_uuid.UUID(cid))
                except (ValueError, AttributeError):
                    pass
            if valid_uuids:
                cases_stmt = select(Case).where(Case.id.in_(valid_uuids))
                cases_result = await db.execute(cases_stmt)
                for c in cases_result.scalars().all():
                    if c.scam_type:
                        cases_by_id[str(c.id)] = c.scam_type
        except Exception:
            pass

    points: list[GeoPoint] = []
    seen_locations: dict[str, GeoPoint] = {}

    for node in location_nodes:
        geo = geocode_location(node.label)
        if not geo:
            continue

        loc_key = geo["matched"]
        if loc_key in seen_locations:
            seen_locations[loc_key].case_count += 1
            continue

        # Use pre-fetched adjacency map instead of per-node queries
        connected_ids = adjacency.get(str(node.id), set())
        scam_types = []
        for cid in connected_ids:
            if cid in case_nodes_map:
                case_label = case_nodes_map[cid]
                if case_label in cases_by_id:
                    scam_types.append(cases_by_id[case_label])

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

    result = GeospatialResponse(
        points=points,
        total_locations=len(points),
        hotspot_count=sum(1 for p in points if p.is_hotspot),
    )
    _set_cached("geospatial", result)
    return result


