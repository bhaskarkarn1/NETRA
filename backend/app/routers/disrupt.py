"""
NETRA Disruption Router — Automated Infrastructure Actions

Simulates outbound webhooks to financial institutions and telecom providers.
When a high-confidence scam is detected, NETRA generates disruption payloads
that demonstrate how the system would integrate with banking fraud desks
and telecom carriers to actively disrupt the kill chain.

All actions are clearly labeled as "simulated" — no fake API calls are made.
The payload formats match real-world banking API patterns (UPI NPCI, RBI CEFT).
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, DisruptionAction, Case

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- Schemas ----------

class BankFreezeRequest(BaseModel):
    case_id: str | None = None
    target_entity: str  # UPI ID or bank account
    entity_type: str  # 'upi_id' or 'bank_account'
    confidence: float


class TelecomBlockRequest(BaseModel):
    case_id: str | None = None
    target_entity: str  # Phone number
    confidence: float


class DisruptionResponse(BaseModel):
    id: str
    action_type: str
    target_entity: str
    target_institution: str
    status: str
    confidence: float
    payload: dict
    reasoning: str
    created_at: str


class DisruptionActionSummary(BaseModel):
    id: str
    action_type: str
    target_entity: str
    target_institution: str
    status: str
    confidence: float
    reasoning: str
    created_at: str


# ---------- Institution Mapping ----------

# Map UPI suffixes to banks (real NPCI mappings)
UPI_BANK_MAP = {
    "ybl": "Yes Bank (PhonePe)",
    "paytm": "Paytm Payments Bank",
    "okaxis": "Axis Bank (Google Pay)",
    "okicici": "ICICI Bank (Google Pay)",
    "oksbi": "SBI (Google Pay)",
    "okhdfcbank": "HDFC Bank (Google Pay)",
    "sbi": "State Bank of India",
    "icici": "ICICI Bank",
    "hdfc": "HDFC Bank",
    "axisbank": "Axis Bank",
    "kotak": "Kotak Mahindra Bank",
    "upi": "UPI (Generic)",
    "apl": "Amazon Pay",
    "ibl": "IDBI Bank",
    "pnb": "Punjab National Bank",
    "phonepe": "PhonePe",
    "gpay": "Google Pay",
}

# Map phone prefixes to telecom carriers (Indian)
TELECOM_MAP = {
    "6": "Jio / Airtel / Vi",
    "7": "BSNL / Jio / Airtel",
    "8": "Airtel / Vi / BSNL",
    "9": "Airtel / Vi / Jio",
}


def _resolve_bank(entity: str, entity_type: str) -> str:
    """Resolve UPI ID or bank account to institution name."""
    if entity_type == "upi_id" and "@" in entity:
        suffix = entity.split("@")[-1].lower()
        return UPI_BANK_MAP.get(suffix, f"Bank ({suffix})")
    return "Reserve Bank of India (CEFT)"


def _resolve_telecom(phone: str) -> str:
    """Resolve phone number to telecom carrier."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) >= 10:
        first = digits[-10]  # First digit of 10-digit number
        return TELECOM_MAP.get(first, "Telecom Provider")
    return "Telecom Provider"


# ---------- Endpoints ----------

@router.post("/bank-freeze", response_model=DisruptionResponse)
async def trigger_bank_freeze(
    req: BankFreezeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simulate a bank fraud desk webhook for UPI/account freeze.

    Generates a structured payload matching banking API patterns.
    Status is always 'simulated' — no live integrations.
    """
    if req.confidence < 0.70:
        raise HTTPException(
            status_code=400,
            detail="Confidence below 0.70 threshold — bank freeze requires high confidence to prevent false positives"
        )

    institution = _resolve_bank(req.target_entity, req.entity_type)

    payload = {
        "webhook_type": "fraud_alert",
        "priority": "P1_CRITICAL" if req.confidence >= 0.90 else "P2_HIGH",
        "source_system": "NETRA_CYBER_INTELLIGENCE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "alert": {
            "type": "ACCOUNT_FREEZE_REQUEST",
            "entity_type": req.entity_type.upper(),
            "entity_value": req.target_entity,
            "institution": institution,
            "fraud_confidence": round(req.confidence, 4),
            "fraud_category": "DIGITAL_ARREST_SCAM",
            "regulatory_basis": "RBI Circular on Fraud Risk Management (2024)",
            "action_requested": "IMMEDIATE_DEBIT_FREEZE",
            "case_reference": req.case_id,
        },
        "compliance": {
            "rbi_direction": "Master Direction on Fraud – Classification and Reporting",
            "reporting_timeline": "Within 7 days to RBI/CRILC",
            "sar_required": req.confidence >= 0.85,
        },
        "simulation_notice": "This is a simulated webhook. No actual freeze was initiated.",
    }

    reasoning = (
        f"Scam detected with {req.confidence:.0%} confidence. "
        f"{req.entity_type.replace('_', ' ').title()} '{req.target_entity}' identified as fraudulent. "
        f"Immediate debit freeze requested at {institution} to prevent financial loss."
    )

    action = DisruptionAction(
        case_id=uuid.UUID(req.case_id) if req.case_id else None,
        action_type="bank_freeze",
        target_entity=req.target_entity,
        target_institution=institution,
        status="simulated",
        confidence=req.confidence,
        payload=payload,
        reasoning=reasoning,
    )
    db.add(action)
    await db.flush()

    return DisruptionResponse(
        id=str(action.id),
        action_type="bank_freeze",
        target_entity=req.target_entity,
        target_institution=institution,
        status="simulated",
        confidence=req.confidence,
        payload=payload,
        reasoning=reasoning,
        created_at=action.created_at.isoformat() if action.created_at else datetime.now(timezone.utc).isoformat(),
    )


@router.post("/telecom-block", response_model=DisruptionResponse)
async def trigger_telecom_block(
    req: TelecomBlockRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Simulate a telecom carrier webhook for spoofed number blocking.

    Generates a structured payload for carrier-level call interception.
    """
    if req.confidence < 0.70:
        raise HTTPException(
            status_code=400,
            detail="Confidence below 0.70 threshold — telecom block requires high confidence"
        )

    carrier = _resolve_telecom(req.target_entity)

    payload = {
        "webhook_type": "fraud_telecom_alert",
        "priority": "P1_CRITICAL" if req.confidence >= 0.90 else "P2_HIGH",
        "source_system": "NETRA_CYBER_INTELLIGENCE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "alert": {
            "type": "NUMBER_BLOCK_REQUEST",
            "phone_number": req.target_entity,
            "carrier": carrier,
            "fraud_confidence": round(req.confidence, 4),
            "fraud_category": "SPOOFED_IDENTITY_CALL",
            "regulatory_basis": "DoT Direction on Prevention of Spoofed Calls (2024)",
            "action_requested": "SUSPEND_OUTGOING_CALLS",
            "case_reference": req.case_id,
        },
        "trai_compliance": {
            "direction": "TRAI Regulation on Unsolicited Commercial Communications",
            "dnd_check": True,
            "cli_spoofing_detected": True,
        },
        "simulation_notice": "This is a simulated webhook. No actual block was initiated.",
    }

    reasoning = (
        f"Scam detected with {req.confidence:.0%} confidence. "
        f"Phone number '{req.target_entity}' used for spoofed identity call. "
        f"Number suspension requested at {carrier} to prevent further victim contact."
    )

    action = DisruptionAction(
        case_id=uuid.UUID(req.case_id) if req.case_id else None,
        action_type="telecom_block",
        target_entity=req.target_entity,
        target_institution=carrier,
        status="simulated",
        confidence=req.confidence,
        payload=payload,
        reasoning=reasoning,
    )
    db.add(action)
    await db.flush()

    return DisruptionResponse(
        id=str(action.id),
        action_type="telecom_block",
        target_entity=req.target_entity,
        target_institution=carrier,
        status="simulated",
        confidence=req.confidence,
        payload=payload,
        reasoning=reasoning,
        created_at=action.created_at.isoformat() if action.created_at else datetime.now(timezone.utc).isoformat(),
    )


@router.get("/actions", response_model=list[DisruptionActionSummary])
async def get_disruption_actions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List recent disruption actions."""
    stmt = (
        select(DisruptionAction)
        .order_by(DisruptionAction.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    actions = result.scalars().all()

    return [
        DisruptionActionSummary(
            id=str(a.id),
            action_type=a.action_type,
            target_entity=a.target_entity,
            target_institution=a.target_institution or "",
            status=a.status or "simulated",
            confidence=a.confidence or 0,
            reasoning=a.reasoning or "",
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in actions
    ]
