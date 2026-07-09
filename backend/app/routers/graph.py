"""
NETRA Graph Router — Fraud Network Investigation Endpoints

Data flow:
- Search: query graph_nodes by label → return matches
- Network: traverse graph_edges from a starting node (2-hop BFS) → return subgraph JSON for D3.js
- Node detail: fetch node + connected edges from database
"""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, GraphNode, GraphEdge, AuditLog

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- Response Schemas ----------

class NodeResponse(BaseModel):
    id: str
    node_type: str
    label: str
    properties: dict
    risk_score: float | None = None
    first_seen: str | None = None
    last_seen: str | None = None


class EdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: str
    properties: dict
    weight: float = 1.0


class NetworkResponse(BaseModel):
    """Full subgraph response for D3.js rendering."""
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]
    center_node_id: str
    total_nodes: int
    total_edges: int


class SearchResult(BaseModel):
    id: str
    node_type: str
    label: str
    risk_score: float | None = None


# ---------- Endpoints ----------

@router.post("/search", response_model=list[SearchResult])
async def search_nodes(
    query: str = Query(..., min_length=2, max_length=200, description="Search term (phone, UPI, account)"),
    db: AsyncSession = Depends(get_db),
):
    """Search for nodes by label (phone number, UPI ID, account number)."""
    stmt = (
        select(GraphNode)
        .where(GraphNode.label.ilike(f"%{query}%"))
        .limit(20)
    )
    result = await db.execute(stmt)
    nodes = result.scalars().all()

    return [
        SearchResult(
            id=str(n.id),
            node_type=n.node_type,
            label=n.label,
            risk_score=n.risk_score,
        )
        for n in nodes
    ]


@router.get("/recent", response_model=list[SearchResult])
async def get_recent_entities(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recently discovered entities (auto-populated from cases)."""
    stmt = (
        select(GraphNode)
        .where(GraphNode.node_type != "case")  # Exclude case nodes
        .order_by(GraphNode.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    nodes = result.scalars().all()

    return [
        SearchResult(
            id=str(n.id),
            node_type=n.node_type,
            label=n.label,
            risk_score=n.risk_score,
        )
        for n in nodes
    ]


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    node_type_counts: dict[str, int]
    high_risk_entities: int
    syndicate_clusters: int


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate graph statistics."""
    from sqlalchemy import func as sqlfunc

    # Total counts
    node_count = await db.execute(select(sqlfunc.count(GraphNode.id)))
    edge_count = await db.execute(select(sqlfunc.count(GraphEdge.id)))

    # Node type breakdown
    type_counts_stmt = (
        select(GraphNode.node_type, sqlfunc.count(GraphNode.id))
        .group_by(GraphNode.node_type)
    )
    type_counts_result = await db.execute(type_counts_stmt)
    type_counts = {row[0]: row[1] for row in type_counts_result.all()}

    # High risk entities (risk_score > 0.7)
    high_risk = await db.execute(
        select(sqlfunc.count(GraphNode.id)).where(GraphNode.risk_score > 0.7)
    )

    # Syndicate clusters: nodes connected to multiple cases
    # (simplified: count nodes with risk > 0.5 that aren't case nodes)
    syndicate = await db.execute(
        select(sqlfunc.count(GraphNode.id)).where(
            GraphNode.risk_score > 0.5,
            GraphNode.node_type != "case",
        )
    )

    return GraphStats(
        total_nodes=node_count.scalar() or 0,
        total_edges=edge_count.scalar() or 0,
        node_type_counts=type_counts,
        high_risk_entities=high_risk.scalar() or 0,
        syndicate_clusters=syndicate.scalar() or 0,
    )


@router.get("/network/{node_id}", response_model=NetworkResponse)
async def get_network(
    node_id: str,
    depth: int = Query(default=2, ge=1, le=3, description="Traversal depth (1-3 hops)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the connected subgraph around a node (BFS traversal).
    Returns nodes and edges for D3.js force graph rendering.
    """
    try:
        center_uid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")

    # Verify center node exists
    stmt = select(GraphNode).where(GraphNode.id == center_uid)
    result = await db.execute(stmt)
    center_node = result.scalar_one_or_none()
    if not center_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # BFS traversal
    visited_node_ids: set[uuid.UUID] = {center_uid}
    frontier: set[uuid.UUID] = {center_uid}
    all_edges: list[GraphEdge] = []

    for _ in range(depth):
        if not frontier:
            break

        # Find all edges connected to frontier nodes
        stmt = select(GraphEdge).where(
            or_(
                GraphEdge.source_id.in_(frontier),
                GraphEdge.target_id.in_(frontier),
            )
        )
        result = await db.execute(stmt)
        edges = result.scalars().all()

        new_frontier: set[uuid.UUID] = set()
        for edge in edges:
            all_edges.append(edge)
            for nid in [edge.source_id, edge.target_id]:
                if nid not in visited_node_ids:
                    visited_node_ids.add(nid)
                    new_frontier.add(nid)

        frontier = new_frontier

    # Fetch all discovered nodes
    if visited_node_ids:
        stmt = select(GraphNode).where(GraphNode.id.in_(visited_node_ids))
        result = await db.execute(stmt)
        all_nodes = result.scalars().all()
    else:
        all_nodes = [center_node]

    # Deduplicate edges
    seen_edge_ids = set()
    unique_edges = []
    for e in all_edges:
        if e.id not in seen_edge_ids:
            seen_edge_ids.add(e.id)
            unique_edges.append(e)

    # Log the investigation
    audit = AuditLog(
        agent_name="graph_engine",
        action="network_traversal",
        input_summary=f"Node {node_id}, depth={depth}",
        output_summary=f"Found {len(all_nodes)} nodes, {len(unique_edges)} edges",
        latency_ms=0,
        status="success",
    )
    db.add(audit)

    return NetworkResponse(
        nodes=[
            NodeResponse(
                id=str(n.id),
                node_type=n.node_type,
                label=n.label,
                properties=n.properties or {},
                risk_score=n.risk_score,
                first_seen=n.first_seen.isoformat() if n.first_seen else None,
                last_seen=n.last_seen.isoformat() if n.last_seen else None,
            )
            for n in all_nodes
        ],
        edges=[
            EdgeResponse(
                id=str(e.id),
                source_id=str(e.source_id),
                target_id=str(e.target_id),
                edge_type=e.edge_type,
                properties=e.properties or {},
                weight=e.weight or 1.0,
            )
            for e in unique_edges
        ],
        center_node_id=str(center_uid),
        total_nodes=len(all_nodes),
        total_edges=len(unique_edges),
    )


@router.get("/node/{node_id}", response_model=NodeResponse)
async def get_node_detail(
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a single node."""
    try:
        uid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")

    stmt = select(GraphNode).where(GraphNode.id == uid)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    return NodeResponse(
        id=str(node.id),
        node_type=node.node_type,
        label=node.label,
        properties=node.properties or {},
        risk_score=node.risk_score,
        first_seen=node.first_seen.isoformat() if node.first_seen else None,
        last_seen=node.last_seen.isoformat() if node.last_seen else None,
    )
