# Regression Hunter AI — План реализации

> Документ для отслеживания прогресса. Отмечайте `[x]` выполненные задачи.
> При возобновлении работы ищите первый неотмеченный пункт.

---

## Этап 0 — Фундамент (2–3 дня)

### 0.1. Инициализация monorepo
- [x] Создать структуру каталогов: `apps/`, `packages/`, `db/`, `infra/`, `evals/`, `scripts/`
- [x] `pyproject.toml` с workspace-настройками (Python)
- [x] `pnpm-workspace.yaml` для frontend
- [x] Базовый `docker-compose.yml` с профилями `core`, `demo`, `llm-mock`, `sandbox`
- [x] Корневой `README.md`

### 0.2. Pydantic-контракты (`packages/contracts/`)
- [x] `RegressionAssessment` — корневая модель отчёта
- [x] `SymbolChange`, `CodeEdge`, `ImpactNode`, `ImpactEdge`
- [x] `RiskAssessment`, `RiskFactor`, `Recommendation`
- [x] `EvidenceBundle` v1.0
- [x] CloudEvents 1.0 envelopes: `pr.received.v1`, `repository.ready.v1`, `diff.analyzed.v1`, `code.graph.built.v1`, `impact.resolved.v1`, `context.built.v1`, `assessment.scored.v1`, `recommendations.ready.v1`, `publish.requested.v1`, `published.v1`
- [x] JSON Schema для REST, сообщений и structured LLM output

### 0.3. Доменная модель (`packages/domain/`)
- [x] Сущности: `PullRequest`, `AnalysisRun`, `SymbolChange`, `ImpactGraph`, `RiskAssessment`, `Recommendation`, `Delivery`
- [x] Политики: `PolicyConfig` — пороги, policy floors, allowed actions
- [x] Типы ошибок: `AnalysisError`, `PolicyViolation`, `InsufficientEvidence`
- [x] Enum'ы: `RiskLevel`, `ChangeType`, `EdgeType`, `BindingType`, `Resolution`

### 0.4. База данных
- [x] Alembic migrations для 12 таблиц
  - [x] `pull_requests`
  - [x] `analysis_runs` (партицирование по месяцам)
  - [x] `symbol_changes`
  - [x] `code_edges`
  - [x] `asset_bindings`
  - [x] `impact_nodes`
  - [x] `impact_edges`
  - [x] `risk_assessments`
  - [x] `risk_factors`
  - [x] `recommendations`
  - [x] `generated_artifacts`
  - [x] `llm_invocations` (партицирование)
  - [x] `deliveries`
  - [x] `outbox_events` (партицирование)
- [x] Seed-данные: demo-команды, политики, risk rules (`db/seed/`)

### 0.5. Docker Compose `core` профиль
- [x] PostgreSQL с pg_partman
- [x] Redis
- [x] RabbitMQ
- [x] MinIO
- [x] Базовый Dockerfile для Python-воркеров (multi-stage, non-root, read-only rootfs)

### 0.6. GitHub App
- [x] Создать GitHub App: `metadata:read`, `pull_requests:read+write`, `checks:write`, `issues:write`
- [x] `packages/github-adapter/` — HMAC verification, webhook handler
- [x] GitHub API client (short-lived installation tokens)
- [x] `apps/pr-listener/` — FastAPI endpoint `POST /v1/webhooks/github`

### 0.7. DataHub identity
- [x] Service principal, scopes
- [x] Mock DataHub endpoint в Compose
- [x] `packages/datahub-adapter/` — базовый Context Kit integration

### 0.8. Mock LLM (`packages/llm-gateway/`)
- [x] Детерминированные JSON fixtures
- [x] Provider adapter interface (для OpenAI/Responses API)
- [x] Token budget tracking

### 0.9. Один replayable fixture
- [x] Пример PR + seeded DataHub граф
- [x] Скрипт `scripts/replay-fixture.sh`
- [x] Демонстрация lifecycle: webhook → run created → stored

**Критерий завершения Этапа 0:** verified webhook-to-run lifecycle работает локально.

---

## Этап 1 — Proof of Value (неделя 1)

### 1.1. PR Listener (`apps/pr-listener/`)
- [x] FastAPI webhook endpoint `POST /v1/webhooks/github`
- [x] HMAC verification, delivery ID dedup
- [x] Transactional outbox: persist run + publish `pr.received.v1`
- [x] Health probes: `/healthz`, `/readyz`, `/metrics`

### 1.2. Repo Worker (`apps/repo-worker/`)
- [x] Shallow clone (без hooks/package scripts)
- [x] Patch materialization (base + head)
- [x] Source archival в S3/MinIO (content-addressed, envelope encryption)
- [x] Publish `repository.ready.v1`

### 1.3. Diff Analyzer (`apps/diff-analyzer/`)
- [x] File deltas: adds/modifies/deletes/renames
- [x] Rename detection: `similarity_index` + AST symbol matching
- [x] Publish `diff.analyzed.v1`

### 1.4. Code Intelligence — Python (`apps/code-intelligence/python_analyzer/`)
- [x] LibCST для lossless edits + tree-sitter
- [x] `Symbol` records: FQN, signature, visibility, source range, decorators, test membership
- [x] Parse confidence per symbol
- [x] Semantic delta classification: public signature change, control-flow edit, SQL edit, exception-handling removal, auth/financial edit, serialization/schema change, dependency upgrade, deleted/renamed symbol
- [x] Edges: `CALLS`, `IMPORTS`, `OVERRIDES`, `IMPLEMENTS`, `READS_DATASET`, `WRITES_DATASET`, `PUBLISHES_TOPIC`, `CONSUMES_TOPIC`, `SCHEDULED_BY`, `EXPOSED_BY`
- [x] Entry-point detection: FastAPI/Flask routes, Celery jobs, Airflow/Dagster/Prefect DAGs, cron, CLI
- [x] Bounded reverse traversal (cycle-safe)

### 1.5. Code Intelligence — TypeScript (`apps/code-intelligence/typescript_analyzer/`)
- [x] `ts-morph` sidecar
- [x] Тот же `LanguageAnalyzer` protocol
- [x] Entry-points: Express/Next.js routes, serverless handlers

### 1.6. Code Graph (`packages/code-graph/`)
- [x] Language-neutral symbol/edge model
- [x] Bounded reverse traversal (cycle-safe, budget)
- [x] Compressed normalized graph storage
- [x] Source ranges (не целые файлы) для LLM context
- [x] Publish `code.graph.built.v1`

### 1.7. DataHub Adapter (`packages/datahub-adapter/`)
- [x] `DataHubContextPort` через Agent Context Kit
- [x] Bounded impact neighborhood: entity type, platform, description, schema/columns, tags, glossary terms, domain, docs, owners
- [x] Upstream/downstream lineage (default depth 3, expand to 5 for critical)
- [x] Column-level lineage when SQL column altered
- [x] Dashboards, DataJobs/DataFlows, ML features/models/deployments
- [x] Quality assertions, incidents, freshness, usage, criticality properties
- [x] `DataHubGraphPort` — SDK/GraphQL для bulk fetch
- [x] Snapshot: entity URNs, aspect versions/timestamps, traversal params, paths

### 1.8. Context Orchestrator (`apps/context-orchestrator/`)
- [x] Code-to-Asset Mapper: 4 уровня binding evidence
  - [x] Level 1: `datahub_assets.yaml` / decorators → AUTHORITATIVE
  - [x] Level 2: OpenLineage, dbt manifest, Airflow metadata, Spark logs → AUTHORITATIVE
  - [x] Level 3: AST-extracted SQL/Kafka/REST refs → AUTHORITATIVE
  - [x] Level 4: DataHub search/semantic search → DISCOVERED, confidence < 1.0
- [x] Evidence Bundle v1.0: redacted, token-budgeted, content-addressed attachments
- [x] Deterministic prioritization: direct paths → production → contractual changes → criticality → ownership gaps → test coverage
- [x] Publish `context.built.v1`

### 1.9. Impact Analyzer (`apps/impact-analyzer/`)
- [x] NetworkX bounded subgraph (max 10k nodes / 50k edges)
- [x] Blast-radius calculation: `min(20, 4*ln(1 + weighted_downstream_assets))`
- [x] Explicit truncation reporting
- [x] Publish `impact.resolved.v1`

### 1.10. Демонстрация Этапа 1
- [x] Replay fixture → evidence graph displayed
- [x] Deterministic medium/high risk report written
- [x] Скриншоты/JSON в `examples/`

**Критерий завершения Этапа 1:** Python/TS diff → symbol analysis → DataHub lineage → evidence graph → deterministic risk report.

---

## Этап 2 — Агент и обратная связь (неделя 2)

### 2.1. Risk Engine (`apps/risk-engine/`)
- [x] V1 additive scorer: 6 факторов
  - [x] Change hazard (0–25)
  - [x] Blast radius (0–20)
  - [x] Business criticality (0–25)
  - [x] Test gap (0–15)
  - [x] Operational history (0–10)
  - [x] Mitigating evidence (−10–0)
- [x] `risk_score = clamp(0, 100, sum(contributions))`
- [x] Policy floors: breaking change + regulated/payment asset + no regression test → floor 85
- [x] Уровни: LOW 0–29, MEDIUM 30–59, HIGH 60–79, CRITICAL 80–100
- [x] `regression_probability`: logistic calibration V1
- [x] `impact_severity`: normalized blast radius + criticality
- [x] `confidence`: 30% mapping + 25% lineage + 20% resolution + 15% test + 10% calibration
- [x] Confidence < 70 → neutral status
- [x] Publish `assessment.scored.v1`

### 2.2. Reasoning Agent (`apps/reasoning-agent/`)
- [x] State machine: `COLLECTING → GROUNDED → SCORED → RECOMMENDING → PUBLISHED | PARTIAL | FAILED`
- [x] Max 12 tool calls, max 3 lineage expansions, 80k token ceiling, wall-clock budget
- [x] Read-only DataHub MCP tools: `search`, `search_documents`, `get_lineage`, `get_lineage_paths_between`, `get_entities`, schema/query tools
- [x] Strict JSON Schema output (`RegressionAssessment`)
- [x] System contract: untrusted input, cite `evidence_refs`, `INSUFFICIENT_EVIDENCE` when missing
- [x] Developer contract: EvidenceBundle + risk features + test inventory + policy + strict schema
- [x] Hypotheses: `{mechanism, impacted_urns, evidence_refs, confidence, recommended_test_ids}`
- [x] Every hypothesis needs ≥1 evidence path or label `UNVERIFIED`

### 2.3. Test Agent (`apps/test-agent/`)
- [x] Test planner: verified hypotheses → narrowest runnable tests
- [x] Per-mechanism test matrix:
  - [x] Pure behavior → pytest/JUnit/Jest/unit
  - [x] REST/GraphQL → API contract/integration
  - [x] UI path → Playwright smoke/regression
  - [x] SQL/dbt → dbt schema/data test, Great Expectations
  - [x] Pipeline/job → containerized integration
  - [x] ML feature → feature schema, drift, inference regression
- [x] Ranking: coverage of risk factors, runtime, fixture feasibility, redundancy
- [x] Generated patches → object storage → sandbox validation (parse, format, lint, run)
- [x] Publish `recommendations.ready.v1`

### 2.4. Publisher (`apps/publisher/`)
- [x] Outbox-backed transaction per target
- [x] DataHub write-back:
  - [x] Regression Report context document (`Regression Hunter / <repo> / PR-<number> / <sha>`)
  - [x] `RegressionAssessment` custom entity (or DataJob/DataProcessInstance fallback)
  - [x] Structured properties: `regression_hunter.latest_risk_score`, `latest_assessment_urn`, `latest_assessed_at`, `open_recommendation_count`
  - [x] `RegressionHunter:AtRisk` tag (high/critical confirmed only, expiry/reconciliation)
  - [x] Assertion candidates (PROPOSED/review-required)
  - [x] Test/review recommendations as structured owner-addressable recommendations
- [x] GitHub:
  - [x] Check Run: `Regression Hunter / pre-deploy impact`
  - [x] Labels: `regression-risk:low|medium|high|critical`, `regression-needs-review`
  - [x] Upserted bot comment (hidden marker `<!-- regression-hunter:repo:pr -->`)
- [x] Delivery ledger: idempotency keys, read-after-write verification
- [x] Retry with exponential backoff + jitter
- [x] Partial report on nonessential enrichment failure

### 2.5. API Gateway (`apps/api-gateway/`)
- [x] `POST /v1/webhooks/github` — webhook (delegated to pr-listener)
- [x] `POST /v1/runs` — manual start/replay
- [x] `GET /v1/runs/{run_id}` — complete report
- [x] `GET /v1/runs/{run_id}/graph?view=impact` — Cytoscape graph
- [x] `GET /v1/pull-requests/{repo}/{number}/latest` — PR check UI
- [x] `GET /v1/runs/{run_id}/events` — SSE live status
- [x] `POST /v1/recommendations/{id}/approve` — approve test patch
- [x] `POST /v1/runs/{run_id}/publish` — retry/explicit publish
- [x] `POST /v1/runs/{run_id}/override` — reasoned risk override
- [x] `GET /v1/healthz`, `/readyz`, `/metrics`
- [x] OIDC bearer auth, RBAC, repository/team entitlements

### 2.6. Демонстрация Этапа 2
- [x] End-to-end video: payment/ML impact scenario
- [x] Скриншоты/JSON в `examples/`

**Критерий завершения Этапа 2:** Полный цикл от PR до GitHub check + comment + DataHub write-back + test recommendations.

---

## Этап 3 — Robustness и polish (неделя 3)

### 3.1. Дополнительные анализаторы
- [x] Java (`apps/code-intelligence/java_analyzer/`) — JavaParser sidecar
- [x] Go (`apps/code-intelligence/go_analyzer/`) — Go AST helper
- [x] C# (`apps/code-intelligence/csharp_analyzer/`) — Roslyn sidecar
- [x] Все: `LanguageAnalyzer` protocol, `analysis_confidence`, `Resolution` enum (EXACT/HEURISTIC/UNKNOWN)

### 3.2. Безопасность
- [x] Context redaction: DLP scan, secret removal, PII omission
- [x] Source sandbox: non-root, read-only, CPU/memory/PID/time quotas, default-deny egress
- [x] Prompt injection defense: untrusted classification, tool allowlist, JSON I/O only
- [x] LLM trace storage: encrypted, retention policy, `store:false` where supported
- [x] Provider allowlist, regional route selection

### 3.3. Frontend (`apps/web/`)
- [x] Next.js + React + Tailwind + Cytoscape
- [x] Overview: run state, score/probability/severity/confidence, policy decision, PR diff summary
- [x] Impact graph: code/pipeline/dataset/dashboard/model/owner nodes, edge evidence/confidence
- [x] Risk timeline: score over commits and previous PRs
- [x] Affected owners: notification status, ownership gaps, acknowledge/override actions
- [x] Critical assets: DataHub summary, quality signals, downstream count, open recommendations
- [x] Dataset Explorer: drill-through к каноническому DataHub entity
- [x] Regression history: similar signatures, incident links, evaluation outcomes, calibration view
- [x] Polling run state during processing; graph pages on demand
- [x] Не получает: raw secrets, private descriptions, LLM prompts, unredacted source

### 3.4. Approval flow
- [x] Asset owner approval для test patches/assertions
- [x] UI: approve, override with reason/expiry
- [x] Audit trail для всех override'ов

### 3.5. Reliability
- [x] Idempotent delivery ledger
- [x] Partial-result handling (`analysis.partial.v1`)
- [x] LLM/DataHub mocks для CI
- [x] Reanalysis: new SHA → new run, never mutate old assessment
- [x] GitHub comment upsert через hidden marker (один текущий отчёт, не spam)

### 3.6. Observability
- [x] OpenTelemetry traces: `github_delivery_id` → `run_id` → events → DataHub/MCP calls → LLM hashes → write receipts
- [x] Prometheus metrics
- [x] Sentry integration
- [x] Alert on: DLQ age, cost/run, score distribution drift, low-confidence rate, DataHub/LLM errors, stale check runs
- [x] Replay console для DLQ

**Критерий завершения Этапа 3:** Java/Go/C# работают, UI полностью функционален, observability покрывает все сервисы.

---

## Этап 4 — Production credibility (неделя 4)

### 4.1. Risk calibration
- [x] Evaluation corpus: historical PRs linked to incidents/rollbacks
- [x] Split by repository and time (prevent leakage)
- [x] Metrics: PR-level precision/recall, Brier score, ECE, critical-recall, false-block rate, mean time-to-explanation
- [x] Logistic calibration V1 → gradient-boosted model (versioned, fallback to V1)
- [x] Train only on post-merge/deploy outcomes

### 4.2. DataHub assertions
- [x] Assertion candidates: non-null, range, schema compat, freshness
- [x] `PROPOSED` lifecycle (never enable enforcement without owner approval)
- [x] Draft assertion definition в recommendation/document

### 4.3. Historical signals
- [x] Prior incidents from DataHub
- [x] Deploy frequency
- [x] Coverage from application history

### 4.4. Kubernetes
- [x] Helm chart (`infra/helm/`)
- [x] KEDA autoscaling on queue depth
- [x] Managed PostgreSQL HA (PITR)
- [x] RabbitMQ quorum queues across zones
- [x] Redis HA
- [x] Versioned object storage
- [x] Secrets manager + workload identity
- [x] Separate namespaces: ingress, agent, publisher, sandbox
- [x] Bounded concurrency + circuit breakers для LLM и DataHub

### 4.5. SLO dashboards
- [x] Webhook ack <2s
- [x] First in-progress check <15s
- [x] P95 standard PR report <8min
- [x] Critical alert publication <10min
- [x] No duplicate GitHub comment/actions
- [x] 99.9% durable event acceptance

### 4.6. Security review
- [x] Threat model walkthrough (9 угроз из документа)
- [x] Signed images, SBOM/CVE gates
- [x] Pinned parsers, dependency scanning
- [x] Separate sandbox runtime

**Критерий завершения Этапа 4:** Kubernetes deployment работает, SLO dashboards показывают метрики, security review пройден.

---

## Этап 5 — Submission hardening (неделя 5)

### 5.1. One-command demo
- [x] `scripts/setup-demo.sh` — запуск всего стека с seeded данными
- [x] Example PRs ready to replay
- [x] `docker compose --profile core --profile demo --profile llm-mock up`

### 5.2. Documentation
- [x] Architecture docs published
- [x] API docs (OpenAPI spec)
- [x] `examples/` с JSON evidence, screenshots

### 5.3. Three narratives
- [x] Revenue dashboard impact
- [x] Broken ETL/Kafka consumer
- [x] ML feature impact

### 5.4. Full integration/evaluation suites
- [x] Unit tests: feature calculation, policy floor, path traversal, adapter parsers, client retries
- [x] Golden fixtures: renamed/deleted symbols, dynamic calls, generated code, SQL extraction, API routes, Kafka, DAGs
- [x] Contract tests: CloudEvent + REST schema, consumer-driven tests
- [x] Integration tests: Docker Compose + seeded DataHub + RabbitMQ + PostgreSQL + GitHub mock + LLM mock
- [x] End-to-end PR replays: single comment, labels, DataHub writebacks, evidence paths, idempotent rerun
- [x] Regression benchmark: historical PRs → incidents/rollbacks, no loss in critical-recall

### 5.5. CI/CD pipeline
- [x] GitHub Actions: formatting/type-check → unit → contract → SBOM/vulnerability scan → image build/sign → integration → ephemeral deployment smoke → Helm/Kubernetes policy checks
- [x] Progressive deployment with metric-based rollback

**Критерий завершения Этапа 5:** One-command demo работает, три narrative проходят, все тесты зелёные, документация опубликована.

---

## Future Production Hardening (Дальнейшие усовершенствования)


- [ ] Type-aware language resolution
- [ ] Coverage provider integrations
- [ ] Incident/change-management connectors
- [ ] DataHub change-event invalidation
- [ ] Richer owner notification channels
- [ ] Canary/deployment correlation
- [ ] Model calibration (continuous)
- [ ] Enterprise tenancy/residency

---

## Definition of Done

Релиз готов к пилоту, когда реальный PR может:

1. [x] Идентифицировать изменённые символы с analyzer confidence
2. [x] Доказать хотя бы один code-to-DataHub lineage path
3. [x] Рассчитать воспроизводимый risk score
4. [x] Предложить evidence-grounded test recommendations
5. [x] Сохранить отчёт и assessment обратно в DataHub
6. [x] Обновить один GitHub check/comment/label идемпотентно
7. [x] Показать reviewer-readable impact graph с owner/action traceability

---

## Зависимости между этапами

```
Этап 0 (фундамент)
    ↓
Этап 1 (proof of value)
    ↓
Этап 2 (агент + feedback)
    ↓
Этап 3 (robustness + polish)
    ↓
Этап 4 (production credibility)
    ↓
Этап 5 (submission hardening)
    ↓
Post-release Hardening

```

## Ключевые технологии

| Компонент | Технология |
|---|---|
| Backend | Python 3.12+, FastAPI, Celery |
| Брокер | RabbitMQ |
| БД | PostgreSQL 16+ + Alembic + pg_partman |
| Кэш/блокировки | Redis |
| Хранилище | S3/MinIO |
| DataHub | Agent Context Kit + MCP Server |
| LLM | OpenAI Responses API (adapter pattern) |
| Frontend | Next.js, React, Tailwind CSS, Cytoscape.js |
| Infra | Docker Compose, Helm, KEDA, ArgoCD |
| Observability | OpenTelemetry, Prometheus, Sentry |
| CI/CD | GitHub Actions |
| Code analysis | LibCST, tree-sitter, ts-morph, JavaParser, Roslyn |