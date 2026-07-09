"""
NETRA Entity Extraction Service — Regex + LLM NER Pipeline

Extracts structured entities from scam text to auto-populate the fraud network graph.

Entity types extracted:
- Phone numbers (Indian: +91, 10-digit)
- UPI IDs (user@bank)
- Bank account numbers
- URLs/domains
- Email addresses
- Person names (via LLM NER)
- Organization names (via LLM NER)
- Location mentions (via LLM NER)
- Amounts (₹/INR mentions)

Two-stage extraction:
1. Regex-based: fast, deterministic (phones, UPI, emails, URLs, amounts)
2. LLM-based: intelligent NER for names, organizations, locations
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """A single extracted entity."""
    entity_type: str          # 'phone', 'upi_id', 'bank_account', 'url', 'email', 'person', 'organization', 'location', 'amount'
    value: str                # The extracted value
    confidence: float = 1.0   # 1.0 for regex, lower for LLM
    source: str = "regex"     # 'regex' or 'llm'
    context: str = ""         # Surrounding text for verification


@dataclass
class ExtractionResult:
    """Complete extraction result from a text."""
    entities: list[ExtractedEntity] = field(default_factory=list)
    entity_count: int = 0
    extraction_method: str = "regex+llm"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [asdict(e) for e in self.entities],
            "entity_count": self.entity_count,
            "extraction_method": self.extraction_method,
        }

    def get_by_type(self, entity_type: str) -> list[ExtractedEntity]:
        return [e for e in self.entities if e.entity_type == entity_type]


# ---------- Regex Patterns (Indian-specific) ----------

# Indian phone: +91-XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX, XXXXXXXXXX
PHONE_PATTERN = re.compile(
    r'(?:\+?91[\s\-.]?)?\b([6-9]\d{9})\b'
)

# UPI ID: username@bankcode (e.g., user@ybl, name@paytm, phone@upi)
UPI_PATTERN = re.compile(
    r'\b([a-zA-Z0-9._\-]+@(?:ybl|paytm|okaxis|okicici|oksbi|okhdfcbank|'
    r'apl|ibl|axl|sbi|upi|icici|hdfc|axisbank|kotak|indus|federal|'
    r'barodampay|unionbankofindia|cnrb|idbi|pnb|rbl|scb|citi|dbs|'
    r'freecharge|gpay|phonepe|amazonpay|airtel|jio|postbank|'
    r'[a-zA-Z]{2,20}))\b',
    re.IGNORECASE
)

# Bank account numbers (8-18 digit sequences, preceded by context keywords)
BANK_ACCOUNT_PATTERN = re.compile(
    r'(?:a/?c|account|acct|bank\s*a/?c)[\s#:.\-]*(\d{8,18})',
    re.IGNORECASE
)

# IFSC Code (4 letters + 0 + 6 alphanumeric)
IFSC_PATTERN = re.compile(
    r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
)

# URLs
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+|www\.[^\s<>"\']+',
    re.IGNORECASE
)

# Email addresses
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b'
)

# Indian currency amounts: ₹1,00,000 or Rs. 50000 or INR 1,000 or 1.5 lakh/crore
AMOUNT_PATTERN = re.compile(
    r'(?:₹|Rs\.?|INR|rupees?)\s*(\d[\d,]*\.?\d*)\s*(?:lakh|lac|crore|cr|k)?'
    r'|(\d[\d,]*\.?\d*)\s*(?:lakh|lac|crore|cr)\b',
    re.IGNORECASE
)

# Aadhaar numbers (12 digits, optionally spaced in groups of 4)
AADHAAR_PATTERN = re.compile(
    r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b'
)

# PAN numbers (5 letters, 4 digits, 1 letter)
PAN_PATTERN = re.compile(
    r'\b([A-Z]{5}\d{4}[A-Z])\b'
)


# ---------- LLM NER Prompt ----------

NER_SYSTEM_PROMPT = """You are an entity extraction engine for cybercrime investigation. Extract ONLY entities that are explicitly mentioned in the text.

Respond in JSON format:
{
    "persons": ["list of person names mentioned"],
    "organizations": ["list of organization/company/bank/agency names"],
    "locations": ["list of city/state/country/address mentions"],
    "designations": ["list of official titles: 'CBI Officer', 'RBI Inspector', etc."]
}

RULES:
- Extract ONLY entities explicitly present in the text
- Do NOT infer or guess entities
- If a category has no entities, use an empty array
- For locations, include both specific places and general areas
- For organizations, include both legitimate (banks, govt) and suspicious
- Respond with JSON ONLY, no explanation
"""


class EntityExtractor:
    """
    Two-stage entity extraction: regex (fast) + LLM NER (intelligent).
    """

    def __init__(self, llm_service=None):
        self.llm = llm_service

    async def extract(self, text: str, use_llm: bool = True) -> ExtractionResult:
        """
        Extract all entities from text.

        Args:
            text: Input text to extract entities from
            use_llm: Whether to use LLM for NER (names, orgs, locations)

        Returns:
            ExtractionResult with all discovered entities
        """
        result = ExtractionResult()

        # Stage 1: Regex-based extraction (deterministic, fast)
        self._extract_regex(text, result)

        # Stage 2: LLM-based NER (intelligent, for names/orgs/locations)
        if use_llm and self.llm:
            await self._extract_llm(text, result)

        # Deduplicate
        self._deduplicate(result)

        result.entity_count = len(result.entities)
        return result

    def _extract_regex(self, text: str, result: ExtractionResult) -> None:
        """Stage 1: Regex-based entity extraction."""

        # Phone numbers
        for match in PHONE_PATTERN.finditer(text):
            phone = match.group(1)
            # Skip if it looks like an account number (too long or contextually wrong)
            if len(phone) == 10:
                start = max(0, match.start() - 30)
                context = text[start:match.end() + 30]
                result.entities.append(ExtractedEntity(
                    entity_type="phone",
                    value=f"+91{phone}",
                    confidence=0.95,
                    source="regex",
                    context=context.strip(),
                ))

        # UPI IDs
        for match in UPI_PATTERN.finditer(text):
            upi = match.group(1)
            # Filter out regular emails that match UPI pattern
            if not any(upi.lower().endswith(d) for d in ['.com', '.org', '.net', '.in', '.co.in', '.gov.in']):
                start = max(0, match.start() - 20)
                context = text[start:match.end() + 20]
                result.entities.append(ExtractedEntity(
                    entity_type="upi_id",
                    value=upi.lower(),
                    confidence=0.90,
                    source="regex",
                    context=context.strip(),
                ))

        # Bank account numbers
        for match in BANK_ACCOUNT_PATTERN.finditer(text):
            account = match.group(1)
            start = max(0, match.start() - 20)
            context = text[start:match.end() + 20]
            result.entities.append(ExtractedEntity(
                entity_type="bank_account",
                value=account,
                confidence=0.85,
                source="regex",
                context=context.strip(),
            ))

        # IFSC codes
        for match in IFSC_PATTERN.finditer(text):
            ifsc = match.group(1)
            start = max(0, match.start() - 20)
            context = text[start:match.end() + 20]
            result.entities.append(ExtractedEntity(
                entity_type="ifsc",
                value=ifsc,
                confidence=0.95,
                source="regex",
                context=context.strip(),
            ))

        # URLs
        for match in URL_PATTERN.finditer(text):
            url = match.group(0)
            result.entities.append(ExtractedEntity(
                entity_type="url",
                value=url,
                confidence=0.95,
                source="regex",
                context="",
            ))

        # Emails
        for match in EMAIL_PATTERN.finditer(text):
            email = match.group(0)
            # Skip if already captured as UPI
            if not any(e.value == email.lower() and e.entity_type == "upi_id" for e in result.entities):
                result.entities.append(ExtractedEntity(
                    entity_type="email",
                    value=email.lower(),
                    confidence=0.95,
                    source="regex",
                    context="",
                ))

        # Amounts
        for match in AMOUNT_PATTERN.finditer(text):
            amount = match.group(1) or match.group(2)
            if amount:
                start = max(0, match.start() - 20)
                context = text[start:match.end() + 20]
                result.entities.append(ExtractedEntity(
                    entity_type="amount",
                    value=f"₹{amount.strip()}",
                    confidence=0.90,
                    source="regex",
                    context=context.strip(),
                ))

        # Aadhaar (flagged as PII — still extracted for graph linking)
        for match in AADHAAR_PATTERN.finditer(text):
            aadhaar = match.group(1).replace(" ", "").replace("-", "")
            if len(aadhaar) == 12 and aadhaar.isdigit():
                # Verify it's not already captured as a phone
                if not any(e.value.endswith(aadhaar[-10:]) and e.entity_type == "phone" for e in result.entities):
                    result.entities.append(ExtractedEntity(
                        entity_type="aadhaar",
                        value=f"XXXX-XXXX-{aadhaar[-4:]}",  # Redacted for privacy
                        confidence=0.70,  # Lower — many 12-digit sequences aren't Aadhaar
                        source="regex",
                        context="",
                    ))

        # PAN
        for match in PAN_PATTERN.finditer(text):
            pan = match.group(1)
            result.entities.append(ExtractedEntity(
                entity_type="pan",
                value=f"XXXXX{pan[5:9]}X",  # Partially redacted
                confidence=0.90,
                source="regex",
                context="",
            ))

    async def _extract_llm(self, text: str, result: ExtractionResult) -> None:
        """Stage 2: LLM-based NER for names, organizations, locations."""
        try:
            # Truncate very long texts
            truncated = text[:3000] if len(text) > 3000 else text

            response = await self.llm.generate(
                prompt=f"Extract entities from this text:\n\n\"\"\"{truncated}\"\"\"",
                system_instruction=NER_SYSTEM_PROMPT,
                response_format="json",
                temperature=0.1,  # Very low for extraction accuracy
                max_tokens=1024,
                tier="fast",  # Use fast model for extraction
            )

            data = response.parse_json()
            if not data:
                return

            # Add person entities
            for person in data.get("persons", []):
                if person and len(person) > 1:
                    result.entities.append(ExtractedEntity(
                        entity_type="person",
                        value=person.strip(),
                        confidence=0.75,
                        source="llm",
                    ))

            # Add organization entities
            for org in data.get("organizations", []):
                if org and len(org) > 1:
                    result.entities.append(ExtractedEntity(
                        entity_type="organization",
                        value=org.strip(),
                        confidence=0.75,
                        source="llm",
                    ))

            # Add location entities
            for loc in data.get("locations", []):
                if loc and len(loc) > 1:
                    result.entities.append(ExtractedEntity(
                        entity_type="location",
                        value=loc.strip(),
                        confidence=0.70,
                        source="llm",
                    ))

            # Add designation entities (fake titles used by scammers)
            for title in data.get("designations", []):
                if title and len(title) > 2:
                    result.entities.append(ExtractedEntity(
                        entity_type="designation",
                        value=title.strip(),
                        confidence=0.80,
                        source="llm",
                    ))

        except Exception as e:
            logger.warning(f"LLM NER extraction failed (non-critical): {e}")
            # Regex results are still valid — this is a graceful degradation

    def _deduplicate(self, result: ExtractionResult) -> None:
        """Remove duplicate entities, keeping highest confidence."""
        seen: dict[str, ExtractedEntity] = {}

        for entity in result.entities:
            key = f"{entity.entity_type}:{entity.value.lower()}"
            if key not in seen or entity.confidence > seen[key].confidence:
                seen[key] = entity

        result.entities = list(seen.values())
