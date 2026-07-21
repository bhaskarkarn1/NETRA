<h1 align="center">NETRA</h1>

<p align="center">
  <strong>National Electronic Threat Recognition & Analysis</strong>
</p>

<p align="center">
  AI-Powered Digital Public Safety Intelligence Platform for India
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white"/>
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white"/>
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini_2.5_Flash-AI_Engine-4285F4?style=flat-square&logo=google&logoColor=white"/>
  <img alt="PostgreSQL" src="https://img.shields.io/badge/Neon_PostgreSQL-Cloud-336791?style=flat-square&logo=postgresql&logoColor=white"/>
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green?style=flat-square"/>
</p>

<p align="center">
  <a href="#problem-statement">Problem Statement</a> ·
  <a href="#solution">Solution</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#features">Features</a> ·
  <a href="#tech-stack">Tech Stack</a> ·
  <a href="#getting-started">Getting Started</a> ·
  <a href="#deployment">Deployment</a> ·
  <a href="#api-reference">API Reference</a>
</p>

---

## Problem Statement

> **PS 6: AI for Digital Public Safety — Defeating Counterfeiting, Fraud & Digital Arrest Scams**
>
> Build an AI-powered platform that detects and defeats counterfeiting, financial fraud, and the rapidly growing menace of "Digital Arrest" scams — where criminals impersonate law enforcement over video calls to extort victims. The solution must combine multi-modal detection (text, images, voice), real-time threat analysis, citizen awareness training, and investigative intelligence to protect India's digital ecosystem.

### Why This Problem Matters

India faces an **epidemic of digital fraud**. Data from the Ministry of Home Affairs (MHA) and Indian Cyber Crime Coordination Centre (I4C):

| Statistic | Value | Source |
|-----------|-------|--------|
| Financial losses to cyber fraud (2024) | **₹11,333 crore** | MHA / I4C Annual Report |
| Complaints registered (2024) | **31 lakh+** | National Cyber Crime Reporting Portal |
| YoY increase in digital arrest scams | **400%** | I4C Threat Advisory |
| Financial fraud as % of all cybercrime | **77.4%** | NCRB Crime in India 2023 |
| UPI transactions (March 2024 alone) | **13.89 billion** | NPCI |

Current solutions are **reactive** — victims file complaints *after* losing money. There is no national-scale tool for real-time scam detection, proactive citizen training, or automated investigative intelligence. NETRA addresses all three gaps.

---

## Solution

**NETRA** treats digital fraud as a **cyber-threat intelligence problem**, not a classification task. The platform operates across four integrated subsystems:

### Detect — Multi-Modal Scam Analysis
Upload suspicious messages (text, screenshots, URLs, voice) and NETRA performs:
- **Kill Chain™ Decomposition** — Maps the scam across 6 attack stages (Contact → Pretext → Pressure → Isolation → Extraction → Persistence)
- **Psychological Tactic Detection** — Identifies manipulation techniques (authority impersonation, urgency creation, fear induction, social proof)
- **Legal Section Mapping** — Maps applicable IPC, IT Act, and BNS 2023 sections with penalties
- **Victim Vulnerability Scoring** — Assesses danger level based on sophistication and targeting
- **SHA-256 Evidence Hashing** — Cryptographic chain-of-custody for forensic admissibility

### Investigate — Fraud Network Intelligence
- **Dual-Stage Entity Extraction** — Regex + LLM NER pipeline extracts Indian financial identifiers (phones, UPI IDs, bank accounts, IFSC, Aadhaar, PAN, URLs, persons, organisations, amounts)
- **Graph Auto-Population** — Extracted entities automatically linked into a fraud network graph with risk scoring
- **Cross-Case Syndicate Detection** — Entities appearing across multiple cases flagged as potential syndicate nodes
- **Influence-Based Risk Propagation** — Independent Cascade model propagates risk scores across the network
- **Causal Intervention Simulator** — "What if we freeze this bank account?" counterfactual analysis
- **Community Detection** — BFS-based connected components for automated syndicate clustering

### Simulate — Adversarial Scam Training
- **AI-Powered Scam Simulations** — Experience realistic Digital Arrest, KYC, and Investment scam scenarios
- **Guardian Agent** — AI monitors user susceptibility in real-time and triggers protective intervention
- **Debrief Analysis** — Post-simulation vulnerability assessment with psychological resilience recommendations
- **Inoculation Theory** — Grounded in McGuire (1961) and van der Linden (2017) research on building psychological resistance

### Command Center — Operational Dashboard
- **D3.js Charts** — Scam type distribution (donut), entity breakdown (bar), risk entity table
- **Live Threat Feed** — Real-time stream of detected scams and simulations
- **Geospatial Crime Map** — MapLibre GL JS heatmap with NCRB cybercrime hotspot overlay (Jamtara, Mewat, Bharatpur, Alwar)
- **Government Alert Generation** — I4C/NCRB-compliant alert documents and forensic dossier export

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        NETRA — System Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │                  FRONTEND · Next.js 15 (Turbopack)            │      │
│  │                                                                │      │
│  │  ┌───────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐  │      │
│  │  │ Dashboard │ │  Detect  │ │ Investigate│ │  Simulate    │  │      │
│  │  │ D3 Charts │ │ Multi-   │ │ D3 Force   │ │ AI Chat +    │  │      │
│  │  │ GeoMap    │ │ Modal    │ │ Graph      │ │ Debrief      │  │      │
│  │  │ Feed      │ │ OCR+Voice│ │ Search     │ │ Intervention │  │      │
│  │  └───────────┘ └──────────┘ └────────────┘ └──────────────┘  │      │
│  └────────────────────────────┬──────────────────────────────────┘      │
│                               │ REST API (40+ endpoints)                │
│  ┌────────────────────────────▼──────────────────────────────────┐      │
│  │                    BACKEND · FastAPI 0.115                     │      │
│  │                                                                │      │
│  │  ┌───────────────────────────────────────────────────────┐    │      │
│  │  │                    API ROUTERS                         │    │      │
│  │  │  detect.py · graph.py · simulate.py · dashboard.py    │    │      │
│  │  └─────────────────────┬─────────────────────────────────┘    │      │
│  │                        │                                       │      │
│  │  ┌─────────────────────▼─────────────────────────────────┐    │      │
│  │  │                  SERVICE LAYER                         │    │      │
│  │  │  LLM Service (Gemini 2.5 → Groq 70B → 8B → Rules)    │    │      │
│  │  │  Entity Extraction (Regex + LLM NER)                   │    │      │
│  │  │  Graph Population (Auto-link + Dedup + Risk)           │    │      │
│  │  │  Detection Agent (Prompt Engineering + JSON Parsing)   │    │      │
│  │  └─────────────────────┬─────────────────────────────────┘    │      │
│  │                        │                                       │      │
│  │  ┌─────────────────────▼─────────────────────────────────┐    │      │
│  │  │              DATA LAYER · Neon PostgreSQL               │    │      │
│  │  │  Cases · GraphNodes · GraphEdges · Simulations          │    │      │
│  │  │  AuditLogs · LegalMappings · DisruptionActions          │    │      │
│  │  │  EvaluationRuns · DiscoveredPatterns · ScamPatterns      │    │      │
│  │  └─────────────────────────────────────────────────────────┘    │      │
│  └────────────────────────────────────────────────────────────────┘      │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐      │
│  │                       AI / ML LAYER                             │      │
│  │  Primary:   Google Gemini 2.5 Flash (text + vision + JSON)     │      │
│  │  Fallback:  Groq Llama 3.3 70B → Llama 3.1 8B                 │      │
│  │  Last:      Rule-based heuristic engine (never fails)          │      │
│  │  NER:       Regex (Indian formats) + LLM extraction            │      │
│  │  Graph:     Independent Cascade risk propagation                │      │
│  └────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Kill Chain™ Decomposition** | 6-stage attack lifecycle mapping — goes beyond binary scam/not-scam classification |
| **Multi-Modal Input** | Text + Screenshot OCR (Gemini Vision) + Voice (Web Speech API) + Counterfeit Currency |
| **Auto-Entity Extraction** | Dual-stage regex + LLM NER for 14 Indian-specific entity types |
| **Fraud Network Graph** | D3 force-directed graph with auto-population from every analysed case |
| **Risk Propagation** | Independent Cascade model (Kempe et al., KDD 2003) across entity network |
| **Syndicate Detection** | BFS community detection identifies connected criminal infrastructure |
| **Causal Intervention** | "What if we freeze this entity?" counterfactual network disruption analysis |
| **Adversarial Simulation** | AI-powered scam role-play with guardian agent and real-time intervention |
| **Government Alerts** | I4C/NCRB-compliant alert documents with SHA-256 evidence hashing |
| **Forensic Dossier** | Downloadable evidence package with kill chain, entities, legal sections |
| **Counterfeit Detection** | 10-point RBI security feature verification for banknote images |
| **Geospatial Intelligence** | MapLibre GL JS crime heatmap with NCRB hotspot data overlay |
| **Graceful Degradation** | Gemini → Groq 70B → Groq 8B → Rule-based fallback — never fails |
| **Full Audit Trail** | Every agent action logged with model, latency, input/output summary |

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 15 (Turbopack) | React server components, optimised builds |
| **Visualisation** | D3.js v7 | Donut charts, bar charts, force-directed graphs, risk tables |
| **Mapping** | MapLibre GL JS | Geospatial crime heatmap with NCRB overlay |
| **Animation** | Framer Motion | Page transitions, micro-interactions |
| **Styling** | Tailwind CSS 4 | Design system with glassmorphism tokens |
| **Icons** | Lucide React | 100+ consistent vector icons |
| **Backend** | FastAPI 0.115 (Python 3.11) | Async REST API with OpenAPI auto-docs |
| **AI — Primary** | Google Gemini 2.5 Flash | Text analysis, vision OCR, structured JSON output |
| **AI — Fallback** | Groq (Llama 3.3 70B / 3.1 8B) | Automatic failover when Gemini is rate-limited |
| **Database** | Neon PostgreSQL + SQLAlchemy Async | Cloud-hosted with connection pooling |
| **Voice** | Web Speech API (en-IN) | Browser-native Hindi/English dictation |
| **Evidence** | SHA-256 | Cryptographic chain-of-custody hashing |
| **Backend Hosting** | Railway | Auto-deploy, SSL, health checks |
| **Frontend Hosting** | Vercel | CDN, edge network, auto-deploy |

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.11+ | With pip |
| Node.js | 18+ | With npm |
| Google Gemini API Key | — | Free tier at [aistudio.google.com](https://aistudio.google.com) |
| Groq API Key | — | Optional — fallback LLM at [console.groq.com](https://console.groq.com) |

### 1. Clone the Repository

```bash
git clone https://github.com/bhaskarkarn1/NETRA.git
cd NETRA
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Required — App
APP_NAME=NETRA
DEBUG=true
CORS_ORIGINS=["http://localhost:3000"]

# Required — AI (Google Gemini)
GOOGLE_API_KEY=your-gemini-api-key

# Optional — Fallback AI (Groq)
GROQ_API_KEY=your-groq-api-key

# Database (Neon PostgreSQL for production, SQLite for local dev)
DATABASE_URL=sqlite+aiosqlite:///./netra.db

# Optional — Geospatial heatmap
MAPBOX_TOKEN=your-mapbox-token
```

```bash
# Seed legal sections reference data (IPC, IT Act, BNS)
python -m app.data.seed_graph

# Start the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be running at `http://localhost:8000`.  
API documentation: `http://localhost:8000/docs` (Swagger UI)

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
# Create .env.local with the backend URL:
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local

# Start the development server
npm run dev
```

The frontend will be running at `http://localhost:3000`.

### 4. Verify Installation

```bash
# Check backend health
curl http://localhost:8000/api/dashboard/metrics

# Expected output:
# {"total_cases_analyzed": 0, "total_scams_detected": 0, ...}
```

Open `http://localhost:3000` in your browser — you should see the NETRA Command Center.

---

## Deployment

NETRA is deployed as a production system with automated CI/CD:

| Component | Service | URL | Status |
|-----------|---------|-----|--------|
| **Frontend** | Vercel | [netra-dusky.vercel.app](https://netra-dusky.vercel.app) | ✅ Live |
| **Backend** | Railway | Auto-deployed from `main` branch | ✅ Live |
| **Database** | Neon PostgreSQL | Cloud-hosted (US-East) | ✅ Live |
| **API Docs** | Swagger UI | `/docs` endpoint on backend | ✅ Auto-generated |

### Deploy Your Own Instance

**Backend (Railway):**
1. Fork this repository
2. Create a new Railway project → Deploy from GitHub
3. Set environment variables: `GOOGLE_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL` (Neon connection string)
4. Railway auto-detects the `Procfile` and deploys

**Frontend (Vercel):**
1. Import the `frontend/` directory to Vercel
2. Set `NEXT_PUBLIC_API_URL` to your Railway backend URL
3. Deploy — Vercel handles build and CDN automatically

---

## API Reference

NETRA exposes **40+ REST API endpoints** across 8 modules. Full interactive documentation available at `/docs` (Swagger UI).

### Detection API — `/api/detect`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/detect` | Analyse suspicious text — kill chain, tactics, legal sections, risk score |
| `POST` | `/api/detect/image` | Upload screenshot → Gemini Vision OCR → full detection pipeline |
| `POST` | `/api/detect/counterfeit` | Analyse banknote image for RBI security features (10-point verification) |
| `GET` | `/api/detect/{id}` | Retrieve specific case by ID |
| `GET` | `/api/detect/{id}/dossier` | Download forensic evidence dossier |
| `GET` | `/api/detect/{id}/intelligence` | Cross-case pattern analysis and syndicate detection |
| `GET` | `/api/detect/{id}/alert` | Generate I4C/NCRB-format alert document |
| `GET` | `/api/detect/recent/list` | List recently analysed cases |

### Graph Intelligence API — `/api/graph`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph/search` | Search entities by phone, UPI, bank account, etc. |
| `GET` | `/api/graph/node/{id}` | Get entity details with risk score |
| `GET` | `/api/graph/network/{id}` | Get entity's connected fraud network |
| `GET` | `/api/graph/recent` | Recently discovered entities |
| `GET` | `/api/graph/stats` | Graph ecosystem statistics |
| `POST` | `/api/graph/propagate-risk` | Influence-based risk propagation across graph |
| `GET` | `/api/graph/communities` | BFS community detection — syndicate clustering |
| `GET` | `/api/graph/intervention/{id}` | Causal intervention — "what if we freeze this?" |

### Simulation API — `/api/simulate`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/simulate/scenarios` | List available scam simulation scenarios |
| `POST` | `/api/simulate/start` | Start a new adversarial scam simulation |
| `POST` | `/api/simulate/{id}/respond` | Send response to simulated scammer |
| `GET` | `/api/simulate/{id}/debrief` | Post-simulation vulnerability analysis |

### Dashboard API — `/api/dashboard`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/metrics` | Real-time platform metrics |
| `GET` | `/api/dashboard/threat-feed` | Live threat activity feed |
| `GET` | `/api/dashboard/analytics` | Chart-ready analytics (scam distribution, entity breakdown) |
| `GET` | `/api/dashboard/geospatial` | Geocoded scam locations with NCRB hotspot overlay |

---

## Kill Chain™ Framework

NETRA introduces a **6-stage Cyber Fraud Kill Chain** — adapted from Lockheed Martin's Cyber Kill Chain for Indian social engineering attacks:

```
S1 CONTACT    →   S2 PRETEXT    →   S3 PRESSURE   →   S4 ISOLATION   →   S5 EXTRACTION  →   S6 PERSISTENCE
 Initial           Fabricated        Urgency &          Prevent victim      Financial /        Maintain control,
 approach           cover story       fear induction     from consulting     data theft         prevent reporting
```

Each stage is scored with:
- **Confidence level** (0–1) — how clearly this stage is present
- **Evidence text** — extracted directly from the original message
- **Progression indicator** — how far the attack has evolved

---

## Entity Extraction Pipeline

Dual-stage NER (Named Entity Recognition) designed for Indian financial identifiers:

**Stage 1 — Regex Pattern Matching:**
| Entity | Pattern | Example |
|--------|---------|---------|
| Phone Numbers | `+91-XXXXX-XXXXX`, `98XXXXXXXX` | +91-98765-43210 |
| UPI IDs | `name@upi`, `name@paytm`, `name@ybl` | fraudster@ybl |
| Bank Accounts | 9–18 digit account numbers | 1234567890123456 |
| IFSC Codes | `SBIN0001234` format | HDFC0001234 |
| Aadhaar Numbers | `XXXX XXXX XXXX` (12-digit) | 1234 5678 9012 |
| PAN Numbers | `ABCDE1234F` format | ABCDE1234F |
| Monetary Amounts | `₹50,000`, `Rs. 1,00,000`, `INR 50000` | ₹2,50,000 |

**Stage 2 — LLM-Based Extraction (Gemini 2.5 Flash):**
- Persons, organisations, locations, designations, identity documents, temporal markers

---

## Research Foundation

NETRA draws on published research in:

| Area | Source |
|------|--------|
| Kill Chain methodology | Lockheed Martin Cyber Kill Chain; Mitnick's attack lifecycle |
| Psychological manipulation | Cialdini's Principles of Influence (2001); Kahneman & Tversky Prospect Theory (1979) |
| Authority compliance | Milgram's Obedience Research (1963) |
| Network influence propagation | Kempe, Kleinberg & Tardos — Maximizing Influence, KDD 2003 |
| Graph representation learning | Hamilton et al. — Inductive Representation Learning on Large Graphs, NeurIPS 2017 |
| Network resilience | Albert, Jeong & Barabási — Error and Attack Tolerance, Nature 2000 |
| Inoculation theory | McGuire (1961); van der Linden — Inoculating Against Misinformation, Science 2017 |
| Indian regulatory framework | IPC Sections 419/420, IT Act Sections 66C/66D, BNS 2023 provisions |

---

## Project Structure

```
NETRA/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── detection.py           # Detection Agent — LLM prompt engineering
│   │   ├── data/
│   │   │   └── seed_graph.py          # Legal sections seed data (IPC, IT Act, BNS)
│   │   ├── evaluation/
│   │   │   └── benchmark.py           # Automated evaluation with TF-IDF baseline
│   │   ├── routers/
│   │   │   ├── dashboard.py           # Metrics, analytics, threat feed, geospatial
│   │   │   ├── detect.py              # Detection, image OCR, counterfeit, alerts, dossier
│   │   │   ├── graph.py               # Fraud network CRUD, propagation, communities
│   │   │   └── simulate.py            # Adversarial simulation engine
│   │   ├── services/
│   │   │   ├── entity_extraction.py   # Dual-stage NER (regex + LLM)
│   │   │   ├── graph_population.py    # Auto-graph population & risk scoring
│   │   │   ├── graph_intelligence.py  # Community detection, PageRank, centrality
│   │   │   ├── baseline_model.py      # TF-IDF + SVM baseline for evaluation
│   │   │   └── llm.py                 # LLM service (Gemini → Groq → fallback)
│   │   ├── config.py                  # Environment configuration
│   │   ├── database.py                # SQLAlchemy async models (12 models)
│   │   └── main.py                    # FastAPI application entry point
│   ├── requirements.txt
│   ├── Procfile                       # Railway deployment
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx               # Command Center dashboard
│   │   │   ├── detect/page.tsx        # Multi-modal detection page
│   │   │   ├── investigate/page.tsx   # Fraud network graph explorer
│   │   │   ├── simulate/page.tsx      # Adversarial simulation trainer
│   │   │   ├── evaluation/page.tsx    # Benchmark evaluation UI
│   │   │   ├── layout.tsx             # Root layout with navbar + footer
│   │   │   └── globals.css            # Design system tokens
│   │   ├── components/
│   │   │   ├── charts/                # D3 donut, bar, risk table
│   │   │   ├── graph/                 # D3 force-directed fraud graph
│   │   │   └── shared/                # Navbar, common components
│   │   ├── hooks/
│   │   │   └── use-voice-input.ts     # Web Speech API hook (en-IN)
│   │   └── lib/
│   │       ├── api.ts                 # REST API client
│   │       ├── types.ts               # TypeScript interfaces
│   │       └── utils.ts               # Utility functions
│   ├── package.json
│   └── tsconfig.json
│
├── docs/
│   ├── submission/
│   │   └── index.html                 # Technical submission document (A4, 12 pages)
│   ├── research-abstract.md           # Research paper abstract
│   ├── architecture.md                # Architecture documentation
│   └── screenshots/                   # Application screenshots
│
├── railway.toml                       # Railway deployment config
└── README.md
```

---

## Database Schema

12 SQLAlchemy async models:

| Model | Table | Purpose |
|-------|-------|---------|
| `Case` | `cases` | Detection results with kill chain, legal sections, evidence hash |
| `ScamPattern` | `scam_patterns` | Reference data for 8 known scam types |
| `LegalMapping` | `legal_mappings` | IPC, IT Act, BNS sections reference |
| `GraphNode` | `graph_nodes` | Fraud network entities with risk scores |
| `GraphEdge` | `graph_edges` | Entity relationships with weights |
| `Simulation` | `simulations` | Training session records |
| `SimulationTurn` | `simulation_turns` | Individual messages in simulations |
| `AuditLog` | `audit_logs` | Complete agent action traceability |
| `DisruptionAction` | `disruption_actions` | Bank freeze / telecom block payloads |
| `EvaluationRun` | `evaluation_runs` | Benchmark results (precision, recall, F1) |
| `DiscoveredPattern` | `discovered_patterns` | Auto-discovered scam clusters |

---

## Screenshots

<table>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/dashboard.png" alt="Command Center"/>
      <p align="center"><strong>Command Center</strong> — D3 charts, metrics, geospatial map, threat feed</p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/detect.png" alt="Detect"/>
      <p align="center"><strong>Detect</strong> — Multi-modal input (text, screenshot OCR, counterfeit, voice)</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/investigate.png" alt="Investigate"/>
      <p align="center"><strong>Investigate</strong> — Auto-populated fraud network graph with risk propagation</p>
    </td>
    <td width="50%">
      <img src="docs/screenshots/simulate.png" alt="Simulate"/>
      <p align="center"><strong>Simulate</strong> — Adversarial AI scam training with intervention</p>
    </td>
  </tr>
</table>

---

## Technical Submission

The full technical submission document (12-page A4 format) is available at [`docs/submission/index.html`](docs/submission/index.html). It includes:

- Executive Summary
- Problem Statement (PS 6)
- Architecture & Technology Stack
- AI Pipeline & Methodology
- Kill Chain Framework
- Entity Extraction Pipeline
- Evaluation & Performance Metrics
- Competitive Analysis
- Security, Scalability & Responsible AI
- Government, Social & Business Impact
- References (12 academic citations)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **Google AI Studio** — Gemini 2.5 Flash API powering core AI analysis
- **Indian Cyber Crime Coordination Centre (I4C)** — Complaint format standards that inspired alert generation
- **National Crime Records Bureau (NCRB)** — Cybercrime statistics informing threat models
- **Reserve Bank of India** — Banknote security feature specifications for counterfeit detection
- **Groq** — Llama inference API providing fallback LLM capability

---

<p align="center">
  <strong>NETRA</strong> — Built by Bhaskar Ranjan Karn for ET GEN AI Hackathon 2026
</p>
<p align="center">
  PS 6: AI for Digital Public Safety — Defeating Counterfeiting, Fraud & Digital Arrest Scams
</p>
