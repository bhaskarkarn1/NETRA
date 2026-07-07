"""
NETRA Simulate Router — Scam Simulation Lab Endpoints

The Simulation Lab uses two AI agents in opposition:
1. Scam Agent (adversarial): Generates realistic scam messages, adapts to user responses
2. Guardian Agent (protective): Analyzes each turn for psychological tactics in real-time

Data flow:
- Start: Create simulation record → Scam Agent generates first message → Store in simulation_turns
- Respond: User sends response → Detection Agent analyzes → Scam Agent generates next turn → Store both
- Debrief: Load all turns + analyses → Generate comprehensive debrief via LLM
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    get_db, Simulation, SimulationTurn, ScamPattern, AuditLog
)
from app.services.llm import get_llm_service
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- Schemas ----------

class StartRequest(BaseModel):
    scenario_type: str = Field(..., description="Scam scenario type (e.g., 'Digital Arrest')")
    user_session_id: str | None = None


class RespondRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's response to the scammer")


class TurnAnalysis(BaseModel):
    tactic_detected: str | None = None
    tactic_description: str | None = None
    confidence: float = 0.0
    risk_level: str = "low"
    explanation: str = ""


class TurnResponse(BaseModel):
    turn_number: int
    scammer_message: str
    analysis: TurnAnalysis
    simulation_status: str  # 'active', 'intervened', 'completed'
    intervention_triggered: bool = False


class SimulationStartResponse(BaseModel):
    simulation_id: str
    scenario_type: str
    scenario_description: str
    first_turn: TurnResponse


class DebriefResponse(BaseModel):
    simulation_id: str
    scenario_type: str
    total_turns: int
    tactics_used: list[str]
    tactics_detected: list[str]
    intervention_turn: int | None = None
    debrief_content: str
    key_lessons: list[str]


class ScenarioInfo(BaseModel):
    name: str
    category: str
    description: str | None = None
    prevalence: str | None = None


# ---------- Scam Agent Prompt ----------

SCAM_AGENT_SYSTEM_PROMPT = """You are simulating a realistic scam caller for EDUCATIONAL purposes in a controlled training environment. This is a SCAM SIMULATION LAB designed to build psychological resistance in citizens.

SCENARIO: {scenario_name}
SCENARIO DESCRIPTION: {scenario_description}
TYPICAL FLOW: {typical_flow}
TACTICS TO USE: {tactics}

RULES:
1. Stay in character as the scammer throughout the conversation
2. Use the psychological tactics listed above naturally in conversation
3. Adapt your approach based on the user's responses
4. If the user resists, try a different tactic (escalate urgency, switch to empathy, use authority)
5. Keep messages realistic — this is how REAL scammers talk in India
6. Use a mix of English and Hindi phrases as real scammers do
7. NEVER break character or reveal this is a simulation
8. Keep each message under 150 words
9. Build the scam gradually — don't ask for money in the first message

Respond with ONLY the scammer's next message. No metadata, no labels, no JSON."""


GUARDIAN_SYSTEM_PROMPT = """You are NETRA's Guardian Agent. Your job is to analyze a scammer's message and identify the psychological manipulation tactics being used.

Respond in valid JSON:
{
    "tactic_detected": "the primary tactic being used (e.g., 'Authority Impersonation', 'Fear Escalation', 'Urgency Pressure', 'Trust Building', 'Isolation', 'Financial Extraction')",
    "tactic_description": "how this specific tactic is being applied in this message",
    "confidence": 0.0 to 1.0,
    "risk_level": "low" | "medium" | "high" | "critical",
    "explanation": "plain-language explanation of what the scammer is doing and WHY it works psychologically"
}

Base your analysis on the ACTUAL CONTENT of the message. Be specific."""


DEBRIEF_SYSTEM_PROMPT = """You are NETRA's debrief generator. Given a complete scam simulation conversation, create a comprehensive educational debrief.

Respond in valid JSON:
{
    "summary": "1-2 sentence summary of what happened in this simulation",
    "tactics_breakdown": [
        {
            "tactic": "tactic name",
            "turn_used": 1,
            "how_it_worked": "explanation of how this tactic manipulates the victim",
            "how_to_resist": "specific, actionable advice on resisting this tactic"
        }
    ],
    "key_lessons": ["lesson 1", "lesson 2", "lesson 3"],
    "red_flags": ["specific red flag that should have been noticed"],
    "what_to_do": "step-by-step instructions if you encounter this scam for real (include 1930 helpline)"
}"""


# ---------- Endpoints ----------

@router.get("/scenarios", response_model=list[ScenarioInfo])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
):
    """List available simulation scenarios (loaded from scam_patterns table)."""
    stmt = select(ScamPattern).order_by(ScamPattern.prevalence.desc())
    result = await db.execute(stmt)
    patterns = result.scalars().all()

    return [
        ScenarioInfo(
            name=p.name,
            category=p.category,
            description=p.description,
            prevalence=p.prevalence,
        )
        for p in patterns
    ]


@router.post("/start", response_model=SimulationStartResponse)
async def start_simulation(
    request: StartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start a new scam simulation session."""
    settings = get_settings()
    llm = get_llm_service()

    # 1. Load scenario from database
    stmt = select(ScamPattern).where(ScamPattern.name == request.scenario_type)
    result = await db.execute(stmt)
    pattern = result.scalar_one_or_none()

    if not pattern:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{request.scenario_type}' not found. Use GET /api/simulate/scenarios for available scenarios."
        )

    # 2. Create simulation record
    simulation = Simulation(
        scenario_type=request.scenario_type,
        user_session_id=request.user_session_id,
        status="active",
        total_turns=0,
    )
    db.add(simulation)
    await db.flush()

    # 3. Generate first scammer message
    scam_prompt = SCAM_AGENT_SYSTEM_PROMPT.format(
        scenario_name=pattern.name,
        scenario_description=pattern.description or "",
        typical_flow=str(pattern.typical_flow or []),
        tactics=", ".join(pattern.tactics or []),
    )

    scam_response = await llm.generate(
        prompt="Begin the scam. Send the FIRST message to the victim. Set the scene and establish your fake identity.",
        system_instruction=scam_prompt,
        temperature=0.8,
        tier="primary",
    )

    # 4. Analyze the first message with guardian agent
    guardian_response = await llm.generate(
        prompt=f"Analyze this scammer's message:\n\n\"{scam_response.content}\"",
        system_instruction=GUARDIAN_SYSTEM_PROMPT,
        response_format="json",
        temperature=0.3,
        tier="fast",
    )

    analysis_data = guardian_response.parse_json() or {
        "tactic_detected": "Initial Contact",
        "tactic_description": "Establishing first contact with the target",
        "confidence": 0.3,
        "risk_level": "low",
        "explanation": "The scammer is initiating contact."
    }

    # 5. Store the first turn
    turn = SimulationTurn(
        simulation_id=simulation.id,
        turn_number=1,
        role="scammer",
        content=scam_response.content,
        analysis=analysis_data,
    )
    db.add(turn)

    simulation.total_turns = 1
    simulation.tactics_used = [analysis_data.get("tactic_detected", "")]
    simulation.tactics_detected = [analysis_data.get("tactic_detected", "")]

    # 6. Audit log
    audit = AuditLog(
        simulation_id=simulation.id,
        agent_name="simulation",
        action="start_simulation",
        input_summary=f"Scenario: {request.scenario_type}",
        output_summary=scam_response.content[:200],
        model_used=scam_response.model_used,
        latency_ms=scam_response.latency_ms,
        status="success",
    )
    db.add(audit)

    return SimulationStartResponse(
        simulation_id=str(simulation.id),
        scenario_type=request.scenario_type,
        scenario_description=pattern.description or "",
        first_turn=TurnResponse(
            turn_number=1,
            scammer_message=scam_response.content,
            analysis=TurnAnalysis(**analysis_data),
            simulation_status="active",
        ),
    )


@router.post("/{simulation_id}/respond", response_model=TurnResponse)
async def respond_to_simulation(
    simulation_id: str,
    request: RespondRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send user's response and get scammer's next message + analysis."""
    settings = get_settings()
    llm = get_llm_service()

    try:
        sim_uid = uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid simulation ID")

    # 1. Load simulation
    stmt = select(Simulation).where(Simulation.id == sim_uid)
    result = await db.execute(stmt)
    simulation = result.scalar_one_or_none()

    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if simulation.status != "active":
        raise HTTPException(status_code=400, detail=f"Simulation is {simulation.status}, not active")

    # 2. Load conversation history
    stmt = (
        select(SimulationTurn)
        .where(SimulationTurn.simulation_id == sim_uid)
        .order_by(SimulationTurn.turn_number)
    )
    result = await db.execute(stmt)
    history = result.scalars().all()

    # 3. Store user's message
    user_turn_number = len(history) + 1
    user_turn = SimulationTurn(
        simulation_id=sim_uid,
        turn_number=user_turn_number,
        role="user",
        content=request.message,
    )
    db.add(user_turn)

    # 4. Load scenario for context
    stmt = select(ScamPattern).where(ScamPattern.name == simulation.scenario_type)
    result = await db.execute(stmt)
    pattern = result.scalar_one_or_none()

    # 5. Build conversation context for scam agent
    conv_history = "\n".join([
        f"{'Scammer' if t.role == 'scammer' else 'Victim'}: {t.content}"
        for t in history
    ])
    conv_history += f"\nVictim: {request.message}"

    scam_prompt = SCAM_AGENT_SYSTEM_PROMPT.format(
        scenario_name=pattern.name if pattern else simulation.scenario_type,
        scenario_description=pattern.description if pattern else "",
        typical_flow=str(pattern.typical_flow or []) if pattern else "[]",
        tactics=", ".join(pattern.tactics or []) if pattern else "",
    )

    # 6. Generate scammer's next response
    scam_response = await llm.generate(
        prompt=f"Conversation so far:\n{conv_history}\n\nContinue as the scammer. Respond to the victim's last message. Adapt your tactics based on their response.",
        system_instruction=scam_prompt,
        temperature=0.8,
        tier="primary",
    )

    # 7. Guardian agent analyzes
    guardian_response = await llm.generate(
        prompt=f"Conversation context:\n{conv_history}\n\nAnalyze the scammer's LATEST message:\n\n\"{scam_response.content}\"",
        system_instruction=GUARDIAN_SYSTEM_PROMPT,
        response_format="json",
        temperature=0.3,
        tier="fast",
    )

    analysis_data = guardian_response.parse_json() or {
        "tactic_detected": None,
        "confidence": 0.0,
        "risk_level": "low",
        "explanation": "Analysis unavailable",
    }

    # 8. Check for intervention
    confidence = analysis_data.get("confidence", 0.0)
    intervention_triggered = confidence >= settings.INTERVENTION_CONFIDENCE_THRESHOLD
    max_turns_reached = user_turn_number >= settings.SIMULATION_MAX_TURNS * 2

    status = "active"
    if intervention_triggered:
        status = "intervened"
    elif max_turns_reached:
        status = "completed"

    # 9. Store scammer's turn
    scammer_turn_number = user_turn_number + 1
    scammer_turn = SimulationTurn(
        simulation_id=sim_uid,
        turn_number=scammer_turn_number,
        role="scammer",
        content=scam_response.content,
        analysis=analysis_data,
    )
    db.add(scammer_turn)

    # 10. Update simulation record
    simulation.total_turns = scammer_turn_number
    simulation.intervention_triggered = intervention_triggered
    simulation.status = status
    if intervention_triggered:
        simulation.intervention_turn = scammer_turn_number
    simulation.final_confidence = confidence

    # Track tactics
    current_tactics_used = simulation.tactics_used or []
    current_tactics_detected = simulation.tactics_detected or []
    new_tactic = analysis_data.get("tactic_detected")
    if new_tactic and new_tactic not in current_tactics_used:
        current_tactics_used.append(new_tactic)
    if new_tactic and new_tactic not in current_tactics_detected:
        current_tactics_detected.append(new_tactic)
    simulation.tactics_used = current_tactics_used
    simulation.tactics_detected = current_tactics_detected

    if status != "active":
        simulation.completed_at = datetime.now(timezone.utc)

    # 11. Audit log
    audit = AuditLog(
        simulation_id=sim_uid,
        agent_name="simulation",
        action="respond_turn",
        input_summary=request.message[:200],
        output_summary=scam_response.content[:200],
        model_used=scam_response.model_used,
        latency_ms=scam_response.latency_ms + guardian_response.latency_ms,
        status="success",
    )
    db.add(audit)

    return TurnResponse(
        turn_number=scammer_turn_number,
        scammer_message=scam_response.content,
        analysis=TurnAnalysis(**analysis_data),
        simulation_status=status,
        intervention_triggered=intervention_triggered,
    )


@router.get("/{simulation_id}/debrief", response_model=DebriefResponse)
async def get_debrief(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate comprehensive educational debrief for a completed simulation."""
    llm = get_llm_service()

    try:
        sim_uid = uuid.UUID(simulation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid simulation ID")

    # 1. Load simulation + turns
    stmt = select(Simulation).where(Simulation.id == sim_uid)
    result = await db.execute(stmt)
    simulation = result.scalar_one_or_none()
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    stmt = (
        select(SimulationTurn)
        .where(SimulationTurn.simulation_id == sim_uid)
        .order_by(SimulationTurn.turn_number)
    )
    result = await db.execute(stmt)
    turns = result.scalars().all()

    # 2. Build conversation + analysis summary
    conv_summary = []
    for t in turns:
        role_label = "Scammer" if t.role == "scammer" else "User" if t.role == "user" else "System"
        entry = f"Turn {t.turn_number} ({role_label}): {t.content}"
        if t.analysis:
            entry += f"\n  [Analysis: {t.analysis.get('tactic_detected', 'N/A')} - {t.analysis.get('explanation', 'N/A')}]"
        conv_summary.append(entry)

    conversation_text = "\n\n".join(conv_summary)

    # 3. Generate debrief
    debrief_response = await llm.generate(
        prompt=f"Scenario: {simulation.scenario_type}\n\nFull conversation with analysis:\n{conversation_text}\n\nGenerate a comprehensive educational debrief.",
        system_instruction=DEBRIEF_SYSTEM_PROMPT,
        response_format="json",
        temperature=0.5,
        tier="primary",
    )

    debrief_data = debrief_response.parse_json() or {
        "summary": "Debrief generation failed.",
        "tactics_breakdown": [],
        "key_lessons": ["Always verify caller identity through official channels", "Never share OTP or transfer money under pressure", "Call 1930 helpline if suspicious"],
        "red_flags": [],
        "what_to_do": "If you encounter a similar call, disconnect immediately and call the 1930 cybercrime helpline.",
    }

    # 4. Update simulation with debrief
    import json
    simulation.debrief_generated = True
    simulation.debrief_content = json.dumps(debrief_data)

    return DebriefResponse(
        simulation_id=str(simulation.id),
        scenario_type=simulation.scenario_type,
        total_turns=simulation.total_turns or 0,
        tactics_used=simulation.tactics_used or [],
        tactics_detected=simulation.tactics_detected or [],
        intervention_turn=simulation.intervention_turn,
        debrief_content=debrief_data.get("summary", ""),
        key_lessons=debrief_data.get("key_lessons", []),
    )
