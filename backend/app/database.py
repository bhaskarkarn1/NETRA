"""
NETRA Database Models — PostgreSQL via SQLAlchemy Async

Every table has a clear purpose in the data pipeline:
- cases: Scam detection results
- scam_patterns: Reference data for known scam types
- legal_mappings: IPC/IT Act sections reference
- graph_nodes: Fraud network entity nodes
- graph_edges: Fraud network relationships
- simulations: Simulation session records
- simulation_turns: Individual messages in simulations
- audit_logs: Every agent action logged
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import get_settings


# ---------- Base ----------

class Base(DeclarativeBase):
    pass


# ---------- Models ----------

class Case(Base):
    """Every scam analysis request becomes a case."""
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_text = Column(Text, nullable=False)
    input_type = Column(String(20), nullable=False)  # 'text', 'transcript', 'url'
    language = Column(String(10), default="en")

    # AI-generated results
    scam_type = Column(String(50))
    confidence = Column(Float)
    risk_level = Column(String(20))
    ai_reasoning = Column(Text)
    model_used = Column(String(50))

    # Linked data
    legal_sections = Column(JSON)  # Array of matched IPC/IT Act sections
    tactics_detected = Column(JSON)  # Array of psychological tactics

    # Kill Chain™ decomposition
    kill_chain = Column(JSON)  # 6-stage attack progression mapping
    victim_vulnerability_score = Column(Float)  # 0.0–1.0
    victim_vulnerability_factors = Column(JSON)  # Array of vulnerability factors

    # Cross-case intelligence
    embedding = Column(JSON)  # Text embedding vector for similarity search
    evidence_hash = Column(String(64))  # SHA-256 hash of input_text

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processing_time_ms = Column(Integer)

    __table_args__ = (
        Index("idx_cases_scam_type", "scam_type"),
        Index("idx_cases_created", "created_at"),
    )


class ScamPattern(Base):
    """Reference data for known scam templates. Seeded from research."""
    __tablename__ = "scam_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text)

    # Pattern indicators
    keywords = Column(JSON)
    tactics = Column(JSON)
    typical_flow = Column(JSON)

    # Legal mapping
    ipc_sections = Column(JSON)
    it_act_sections = Column(JSON)

    # Metadata
    source = Column(String(500))  # URL or citation
    prevalence = Column(String(20))
    avg_loss_inr = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LegalMapping(Base):
    """IPC and IT Act sections reference table."""
    __tablename__ = "legal_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), nullable=False, unique=True)  # 'IPC_419', 'IT_66D'
    law = Column(String(50), nullable=False)
    section = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    punishment = Column(Text)
    applicability = Column(JSON)  # Which scam types this applies to
    is_cognizable = Column(Boolean, default=True)


class GraphNode(Base):
    """Entities in the fraud network."""
    __tablename__ = "graph_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_type = Column(String(30), nullable=False)  # 'phone', 'bank_account', 'upi_id', 'victim', 'location'
    label = Column(String(200), nullable=False)
    properties = Column(JSON, nullable=False)
    risk_score = Column(Float)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    outgoing_edges = relationship("GraphEdge", foreign_keys="GraphEdge.source_id", back_populates="source_node")
    incoming_edges = relationship("GraphEdge", foreign_keys="GraphEdge.target_id", back_populates="target_node")

    __table_args__ = (
        Index("idx_graph_nodes_type", "node_type"),
    )


class GraphEdge(Base):
    """Relationships between fraud network entities."""
    __tablename__ = "graph_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    edge_type = Column(String(30), nullable=False)  # 'called', 'transferred', 'reported', 'linked_to', 'located_at'
    properties = Column(JSON, nullable=False)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node = relationship("GraphNode", foreign_keys=[target_id], back_populates="incoming_edges")

    __table_args__ = (
        Index("idx_graph_edges_source", "source_id"),
        Index("idx_graph_edges_target", "target_id"),
    )


class Simulation(Base):
    """Each simulation session."""
    __tablename__ = "simulations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_type = Column(String(50), nullable=False)
    user_session_id = Column(String(100))

    status = Column(String(20), default="active")  # 'active', 'completed', 'intervened'
    total_turns = Column(Integer, default=0)
    intervention_triggered = Column(Boolean, default=False)
    intervention_turn = Column(Integer)
    final_confidence = Column(Float)
    tactics_used = Column(JSON)
    tactics_detected = Column(JSON)

    debrief_generated = Column(Boolean, default=False)
    debrief_content = Column(Text)

    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    turns = relationship("SimulationTurn", back_populates="simulation", order_by="SimulationTurn.turn_number")

    __table_args__ = (
        Index("idx_simulations_scenario", "scenario_type"),
    )


class SimulationTurn(Base):
    """Each message in a simulation."""
    __tablename__ = "simulation_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id = Column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # 'scammer', 'user', 'system'
    content = Column(Text, nullable=False)
    analysis = Column(JSON)  # Guardian agent's real-time analysis

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    simulation = relationship("Simulation", back_populates="turns")


class AuditLog(Base):
    """Every agent action is logged."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True)
    simulation_id = Column(UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=True)

    agent_name = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    input_summary = Column(Text)
    output_summary = Column(Text)
    model_used = Column(String(50))
    latency_ms = Column(Integer)

    status = Column(String(20), default="success")  # 'success', 'fallback', 'error'
    error_message = Column(Text)
    fallback_model = Column(String(50))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_audit_case", "case_id"),
        Index("idx_audit_created", "created_at"),
    )


# ---------- Database Engine ----------

_engine = None
_session_factory = None


async def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,   # Auto-recover from dead connections
            pool_recycle=300,     # Recycle connections every 5 min (Neon timeout)
        )
    return _engine


async def get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = await get_engine()
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    factory = await get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables. Called on app startup."""
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close engine. Called on app shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
