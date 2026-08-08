"""
NETRA Detection Agent — Scam Classification & Analysis

This agent does NOT use hardcoded if/else logic for classification.
Instead, it:
1. Loads known scam patterns from the database (scam_patterns table)
2. Constructs a dynamic prompt that includes these patterns as context
3. Sends the suspicious text to the LLM for classification
4. Falls back through the model chain if primary fails
5. Maps detected scam types to legal codes using pattern data from DB

The only "rule-based" component is the final legal code lookup,
which maps scam_type → IPC/IT Act sections using the database.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import ScamPattern
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)


# System instruction for the detection agent
DETECTION_SYSTEM_PROMPT = """You are NETRA, an expert digital forensic analyst specializing in Indian cybercrime patterns.

Your task: Analyze the provided text (a suspicious message, call transcript, or URL) and determine if it is a scam.

## NETRA SCAM KILL CHAIN™ — Attack Progression Taxonomy

Every social engineering scam follows a staged attack progression. You MUST map the analyzed text to these stages:

| Stage | Code | Name | Description |
|-------|------|------|-------------|
| 1 | S1_CONTACT | Contact | Initial reach — cold call, SMS, WhatsApp, email. How the scammer first contacts the victim. |
| 2 | S2_PRETEXT | Pretext | False narrative — fake identity, fabricated emergency, false authority claim. |
| 3 | S3_PRESSURE | Pressure | Psychological manipulation — fear, urgency, authority, threats, legal consequences. |
| 4 | S4_ISOLATION | Isolation | Cutting victim off — "don't tell anyone", "this is confidential", "stay on the line". |
| 5 | S5_EXTRACTION | Extraction | Money/data demanded — transfer funds, share OTP, install remote access app. |
| 6 | S6_PERSISTENCE | Persistence | Continued exploitation — follow-up demands, "more fees needed", repeated contact. |

For each stage PRESENT in the text, provide the evidence (exact quotes from the text).
For stages NOT present, mark as not_detected.
A single message may contain evidence for multiple stages simultaneously.

You MUST respond in valid JSON with this exact structure:
{
    "is_scam": true/false,
    "scam_type": "the scam category name from the known patterns, or 'unknown' if not matching any known pattern, or null if not a scam",
    "confidence": 0.0 to 1.0,
    "risk_level": "critical" | "high" | "medium" | "low",
    "language": "detected language code (en, hi, ta, etc.)",
    "reasoning": "detailed explanation of WHY you classified it this way, citing specific indicators found in the text",
    "tactics": [
        {
            "name": "tactic name (e.g., 'Authority Impersonation', 'Fear Escalation', 'Urgency Pressure')",
            "description": "how this tactic is being used in the text",
            "confidence": 0.0 to 1.0
        }
    ],
    "kill_chain": [
        {
            "stage": "S1_CONTACT | S2_PRETEXT | S3_PRESSURE | S4_ISOLATION | S5_EXTRACTION | S6_PERSISTENCE",
            "detected": true/false,
            "evidence": "exact quote from text that demonstrates this stage, or null if not detected",
            "severity": "critical | high | medium | low | none"
        }
    ],
    "victim_vulnerability_score": 0.0 to 1.0,
    "victim_vulnerability_factors": ["list of factors: e.g., 'targets elderly', 'exploits financial anxiety', 'uses technical jargon to confuse'"],
    "key_indicators": ["list of specific phrases or patterns that triggered the classification"]
}

IMPORTANT RULES:
- Base your analysis on the ACTUAL CONTENT of the text, not assumptions
- If the text is ambiguous, reflect that in a lower confidence score
- Do NOT hallucinate indicators that aren't in the text
- Confidence thresholds: critical >= 0.85, high >= 0.65, medium >= 0.40, low < 0.40
- If the text is clearly NOT a scam (e.g., a normal conversation), set is_scam=false with reasoning
- kill_chain MUST always contain exactly 6 entries (one per stage), even if not detected
- victim_vulnerability_score: 0.0 = low vulnerability, 1.0 = extreme vulnerability. Base on content analysis: does the scam target specific demographics, exploit emotional states, or use advanced manipulation?
"""


class DetectionAgent:
    """
    Scam detection agent that classifies suspicious text using LLM + database context.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_llm_service()

    async def analyze(self, text: str, input_type: str = "text") -> dict[str, Any]:
        """
        Analyze suspicious text for scam patterns.

        Returns dict with: scam_type, confidence, risk_level, reasoning, tactics, legal_codes, model_used
        """
        # 1. Load known scam patterns from database for context
        patterns_context = await self._load_patterns_context()

        # 2. Construct the analysis prompt
        prompt = self._build_prompt(text, input_type, patterns_context)

        # 3. Call LLM with fallback chain
        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_instruction=DETECTION_SYSTEM_PROMPT,
                response_format="json",
                temperature=0.3,  # Low temperature for classification accuracy
                tier="primary",
            )

            result = response.parse_json()
            if result is None:
                logger.warning("LLM returned non-JSON response, attempting text parse")
                result = self._parse_text_response(response.content)

        except Exception as e:
            logger.error(f"All LLM models failed: {e}")
            # Final fallback: rule-based analysis using patterns from DB
            result = await self._rule_based_fallback(text)
            result["model_used"] = "rule_based"
            result["was_fallback"] = True
            return result

        # 4. Enrich with legal codes from database
        if result.get("is_scam") and result.get("scam_type"):
            legal_codes = await self._lookup_legal_codes(result["scam_type"])
            result["legal_codes"] = legal_codes

        result["model_used"] = response.model_used
        result["was_fallback"] = response.was_fallback
        result["fallback_model"] = response.model_used if response.was_fallback else None

        return result

    async def _load_patterns_context(self) -> str:
        """Load scam patterns from database to provide as context to LLM."""
        try:
            stmt = select(ScamPattern).order_by(ScamPattern.prevalence.desc())
            result = await self.db.execute(stmt)
            patterns = result.scalars().all()

            if not patterns:
                return "No known scam patterns loaded. Analyze based on general fraud indicators."

            context_lines = ["KNOWN SCAM PATTERNS (from NETRA intelligence database):"]
            for p in patterns:
                context_lines.append(
                    f"\n- **{p.name}** (Category: {p.category}, Prevalence: {p.prevalence})"
                )
                if p.description:
                    context_lines.append(f"  Description: {p.description}")
                if p.keywords:
                    context_lines.append(f"  Keywords: {', '.join(p.keywords[:10])}")
                if p.tactics:
                    context_lines.append(f"  Tactics: {', '.join(p.tactics[:5])}")

            return "\n".join(context_lines)

        except Exception as e:
            logger.warning(f"Failed to load patterns from DB: {e}")
            return "Database unavailable. Analyze based on general fraud indicators."

    def _build_prompt(self, text: str, input_type: str, patterns_context: str) -> str:
        """Build the analysis prompt with database-loaded context."""
        type_labels = {
            "text": "a text message or WhatsApp message",
            "transcript": "a phone call transcript",
            "url": "a URL or website content",
        }
        type_desc = type_labels.get(input_type, "a suspicious communication")

        return f"""{patterns_context}

---

ANALYZE THE FOLLOWING ({type_desc}):

\"\"\"{text}\"\"\"

Classify this against the known patterns above. If it matches a known pattern, use that pattern's name as the scam_type. If it doesn't match any known pattern but is still suspicious, classify as 'unknown'.

Respond in valid JSON only."""

    async def _lookup_legal_codes(self, scam_type: str) -> list[str]:
        """Look up applicable IPC/IT Act section codes from scam_patterns table."""
        try:
            stmt = select(ScamPattern).where(ScamPattern.name == scam_type)
            result = await self.db.execute(stmt)
            pattern = result.scalar_one_or_none()

            if pattern:
                codes = []
                if pattern.ipc_sections:
                    codes.extend(pattern.ipc_sections)
                if pattern.it_act_sections:
                    codes.extend(pattern.it_act_sections)
                return codes

            return []
        except Exception as e:
            logger.warning(f"Failed to lookup legal codes: {e}")
            return []

    async def _rule_based_fallback(self, text: str) -> dict[str, Any]:
        """
        Final fallback when ALL LLM models fail.
        Uses pattern keywords from database for basic matching.
        This is a safety net, not the primary classification method.
        """
        text_lower = text.lower()

        try:
            stmt = select(ScamPattern)
            result = await self.db.execute(stmt)
            patterns = result.scalars().all()

            best_match = None
            best_score = 0

            for pattern in patterns:
                if not pattern.keywords:
                    continue
                # Count keyword matches
                match_count = sum(
                    1 for kw in pattern.keywords if kw.lower() in text_lower
                )
                score = match_count / len(pattern.keywords) if pattern.keywords else 0

                if score > best_score:
                    best_score = score
                    best_match = pattern

            if best_match and best_score > 0.15:  # At least 15% keyword match
                risk_level = (
                    "critical" if best_score > 0.6
                    else "high" if best_score > 0.4
                    else "medium" if best_score > 0.2
                    else "low"
                )
                legal_codes = (best_match.ipc_sections or []) + (best_match.it_act_sections or [])
                return {
                    "is_scam": True,
                    "scam_type": best_match.name,
                    "confidence": round(min(best_score * 1.2, 0.75), 2),  # Cap at 0.75 for rule-based
                    "risk_level": risk_level,
                    "language": "en",
                    "reasoning": (
                        f"Rule-based fallback (LLM unavailable). "
                        f"Matched {int(best_score * 100)}% of keywords for pattern '{best_match.name}'. "
                        f"This is a lower-confidence analysis — LLM-based analysis is recommended."
                    ),
                    "tactics": [],
                    "key_indicators": [
                        kw for kw in (best_match.keywords or [])
                        if kw.lower() in text_lower
                    ],
                    "legal_codes": legal_codes,
                }

            return {
                "is_scam": False,
                "scam_type": None,
                "confidence": 0.3,
                "risk_level": "low",
                "language": "en",
                "reasoning": "Rule-based fallback could not determine scam status. LLM unavailable.",
                "tactics": [],
                "key_indicators": [],
                "legal_codes": [],
            }

        except Exception as e:
            logger.error(f"Rule-based fallback failed: {e}")
            return {
                "is_scam": False,
                "scam_type": None,
                "confidence": 0.0,
                "risk_level": "unknown",
                "language": "en",
                "reasoning": f"Analysis failed: {str(e)}",
                "tactics": [],
                "key_indicators": [],
                "legal_codes": [],
            }

    def _parse_text_response(self, text: str) -> dict[str, Any]:
        """
        Extract structured data from non-JSON LLM response using regex patterns.
        This is a safety net — if the LLM returns prose instead of JSON,
        we still extract what we can rather than defaulting to is_scam=False.
        """
        import re

        result = {
            "is_scam": False,
            "scam_type": None,
            "confidence": 0.0,
            "risk_level": "unknown",
            "language": "en",
            "reasoning": f"Extracted from non-JSON LLM response.",
            "tactics": [],
            "key_indicators": [],
            "legal_codes": [],
            "kill_chain": [],
        }

        text_lower = text.lower()

        # Extract is_scam: look for "is_scam": true or "is_scam" : true patterns
        is_scam_match = re.search(r'"is_scam"\s*:\s*(true|false)', text_lower)
        if is_scam_match:
            result["is_scam"] = is_scam_match.group(1) == "true"
        else:
            # Heuristic: if the response contains strong scam indicators
            scam_keywords = ["scam", "fraud", "phishing", "impersonation", "fake", "suspicious"]
            benign_keywords = ["legitimate", "not a scam", "benign", "genuine", "safe"]
            scam_hits = sum(1 for kw in scam_keywords if kw in text_lower)
            benign_hits = sum(1 for kw in benign_keywords if kw in text_lower)
            if scam_hits > benign_hits:
                result["is_scam"] = True

        # Extract confidence
        conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', text)
        if conf_match:
            try:
                result["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass

        # Extract scam_type
        type_match = re.search(r'"scam_type"\s*:\s*"([^"]+)"', text)
        if type_match:
            val = type_match.group(1)
            if val.lower() != "null" and val.lower() != "none":
                result["scam_type"] = val

        # Extract risk_level
        risk_match = re.search(r'"risk_level"\s*:\s*"([^"]+)"', text)
        if risk_match:
            result["risk_level"] = risk_match.group(1)

        # Extract reasoning
        reason_match = re.search(r'"reasoning"\s*:\s*"([^"]{10,})"', text)
        if reason_match:
            result["reasoning"] = reason_match.group(1)[:500]

        logger.info(
            f"Text response parsed: is_scam={result['is_scam']}, "
            f"confidence={result['confidence']}, scam_type={result['scam_type']}"
        )

        return result
