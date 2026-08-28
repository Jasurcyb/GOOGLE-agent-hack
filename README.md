# 🛡️ Regression Hunter AI
### Autonomous Pre-Deploy Regression Defense Fleet powered by Google Gemini 3.5 & DataHub MCP

[![All Things Agentic Hackathon](https://img.shields.io/badge/All_Things_Agentic_Hackathon-Google_%2B_Devpost-4285F4?style=for-the-badge&logo=google)](https://allthingsagentichackathon.devpost.com/)
[![Track: The Fortified Enterprise Fleet](https://img.shields.io/badge/Track-Fortified_Enterprise_Fleet-34A853?style=for-the-badge)](#)
[![Model: Google Gemini 3.5](https://img.shields.io/badge/Model-Gemini_3.5_Flash-FBBC05?style=for-the-badge&logo=googlegemini)](#)
[![Cloud: Google Cloud Run & Firestore](https://img.shields.io/badge/Cloud-Google_Cloud_Run-EA4335?style=for-the-badge&logo=googlecloud)](#)
[![Tests: 61/61 Passed](https://img.shields.io/badge/Tests-61%2F61_Passed-brightgreen.svg?style=for-the-badge)](tests/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg?style=for-the-badge)](LICENSE)

---

## 🎯 Executive Summary & The Problem

Modern software delivery suffers from a catastrophic visibility gap: **code changes frequently break downstream analytics dashboards, ETL pipelines, and ML models without failing any localized unit tests.**

When an engineer renames a database field, modifies a serializer, or alters an enum in a backend microservice:
1. Local unit tests pass green.
2. The pull request is merged.
3. Days later, executive revenue dashboards show `$0`, Kafka stream ingestion silently drops records, or production fraud models fail due to null feature drift.

### The Solution: Autonomous Multi-Agent Defense Fleet
**Regression Hunter AI** intercepts GitHub pull requests in real time, extracts deep AST code-level deltas across multiple languages (Python, TypeScript, Java, Go, C#), traverses the enterprise metadata lineage graph via **DataHub MCP (Model Context Protocol)**, and executes a multi-agent reasoning chain powered by **Google Gemini 3.5 / 2.5 Flash** to:
* **Quantify blast radius:** Pinpoint exact downstream tables, dashboards, and consumers affected by the code change.
* **Formulate grounded hypotheses:** Detect root causes with strict quotation of evidence and zero hallucinations.
* **Autonomously synthesize and validate tests:** Generate executable regression tests in an isolated sandbox.
* **Persist institutional state:** Store session memories and reasoning traces in **Google Cloud Firestore Memory Bank**.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph INGESTION["1. Autonomous Ingestion Layer"]
        PR[GitHub Pull Request Webhook] --> Listener[PR Listener Service: FastAPI]
        Listener --> DiffAnalyzer[Diff Analyzer & AST Classifier]
    end

    subgraph KNOWLEDGE["2. Lineage & Enterprise Knowledge"]
        DiffAnalyzer --> CodeIntel[Code Intelligence: AST & Symbols]
        CodeIntel --> MCP[DataHub MCP Client]
        MCP --> LineageGraph[(DataHub Metadata & Column Lineage Graph)]
    end

    subgraph AGENTIC_FLEET["3. Multi-Agent Reasoning Fleet (Gemini 3.5)"]
        LineageGraph --> ContextOrch[Context Orchestrator]
        ContextOrch --> EvidenceBundle[Structured Evidence Bundle]
        
        EvidenceBundle --> ReasoningAgent[Reasoning Agent: Gemini 3.5 Flash]
        ReasoningAgent --> RiskEngine[Risk Scorer & Policy Evaluator]
        RiskEngine --> TestAgent[Test Planning & Sandbox Agent]
        
        subgraph SECURITY["Security & Guardrails"]
            InjectionGuard[Model Armor / Prompt Injection Filter]
            Redactor[PII & Secret Redaction Engine]
        end
        ReasoningAgent -.-> InjectionGuard
        ReasoningAgent -.-> Redactor
    end

    subgraph TELEMETRY["4. Google Cloud Telemetry & Memory Bank"]
        ReasoningAgent --> MemoryBank[(Google Cloud Firestore Memory Bank)]
        TestAgent --> MemoryBank
        MemoryBank --> AuditTrace[OpenTelemetry Audit & Reasoning Logs]
    end

    subgraph OUTPUT["5. Action & UI Delivery"]
        RiskEngine --> Publisher[DataHub & GitHub Publisher]
        Publisher --> GHComment[PR Sticky Markdown Report]
        Publisher --> WebUI[Next.js Interactive Impact Dashboard]
    end
```

---

## 🤖 Alignment with Hackathon Tracks

### Primary Track: **The Fortified Enterprise Fleet**
* **Agent Registry & Discovery:** Decoupled, modular agent roles (`ReasoningAgent`, `TestAgent`, `RiskEngine`, `ImpactAnalyzer`).
* **Core Execution & State:** Asynchronous, long-running agent pipeline with **Cloud Memory Bank** (Google Cloud Firestore persistence).
* **Security & Governance:** Strict zero-trust input validation, prompt injection defense, and PII redaction engine.
* **Observability:** OpenTelemetry-compatible tracing, latency tracking, and verifiable evidence citation.

### Secondary Capabilities: **The Taskmaster**
* Completely autonomous end-to-end pipeline: PR webhook $	o$ AST parsing $	o$ MCP traversal $	o$ Gemini reasoning $	o$ Sandbox test execution $	o$ PR comment publication without human hand-holding.

---

## ⚡ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **LLM Engine** | **Google Gemini 3.5 / 2.5 Flash** | Deep multi-step reasoning, hypothesis generation, root-cause analysis |
| **Agent Framework** | **Google GenAI SDK (`google-genai`)** | Official Google SDK for high-performance agent communication |
| **Cloud Infrastructure** | **Google Cloud Run** | Scalable containerized microservice execution (scales to zero) |
| **State & Memory** | **Google Cloud Firestore** | Enterprise Memory Bank for persistent cross-session context |
| **Metadata Protocol** | **DataHub MCP Client** | Model Context Protocol integration for column-level graph lineage |
| **Frontend UI** | **Next.js 15 + React 19 + Tailwind CSS** | Interactive Blast Radius graph and Risk Scorecard visualization |
| **Testing & CI** | **Pytest (61 passed unit & integration tests)** | Robust, production-grade test coverage |

---

## 🚀 Quickstart & Spin-up Instructions

### Prerequisites
* Python 3.11+
* (Optional) `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com) (Free tier)

### 1. Clone & Setup Environment
```bash
# Clone the repository
git clone https://github.com/Jasurcyb/regression-hunter-agentic.git
cd regression-hunter-agentic

# Install dependencies
pip install -r requirements.txt
pip install google-genai pytest
```

### 2. Set Gemini API Key (Optional for live LLM calls)
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key-here"

# Linux / macOS
export GEMINI_API_KEY="your-gemini-api-key-here"
```
*(Note: If `GEMINI_API_KEY` is omitted, the system automatically uses deterministic mock providers for offline testing).*

### 3. Run the Automated Demo Pipeline
```bash
python scripts/run_gemini_demo.py
```

### 4. Run Test Suite
```bash
python -m pytest
```
*(All 61 unit, integration, and security tests will run and pass).*

---

## ☁️ Google Cloud Deployment (Cloud Run)

Regression Hunter AI includes complete production configuration for **Google Cloud Run** with automatic scale-to-zero (zero idle cost).

### 1-Command Cloud Run Deploy:
```bash
gcloud run deploy regression-hunter-agentic     --source .     --region us-central1     --platform managed     --allow-unauthenticated     --min-instances 0     --max-instances 2     --set-env-vars GEMINI_MODEL=gemini-2.5-flash
```

---

## 📊 Live Demo Output Example

```text
======================================================================
=== ALL THINGS AGENTIC HACKATHON: REGRESSION HUNTER AI (Gemini 3.5 + Google Cloud) ===
======================================================================
1. [PR Listener] Run Key: acme/payment-service:42:a1b2c3d4...
2. [Repo Worker] Snapshot created. Size: 1024 bytes
3. [Diff Analyzer] File: payment/service.py | Language: python | Added Lines: 13
4. [Code Intelligence] Discovered AST Symbols: ['payment.service.process_payment']
5. [Context Orchestrator] EvidenceBundle Built (Downstream Blast Radius: 4 assets)
6. [Risk Engine] Risk Score: 85/100 | Level: HIGH
7. [Reasoning Agent] Generated & Verified Hypotheses via Gemini 3.5: 2
8. [Test Agent Sandbox] Sandbox Validation Result: Valid=True | Generated Tests=2
9. [Google Cloud Memory Bank] Audit Telemetry Persisted -> local://memory_bank/...
10. [Publisher] GitHub Sticky Report & DataHub Assertions Published Successfully!
```

---

## 📄 License
Licensed under the [Apache License, Version 2.0](LICENSE).
