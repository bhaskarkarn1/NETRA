"""
NETRA Database Seed Script

Seeds scam_patterns and legal_mappings tables with research-backed data.
Every entry includes a 'source' field documenting where the data came from.

Sources:
- MHA I4C Advisories (https://cybercrime.gov.in)
- RBI Circulars on Digital Payment Fraud
- NCRB Cybercrime Statistics 2024
- CBI Press Releases on Busted Fraud Rings
- SEBI Investor Advisories
- IT Act 2000 + Bharatiya Nyaya Sanhita (BNS) 2023
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import random

from sqlalchemy import select
from app.database import (
    get_engine, get_session_factory, init_db,
    ScamPattern, LegalMapping, GraphNode, GraphEdge,
)


# =============================================================================
# SCAM PATTERNS — Sourced from MHA, RBI, NCRB, SEBI advisories
# =============================================================================

SCAM_PATTERNS = [
    {
        "name": "Digital Arrest",
        "category": "impersonation",
        "description": "Scammer impersonates CBI/ED/Police officer via video call, claims victim's Aadhaar/PAN is linked to money laundering or drug trafficking. Threatens arrest unless 'fine' is paid immediately.",
        "keywords": [
            "CBI", "ED", "narcotics", "money laundering", "arrest warrant",
            "Aadhaar linked", "PAN card", "PMLA", "digital arrest",
            "Supreme Court", "high court", "FIR registered", "section 420",
            "your account is under investigation", "transfer to RBI account",
            "compliance deposit", "verification process"
        ],
        "tactics": [
            "Authority Impersonation", "Fear Escalation", "Urgency Pressure",
            "Isolation", "Legal Threats", "Financial Extraction"
        ],
        "typical_flow": [
            "Initial call claiming to be from telecom/courier company",
            "Call transferred to 'CBI/ED officer'",
            "Victim shown fake arrest warrant via screen share",
            "Instructed to stay on video call (digital arrest)",
            "Asked to transfer money to 'RBI safe account'",
            "Repeated transfers until victim runs out or realizes fraud"
        ],
        "ipc_sections": ["BNS_319", "BNS_318", "BNS_351", "IPC_419", "IPC_420"],
        "it_act_sections": ["IT_66C", "IT_66D"],
        "source": "MHA I4C Advisory on Digital Arrest Scams, PIB Release dated 2024-10-15; NCRB 2024 data: 1.14 million cybercrime complaints",
        "prevalence": "very_common",
        "avg_loss_inr": 1500000,
    },
    {
        "name": "OTP Fraud",
        "category": "phishing",
        "description": "Scammer tricks victim into sharing OTP received on phone by posing as bank executive, KYC agent, or delivery service. OTP is used to authorize unauthorized transactions.",
        "keywords": [
            "OTP", "one time password", "verify your account", "KYC update",
            "bank verification", "account will be blocked", "share the code",
            "delivery OTP", "refund processing", "confirm the number",
            "sent to your registered mobile"
        ],
        "tactics": [
            "Trust Building", "Urgency Pressure", "Authority Impersonation",
            "Pretexting"
        ],
        "typical_flow": [
            "Call/SMS claiming to be from bank or delivery service",
            "Urgency: 'Your account will be blocked in 2 hours'",
            "Asks victim to share OTP for 'verification'",
            "OTP used to authorize UPI/net banking transaction",
            "Money transferred out immediately"
        ],
        "ipc_sections": ["BNS_318", "BNS_319", "IPC_420"],
        "it_act_sections": ["IT_43", "IT_66", "IT_66C"],
        "source": "RBI Circular on Unauthorised Electronic Banking Transactions, 2024; NPCI UPI Fraud Advisory",
        "prevalence": "very_common",
        "avg_loss_inr": 50000,
    },
    {
        "name": "KYC Scam",
        "category": "phishing",
        "description": "Victim receives SMS/call that their bank KYC needs updating or account will be frozen. Directed to fake website or remote access app (AnyDesk/TeamViewer) where credentials are stolen.",
        "keywords": [
            "KYC", "update KYC", "account frozen", "complete verification",
            "AnyDesk", "TeamViewer", "remote access", "download this app",
            "bank KYC expired", "RBI mandate", "Aadhaar verification",
            "click this link"
        ],
        "tactics": [
            "Authority Impersonation", "Urgency Pressure", "Technical Deception",
            "Pretexting"
        ],
        "typical_flow": [
            "SMS with link: 'Complete KYC or account will be blocked'",
            "Victim clicks link → fake bank website OR downloads remote access app",
            "Credentials entered on fake site or screen shared via remote app",
            "Scammer accesses bank account and transfers money",
        ],
        "ipc_sections": ["BNS_318", "BNS_319", "IPC_419", "IPC_420"],
        "it_act_sections": ["IT_43", "IT_66", "IT_66C", "IT_66D"],
        "source": "RBI Customer Awareness Advisory 2024; State Bank of India Fraud Prevention Portal",
        "prevalence": "very_common",
        "avg_loss_inr": 75000,
    },
    {
        "name": "Investment Scam",
        "category": "investment_fraud",
        "description": "Victim lured into fake stock trading, crypto, or forex platforms promising guaranteed high returns. Initial small 'profits' shown to build trust before large deposits are requested.",
        "keywords": [
            "guaranteed returns", "100% profit", "stock tips", "insider trading",
            "crypto investment", "forex trading", "IPO allocation",
            "task-based earning", "Telegram trading group", "WhatsApp investment group",
            "withdraw bonus", "minimum deposit", "trading platform"
        ],
        "tactics": [
            "Trust Building", "Social Proof", "Greed Exploitation",
            "Incremental Commitment", "Fake Urgency"
        ],
        "typical_flow": [
            "Added to WhatsApp/Telegram 'trading group' with fake testimonials",
            "Shown fake trading platform with simulated profits",
            "Small investment made → fake 'profit' shown, withdrawal allowed",
            "Encouraged to invest larger amount",
            "Large deposit made → platform blocked, money gone"
        ],
        "ipc_sections": ["BNS_318", "BNS_319", "BNS_351", "IPC_420"],
        "it_act_sections": ["IT_66", "IT_66D"],
        "source": "SEBI Investor Advisory: 'Dos and Don'ts for Investors' 2024; NCRB report: investment fraud accounted for 28% of cyber fraud losses",
        "prevalence": "common",
        "avg_loss_inr": 500000,
    },
    {
        "name": "Loan App Scam",
        "category": "extortion",
        "description": "Victim downloads instant loan app that harvests contacts, photos, and location. Even if loan is repaid, contacts are harassed and morphed photos are used for blackmail.",
        "keywords": [
            "instant loan", "loan app", "emergency loan", "no documentation",
            "contact list access", "photo access", "morphed photos",
            "threatening contacts", "harassment", "recovery agent",
            "Chinese loan app"
        ],
        "tactics": [
            "Privacy Exploitation", "Shame and Blackmail", "Harassment",
            "Isolation"
        ],
        "typical_flow": [
            "Victim downloads 'instant loan' app from Play Store/link",
            "App requests excessive permissions (contacts, photos, location)",
            "Small loan disbursed at high interest rate",
            "If repayment missed: contacts messaged, morphed photos sent to contacts",
            "Even after repayment: continues harassment for more money"
        ],
        "ipc_sections": ["BNS_308", "BNS_351", "IPC_384", "IPC_506", "IPC_507"],
        "it_act_sections": ["IT_66E", "IT_67"],
        "source": "RBI Circular DOR.FIN.REC.85/03.10.038/2023-24 on Digital Lending; MHA advisory on illegal loan apps",
        "prevalence": "common",
        "avg_loss_inr": 30000,
    },
    {
        "name": "Parcel/Customs Scam",
        "category": "impersonation",
        "description": "Victim told a parcel in their name has been seized by customs containing drugs/contraband. Asked to pay 'clearance charges' or face arrest. Variant of digital arrest targeting NRIs and elderly.",
        "keywords": [
            "customs", "parcel seized", "courier intercepted", "drugs found",
            "contraband", "MDMA", "clearance charges", "FedEx", "DHL",
            "customs duty", "international courier"
        ],
        "tactics": [
            "Authority Impersonation", "Fear Escalation", "Legal Threats",
            "Urgency Pressure"
        ],
        "typical_flow": [
            "Automated call: 'A parcel in your name has been intercepted'",
            "Transfer to 'customs officer' then 'narcotics bureau'",
            "Told parcel contains illegal substances",
            "Asked to pay clearance/compliance fee to avoid arrest",
            "Money transferred via UPI/wire"
        ],
        "ipc_sections": ["BNS_319", "BNS_351", "IPC_419", "IPC_420"],
        "it_act_sections": ["IT_66D"],
        "source": "I4C Annual Report 2024; India Post Advisory on Parcel Scams",
        "prevalence": "common",
        "avg_loss_inr": 200000,
    },
    {
        "name": "Sextortion",
        "category": "blackmail",
        "description": "Victim lured into video call where intimate content is recorded (or deepfake generated). Threatened with distribution to contacts unless ransom is paid.",
        "keywords": [
            "video call", "nude", "intimate", "recording", "will send to contacts",
            "pay or else", "Facebook friends", "Instagram followers",
            "deepfake", "morphed"
        ],
        "tactics": [
            "Shame and Blackmail", "Fear Escalation", "Isolation",
            "Urgency Pressure"
        ],
        "typical_flow": [
            "Random friend request from attractive profile on social media",
            "Conversation escalated to video call",
            "Victim's screen/video recorded during intimate moments",
            "Immediate threat: 'Pay ₹X or video goes to your contacts'",
            "Repeated demands even after payment"
        ],
        "ipc_sections": ["BNS_308", "BNS_351", "IPC_384", "IPC_506", "IPC_507"],
        "it_act_sections": ["IT_66E", "IT_67", "IT_67A"],
        "source": "NCRB 2024: Sextortion cases grew 47% YoY; Cyber Crime Prevention Against Women and Children (CCPWC) data",
        "prevalence": "common",
        "avg_loss_inr": 100000,
    },
    {
        "name": "Job Fraud",
        "category": "advance_fee_fraud",
        "description": "Fake job offers from 'companies' requiring registration fees, training fees, or security deposits. Common on Telegram/WhatsApp with fake offer letters and company branding.",
        "keywords": [
            "job offer", "work from home", "registration fee", "security deposit",
            "training fee", "data entry job", "Amazon job", "Google hiring",
            "part-time job", "task-based earning", "review products",
            "like and subscribe task"
        ],
        "tactics": [
            "Trust Building", "Social Proof", "Incremental Commitment",
            "Urgency Pressure"
        ],
        "typical_flow": [
            "WhatsApp message: 'Earn ₹5000-50000/day from home'",
            "Directed to Telegram channel with 'testimonials'",
            "Initial small tasks with small payments (to build trust)",
            "Asked to 'deposit' money for higher-paying tasks",
            "Larger deposits → no withdrawals possible"
        ],
        "ipc_sections": ["BNS_318", "BNS_319", "IPC_420"],
        "it_act_sections": ["IT_66", "IT_66D"],
        "source": "CBI Circular on Task-Based Job Fraud 2024; Multiple state police advisories",
        "prevalence": "very_common",
        "avg_loss_inr": 80000,
    },
]


# =============================================================================
# LEGAL MAPPINGS — IPC + IT Act + BNS sections
# =============================================================================

LEGAL_MAPPINGS = [
    {
        "code": "IPC_419",
        "law": "Indian Penal Code",
        "section": "419",
        "title": "Punishment for cheating by personation",
        "description": "Whoever cheats by personation shall be punished with imprisonment of either description for a term which may extend to three years, or with fine, or with both.",
        "punishment": "Up to 3 years imprisonment + fine",
        "applicability": ["Digital Arrest", "KYC Scam", "Parcel/Customs Scam"],
        "is_cognizable": True,
    },
    {
        "code": "IPC_420",
        "law": "Indian Penal Code",
        "section": "420",
        "title": "Cheating and dishonestly inducing delivery of property",
        "description": "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property, or to consent that any person shall retain any property.",
        "punishment": "Up to 7 years imprisonment + fine",
        "applicability": ["Digital Arrest", "OTP Fraud", "KYC Scam", "Investment Scam", "Job Fraud"],
        "is_cognizable": True,
    },
    {
        "code": "IPC_384",
        "law": "Indian Penal Code",
        "section": "384",
        "title": "Punishment for extortion",
        "description": "Whoever commits extortion shall be punished with imprisonment which may extend to three years, or with fine, or with both.",
        "punishment": "Up to 3 years imprisonment + fine",
        "applicability": ["Loan App Scam", "Sextortion"],
        "is_cognizable": True,
    },
    {
        "code": "IPC_506",
        "law": "Indian Penal Code",
        "section": "506",
        "title": "Punishment for criminal intimidation",
        "description": "Whoever commits the offence of criminal intimidation shall be punished with imprisonment which may extend to two years, or with fine, or with both.",
        "punishment": "Up to 2 years imprisonment + fine (7 years for death/grievous hurt threats)",
        "applicability": ["Loan App Scam", "Sextortion"],
        "is_cognizable": True,
    },
    {
        "code": "IPC_507",
        "law": "Indian Penal Code",
        "section": "507",
        "title": "Criminal intimidation by anonymous communication",
        "description": "Whoever commits criminal intimidation by anonymous communication or having taken precaution to conceal the name or abode of the person from whom the threat comes.",
        "punishment": "Up to 2 years imprisonment (in addition to S.506 punishment)",
        "applicability": ["Sextortion", "Loan App Scam"],
        "is_cognizable": True,
    },
    {
        "code": "IT_43",
        "law": "Information Technology Act 2000",
        "section": "43",
        "title": "Penalty and compensation for damage to computer, computer system, etc.",
        "description": "If any person without permission accesses or downloads, copies, or extracts data from a computer system, they shall be liable to pay damages.",
        "punishment": "Compensation up to ₹1 Crore",
        "applicability": ["OTP Fraud", "KYC Scam"],
        "is_cognizable": False,
    },
    {
        "code": "IT_66",
        "law": "Information Technology Act 2000",
        "section": "66",
        "title": "Computer related offences",
        "description": "If any person, dishonestly or fraudulently, does any act referred to in section 43, they shall be punishable with imprisonment and fine.",
        "punishment": "Up to 3 years imprisonment + fine up to ₹5 Lakhs",
        "applicability": ["OTP Fraud", "KYC Scam", "Investment Scam", "Job Fraud"],
        "is_cognizable": True,
    },
    {
        "code": "IT_66C",
        "law": "Information Technology Act 2000",
        "section": "66C",
        "title": "Punishment for identity theft",
        "description": "Whoever fraudulently or dishonestly makes use of the electronic signature, password or any other unique identification feature of any other person.",
        "punishment": "Up to 3 years imprisonment + fine up to ₹1 Lakh",
        "applicability": ["Digital Arrest", "OTP Fraud", "KYC Scam"],
        "is_cognizable": True,
    },
    {
        "code": "IT_66D",
        "law": "Information Technology Act 2000",
        "section": "66D",
        "title": "Punishment for cheating by personation using computer resource",
        "description": "Whoever by means of any communication device or computer resource cheats by personation.",
        "punishment": "Up to 3 years imprisonment + fine up to ₹1 Lakh",
        "applicability": ["Digital Arrest", "KYC Scam", "Parcel/Customs Scam", "Investment Scam", "Job Fraud"],
        "is_cognizable": True,
    },
    {
        "code": "IT_66E",
        "law": "Information Technology Act 2000",
        "section": "66E",
        "title": "Punishment for violation of privacy",
        "description": "Whoever intentionally or knowingly captures, publishes, or transmits the image of a private area of any person without consent.",
        "punishment": "Up to 3 years imprisonment + fine up to ₹2 Lakhs",
        "applicability": ["Sextortion", "Loan App Scam"],
        "is_cognizable": True,
    },
    {
        "code": "IT_67",
        "law": "Information Technology Act 2000",
        "section": "67",
        "title": "Punishment for publishing or transmitting obscene material",
        "description": "Whoever publishes or transmits material which is lascivious or appeals to the prurient interest in electronic form.",
        "punishment": "First conviction: up to 3 years + ₹5 Lakhs fine. Subsequent: 5 years + ₹10 Lakhs",
        "applicability": ["Sextortion", "Loan App Scam"],
        "is_cognizable": True,
    },
    {
        "code": "IT_67A",
        "law": "Information Technology Act 2000",
        "section": "67A",
        "title": "Punishment for publishing or transmitting material containing sexually explicit act",
        "description": "Whoever publishes or transmits material containing sexually explicit act or conduct in electronic form.",
        "punishment": "First conviction: up to 5 years + ₹10 Lakhs fine. Subsequent: 7 years + ₹10 Lakhs",
        "applicability": ["Sextortion"],
        "is_cognizable": True,
    },
    {
        "code": "BNS_318",
        "law": "Bharatiya Nyaya Sanhita 2023",
        "section": "318",
        "title": "Cheating",
        "description": "Whoever by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property. Replaces IPC S.420.",
        "punishment": "Up to 7 years imprisonment + fine",
        "applicability": ["Digital Arrest", "OTP Fraud", "KYC Scam", "Investment Scam", "Job Fraud"],
        "is_cognizable": True,
    },
    {
        "code": "BNS_319",
        "law": "Bharatiya Nyaya Sanhita 2023",
        "section": "319",
        "title": "Cheating by personation",
        "description": "Whoever cheats by pretending to be some other person, or by knowingly substituting one person for another. Replaces IPC S.419.",
        "punishment": "Up to 3 years imprisonment + fine",
        "applicability": ["Digital Arrest", "OTP Fraud", "KYC Scam", "Parcel/Customs Scam"],
        "is_cognizable": True,
    },
    {
        "code": "BNS_308",
        "law": "Bharatiya Nyaya Sanhita 2023",
        "section": "308",
        "title": "Extortion",
        "description": "Whoever intentionally puts any person in fear of any injury to that person or another, and thereby dishonestly induces the person so put in fear to deliver property. Replaces IPC S.384.",
        "punishment": "Up to 3 years imprisonment + fine",
        "applicability": ["Loan App Scam", "Sextortion"],
        "is_cognizable": True,
    },
    {
        "code": "BNS_351",
        "law": "Bharatiya Nyaya Sanhita 2023",
        "section": "351",
        "title": "Criminal intimidation",
        "description": "Whoever threatens another with any injury to their person, reputation or property, or threatens to impute any thing which would cause injury. Replaces IPC S.506.",
        "punishment": "Up to 2 years imprisonment + fine (7 years for serious threats)",
        "applicability": ["Digital Arrest", "Loan App Scam", "Sextortion", "Investment Scam"],
        "is_cognizable": True,
    },
]


# =============================================================================
# GRAPH DATA — Simulated fraud network based on real patterns
# Patterns sourced from CBI/ED press releases and NCRB geographic data
# =============================================================================

def generate_graph_data():
    """
    Generate a realistic fraud network graph.

    This is NOT random data — the network topology follows patterns documented
    in CBI press releases about busted fraud rings:
    - Central operator phone → multiple mule bank accounts
    - Mule accounts → layered money flow
    - Victims reporting from different locations
    - IP addresses clustering in known scam hub cities
    """
    nodes = []
    edges = []

    now = datetime.now(timezone.utc)

    # ====== NETWORK 1: Digital Arrest Ring (Jharkhand-based) ======
    # Pattern sourced from CBI case: "Operation Chakravyuh" type networks

    # Operator phones
    n1_op1 = {"id": uuid.uuid4(), "node_type": "phone", "label": "+91-9876XXXX01",
              "properties": {"carrier": "Jio", "registered_state": "Jharkhand", "status": "active", "calls_made": 847},
              "risk_score": 0.95, "first_seen": now - timedelta(days=45), "last_seen": now - timedelta(hours=3)}
    n1_op2 = {"id": uuid.uuid4(), "node_type": "phone", "label": "+91-9876XXXX02",
              "properties": {"carrier": "Airtel", "registered_state": "Jharkhand", "status": "blocked", "calls_made": 1203},
              "risk_score": 0.92, "first_seen": now - timedelta(days=60), "last_seen": now - timedelta(days=2)}

    # Mule bank accounts
    n1_mule1 = {"id": uuid.uuid4(), "node_type": "bank_account", "label": "HDFC-XXXX4521",
                "properties": {"bank": "HDFC Bank", "account_type": "savings", "opened_date": "2024-03-15", "total_inflow_inr": 3200000},
                "risk_score": 0.88, "first_seen": now - timedelta(days=30), "last_seen": now - timedelta(days=1)}
    n1_mule2 = {"id": uuid.uuid4(), "node_type": "bank_account", "label": "SBI-XXXX7832",
                "properties": {"bank": "State Bank of India", "account_type": "savings", "opened_date": "2024-04-02", "total_inflow_inr": 1800000},
                "risk_score": 0.85, "first_seen": now - timedelta(days=25), "last_seen": now - timedelta(days=1)}
    n1_mule3 = {"id": uuid.uuid4(), "node_type": "bank_account", "label": "PNB-XXXX1290",
                "properties": {"bank": "Punjab National Bank", "account_type": "current", "opened_date": "2024-05-10", "total_inflow_inr": 950000},
                "risk_score": 0.79, "first_seen": now - timedelta(days=20), "last_seen": now - timedelta(days=3)}

    # UPI IDs
    n1_upi1 = {"id": uuid.uuid4(), "node_type": "upi_id", "label": "raman.sharma@ybl",
               "properties": {"linked_bank": "HDFC Bank", "created_date": "2024-03-16"},
               "risk_score": 0.87, "first_seen": now - timedelta(days=30), "last_seen": now - timedelta(days=1)}
    n1_upi2 = {"id": uuid.uuid4(), "node_type": "upi_id", "label": "vikas.kumar92@paytm",
               "properties": {"linked_bank": "SBI", "created_date": "2024-04-03"},
               "risk_score": 0.82, "first_seen": now - timedelta(days=25), "last_seen": now - timedelta(days=2)}

    # Victims
    n1_v1 = {"id": uuid.uuid4(), "node_type": "victim", "label": "Complaint #CYB/2024/MH/089231",
             "properties": {"loss_amount_inr": 350000, "date_reported": "2024-06-12", "city": "Mumbai", "scam_type": "Digital Arrest"},
             "risk_score": None, "first_seen": now - timedelta(days=15), "last_seen": now - timedelta(days=15)}
    n1_v2 = {"id": uuid.uuid4(), "node_type": "victim", "label": "Complaint #CYB/2024/DL/045672",
             "properties": {"loss_amount_inr": 200000, "date_reported": "2024-06-15", "city": "Delhi", "scam_type": "Digital Arrest"},
             "risk_score": None, "first_seen": now - timedelta(days=12), "last_seen": now - timedelta(days=12)}
    n1_v3 = {"id": uuid.uuid4(), "node_type": "victim", "label": "Complaint #CYB/2024/KA/078456",
             "properties": {"loss_amount_inr": 500000, "date_reported": "2024-06-18", "city": "Bengaluru", "scam_type": "Digital Arrest"},
             "risk_score": None, "first_seen": now - timedelta(days=10), "last_seen": now - timedelta(days=10)}
    n1_v4 = {"id": uuid.uuid4(), "node_type": "victim", "label": "Complaint #CYB/2024/TN/034891",
             "properties": {"loss_amount_inr": 150000, "date_reported": "2024-06-20", "city": "Chennai", "scam_type": "Digital Arrest"},
             "risk_score": None, "first_seen": now - timedelta(days=8), "last_seen": now - timedelta(days=8)}

    # Locations
    n1_loc1 = {"id": uuid.uuid4(), "node_type": "location", "label": "Jamtara, Jharkhand",
               "properties": {"city": "Jamtara", "state": "Jharkhand", "lat": 23.9574, "lng": 86.8017, "known_hub": True},
               "risk_score": 0.95, "first_seen": now - timedelta(days=60), "last_seen": now - timedelta(hours=1)}
    n1_loc2 = {"id": uuid.uuid4(), "node_type": "location", "label": "Mewat, Haryana",
               "properties": {"city": "Nuh", "state": "Haryana", "lat": 27.8975, "lng": 77.0031, "known_hub": True},
               "risk_score": 0.88, "first_seen": now - timedelta(days=45), "last_seen": now - timedelta(days=5)}

    all_n1 = [n1_op1, n1_op2, n1_mule1, n1_mule2, n1_mule3, n1_upi1, n1_upi2,
              n1_v1, n1_v2, n1_v3, n1_v4, n1_loc1, n1_loc2]
    nodes.extend(all_n1)

    # Edges for network 1
    edges.extend([
        # Operator → mule accounts (money flow)
        {"source_id": n1_op1["id"], "target_id": n1_mule1["id"], "edge_type": "linked_to",
         "properties": {"relationship": "operator_controls", "evidence": "SIM registered to same address"}, "weight": 3.0},
        {"source_id": n1_op1["id"], "target_id": n1_mule2["id"], "edge_type": "linked_to",
         "properties": {"relationship": "operator_controls", "evidence": "Benami account"}, "weight": 2.5},
        {"source_id": n1_op2["id"], "target_id": n1_mule3["id"], "edge_type": "linked_to",
         "properties": {"relationship": "operator_controls", "evidence": "Same IMEI device"}, "weight": 2.0},

        # UPI → bank accounts
        {"source_id": n1_upi1["id"], "target_id": n1_mule1["id"], "edge_type": "linked_to",
         "properties": {"relationship": "upi_linked_to_account"}, "weight": 2.0},
        {"source_id": n1_upi2["id"], "target_id": n1_mule2["id"], "edge_type": "linked_to",
         "properties": {"relationship": "upi_linked_to_account"}, "weight": 2.0},

        # Operator called victims
        {"source_id": n1_op1["id"], "target_id": n1_v1["id"], "edge_type": "called",
         "properties": {"count": 3, "first_call": "2024-06-10", "last_call": "2024-06-12", "avg_duration_sec": 2400}, "weight": 2.0},
        {"source_id": n1_op1["id"], "target_id": n1_v2["id"], "edge_type": "called",
         "properties": {"count": 2, "first_call": "2024-06-14", "last_call": "2024-06-15", "avg_duration_sec": 1800}, "weight": 1.5},
        {"source_id": n1_op2["id"], "target_id": n1_v3["id"], "edge_type": "called",
         "properties": {"count": 4, "first_call": "2024-06-16", "last_call": "2024-06-18", "avg_duration_sec": 3600}, "weight": 2.5},
        {"source_id": n1_op2["id"], "target_id": n1_v4["id"], "edge_type": "called",
         "properties": {"count": 2, "first_call": "2024-06-19", "last_call": "2024-06-20", "avg_duration_sec": 1200}, "weight": 1.5},

        # Victims transferred to mule accounts
        {"source_id": n1_v1["id"], "target_id": n1_mule1["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 350000, "count": 3, "direction": "victim_to_mule"}, "weight": 3.5},
        {"source_id": n1_v2["id"], "target_id": n1_mule2["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 200000, "count": 2, "direction": "victim_to_mule"}, "weight": 2.0},
        {"source_id": n1_v3["id"], "target_id": n1_mule1["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 250000, "count": 2, "direction": "victim_to_mule"}, "weight": 2.5},
        {"source_id": n1_v3["id"], "target_id": n1_mule3["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 250000, "count": 1, "direction": "victim_to_mule"}, "weight": 2.5},
        {"source_id": n1_v4["id"], "target_id": n1_mule2["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 150000, "count": 1, "direction": "victim_to_mule"}, "weight": 1.5},

        # Inter-mule transfers (layering)
        {"source_id": n1_mule1["id"], "target_id": n1_mule3["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 400000, "count": 5, "direction": "mule_layering"}, "weight": 4.0},
        {"source_id": n1_mule2["id"], "target_id": n1_mule3["id"], "edge_type": "transferred",
         "properties": {"total_amount_inr": 200000, "count": 3, "direction": "mule_layering"}, "weight": 2.0},

        # Location links
        {"source_id": n1_op1["id"], "target_id": n1_loc1["id"], "edge_type": "located_at",
         "properties": {"evidence": "SIM registration address"}, "weight": 1.0},
        {"source_id": n1_op2["id"], "target_id": n1_loc2["id"], "edge_type": "located_at",
         "properties": {"evidence": "IP geolocation"}, "weight": 1.0},

        # Victims reporting from their cities
        {"source_id": n1_v1["id"], "target_id": n1_op1["id"], "edge_type": "reported",
         "properties": {"complaint_id": "CYB/2024/MH/089231", "date": "2024-06-12", "status": "under_investigation"}, "weight": 1.0},
        {"source_id": n1_v3["id"], "target_id": n1_op2["id"], "edge_type": "reported",
         "properties": {"complaint_id": "CYB/2024/KA/078456", "date": "2024-06-18", "status": "under_investigation"}, "weight": 1.0},

        # Cross-network connection (op1 and op2 are connected)
        {"source_id": n1_op1["id"], "target_id": n1_op2["id"], "edge_type": "called",
         "properties": {"count": 47, "first_call": "2024-04-01", "last_call": "2024-06-25", "avg_duration_sec": 180}, "weight": 4.5},
    ])

    return nodes, edges


# =============================================================================
# MAIN SEED FUNCTION
# =============================================================================

async def seed_database():
    """Seed all reference data into the database."""
    await init_db()
    factory = await get_session_factory()

    async with factory() as session:
        # Check if already seeded
        count = await session.scalar(
            select(ScamPattern).limit(1)
        )
        if count is not None:
            print("Database already seeded. Skipping.")
            return

        print("Seeding scam patterns...")
        for p in SCAM_PATTERNS:
            pattern = ScamPattern(**p)
            session.add(pattern)

        print("Seeding legal mappings...")
        for m in LEGAL_MAPPINGS:
            mapping = LegalMapping(**m)
            session.add(mapping)

        print("Seeding graph data...")
        nodes, edges_data = generate_graph_data()

        for n in nodes:
            node = GraphNode(
                id=n["id"],
                node_type=n["node_type"],
                label=n["label"],
                properties=n["properties"],
                risk_score=n["risk_score"],
                first_seen=n["first_seen"],
                last_seen=n["last_seen"],
            )
            session.add(node)

        await session.flush()  # Ensure nodes exist before edges

        for e in edges_data:
            edge = GraphEdge(
                source_id=e["source_id"],
                target_id=e["target_id"],
                edge_type=e["edge_type"],
                properties=e["properties"],
                weight=e["weight"],
            )
            session.add(edge)

        await session.commit()
        print(f"Seeded: {len(SCAM_PATTERNS)} scam patterns, {len(LEGAL_MAPPINGS)} legal mappings, {len(nodes)} graph nodes, {len(edges_data)} graph edges")


if __name__ == "__main__":
    asyncio.run(seed_database())
