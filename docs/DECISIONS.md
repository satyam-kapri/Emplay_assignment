# Implementation decision record

Each material choice records its requirement, reason, tradeoff and verification. Initial architecture choices are in PROJECT_PLAN.md. Updated 4 October 2026.

## D01: explicit agent state machine

Requirement: cooperating specialized agents, shared typed state, parallelism and validator feedback.
Selection: asyncio orchestrator, immutable worker results, Pydantic messages and a per-field repair limit.
Reason: the workflow has a known graph; explicit transitions are easier to inspect than autonomous conversation routing. Ingestion and search are deterministic tool roles; reasoning roles call the configurable LLM.
Tradeoff: scheduling and state merging belong to this application rather than a framework.
Evidence: tests exercise targeted repair and exhausted repair budgets. Real model behavior still requires live verification.
Revisit: a substantially more dynamic workflow or durable distributed execution.

## D02: Qdrant local plus SQLite active generations

Requirement: dense retrieval, metadata filtering, incremental updates and traceable passages.
Selection: persistent Qdrant vectors, SQLite source records and active file generations, in-process lock.
Reason: vectors are staged before SQLite activation; failed parsing/indexing leaves the previous generation usable. New bid folders do not re-embed unchanged files. Keyword rankings are reconstructed from active filtered records.
Tradeoff: local Qdrant supports one process; keyword corpus reconstruction is suitable for a small assignment corpus, not a production fleet. Old vector collections remain on disk if the embedding model changes.
Evidence: tests cover unchanged files, changed files, deleted files, bid filtering and failure preservation.
Revisit: concurrent processes or a large corpus; migrate the adapter to Qdrant server and a scalable keyword backend.

## D03: coordinate-based borderless table fallback

Requirement: preserve specification/SKU relationships and generalize beyond provided bid names.
Observation: default PDF table detection found no table on the supplied Dell spec sheet, and flattened text mixed SKU columns with descriptions.
Selection: generic SKU/Description header detection and aligned identifier coordinates; continuation requires multiple aligned identifiers in a specs document. Keep the original text alongside recovered tables.
Reason: a text-grid heuristic split words into spurious columns during inspection; coordinate grouping retained the actual row relationship.
Tradeoff: handles an identifiable two-column layout, not arbitrary image or merged-cell tables. No document-specific SKU values are embedded in production code.
Evidence: rendered page inspected; real-file regression tests verify CPU, RAM and storage SKU mappings.
Revisit: observed unmatched layouts; do not silently claim all table forms are covered.

## D04: retain HTML labels with values

Observation: saved portal HTML wraps labels and values in separate sibling nodes.
Selection: preserve nearby generic label elements while extracting leaf text; remove navigation and interactive controls.
Reason: a closing-date value without its label can be confused with publication or question deadlines.
Tradeoff: heuristic DOM parsing can retain irrelevant portal text; it avoids a BidNet-only selector dependency.
Evidence: regression test for Closing Date plus the actual saved portal content in corpus audit.

## D05: configurable compatible LLM adapter

Requirement: configurable model/provider, structured messages, timeout/bad JSON recovery, no secrets in code.
Selection: HTTP chat-completions adapter with schema instructions, JSON object mode, Pydantic validation and three bounded transport/schema attempts.
Reason: no LLM endpoint/model/key is configured in the workspace. A compatible hosted or local service can be supplied without changing agent code.
Tradeoff: providers without this endpoint/JSON mode require another adapter; JSON-mode output is validated locally rather than relying on provider-specific strict schemas.
Evidence: mocked HTTP tests cover malformed output repair and timeout exhaustion. No fabricated LLM-generated deliverables are included.
Revisit: user chooses a provider requiring a different protocol, or live schema reliability warrants provider-native strict outputs.

## D06: exact evidence checks plus semantic critic

Requirement: every value supported, no hallucinated obligations, latest field-specific override.
Selection: verify chunk existence, bid/file/page/locator identity and verbatim quote; then ask a separate critic to assess semantic support and consistency. Rejected fields are re-retrieved and re-extracted; final failures become null with failure notes.
Reason: a citation can exist while failing to support the value. Blank forms and missing time zones must not become invented obligations or dates.
Tradeoff: semantic critic quality depends on the configured model; its confidence scores are heuristics, not statistical calibration. It cannot certify absent facts on unreadable pages.
Evidence: citation mismatch, unsupported title and retry-limit tests; actual accuracy is unverified until live extraction is reviewed.

## D07: no OCR and explicit partial corpus reporting

Observation: Bid1 RFP physical pages 54-59 have no extractable text.
Selection: warn per page and propagate partial status; keep readable pages indexed. OCR remains deferred as requested.
Reason: hiding missing pages could make an unsupported null appear to prove absence.
Tradeoff: inaccessible page content can reduce field completeness. The warning deliberately remains visible in outputs.
Revisit: core evaluation shows required facts only exist on scanned pages, or OCR is authorized as added scope.

## D08: measurement before ranking claims

Selection: 22 source-verified questions with six development and sixteen held-out questions; dense, hybrid and reranked modes use identical evidence corpus and explicit bid filters.
Reason: retrieval is independently graded and must be measured, not inferred from plausible answers. File/page/quote relevance labels are reproducible.
Tradeoff: this small set is not a statistically strong external benchmark; it mostly has one required passage per question. Multi-passage metric logic is tested separately.
Evidence: eval/questions.json and generated retrieval reports; no tune-after-test claims are permitted.

## D09: Python 3.12 validation environment

Observation: default host Python 3.14 failed virtual-environment pip bootstrapping; bundled Python 3.12 was available.
Selection: local .venv based on Python 3.12, isolated dependencies, version lock from the verified environment.
Reason: keeps changes out of global packages and meets the assignment's Python version requirement.
Tradeoff: Windows requires network access for packages/models and a usable Python install; tested setup is documented rather than asserting compatibility on every platform.

## D10: CLI and REST; bonus UI deferred

Selection: one-command extraction includes indexing; standalone search and thin localhost FastAPI routes share service code. Outputs and traces are ordinary JSON/JSONL files.
Reason: meets reproducibility and tool requirements while concentrating effort on required retrieval and orchestration.
Tradeoff: API requests run synchronously to completion; no job queue, authentication or deployment hardening is included. Intended for local assignment use.

## D11: raw text retained but excluded from reasoning prompts

Selection: retain original source text in audit storage; agents receive selected chunk text and metadata through Evidence.prompt_data().
Reason: sending raw pages alongside each chunk would bypass the retrieval boundary, duplicate content and inflate context.
Tradeoff: traces and source storage remain larger than minimal text-only indices. Logs never contain credentials.

## D12: measured default and addendum sentence integrity

Observation: initial development MRR@5 was 0.7000 for hybrid versus 0.6250 for reranked hybrid and 0.5833 for dense-only. The reranker is not assumed to improve this corpus.
Selection: configurable hybrid default; keep reranking available and benchmark all three configurations. This selection uses development results, not an assertion of broad superiority.
Observation: a retrieval miss showed uppercase amendment obligations being incorrectly split into heading fragments.
Selection: keep addendum page context together before token chunking; version that stage separately. Also fix the generic continuation-header ambiguity in specification tables.
Reason: document grammar and identifier associations must survive parsing; these are correctness repairs, not changes to expected answers.
Evidence: real-file table continuation test; initial report retained before the final benchmark. The inspected nominal hold-out partition is disclosed as a regression set, not a pristine final test.

Outcome: after correctness repairs, development MRR is 0.6389 for both hybrid and reranked hybrid. Final regression Recall@5 is 1.0000 for hybrid versus 0.8750 for reranked hybrid; no universal reranking gain is claimed. Default hybrid avoids an additional inference pass, while reranking remains selectable.

## D13: source-stated document date metadata

Selection: extract only explicitly labeled issue/document/publication dates and retain their source representation, including day-month-name formats.
Reason: the supplied RFP uses an issue date such as 26-MAY-2024; treating a submission deadline as a document issue date would corrupt precedence metadata. Parser revision v5 refreshes prior metadata as well as future indexing.
Evidence: a regression test distinguishes issue date from closing date. Dates without an explicit recognized source label remain null.

## D14: reproducible local Git submission

Selection: commit application code, tests, configuration examples, supplied input documents, labels, measured retrieval reports and decision documentation. Exclude credentials, virtual environments, cached model weights, local indices and temporary test files.
Reason: the reviewer can reproduce parsing tests and the benchmark from the repository while keeping machine-specific and secret data outside version control. Existing Git author configuration is used; no remote publishing is performed by this task.
