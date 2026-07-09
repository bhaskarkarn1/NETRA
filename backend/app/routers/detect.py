"""
NETRA Detect Router — Scam Analysis + Kill Chain + Forensic Dossier + Intelligence

Data flow:
1. User submits suspicious text via POST /api/detect
2. Detection Agent classifies via LLM (Gemini → Groq → Rules)
3. Kill Chain™ decomposition maps attack stages
4. Compliance engine maps legal sections from database
5. SHA-256 evidence hash for chain-of-custody
6. Result is stored in cases table
7. Every step is logged in audit_logs

Extended endpoints:
- GET /api/detect/{case_id}/dossier → Forensic PDF report
- GET /api/detect/{case_id}/intelligence → Cross-case pattern linking
"""

import hashlib
import io
import json
import math
import time
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, Case, LegalMapping, ScamPattern, AuditLog
from app.agents.detection import DetectionAgent
from app.services.llm import get_llm_service
from app.services.entity_extraction import EntityExtractor
from app.services.graph_population import GraphPopulationService

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- Request/Response Schemas ----------

class DetectRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=10000, description="Suspicious message or call transcript")
    input_type: str = Field(default="text", pattern="^(text|transcript|url)$")


class TacticDetected(BaseModel):
    name: str
    description: str
    confidence: float


class LegalSectionResponse(BaseModel):
    code: str
    law: str
    section: str
    title: str
    punishment: str | None = None


class KillChainStage(BaseModel):
    stage: str
    stage_name: str
    detected: bool
    evidence: str | None = None
    severity: str = "none"


class EntityInfo(BaseModel):
    entity_type: str
    value: str
    confidence: float
    source: str


class GraphIntel(BaseModel):
    nodes_created: int = 0
    edges_created: int = 0
    nodes_linked: int = 0
    entities_extracted: list[EntityInfo] = []


class DetectResponse(BaseModel):
    id: str
    scam_type: str | None
    confidence: float
    risk_level: str
    ai_reasoning: str
    tactics_detected: list[TacticDetected]
    legal_sections: list[LegalSectionResponse]
    kill_chain: list[KillChainStage]
    victim_vulnerability_score: float
    victim_vulnerability_factors: list[str]
    evidence_hash: str
    language: str
    model_used: str
    processing_time_ms: int
    graph_intel: GraphIntel | None = None


class CaseSummary(BaseModel):
    id: str
    scam_type: str | None
    confidence: float
    risk_level: str
    input_preview: str
    created_at: str


class RelatedCase(BaseModel):
    id: str
    scam_type: str | None
    confidence: float
    similarity_score: float
    similarity_reason: str
    input_preview: str
    created_at: str


class IntelligenceResponse(BaseModel):
    case_id: str
    related_cases: list[RelatedCase]
    entity_overlaps: list[dict]
    syndicate_indicators: list[str]
    total_linked_cases: int


class ImageAnalyzeRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded image data")
    mime_type: str = Field(default="image/jpeg", description="MIME type of the image")
    input_type: str = Field(default="screenshot", description="Type: 'screenshot', 'document'")


class ImageAnalyzeResponse(BaseModel):
    extracted_text: str
    detection_result: DetectResponse | None = None
    ocr_confidence: float = 0.0
    image_description: str = ""


class CounterfeitRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded banknote image")
    mime_type: str = Field(default="image/jpeg")
    denomination: str | None = Field(default=None, description="Expected denomination (₹100, ₹200, ₹500, ₹2000)")


class SecurityFeature(BaseModel):
    feature_name: str
    status: str  # 'pass', 'fail', 'uncertain', 'not_visible'
    confidence: float
    description: str


class CounterfeitResponse(BaseModel):
    verdict: str  # 'genuine', 'suspect', 'counterfeit', 'inconclusive'
    confidence: float
    denomination_detected: str | None
    security_features: list[SecurityFeature]
    overall_assessment: str
    rbi_guidelines: str
    evidence_hash: str
    model_used: str
    processing_time_ms: int


# ---------- Helpers ----------

STAGE_NAMES = {
    "S1_CONTACT": "Contact",
    "S2_PRETEXT": "Pretext",
    "S3_PRESSURE": "Pressure",
    "S4_ISOLATION": "Isolation",
    "S5_EXTRACTION": "Extraction",
    "S6_PERSISTENCE": "Persistence",
}

DEFAULT_KILL_CHAIN = [
    KillChainStage(stage=code, stage_name=name, detected=False, severity="none")
    for code, name in STAGE_NAMES.items()
]


def _parse_kill_chain(raw: list[dict] | None) -> list[KillChainStage]:
    """Parse kill chain from LLM output, ensuring exactly 6 stages."""
    if not raw:
        return DEFAULT_KILL_CHAIN

    stages_map = {}
    for entry in raw:
        stage_code = entry.get("stage", "")
        if stage_code in STAGE_NAMES:
            stages_map[stage_code] = KillChainStage(
                stage=stage_code,
                stage_name=STAGE_NAMES[stage_code],
                detected=entry.get("detected", False),
                evidence=entry.get("evidence"),
                severity=entry.get("severity", "none"),
            )

    # Ensure all 6 stages are present
    result = []
    for code, name in STAGE_NAMES.items():
        if code in stages_map:
            result.append(stages_map[code])
        else:
            result.append(KillChainStage(stage=code, stage_name=name, detected=False, severity="none"))

    return result


def _compute_evidence_hash(text: str) -> str:
    """SHA-256 hash of the input text for chain-of-custody."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------- Endpoints ----------

@router.post("", response_model=DetectResponse)
async def analyze_text(
    request: DetectRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze suspicious text for scam patterns.

    Flow: Input → Detection Agent (LLM) → Kill Chain → Compliance Engine (DB) → Store → Return
    """
    start_time = time.monotonic()

    # 0. Compute evidence hash
    evidence_hash = _compute_evidence_hash(request.text)

    # 1. Run detection agent (now returns kill_chain + vulnerability)
    agent = DetectionAgent(db)
    detection_result = await agent.analyze(request.text, request.input_type)

    # 2. Look up legal sections from database
    legal_sections = []
    if detection_result.get("legal_codes"):
        stmt = select(LegalMapping).where(
            LegalMapping.code.in_(detection_result["legal_codes"])
        )
        result = await db.execute(stmt)
        legal_rows = result.scalars().all()
        legal_sections = [
            LegalSectionResponse(
                code=row.code,
                law=row.law,
                section=row.section,
                title=row.title,
                punishment=row.punishment,
            )
            for row in legal_rows
        ]

    # 3. Parse kill chain stages
    kill_chain = _parse_kill_chain(detection_result.get("kill_chain"))

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    # 4. Generate text embedding for cross-case intelligence
    embedding = None
    try:
        llm = get_llm_service()
        embedding = await llm.embed(request.text)
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")

    # 5. Store case in database
    case = Case(
        input_text=request.text,
        input_type=request.input_type,
        language=detection_result.get("language", "en"),
        scam_type=detection_result.get("scam_type"),
        confidence=detection_result.get("confidence", 0.0),
        risk_level=detection_result.get("risk_level", "unknown"),
        ai_reasoning=detection_result.get("reasoning", ""),
        model_used=detection_result.get("model_used", ""),
        legal_sections=[s.model_dump() for s in legal_sections],
        tactics_detected=detection_result.get("tactics", []),
        kill_chain=[kc.model_dump() for kc in kill_chain],
        victim_vulnerability_score=detection_result.get("victim_vulnerability_score", 0.0),
        victim_vulnerability_factors=detection_result.get("victim_vulnerability_factors", []),
        embedding=embedding,
        evidence_hash=evidence_hash,
        processing_time_ms=elapsed_ms,
    )
    db.add(case)
    await db.flush()

    # 6. Auto-extract entities and populate fraud network graph
    graph_intel = GraphIntel()
    try:
        llm = get_llm_service()
        extractor = EntityExtractor(llm_service=llm)
        extraction_result = await extractor.extract(request.text, use_llm=True)

        if extraction_result.entities:
            graph_service = GraphPopulationService(db)
            pop_result = await graph_service.populate_from_case(
                case_id=case.id,
                scam_type=detection_result.get("scam_type"),
                risk_level=detection_result.get("risk_level"),
                confidence=detection_result.get("confidence", 0.0),
                extraction_result=extraction_result,
            )
            graph_intel = GraphIntel(
                nodes_created=pop_result["nodes_created"],
                edges_created=pop_result["edges_created"],
                nodes_linked=pop_result["nodes_linked"],
                entities_extracted=[
                    EntityInfo(
                        entity_type=e.entity_type,
                        value=e.value,
                        confidence=e.confidence,
                        source=e.source,
                    )
                    for e in extraction_result.entities
                ],
            )
            logger.info(f"Graph auto-populated: {pop_result}")
    except Exception as e:
        logger.warning(f"Entity extraction/graph population failed (non-critical): {e}")

    # 7. Log to audit trail
    audit = AuditLog(
        case_id=case.id,
        agent_name="detection",
        action="classify_scam",
        input_summary=request.text[:200],
        output_summary=f"{detection_result.get('scam_type')} ({detection_result.get('confidence', 0):.2f})",
        model_used=detection_result.get("model_used"),
        latency_ms=elapsed_ms,
        status="fallback" if detection_result.get("was_fallback") else "success",
        fallback_model=detection_result.get("fallback_model"),
    )
    db.add(audit)

    return DetectResponse(
        id=str(case.id),
        scam_type=detection_result.get("scam_type"),
        confidence=detection_result.get("confidence", 0.0),
        risk_level=detection_result.get("risk_level", "unknown"),
        ai_reasoning=detection_result.get("reasoning", ""),
        tactics_detected=[
            TacticDetected(**t) for t in detection_result.get("tactics", [])
        ],
        legal_sections=legal_sections,
        kill_chain=kill_chain,
        victim_vulnerability_score=detection_result.get("victim_vulnerability_score", 0.0),
        victim_vulnerability_factors=detection_result.get("victim_vulnerability_factors", []),
        evidence_hash=evidence_hash,
        language=detection_result.get("language", "en"),
        model_used=detection_result.get("model_used", ""),
        processing_time_ms=elapsed_ms,
        graph_intel=graph_intel,
    )


@router.get("/{case_id}", response_model=DetectResponse)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a past analysis by case ID."""
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid case ID format")

    stmt = select(Case).where(Case.id == uid)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return DetectResponse(
        id=str(case.id),
        scam_type=case.scam_type,
        confidence=case.confidence or 0.0,
        risk_level=case.risk_level or "unknown",
        ai_reasoning=case.ai_reasoning or "",
        tactics_detected=[
            TacticDetected(**t) for t in (case.tactics_detected or [])
        ],
        legal_sections=[
            LegalSectionResponse(**s) for s in (case.legal_sections or [])
        ],
        kill_chain=[
            KillChainStage(**kc) for kc in (case.kill_chain or [])
        ] or DEFAULT_KILL_CHAIN,
        victim_vulnerability_score=case.victim_vulnerability_score or 0.0,
        victim_vulnerability_factors=case.victim_vulnerability_factors or [],
        evidence_hash=case.evidence_hash or "",
        language=case.language or "en",
        model_used=case.model_used or "",
        processing_time_ms=case.processing_time_ms or 0,
    )


@router.get("/recent/list", response_model=list[CaseSummary])
async def list_recent_cases(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List recent scam analysis cases."""
    stmt = select(Case).order_by(Case.created_at.desc()).limit(min(limit, 50))
    result = await db.execute(stmt)
    cases = result.scalars().all()

    return [
        CaseSummary(
            id=str(c.id),
            scam_type=c.scam_type,
            confidence=c.confidence or 0.0,
            risk_level=c.risk_level or "unknown",
            input_preview=c.input_text[:100] + ("..." if len(c.input_text) > 100 else ""),
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in cases
    ]


# ---------- Evolution 2: Forensic Evidence Dossier ----------

@router.get("/{case_id}/dossier")
async def generate_dossier(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a forensic evidence dossier PDF for a case.

    The dossier includes:
    - Case summary with classification
    - Kill Chain decomposition
    - Psychological tactic analysis
    - Legal framework (IPC/IT Act/BNS sections)
    - Complaint draft for cybercrime.gov.in
    - SHA-256 evidence hash for chain-of-custody
    - Recommended next steps
    """
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid case ID format")

    stmt = select(Case).where(Case.id == uid)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Generate complaint draft via LLM
    complaint_draft = await _generate_complaint_draft(case, db)

    # Build PDF
    pdf_bytes = _build_dossier_pdf(case, complaint_draft)

    # Log dossier generation
    audit = AuditLog(
        case_id=case.id,
        agent_name="dossier_engine",
        action="generate_forensic_dossier",
        input_summary=f"Case {case_id}",
        output_summary=f"PDF generated, {len(pdf_bytes)} bytes",
        latency_ms=0,
        status="success",
    )
    db.add(audit)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="NETRA_Dossier_{case_id[:8]}.pdf"'
        },
    )


async def _generate_complaint_draft(case: Case, db: AsyncSession) -> str:
    """Use LLM to generate a formatted complaint draft for cybercrime.gov.in."""
    llm = get_llm_service()

    legal_text = ""
    if case.legal_sections:
        for ls in case.legal_sections:
            legal_text += f"- {ls.get('law', '')} Section {ls.get('section', '')}: {ls.get('title', '')}\n"

    prompt = f"""Generate a formal cybercrime complaint draft for filing on https://cybercrime.gov.in.

The complaint should be written in formal English, suitable for submission to Indian cyber police.

CASE DETAILS:
- Scam Type: {case.scam_type}
- Risk Level: {case.risk_level}
- Confidence: {case.confidence}
- AI Analysis: {case.ai_reasoning}
- Applicable Laws:
{legal_text}

ORIGINAL SCAM MESSAGE:
\"\"\"{case.input_text[:2000]}\"\"\"

FORMAT the complaint as follows:
1. Subject line
2. Date of incident
3. Description of the incident (formal language)
4. Evidence (reference the original message)
5. Applicable legal sections
6. Prayer/Request to the authorities

Write in a professional, legal tone. Do not add any JSON formatting, just plain text."""

    try:
        response = await llm.generate(
            prompt=prompt,
            system_instruction="You are a legal document drafting assistant specializing in Indian cybercrime law.",
            temperature=0.3,
            tier="primary",
        )
        return response.content
    except Exception as e:
        logger.warning(f"Complaint draft generation failed: {e}")
        return f"[Complaint draft could not be auto-generated. Please describe the incident in your own words when filing at cybercrime.gov.in. Reference: Case ID {case.id}]"


def _build_dossier_pdf(case: Case, complaint_draft: str) -> bytes:
    """Build a forensic dossier PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    except ImportError:
        # Fallback: generate plain text report if reportlab not available
        return _build_plain_text_dossier(case, complaint_draft)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        name="DossierTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=HexColor("#06b6d4"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="DossierSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor("#6b7280"),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HexColor("#1e293b"),
        spaceBefore=16,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="DossierBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name="EvidenceText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        backColor=HexColor("#f1f5f9"),
        leftIndent=10,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="LegalRef",
        parent=styles["Normal"],
        fontSize=9,
        textColor=HexColor("#dc2626"),
        leftIndent=10,
    ))

    story = []

    # === HEADER ===
    story.append(Paragraph("NETRA — FORENSIC EVIDENCE DOSSIER", styles["DossierTitle"]))
    story.append(Paragraph("नेत्र — THE EYE | AI-Powered Digital Forensic Intelligence", styles["DossierSubtitle"]))
    story.append(Paragraph(
        f"<b>Case ID:</b> {case.id}<br/>"
        f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}<br/>"
        f"<b>Classification:</b> CONFIDENTIAL — FOR LAW ENFORCEMENT USE",
        styles["DossierSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=HexColor("#06b6d4")))
    story.append(Spacer(1, 10))

    # === 1. CASE SUMMARY ===
    story.append(Paragraph("1. CASE SUMMARY", styles["SectionHeader"]))

    risk_color = {
        "critical": "#dc2626", "high": "#f97316",
        "medium": "#eab308", "low": "#22c55e"
    }.get(case.risk_level, "#6b7280")

    summary_data = [
        ["Scam Classification", case.scam_type or "Unclassified"],
        ["Confidence Score", f"{(case.confidence or 0) * 100:.1f}%"],
        ["Risk Level", (case.risk_level or "unknown").upper()],
        ["Language Detected", case.language or "en"],
        ["AI Model Used", case.model_used or "N/A"],
        ["Processing Time", f"{case.processing_time_ms or 0}ms"],
        ["Input Type", case.input_type or "text"],
    ]
    t = Table(summary_data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f1f5f9")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # AI Reasoning
    story.append(Paragraph("<b>AI Analysis:</b>", styles["DossierBody"]))
    story.append(Paragraph(case.ai_reasoning or "No reasoning available.", styles["DossierBody"]))

    # === 2. KILL CHAIN DECOMPOSITION ===
    story.append(Paragraph("2. SCAM KILL CHAIN™ — ATTACK PROGRESSION", styles["SectionHeader"]))
    story.append(Paragraph(
        "NETRA's Kill Chain maps the detected scam to a standardized 6-stage attack taxonomy, "
        "analogous to MITRE ATT&CK for social engineering.",
        styles["DossierBody"]
    ))

    kill_chain_data = [["Stage", "Name", "Detected", "Severity", "Evidence"]]
    for kc in (case.kill_chain or []):
        detected = "✓" if kc.get("detected") else "—"
        evidence = (kc.get("evidence") or "—")[:80]
        kill_chain_data.append([
            kc.get("stage", ""),
            kc.get("stage_name", ""),
            detected,
            kc.get("severity", "none"),
            evidence,
        ])

    if len(kill_chain_data) > 1:
        kc_table = Table(kill_chain_data, colWidths=[80, 60, 50, 50, 210])
        kc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#06b6d4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(kc_table)

    # === 3. PSYCHOLOGICAL TACTICS ===
    story.append(Paragraph("3. PSYCHOLOGICAL TACTICS DETECTED", styles["SectionHeader"]))

    for tactic in (case.tactics_detected or []):
        name = tactic.get("name", "Unknown")
        desc = tactic.get("description", "")
        conf = tactic.get("confidence", 0) * 100
        story.append(Paragraph(
            f"<b>{name}</b> — Confidence: {conf:.0f}%",
            styles["DossierBody"]
        ))
        story.append(Paragraph(desc, styles["EvidenceText"]))

    # === 4. VICTIM VULNERABILITY ===
    vuln_score = case.victim_vulnerability_score or 0
    story.append(Paragraph("4. VICTIM VULNERABILITY ASSESSMENT", styles["SectionHeader"]))
    story.append(Paragraph(
        f"<b>Vulnerability Score:</b> {vuln_score * 100:.0f}%",
        styles["DossierBody"]
    ))
    for factor in (case.victim_vulnerability_factors or []):
        story.append(Paragraph(f"• {factor}", styles["DossierBody"]))

    # === 5. LEGAL FRAMEWORK ===
    story.append(Paragraph("5. APPLICABLE LEGAL FRAMEWORK", styles["SectionHeader"]))

    for ls in (case.legal_sections or []):
        story.append(Paragraph(
            f"<b>{ls.get('law', '')} Section {ls.get('section', '')}</b> — {ls.get('title', '')}",
            styles["LegalRef"]
        ))
        if ls.get("punishment"):
            story.append(Paragraph(f"  Punishment: {ls['punishment']}", styles["EvidenceText"]))

    # === 6. EVIDENCE PRESERVATION ===
    story.append(Paragraph("6. EVIDENCE PRESERVATION — CHAIN OF CUSTODY", styles["SectionHeader"]))
    story.append(Paragraph(
        f"<b>SHA-256 Hash of Original Evidence:</b>",
        styles["DossierBody"]
    ))
    story.append(Paragraph(
        f"<font face='Courier'>{case.evidence_hash or 'N/A'}</font>",
        styles["EvidenceText"]
    ))
    story.append(Paragraph(
        "This hash can be used to verify that the original evidence has not been tampered with. "
        "Any modification to the original text will produce a different hash.",
        styles["DossierBody"]
    ))
    story.append(Paragraph("<b>Original Evidence (preserved):</b>", styles["DossierBody"]))
    # Escape HTML special chars
    safe_text = (case.input_text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    story.append(Paragraph(safe_text[:3000], styles["EvidenceText"]))

    # === 7. COMPLAINT DRAFT ===
    story.append(PageBreak())
    story.append(Paragraph("7. COMPLAINT DRAFT — FOR CYBERCRIME.GOV.IN", styles["SectionHeader"]))
    story.append(Paragraph(
        "The following complaint draft has been auto-generated by NETRA's legal intelligence engine. "
        "Review, edit, and submit at https://cybercrime.gov.in or call 1930.",
        styles["DossierBody"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))
    # Split complaint into paragraphs
    for para in complaint_draft.split("\n"):
        if para.strip():
            safe_para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_para, styles["DossierBody"]))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#e2e8f0")))

    # === 8. NEXT STEPS ===
    story.append(Paragraph("8. RECOMMENDED NEXT STEPS", styles["SectionHeader"]))
    steps = [
        "Call the National Cyber Crime Helpline: 1930 (available 24x7)",
        "File a formal complaint at https://cybercrime.gov.in",
        "Contact your bank immediately to freeze suspicious transactions",
        "Preserve all evidence — do NOT delete messages, call logs, or screenshots",
        "Report the phone number/UPI ID at https://sancharsaathi.gov.in",
        "Do NOT engage further with the scammer",
    ]
    for i, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{i}.</b> {step}", styles["DossierBody"]))

    # === FOOTER ===
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=2, color=HexColor("#06b6d4")))
    story.append(Paragraph(
        "<i>This dossier was generated by NETRA (नेत्र) — AI-Powered Digital Forensic Intelligence Platform. "
        "This document is intended to assist law enforcement and citizens in cybercrime reporting. "
        "It should not be treated as a substitute for professional legal advice.</i>",
        styles["DossierSubtitle"]
    ))

    doc.build(story)
    return buffer.getvalue()


def _build_plain_text_dossier(case: Case, complaint_draft: str) -> bytes:
    """Fallback: plain text report if reportlab is not installed."""
    lines = [
        "=" * 60,
        "NETRA — FORENSIC EVIDENCE DOSSIER",
        "नेत्र — THE EYE",
        "=" * 60,
        f"Case ID: {case.id}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Classification: {case.scam_type}",
        f"Confidence: {(case.confidence or 0) * 100:.1f}%",
        f"Risk Level: {(case.risk_level or 'unknown').upper()}",
        f"Evidence Hash (SHA-256): {case.evidence_hash or 'N/A'}",
        "",
        "--- AI ANALYSIS ---",
        case.ai_reasoning or "N/A",
        "",
        "--- COMPLAINT DRAFT ---",
        complaint_draft,
        "",
        "--- NEXT STEPS ---",
        "1. Call 1930 (National Cyber Crime Helpline)",
        "2. File at https://cybercrime.gov.in",
        "3. Contact your bank immediately",
        "=" * 60,
    ]
    return "\n".join(lines).encode("utf-8")


# ---------- Evolution 3: Cross-Case Intelligence Engine ----------

@router.get("/{case_id}/intelligence", response_model=IntelligenceResponse)
async def get_intelligence(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Cross-case intelligence: find related cases using embedding similarity,
    tactic fingerprints, and entity overlaps.
    """
    try:
        uid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid case ID format")

    stmt = select(Case).where(Case.id == uid)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # 1. Get all other cases for comparison
    stmt = select(Case).where(Case.id != uid).order_by(Case.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    other_cases = result.scalars().all()

    related_cases = []

    for other in other_cases:
        similarity = 0.0
        reasons = []

        # a) Embedding similarity (if both have embeddings)
        if case.embedding and other.embedding:
            embed_sim = _cosine_similarity(case.embedding, other.embedding)
            if embed_sim > 0.70:
                similarity = max(similarity, embed_sim)
                reasons.append(f"Linguistic similarity: {embed_sim * 100:.0f}%")

        # b) Same scam type
        if case.scam_type and case.scam_type == other.scam_type:
            type_sim = 0.60
            similarity = max(similarity, type_sim)
            reasons.append(f"Same scam type: {case.scam_type}")

        # c) Tactic fingerprint overlap
        if case.tactics_detected and other.tactics_detected:
            case_tactics = {t.get("name") for t in case.tactics_detected}
            other_tactics = {t.get("name") for t in other.tactics_detected}
            if case_tactics and other_tactics:
                overlap = len(case_tactics & other_tactics) / max(len(case_tactics | other_tactics), 1)
                if overlap > 0.5:
                    tactic_sim = overlap * 0.85
                    similarity = max(similarity, tactic_sim)
                    reasons.append(f"Tactic overlap: {overlap * 100:.0f}%")

        if similarity > 0.50 and reasons:
            related_cases.append(RelatedCase(
                id=str(other.id),
                scam_type=other.scam_type,
                confidence=other.confidence or 0.0,
                similarity_score=round(similarity, 3),
                similarity_reason=" | ".join(reasons),
                input_preview=other.input_text[:100] + ("..." if len(other.input_text) > 100 else ""),
                created_at=other.created_at.isoformat() if other.created_at else "",
            ))

    # Sort by similarity (descending)
    related_cases.sort(key=lambda x: x.similarity_score, reverse=True)

    # 2. Entity overlap check (phone numbers, UPI IDs in text)
    entity_overlaps = []
    # Simple regex-based entity extraction from case text
    import re
    phone_pattern = re.compile(r"\+?91[\-\s]?\d{10}|\d{10}")
    upi_pattern = re.compile(r"[\w.]+@[\w]+")

    case_phones = set(phone_pattern.findall(case.input_text or ""))
    case_upis = set(upi_pattern.findall(case.input_text or ""))

    for other in other_cases:
        other_phones = set(phone_pattern.findall(other.input_text or ""))
        other_upis = set(upi_pattern.findall(other.input_text or ""))

        common_phones = case_phones & other_phones
        common_upis = case_upis & other_upis

        if common_phones or common_upis:
            entity_overlaps.append({
                "case_id": str(other.id),
                "scam_type": other.scam_type,
                "common_phones": list(common_phones),
                "common_upis": list(common_upis),
            })

    # 3. Syndicate indicators
    syndicate_indicators = []
    if len(related_cases) >= 2:
        syndicate_indicators.append(
            f"Pattern cluster detected: {len(related_cases)} cases share similar characteristics"
        )
    if entity_overlaps:
        syndicate_indicators.append(
            f"Entity reuse detected: {len(entity_overlaps)} cases share phone numbers or UPI IDs"
        )
    if related_cases and all(rc.scam_type == case.scam_type for rc in related_cases[:3]):
        syndicate_indicators.append(
            f"Consistent modus operandi: Multiple cases classified as '{case.scam_type}'"
        )

    # Log intelligence query
    audit = AuditLog(
        case_id=case.id,
        agent_name="intelligence_engine",
        action="cross_case_analysis",
        input_summary=f"Case {case_id}",
        output_summary=f"Found {len(related_cases)} related, {len(entity_overlaps)} entity overlaps",
        latency_ms=0,
        status="success",
    )
    db.add(audit)

    return IntelligenceResponse(
        case_id=case_id,
        related_cases=related_cases[:10],
        entity_overlaps=entity_overlaps[:10],
        syndicate_indicators=syndicate_indicators,
        total_linked_cases=len(related_cases),
    )


# ---------- Evolution 4: Multi-Modal Image OCR ----------

IMAGE_OCR_PROMPT = """Extract ALL text visible in this image. This is a screenshot of a potentially fraudulent message (SMS, WhatsApp, email, social media, or notification).

RULES:
1. Extract the text EXACTLY as it appears — preserve spelling errors, unusual formatting, and mixed languages
2. Include sender information, timestamps, URLs, phone numbers, and any UI elements with text
3. If the image contains multiple messages, extract all of them in order
4. If text is partially visible or blurry, extract what you can and mark uncertain parts with [unclear]
5. Do NOT add any commentary or analysis — ONLY output the extracted text
6. If the image does not contain any text, respond with: [NO TEXT DETECTED]"""


@router.post("/image", response_model=ImageAnalyzeResponse)
async def analyze_image(
    request: ImageAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Multi-modal scam detection: Extract text from a screenshot/image,
    then run the full detection pipeline on the extracted text.
    
    Supports: WhatsApp screenshots, SMS screenshots, email screenshots,
    social media DMs, notification screenshots.
    """
    import base64

    start_time = time.time()
    llm = get_llm_service()

    # Validate base64
    try:
        decoded = base64.b64decode(request.image_base64)
        if len(decoded) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Image too large (max 10MB)")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    # Step 1: OCR via Gemini Vision
    try:
        ocr_response = await llm.vision_analyze(
            image_base64=request.image_base64,
            prompt=IMAGE_OCR_PROMPT,
            system_instruction="You are a precise OCR engine. Extract text exactly as shown.",
            mime_type=request.mime_type,
            temperature=0.1,
        )
        extracted_text = ocr_response.content.strip()
    except Exception as e:
        logger.error(f"Image OCR failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image text extraction failed: {e}")

    if not extracted_text or extracted_text == "[NO TEXT DETECTED]":
        # Get image description instead
        try:
            desc_response = await llm.vision_analyze(
                image_base64=request.image_base64,
                prompt="Describe what you see in this image in 2-3 sentences.",
                mime_type=request.mime_type,
                temperature=0.3,
            )
            return ImageAnalyzeResponse(
                extracted_text="",
                detection_result=None,
                ocr_confidence=0.0,
                image_description=desc_response.content,
            )
        except Exception:
            return ImageAnalyzeResponse(
                extracted_text="",
                detection_result=None,
                ocr_confidence=0.0,
                image_description="Could not analyze the image.",
            )

    # Step 2: Run full detection pipeline on extracted text
    detection_result = None
    try:
        # Use the internal analyze logic
        detect_request = DetectRequest(text=extracted_text, input_type="screenshot")
        detection_result = await analyze_text(detect_request, db)
    except Exception as e:
        logger.warning(f"Detection on extracted text failed: {e}")

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Log
    audit = AuditLog(
        agent_name="vision_ocr",
        action="image_text_extraction",
        input_summary=f"Image ({request.mime_type}, {len(decoded)} bytes)",
        output_summary=f"Extracted {len(extracted_text)} chars, {'analyzed' if detection_result else 'no analysis'}",
        model_used=ocr_response.model_used,
        latency_ms=elapsed_ms,
        status="success",
    )
    db.add(audit)
    await db.commit()

    return ImageAnalyzeResponse(
        extracted_text=extracted_text,
        detection_result=detection_result,
        ocr_confidence=0.9 if len(extracted_text) > 20 else 0.5,
        image_description=f"Screenshot analyzed: {len(extracted_text)} characters extracted",
    )


# ---------- Evolution 5: Counterfeit Currency Analysis ----------

COUNTERFEIT_ANALYSIS_PROMPT = """Analyze this banknote image for authenticity indicators based on Reserve Bank of India (RBI) security features.

For each security feature, provide your assessment:

MANDATORY FEATURES TO CHECK:
1. **Watermark**: Mahatma Gandhi portrait watermark and electrotype denomination
2. **Security Thread**: Color-shifting/windowed security thread with "RBI" and denomination
3. **Latent Image**: Denomination numeral visible when held at 45°
4. **Microlettering**: "RBI" and denomination in tiny text along the security thread
5. **Intaglio Printing**: Raised printing feel on key elements (portrait, denomination, RBI seal)
6. **Color-Shifting Ink**: Denomination numeral changes color when tilted (₹200, ₹500, ₹2000)
7. **See-Through Register**: Denomination numeral visible when held against light
8. **Fluorescence**: Features visible under UV light
9. **Optically Variable Ink**: Color-changing features
10. **Number Panel**: Ascending font size serial numbers

RESPOND IN VALID JSON:
{
    "denomination_detected": "₹500" or null if unclear,
    "verdict": "genuine" | "suspect" | "counterfeit" | "inconclusive",
    "confidence": 0.0-1.0,
    "features": [
        {
            "feature_name": "Watermark",
            "status": "pass" | "fail" | "uncertain" | "not_visible",
            "confidence": 0.0-1.0,
            "description": "Brief explanation"
        }
    ],
    "overall_assessment": "Detailed 2-3 sentence summary",
    "rbi_guidelines": "What RBI says to do in this case"
}

IMPORTANT: Be conservative — if you cannot clearly see a feature, mark it "not_visible" rather than "fail". A photo may not capture all security features. Only mark "counterfeit" if multiple features clearly fail."""


@router.post("/counterfeit", response_model=CounterfeitResponse)
async def analyze_counterfeit(
    request: CounterfeitRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a banknote image for counterfeit indicators using Gemini Vision.
    Checks against RBI security feature guidelines.
    """
    import base64

    start_time = time.time()
    llm = get_llm_service()

    # Validate
    try:
        decoded = base64.b64decode(request.image_base64)
        if len(decoded) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 10MB)")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    # Evidence hash
    evidence_hash = hashlib.sha256(decoded).hexdigest()

    # Analyze with Gemini Vision
    try:
        prompt = COUNTERFEIT_ANALYSIS_PROMPT
        if request.denomination:
            prompt += f"\n\nEXPECTED DENOMINATION: {request.denomination}"

        response = await llm.vision_analyze(
            image_base64=request.image_base64,
            prompt=prompt,
            system_instruction="You are an expert forensic document examiner specializing in Indian currency authentication per RBI Master Direction 2025.",
            mime_type=request.mime_type,
            temperature=0.2,
        )

        # Parse JSON response
        analysis = response.parse_json()
        if not analysis:
            raise ValueError("Could not parse analysis response as JSON")

    except Exception as e:
        logger.error(f"Counterfeit analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Currency analysis failed: {e}")

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Build response
    features = []
    for f in analysis.get("features", []):
        features.append(SecurityFeature(
            feature_name=f.get("feature_name", "Unknown"),
            status=f.get("status", "uncertain"),
            confidence=f.get("confidence", 0.5),
            description=f.get("description", ""),
        ))

    # RBI guidelines for counterfeit notes
    rbi_text = analysis.get("rbi_guidelines", "")
    if not rbi_text:
        verdict = analysis.get("verdict", "inconclusive")
        if verdict in ("counterfeit", "suspect"):
            rbi_text = (
                "As per RBI Master Direction 2025: (1) Do NOT return the note to the presenter. "
                "(2) Issue a receipt. (3) File Counterfeit Currency Report (CCR) via FICTC portal. "
                "(4) Forward the note to the nearest police station or RBI Issue Office. "
                "Helpline: 14440 | RBI FICN Portal: https://paisaboltahai.rbi.org.in"
            )
        else:
            rbi_text = (
                "The note appears genuine based on visible features. For definitive verification, "
                "use a UV lamp and magnifying glass, or visit your nearest bank branch. "
                "Learn more: https://paisaboltahai.rbi.org.in"
            )

    # Audit
    audit = AuditLog(
        agent_name="counterfeit_analyzer",
        action="currency_authentication",
        input_summary=f"Banknote image ({len(decoded)} bytes), denomination: {request.denomination or 'auto'}",
        output_summary=f"Verdict: {analysis.get('verdict', 'inconclusive')}, {len(features)} features checked",
        model_used=response.model_used,
        latency_ms=elapsed_ms,
        status="success",
    )
    db.add(audit)
    await db.commit()

    return CounterfeitResponse(
        verdict=analysis.get("verdict", "inconclusive"),
        confidence=analysis.get("confidence", 0.5),
        denomination_detected=analysis.get("denomination_detected"),
        security_features=features,
        overall_assessment=analysis.get("overall_assessment", "Analysis complete."),
        rbi_guidelines=rbi_text,
        evidence_hash=evidence_hash,
        model_used=response.model_used,
        processing_time_ms=elapsed_ms,
    )


# ---------- Evolution 6: MHA/NCRB Alert Generation ----------

class AlertResponse(BaseModel):
    case_id: str
    alert_type: str  # "I4C_ALERT", "NCRB_COMPLAINT", "FIR_DRAFT"
    generated_text: str
    sections: list[dict]
    recommended_actions: list[str]
    severity: str
    generated_at: str


@router.get("/{case_id}/alert", response_model=AlertResponse)
async def generate_alert(
    case_id: str,
    alert_type: str = "I4C_ALERT",
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a formal MHA/NCRB/I4C-format alert document for a case.
    Used for filing with Indian Cyber Crime Coordination Centre.
    """
    # Fetch case
    stmt = select(Case).where(Case.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Parse stored analysis
    analysis = json.loads(case.analysis_json) if case.analysis_json else {}

    # Build alert sections
    now = datetime.now(timezone.utc)
    sections = []

    # Section 1: Incident Summary
    scam_type = case.scam_type or "Unknown"
    confidence = case.confidence or 0.0
    risk_level = case.risk_level or "unknown"

    sections.append({
        "title": "1. INCIDENT SUMMARY",
        "content": (
            f"Incident Type: Cyber Fraud - {scam_type}\n"
            f"Risk Classification: {risk_level.upper()}\n"
            f"AI Confidence Score: {confidence * 100:.1f}%\n"
            f"Detection Timestamp: {case.created_at.isoformat() if case.created_at else 'N/A'}\n"
            f"Evidence Hash (SHA-256): {case.evidence_hash or 'N/A'}\n"
            f"NETRA Case Reference: {case_id}"
        ),
    })

    # Section 2: Verbatim Content
    sections.append({
        "title": "2. VERBATIM FRAUDULENT CONTENT",
        "content": case.input_text[:2000] if case.input_text else "N/A",
    })

    # Section 3: Kill Chain Analysis
    kill_chain = analysis.get("kill_chain", [])
    if kill_chain:
        kc_text = ""
        for stage in kill_chain:
            name = stage.get("stage_name", "Unknown")
            evidence = stage.get("evidence", "N/A")
            kc_text += f"• {name}: {evidence}\n"
        sections.append({
            "title": "3. KILL CHAIN DECOMPOSITION (NETRA™ Framework)",
            "content": kc_text.strip(),
        })

    # Section 4: Entities Extracted
    from app.database import GraphNode, GraphEdge
    entity_stmt = (
        select(GraphNode)
        .join(GraphEdge, GraphEdge.source_id == GraphNode.id)
        .join(GraphNode.__class__, GraphEdge.target_id == GraphNode.id)  # noqa
        .where(GraphNode.label == case_id, GraphNode.node_type == "case")
    )
    # Simpler: find all edges for this case
    case_node_stmt = select(GraphNode).where(
        GraphNode.label == case_id, GraphNode.node_type == "case"
    )
    case_node_result = await db.execute(case_node_stmt)
    case_node = case_node_result.scalar_one_or_none()

    entities_text = ""
    if case_node:
        edge_stmt = select(GraphEdge).where(GraphEdge.source_id == case_node.id)
        edge_result = await db.execute(edge_stmt)
        edges = edge_result.scalars().all()

        target_ids = [e.target_id for e in edges]
        if target_ids:
            ent_stmt = select(GraphNode).where(GraphNode.id.in_(target_ids))
            ent_result = await db.execute(ent_stmt)
            entities = ent_result.scalars().all()
            for ent in entities:
                entities_text += f"• {ent.node_type.upper()}: {ent.label} (Risk Score: {ent.risk_score or 0:.2f})\n"

    if entities_text:
        sections.append({
            "title": "4. EXTRACTED IDENTIFIERS (Auto-NER)",
            "content": entities_text.strip(),
        })

    # Section 5: Legal Sections
    legal_sections = analysis.get("legal_sections", [])
    if legal_sections:
        legal_text = ""
        for ls in legal_sections:
            section = ls.get("section", "")
            desc = ls.get("description", "")
            legal_text += f"• {section}: {desc}\n"
        sections.append({
            "title": "5. APPLICABLE LEGAL PROVISIONS",
            "content": legal_text.strip(),
        })

    # Section 6: AI Reasoning
    ai_reasoning = analysis.get("ai_reasoning", "")
    if ai_reasoning:
        sections.append({
            "title": "6. AI ANALYSIS RATIONALE",
            "content": ai_reasoning,
        })

    # Section 7: Tactics
    tactics = analysis.get("tactics_detected", [])
    if tactics:
        tactic_text = ""
        for t in tactics:
            name = t.get("tactic_name", "Unknown")
            evidence = t.get("evidence_text", "N/A")
            tactic_text += f"• {name}: \"{evidence}\"\n"
        sections.append({
            "title": "7. PSYCHOLOGICAL MANIPULATION TACTICS DETECTED",
            "content": tactic_text.strip(),
        })

    # Recommended actions
    recommended_actions = [
        "File a complaint on National Cyber Crime Reporting Portal (cybercrime.gov.in)",
        "Report the incident to the local police station with this alert document",
        "Block and report the sender's phone number/UPI ID with your telecom provider/bank",
        f"If financial loss occurred, immediately call 1930 (National Cyber Crime Helpline)",
        "Preserve all evidence (screenshots, call recordings, transaction receipts)",
    ]

    if risk_level in ("critical", "high"):
        recommended_actions.insert(0, "⚠️ IMMEDIATE ACTION REQUIRED — Contact 1930 helpline NOW")
        recommended_actions.append("Request immediate freeze on linked bank accounts via the concerned bank's fraud department")

    # Build full text
    header = (
        "=" * 72 + "\n"
        "INDIAN CYBER CRIME COORDINATION CENTRE (I4C)\n"
        "MINISTRY OF HOME AFFAIRS, GOVERNMENT OF INDIA\n"
        "=" * 72 + "\n"
        f"CYBER CRIME ALERT — AUTO-GENERATED BY NETRA AI v3.0\n"
        f"Alert Type: {alert_type}\n"
        f"Generated: {now.strftime('%d-%b-%Y %H:%M:%S')} UTC\n"
        f"Classification: {'URGENT' if risk_level in ('critical', 'high') else 'STANDARD'}\n"
        "=" * 72 + "\n\n"
    )

    body = ""
    for s in sections:
        body += f"\n{s['title']}\n{'-' * len(s['title'])}\n{s['content']}\n"

    actions_text = "\n\nRECOMMENDED ACTIONS\n" + "-" * 19 + "\n"
    for i, action in enumerate(recommended_actions, 1):
        actions_text += f"{i}. {action}\n"

    footer = (
        "\n\n" + "=" * 72 + "\n"
        "DISCLAIMER: This alert was auto-generated by NETRA AI for informational purposes.\n"
        "It should be verified by a human investigator before formal legal proceedings.\n"
        "NETRA AI — National Electronic Threat Recognition & Analysis\n"
        "=" * 72 + "\n"
    )

    full_text = header + body + actions_text + footer

    # Determine severity
    severity_map = {"critical": "P1-CRITICAL", "high": "P2-HIGH", "medium": "P3-MEDIUM", "low": "P4-LOW"}
    severity = severity_map.get(risk_level, "P3-MEDIUM")

    return AlertResponse(
        case_id=case_id,
        alert_type=alert_type,
        generated_text=full_text,
        sections=sections,
        recommended_actions=recommended_actions,
        severity=severity,
        generated_at=now.isoformat(),
    )


