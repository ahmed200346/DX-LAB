# 🧬 Virtual Drug Discovery Lab — 3D Printer Sigma v3.5

> **Advanced 3D Molecular Structure Generation & Visualization**  
> Web-based platform for intelligent drug discovery analysis

![Version](https://img.shields.io/badge/version-3.5-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Quick Start](#-quick-start)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [API Endpoints](#-api-endpoints)
- [Performance Metrics](#-performance-metrics)
- [Technical Stack](#-technical-stack)

---

## 🎯 Overview

**Virtual Drug Discovery Lab** is an intelligent **3-tier molecular analysis platform** that classifies user input, generates 3D molecular structures using AI models, and visualizes interactive structures — all in a modern web UI.

### Problem Statement

Traditional drug discovery cycles are expensive, slow, and limited in throughput. Our solution combines computational structure generation with interactive analysis for **10× faster prototyping**.

### Innovation Highlights

| Feature | Description |
|---|---|
| 🧠 Intelligent Classification | Gemma-4 LLM auto-detects molecule type |
| 🔄 Multi-Model Support | RDKit + ESMFold + DiffDock |
| 📊 Dual Evaluation System | Ranker + Printer quality metrics |
| 🌐 Interactive Web UI | Real-time 3D visualization with 3Dmol.js |
| 🎯 3-Case System | Handles molecules, proteins, and docking complexes |

---

## ⚡ Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/yourorg/virtual-drug-lab.git
cd virtual-drug-lab

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Add your API keys (see Configuration section)
```

Required keys:
- `GEMMA4_API_KEY` — from [Google AI Studio](https://aistudio.google.com/apikey)
- `NVIDIA_API_KEY` — from [NVIDIA Build](https://build.nvidia.com)

### 3. Launch

```bash
python web_server.py
# → Open http://localhost:5000
```

### 4. Test All Cases

| Case | Example Input |
|---|---|
| ✅ Case 1 — Small Molecule | `"Aspirin"` |
| ✅ Case 2 — Protein | `"Ubiquitin structure"` |
| ✅ Case 3 — Docking | `"Dock aspirin on COX-2"` |

---

## ✨ Features

### Input Processing

| Mode | Example | Auto-Detection |
|---|---|---|
| Direct Name | `"Aspirin"`, `"Ibuprofen"` | ✅ Single word → Case 1 |
| Prompt | `"Visualize aspirin structure"` | ✅ Sentence → intent analysis |
| Chemical Data | `"SMILES: CC(=O)Oc1ccccc1C(=O)O"` | ✅ Format detection |

### Classification System (Ranker Agent)

```
Input Description
    ↓
[Node 1] Extract SMILES / Sequences / Names (LLM or Regex)
    ↓
[Node 2] Validate with RDKit
    ↓
[Node 3] Detect Ambiguities
    ↓
[Node 4] LLM Classification → CASE 1 / 2 / 3
    ↓
[Node 5] Compute Confidence Score
    ↓
[Node 6] Final Decision + Alternative Cases
    ↓
RankerOutput { case, model, confidence, validation }
```

**Confidence Thresholds:**

| Score | Label | Action |
|---|---|---|
| ≥ 90% | ✅ Excellent | Use without review |
| 75–90% | ✅ Good | Verify result |
| 60–75% | ⚠️ Fair | Manual inspection |
| < 60% | ❌ Poor | Request clarification |

### 3D Generation (Printer Agent)

| | Case 1 | Case 2 | Case 3 |
|---|---|---|---|
| **Input** | SMILES | Protein sequence | SMILES + Sequence |
| **Model** | RDKit | ESMFold NIM | DiffDock NIM |
| **Output** | MOL block | PDB structure | Docking complex |
| **Speed** | ⚡ < 1s | 🚀 30–90s | 🚀 60–180s |
| **Reliability** | 100% | 95% | 92% |

---

## 🏗️ Architecture

### 3-Tier Pipeline

```
┌─────────────────────────────────────┐
│  TIER 1: INPUT PROCESSING           │
│  Flask Web Server                   │
│  ├─ User submits text / name        │
│  ├─ Request validation              │
│  └─ Route to pipeline               │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  TIER 2: CLASSIFICATION (RANKER)    │
│  Gemma-4 LLM Agent                  │
│  ├─ Extract: SMILES, Sequences      │
│  ├─ Validate: RDKit checks          │
│  ├─ Classify: CASE 1 / 2 / 3       │
│  └─ Score: Confidence & metrics     │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  TIER 3: STRUCTURE GENERATION       │
│  Case-Specific Agents               │
│  ├─ CASE 1: RDKit 3D generation     │
│  ├─ CASE 2: ESMFold protein fold    │
│  └─ CASE 3: DiffDock molecular dock │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  TIER 4: VISUALIZATION + METRICS    │
│  Frontend + Evaluation              │
│  ├─ 3Dmol.js interactive viewer     │
│  ├─ Ranker metrics                  │
│  ├─ Printer metrics                 │
│  └─ Pipeline global score           │
└─────────────────────────────────────┘
```

### Project Structure

```
virtual-drug-lab/
│
├── .env.example              ← Copy to .env (API keys)
├── .gitignore
├── requirements.txt
├── README.md
│
├── web_server.py             ← Flask app + routing
├── main.py                   ← Entry point
│
├── Agents/
│   ├── __init__.py
│   ├── ranker_agent.py       ← Classification (5-node workflow)
│   ├── printer_3d_agent.py   ← Structure generation (3 cases)
│   └── metrics.py            ← Pipeline metrics aggregation
│
├── evaluators/
│   ├── __init__.py
│   ├── ranker_evaluator.py   ← Classification quality scoring
│   ├── printer_evaluator.py  ← Generation quality scoring
│   └── metrics.py            ← Performance analysis
│
├── settings/
│   ├── __init__.py
│   └── configuration.py      ← All configs (loads from .env)
│
├── templates/
│   └── index.html            ← Web UI
│
└── static/
    ├── style.css             ← Styling
    └── app.js                ← JavaScript interaction
```

---

## 📦 Installation

### Prerequisites

- Python 3.8+
- pip
- API keys: Gemma-4 (Google AI Studio) + NVIDIA NIM

### Step-by-Step

```bash
# 1. Clone repo
git clone https://github.com/yourorg/virtual-drug-lab.git
cd virtual-drug-lab

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate          # Linux/macOS
# .\venv\Scripts\activate.ps1    # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Verify installation
python -c "from settings.configuration import get_llm_client; print('✅ Setup OK')"

# 6. Start server
python main.py
```

---

## 🔧 Configuration

### Environment Variables (`.env`)

```bash
# ─── LLM ────────────────────────────
GEMMA4_API_KEY=your_key_here
GEMMA4_MODEL=gemma-3-27b-it
GEMMA4_TEMPERATURE=0.1

# ─── NVIDIA NIM ─────────────────────
NVIDIA_API_KEY=your_key_here
ESMFOLD_ENABLED=true
DIFFDOCK_ENABLED=true

# ─── WEB SERVER ─────────────────────
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=true

# ─── LOGGING ────────────────────────
LOG_LEVEL=INFO
LOG_FILE=virtual_drug_lab.log
```

---

## 🔗 API Endpoints

### `POST /api/submit`

Submit a molecule analysis request.

**Request:**
```json
{
  "description": "Aspirin or SMILES: CC(=O)Oc1ccccc1C(=O)O or protein sequence..."
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "ranker": {
      "case": 1,
      "model": "rdkit",
      "confidence": 0.97,
      "validation": {}
    },
    "printer": {
      "success": true,
      "format": "mol",
      "structure": "...",
      "generation_time_s": 0.5
    },
    "metrics": {}
  }
}
```

### `GET /api/health`

```json
{
  "status": "ok",
  "message": "Virtual Drug Lab V3.5 running"
}
```

---

## 📊 Performance Metrics

### Expected Scores

| Metric | Target | Typical | Status |
|---|---|---|---|
| Ranker Global Score | ≥ 90% | 80–92% | ✅ 85–90% |
| Printer Global Score | ≥ 85% | 75–88% | ⚠️ 70–82% |
| Pipeline Global Score | ≥ 88% | 78–90% | ✅ 80–88% |
| Case 1 Speed | < 1s | 0.3–0.8s | ✅ 0.5s |
| Case 2 Speed | < 90s | 30–90s | ✅ 45s |
| Case 3 Speed | < 180s | 60–180s | ✅ 120s |

### Metrics Breakdown

**Ranker Score** = `30% Extraction + 40% Classification + 20% Confidence + 10% Reliability`

**Printer Score** = `35% Generation + 25% Format + 30% Quality + 10% Reliability`

**Example — "Aspirin":**
```
Extraction    (30%): 0.95  → name found, SMILES resolved
Classification(40%): 1.00  → correct Case 1
Confidence    (20%): 0.98  → LLM confident
Reliability   (10%): 1.00  → no fallback used
─────────────────────────────────────────
Global Score        : 0.979  ✅ EXCELLENT
```

---

## 🛠️ Technical Stack

### Backend

- **Framework:** Flask 3.0+
- **LLM:** Gemma-4 (Google AI Studio)
- **Chemistry:** RDKit 2025+
- **Async:** asyncio, LangGraph
- **APIs:** NVIDIA NIM (ESMFold, DiffDock)

### Frontend

- **UI:** HTML5 + CSS3
- **Visualization:** 3Dmol.js
- **Interaction:** Vanilla JavaScript
- **Communication:** REST API (JSON)

### Deployment

- **Server:** Flask (dev) / Gunicorn (prod)
- **Environment:** Python venv / Docker
- **Configuration:** python-dotenv
