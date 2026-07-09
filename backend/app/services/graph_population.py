"""
NETRA Graph Population Service — Auto-builds fraud network from extracted entities

When a scam is analyzed, this service:
1. Takes extracted entities from EntityExtractor
2. Creates GraphNode entries for each entity (deduplicating by value)
3. Creates a "case" node for the analysis itself
4. Creates GraphEdge entries linking entities to the case
5. Cross-links entities that appear in multiple cases (syndicate detection)

This transforms the Investigate page from static seed data into a live,
case-driven intelligence graph.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import GraphNode, GraphEdge, AuditLog
from app.services.entity_extraction import ExtractedEntity, ExtractionResult

logger = logging.getLogger(__name__)


# Map entity types to graph node types
ENTITY_TO_NODE_TYPE = {
    "phone": "phone",
    "upi_id": "upi_id",
    "bank_account": "bank_account",
    "email": "email",
    "url": "url",
    "person": "suspect",
    "organization": "organization",
    "location": "location",
    "amount": "amount",
    "ifsc": "bank_account",
    "aadhaar": "identity_doc",
    "pan": "identity_doc",
    "designation": "designation",
}

# Map entity types to edge types (entity → case)
ENTITY_TO_EDGE_TYPE = {
    "phone": "used_in",
    "upi_id": "used_in",
    "bank_account": "used_in",
    "email": "used_in",
    "url": "used_in",
    "person": "mentioned_in",
    "organization": "impersonated_in",
    "location": "located_in",
    "amount": "demanded_in",
    "ifsc": "used_in",
    "aadhaar": "referenced_in",
    "pan": "referenced_in",
    "designation": "claimed_in",
}


class GraphPopulationService:
    """
    Populates the fraud network graph from extracted entities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def populate_from_case(
        self,
        case_id: uuid.UUID,
        scam_type: str | None,
        risk_level: str | None,
        confidence: float,
        extraction_result: ExtractionResult,
    ) -> dict:
        """
        Create graph nodes and edges from a case's extracted entities.

        Returns summary of what was created.
        """
        if not extraction_result.entities:
            return {"nodes_created": 0, "edges_created": 0, "nodes_linked": 0}

        nodes_created = 0
        edges_created = 0
        nodes_linked = 0  # Existing nodes linked to this case

        # 1. Create or find the "case" node
        case_node = await self._get_or_create_node(
            node_type="case",
            label=f"Case: {scam_type or 'Analysis'}",
            properties={
                "case_id": str(case_id),
                "scam_type": scam_type,
                "risk_level": risk_level,
                "confidence": confidence,
            },
            risk_score=confidence if scam_type else 0.0,
        )
        if case_node["is_new"]:
            nodes_created += 1

        # 2. Process each extracted entity
        for entity in extraction_result.entities:
            node_type = ENTITY_TO_NODE_TYPE.get(entity.entity_type, "unknown")
            edge_type = ENTITY_TO_EDGE_TYPE.get(entity.entity_type, "linked_to")

            # Determine risk score based on entity type and context
            entity_risk = self._calculate_entity_risk(entity, confidence)

            # Create or find the entity node
            node_result = await self._get_or_create_node(
                node_type=node_type,
                label=entity.value,
                properties={
                    "extraction_source": entity.source,
                    "extraction_confidence": entity.confidence,
                    "context": entity.context[:200] if entity.context else "",
                },
                risk_score=entity_risk,
            )

            if node_result["is_new"]:
                nodes_created += 1
            else:
                nodes_linked += 1
                # Update risk score if new case has higher risk
                if entity_risk > (node_result.get("existing_risk", 0) or 0):
                    await self._update_node_risk(
                        node_result["node_id"],
                        entity_risk,
                    )

            # Create edge: entity → case
            edge_created = await self._create_edge_if_not_exists(
                source_id=node_result["node_id"],
                target_id=case_node["node_id"],
                edge_type=edge_type,
                properties={
                    "case_id": str(case_id),
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "confidence": entity.confidence,
                },
                weight=entity.confidence,
            )
            if edge_created:
                edges_created += 1

        # 3. Cross-link entities within this case (e.g., phone → UPI used together)
        cross_links = await self._create_cross_links(
            extraction_result.entities,
            case_node["node_id"],
        )
        edges_created += cross_links

        # 4. Find and link to other cases sharing entities (syndicate detection)
        syndicate_links = await self._detect_syndicate_links(
            extraction_result.entities,
            case_id,
        )
        edges_created += syndicate_links

        # Log the population
        audit = AuditLog(
            case_id=case_id,
            agent_name="graph_population",
            action="auto_populate_graph",
            input_summary=f"{extraction_result.entity_count} entities extracted",
            output_summary=f"Created {nodes_created} nodes, {edges_created} edges, linked {nodes_linked} existing",
            latency_ms=0,
            status="success",
        )
        self.db.add(audit)

        logger.info(
            f"Graph populated for case {case_id}: "
            f"{nodes_created} new nodes, {edges_created} edges, {nodes_linked} linked"
        )

        return {
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "nodes_linked": nodes_linked,
        }

    async def _get_or_create_node(
        self,
        node_type: str,
        label: str,
        properties: dict,
        risk_score: float | None = None,
    ) -> dict:
        """
        Find existing node by (node_type, label) or create new.
        Returns dict with node_id and is_new flag.
        """
        # Search for existing node with same type and label
        stmt = select(GraphNode).where(
            GraphNode.node_type == node_type,
            GraphNode.label == label,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update last_seen
            existing.last_seen = datetime.now(timezone.utc)
            return {
                "node_id": existing.id,
                "is_new": False,
                "existing_risk": existing.risk_score,
            }

        # Create new node
        now = datetime.now(timezone.utc)
        node = GraphNode(
            node_type=node_type,
            label=label,
            properties=properties,
            risk_score=risk_score,
            first_seen=now,
            last_seen=now,
        )
        self.db.add(node)
        await self.db.flush()  # Get the generated ID

        return {
            "node_id": node.id,
            "is_new": True,
            "existing_risk": None,
        }

    async def _update_node_risk(self, node_id: uuid.UUID, new_risk: float) -> None:
        """Update a node's risk score."""
        stmt = select(GraphNode).where(GraphNode.id == node_id)
        result = await self.db.execute(stmt)
        node = result.scalar_one_or_none()
        if node:
            # Use max of existing and new risk
            node.risk_score = max(node.risk_score or 0, new_risk)

    async def _create_edge_if_not_exists(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        edge_type: str,
        properties: dict,
        weight: float = 1.0,
    ) -> bool:
        """Create an edge if it doesn't already exist. Returns True if created."""
        # Check for existing edge
        stmt = select(GraphEdge).where(
            GraphEdge.source_id == source_id,
            GraphEdge.target_id == target_id,
            GraphEdge.edge_type == edge_type,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return False

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties,
            weight=weight,
        )
        self.db.add(edge)
        return True

    async def _create_cross_links(
        self,
        entities: list[ExtractedEntity],
        case_node_id: uuid.UUID,
    ) -> int:
        """
        Create edges between entities within the same case.
        E.g., if a phone number and UPI ID appear together, link them.
        """
        edges_created = 0
        # Group entities by type
        phones = [e for e in entities if e.entity_type == "phone"]
        upis = [e for e in entities if e.entity_type == "upi_id"]
        accounts = [e for e in entities if e.entity_type == "bank_account"]

        # Link phones ↔ UPI IDs (likely same person)
        for phone in phones:
            for upi in upis:
                phone_node = await self._find_node("phone", phone.value)
                upi_node = await self._find_node("upi_id", upi.value)
                if phone_node and upi_node:
                    created = await self._create_edge_if_not_exists(
                        source_id=phone_node.id,
                        target_id=upi_node.id,
                        edge_type="linked_to",
                        properties={"link_type": "co-occurrence", "case_derived": True},
                        weight=0.8,
                    )
                    if created:
                        edges_created += 1

        # Link UPI IDs ↔ bank accounts
        for upi in upis:
            for account in accounts:
                upi_node = await self._find_node("upi_id", upi.value)
                acc_node = await self._find_node("bank_account", account.value)
                if upi_node and acc_node:
                    created = await self._create_edge_if_not_exists(
                        source_id=upi_node.id,
                        target_id=acc_node.id,
                        edge_type="linked_to",
                        properties={"link_type": "financial_link", "case_derived": True},
                        weight=0.9,
                    )
                    if created:
                        edges_created += 1

        return edges_created

    async def _detect_syndicate_links(
        self,
        entities: list[ExtractedEntity],
        current_case_id: uuid.UUID,
    ) -> int:
        """
        Find entities that appear in OTHER cases and create syndicate links.
        This is the key intelligence feature — it auto-detects crime networks.
        """
        edges_created = 0

        for entity in entities:
            node_type = ENTITY_TO_NODE_TYPE.get(entity.entity_type, "unknown")

            # Find existing node
            stmt = select(GraphNode).where(
                GraphNode.node_type == node_type,
                GraphNode.label == entity.value,
            )
            result = await self.db.execute(stmt)
            node = result.scalar_one_or_none()

            if not node:
                continue

            # Check how many case edges this node has
            stmt = select(GraphEdge).where(
                GraphEdge.source_id == node.id,
                GraphEdge.edge_type.in_(["used_in", "mentioned_in", "impersonated_in"]),
            )
            result = await self.db.execute(stmt)
            case_edges = result.scalars().all()

            # If this entity is linked to multiple cases, it's a potential syndicate indicator
            if len(case_edges) > 1:
                # Increase risk score — repeated appearance across cases
                node.risk_score = min(1.0, (node.risk_score or 0) + 0.15)
                logger.info(
                    f"Syndicate indicator: {entity.entity_type} '{entity.value}' "
                    f"found in {len(case_edges)} cases"
                )

        return edges_created

    async def _find_node(self, node_type: str, label: str) -> GraphNode | None:
        """Find a node by type and label."""
        stmt = select(GraphNode).where(
            GraphNode.node_type == node_type,
            GraphNode.label == label,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _calculate_entity_risk(
        self,
        entity: ExtractedEntity,
        case_confidence: float,
    ) -> float:
        """
        Calculate risk score for an entity based on its type and the case confidence.
        Higher case confidence = higher entity risk.
        """
        # Base risk weights by entity type
        type_weights = {
            "phone": 0.7,
            "upi_id": 0.8,
            "bank_account": 0.85,
            "email": 0.5,
            "url": 0.6,
            "person": 0.4,
            "organization": 0.3,
            "location": 0.2,
            "amount": 0.3,
            "ifsc": 0.5,
            "aadhaar": 0.6,
            "pan": 0.6,
            "designation": 0.3,
        }

        base = type_weights.get(entity.entity_type, 0.3)
        # Risk = base weight * case confidence * entity extraction confidence
        risk = base * case_confidence * entity.confidence
        return round(min(1.0, risk), 3)
