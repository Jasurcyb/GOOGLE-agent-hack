# Devpost Submission Kit — All Things Agentic Hackathon

Deadline: **Aug 31, 2026 @ 5:00pm PDT**. Category: **The Fortified Enterprise Fleet**.

---

## 1. Devpost Form — Text Description (copy-paste ready)

### Features and functionality
Regression Hunter AI is an autonomous multi-agent defense fleet that intercepts GitHub pull
requests and predicts, explains, and prevents regressions in downstream data assets *before
merge*. End-to-end autonomous pipeline: GitHub PR webhook → AST diff analysis across 5
languages (Python, TypeScript, Java, Go, C#) → enterprise lineage traversal via DataHub MCP →
Gemini 3.5 Flash reasoning chain → autonomous test synthesis in an isolated sandbox → GitHub
PR report + DataHub assertions + interactive Next.js impact dashboard. Key capabilities:

- **Blast radius quantification** — pinpoints exact downstream Snowflake tables, Kafka topics,
  dbt models, and dashboards affected by a code change via column-level lineage.
- **Grounded root-cause hypotheses** — Gemini 3.5 Flash formulates hypotheses strictly bound to
  quoted evidence; unverified hypotheses are flagged, not hallucinated.
- **Autonomous test synthesis** — generates and executes regression tests in a sandbox.
- **Institutional Memory Bank** — cross-session context persisted in Google Cloud Firestore.
- **Security guardrails** — prompt-injection detection, PII/secret redaction, zero-trust input
  validation, tool-call budgets.

### Technologies used
- **Gemini 3.5 Flash** via the **Gemini API** (`google-genai` SDK)
- **Google GenAI SDK** as the Google Agent Framework
- **Google Cloud Run** (containerized deployment, `cloudbuild.yaml` CI/CD) and
  **Google Cloud Firestore** (Enterprise Memory Bank, Firebase free tier — no billing required)
- DataHub MCP (Model Context Protocol) client, FastAPI, Next.js 15 / React 19, Pytest

### Other data sources used
DataHub Metadata & Column-Level Lineage Graph (via MCP), GitHub webhook payloads and commit
history, repository source snapshots, risk calibration corpus (`evals/corpus.json`).

### Findings and learnings
- Grounding beats prompting: forcing the agent to cite lineage-graph evidence eliminated
  hallucinated blast-radius claims (verified via 61 automated tests + evidence citations).
- Injection-proofing untrusted PR content before it reaches the LLM is cheap and effective.
- Firestore's free Spark tier is fully sufficient for a cross-session enterprise Memory Bank,
  removing the need for a billing account in the demo environment.

---

## 2. Architecture Diagram

Ready-made image: **`docs/architecture-diagram.png`** — upload it to the Devpost form.
(Editable source: the mermaid block in README → https://mermaid.live if regeneration is needed.)

---

## 3. Demo Video Script (~4 min, single take, no editing)

| Time | Shot | What to show |
| :--- | :--- | :--- |
| 0:00–0:40 | Screen: slides/README | Problem: renames break dashboards without failing tests. Value: catch it pre-merge. |
| 0:40–1:20 | Google Cloud Console | Open **Firestore** (agent_memory_bank collection with real docs) + Cloud Shell session — proof of Google Cloud deployment. |
| 1:20–2:20 | Terminal: `python scripts/run_gemini_demo.py` | Live pipeline: PR listener → AST symbols → EvidenceBundle → Risk 85/CRITICAL (policy floor: breaking change on regulated payment path) → Gemini hypotheses → sandbox tests → Firestore persist → publisher. |
| 2:20–3:00 | Terminal: `python scripts/run_firestore_demo.py` | Cross-session recall: "which past regressions touched payments?" — Memory Bank answers from Firestore. |
| 3:00–3:40 | Browser: Next.js dashboard + real PR comment | Blast-radius graph, risk scorecard, PR sticky report. |
| 3:40–4:00 | Slides: architecture | Fleet diagram; one line on track alignment + why it's production-ready. |

Checklist before recording: `pip install -r requirements.txt` ✔, optional `GEMINI_API_KEY` set
(mock provider is fine), Firestore demo pre-run once so the collection is non-empty.

---

## 4. Pre-Submit Checklist

- [ ] `python -m pytest` → 61/61 green
- [ ] `python scripts/run_gemini_demo.py` runs clean
- [ ] `python scripts/run_firestore_demo.py` persists to Firestore (free Firebase project)
- [ ] Architecture diagram PNG exported and attached
- [ ] Demo video (~4 min) uploaded to YouTube (public), GCP Console visible in frame
- [ ] Repo pushed; if private → share with testing@devpost.com and cloudhackathons@google.com
- [ ] Devpost form: category = The Fortified Enterprise Fleet, all text fields pasted from above

## 5. Bonus Points (optional)

- Blog post on dev.to / Medium: "Building an autonomous regression-defense fleet with Gemini
  3.5, google-genai and Firestore" — include the phrase "created for the All Things Agentic
  Hackathon".
- Post on X/LinkedIn with hashtag **#AllThingsAgenticHackathon** and the demo video.
