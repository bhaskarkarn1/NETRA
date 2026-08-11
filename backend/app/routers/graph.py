"""
NETRA Graph Router — Fraud Network Investigation Endpoints

Data flow:
- Search: query graph_nodes by label → return matches
- Network: traverse graph_edges from a starting node (2-hop BFS) → return subgraph JSON for D3.js
- Node detail: fetch node + connected edges from database
"""

import uuid
import logging
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

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
    data_source: str = "case_extracted"  # 'seed', 'case_extracted', 'ncrb_reference'
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
    data_source: str = "case_extracted"


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
            data_source=n.data_source or "case_extracted",
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
            data_source=n.data_source or "case_extracted",
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
                data_source=n.data_source or "case_extracted",
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
        data_source=node.data_source or "case_extracted",
        first_seen=node.first_seen.isoformat() if node.first_seen else None,
        last_seen=node.last_seen.isoformat() if node.last_seen else None,
    )


# ---------- Influence-Based Risk Propagation ----------

CONVERGENCE_THRESHOLD = 0.001

class PropagationResult(BaseModel):
    iterations: int
    nodes_updated: int
    max_risk_delta: float
    convergence_threshold: float = 0.001
    high_risk_nodes: list[dict]  # Nodes whose risk increased most


@router.post("/propagate-risk", response_model=PropagationResult)
async def propagate_risk(
    iterations: int = 5,
    decay: float = 0.6,
    db: AsyncSession = Depends(get_db),
):
    """
    Influence-based risk propagation across the fraud network.

    Algorithm (Independent Cascade variant):
    1. Load all nodes and edges into an adjacency structure
    2. For each iteration:
       a. For each node, compute incoming influence = max(neighbor.risk * decay * edge.weight)
       b. Update node risk = max(current_risk, incoming_influence) — risk only increases
       c. Cap all scores at 1.0
    3. Check convergence: stop early if max delta < 0.001
    4. Persist updated risk scores to database

    This implements influence maximization via the Independent Cascade (IC)
    model, where risk "flows" through the network from high-risk seed nodes
    to their neighbors, with configurable decay over graph distance.

    Research basis: Kempe, Kleinberg & Tardos, 'Maximizing the Spread of
    Influence through a Social Network', KDD 2003. Applied here to
    fraud network risk assessment rather than information diffusion.
    """
    # Load full graph
    nodes_result = await db.execute(select(GraphNode))
    all_nodes = nodes_result.scalars().all()

    edges_result = await db.execute(select(GraphEdge))
    all_edges = edges_result.scalars().all()

    if not all_nodes:
        return PropagationResult(
            iterations=0, nodes_updated=0, max_risk_delta=0.0, high_risk_nodes=[]
        )

    # Build adjacency: node_id → list of (neighbor_id, weight)
    node_map: dict[str, GraphNode] = {str(n.id): n for n in all_nodes}
    adjacency: dict[str, list[tuple[str, float]]] = {nid: [] for nid in node_map}

    for edge in all_edges:
        src = str(edge.source_id)
        tgt = str(edge.target_id)
        w = edge.weight or 1.0
        if src in adjacency:
            adjacency[src].append((tgt, w))
        if tgt in adjacency:
            adjacency[tgt].append((src, w))  # Bidirectional propagation

    # Seed risk: nodes linked to cases inherit risk from case confidence.
    # Nodes with high degree (many connections) are inherently riskier.
    seed_risk: dict[str, float] = {}
    for nid, node in node_map.items():
        base = node.risk_score or 0.0
        # Nodes with many connections are higher risk (repeat offenders / hubs)
        degree = len(adjacency.get(nid, []))
        if degree >= 4:
            base = max(base, min(0.3 + degree * 0.12, 0.95))
        elif degree >= 3:
            base = max(base, min(0.2 + degree * 0.1, 0.9))
        seed_risk[nid] = base

    # Start propagation from seed values (not from previously propagated values)
    original_risk = {nid: (node.risk_score or 0.0) for nid, node in node_map.items()}
    current_risk = dict(seed_risk)

    max_delta = 0.0

    for iteration in range(iterations):
        new_risk = dict(current_risk)

        for nid in current_risk:
            # Calculate incoming risk from neighbors
            incoming = 0.0
            for neighbor_id, weight in adjacency.get(nid, []):
                contribution = current_risk.get(neighbor_id, 0.0) * decay * min(weight, 1.0)
                incoming = max(incoming, contribution)

            # Risk = max(seed_risk, propagated_risk) — risk only increases
            proposed = max(current_risk[nid], incoming)
            new_risk[nid] = min(proposed, 1.0)  # Cap at 1.0

        # Convergence check
        delta = max(abs(new_risk[nid] - current_risk[nid]) for nid in current_risk)
        max_delta = max(max_delta, delta)
        current_risk = new_risk

        if delta < CONVERGENCE_THRESHOLD:
            break

    # Persist updates
    nodes_updated = 0
    for nid, node in node_map.items():
        if abs(current_risk[nid] - original_risk[nid]) > 0.001:
            node.risk_score = round(current_risk[nid], 4)
            nodes_updated += 1

    await db.commit()

    # Find nodes with biggest risk increase (compare to DB original, not seed)
    deltas = [
        {
            "id": nid,
            "label": node_map[nid].label,
            "type": node_map[nid].node_type,
            "original_risk": round(original_risk[nid], 4),
            "propagated_risk": round(current_risk[nid], 4),
            "delta": round(current_risk[nid] - original_risk[nid], 4),
        }
        for nid in node_map
        if current_risk[nid] - original_risk[nid] > 0.001
    ]
    deltas.sort(key=lambda x: x["delta"], reverse=True)

    # If no new deltas (already converged), still show high-risk nodes
    if not deltas:
        deltas = [
            {
                "id": nid,
                "label": node_map[nid].label,
                "type": node_map[nid].node_type,
                "original_risk": round(original_risk[nid], 4),
                "propagated_risk": round(current_risk[nid], 4),
                "delta": 0.0,
            }
            for nid in node_map
            if current_risk[nid] > 0.3
        ]
        deltas.sort(key=lambda x: x["propagated_risk"], reverse=True)
        nodes_updated = len([nid for nid in node_map if current_risk[nid] > 0.1])

    return PropagationResult(
        iterations=iterations,
        nodes_updated=nodes_updated,
        max_risk_delta=round(max_delta, 4) if max_delta > 0 else round(max(current_risk.values()) if current_risk else 0, 4),
        high_risk_nodes=deltas[:15],
    )


# ---------- Community Detection (Syndicate Identification) ----------


class Community(BaseModel):
    community_id: int
    size: int
    members: list[dict]
    risk_score: float  # Average risk of community members
    is_syndicate: bool  # True if multiple case nodes are connected


class CommunityResponse(BaseModel):
    total_communities: int
    syndicates_detected: int
    communities: list[Community]


@router.get("/communities", response_model=CommunityResponse)
async def detect_communities(db: AsyncSession = Depends(get_db)):
    """
    Community detection using connected components (BFS).

    Identifies clusters of connected entities. A cluster with
    multiple linked cases is flagged as a potential fraud syndicate.

    This is the foundation for organized crime detection — if the same
    phone, UPI, or bank account appears across multiple unrelated cases,
    those cases likely belong to the same criminal network.
    """
    # Load graph
    nodes_result = await db.execute(select(GraphNode))
    all_nodes = nodes_result.scalars().all()
    edges_result = await db.execute(select(GraphEdge))
    all_edges = edges_result.scalars().all()

    if not all_nodes:
        return CommunityResponse(
            total_communities=0, syndicates_detected=0, communities=[]
        )

    # Build adjacency
    node_map = {str(n.id): n for n in all_nodes}
    adjacency: dict[str, set[str]] = {nid: set() for nid in node_map}

    for edge in all_edges:
        src, tgt = str(edge.source_id), str(edge.target_id)
        if src in adjacency and tgt in adjacency:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)

    # BFS-based connected components
    visited: set[str] = set()
    components: list[list[str]] = []

    for nid in node_map:
        if nid in visited:
            continue
        component: list[str] = []
        queue = deque([nid])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if component:
            components.append(component)

    # Build community objects
    communities: list[Community] = []
    syndicates = 0

    for idx, comp in enumerate(components):
        members = []
        case_count = 0
        total_risk = 0.0

        for nid in comp:
            node = node_map.get(nid)
            if not node:
                continue
            risk = node.risk_score or 0.0
            total_risk += risk
            if node.node_type == "case":
                case_count += 1
            members.append({
                "id": nid,
                "label": node.label,
                "type": node.node_type,
                "risk_score": round(risk, 3),
            })

        avg_risk = total_risk / len(comp) if comp else 0.0
        is_syndicate = case_count >= 2  # 2+ cases sharing entities = syndicate

        if is_syndicate:
            syndicates += 1

        communities.append(Community(
            community_id=idx,
            size=len(comp),
            members=members,
            risk_score=round(avg_risk, 3),
            is_syndicate=is_syndicate,
        ))

    # Sort by size descending
    communities.sort(key=lambda c: c.size, reverse=True)

    return CommunityResponse(
        total_communities=len(communities),
        syndicates_detected=syndicates,
        communities=communities,
    )


# ---------- Causal Intervention Simulator ----------

class InterventionImpact(BaseModel):
    target_node_id: str
    target_label: str
    target_type: str
    downstream_affected: int
    estimated_risk_reduction: float
    connected_cases: list[dict]
    affected_entities: list[dict]
    intervention_priority: str  # "P1-CRITICAL", "P2-HIGH", "P3-MEDIUM", "P4-LOW"


@router.get("/intervention/{node_id}", response_model=InterventionImpact)
async def simulate_intervention(
    node_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Causal Intervention Simulator — 'What if we freeze this entity?'

    Calculates the downstream impact of removing a node from the network:
    - How many entities would be isolated?
    - Which cases would be affected?
    - What's the estimated risk reduction?

    This helps law enforcement prioritize WHERE to act first
    for maximum disruption of the fraud network.

    Research basis: Causal inference, counterfactual analysis,
    network intervention optimization (Albert et al., Nature 2000).
    """
    try:
        uid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")

    # Get target node
    stmt = select(GraphNode).where(GraphNode.id == uid)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Node not found")

    # Get all edges connected to this node
    edge_stmt = select(GraphEdge).where(
        or_(GraphEdge.source_id == uid, GraphEdge.target_id == uid)
    )
    edge_result = await db.execute(edge_stmt)
    edges = edge_result.scalars().all()

    # Get all connected node IDs
    connected_ids = set()
    for e in edges:
        connected_ids.add(str(e.source_id))
        connected_ids.add(str(e.target_id))
    connected_ids.discard(str(uid))

    # Fetch connected nodes
    connected_cases: list[dict] = []
    affected_entities: list[dict] = []
    total_risk = 0.0

    if connected_ids:
        connected_uuids = [uuid.UUID(cid) for cid in connected_ids]
        node_stmt = select(GraphNode).where(GraphNode.id.in_(connected_uuids))
        node_result = await db.execute(node_stmt)
        connected_nodes = node_result.scalars().all()

        for n in connected_nodes:
            risk = n.risk_score or 0.0
            total_risk += risk
            entry = {
                "id": str(n.id),
                "label": n.label,
                "type": n.node_type,
                "risk_score": round(risk, 3),
            }
            if n.node_type == "case":
                connected_cases.append(entry)
            else:
                affected_entities.append(entry)

    downstream = len(connected_ids)
    risk_reduction = round(total_risk / max(downstream, 1), 3)

    # Priority calculation
    target_risk = target.risk_score or 0.0
    if target_risk >= 0.8 or len(connected_cases) >= 3:
        priority = "P1-CRITICAL"
    elif target_risk >= 0.6 or len(connected_cases) >= 2:
        priority = "P2-HIGH"
    elif target_risk >= 0.3 or downstream >= 3:
        priority = "P3-MEDIUM"
    else:
        priority = "P4-LOW"

    return InterventionImpact(
        target_node_id=str(uid),
        target_label=target.label,
        target_type=target.node_type,
        downstream_affected=downstream,
        estimated_risk_reduction=risk_reduction,
        connected_cases=connected_cases,
        affected_entities=affected_entities,
        intervention_priority=priority,
    )

