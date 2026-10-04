# Work log

## 4 October 2026

- Inspected workspace and initialized Git because the provided folder had no repository.
- Built typed schemas first to establish the 20-field and evidence contracts before agent implementation.
- Added PDF/HTML ingestion, metadata and cleanup; audited all provided files to expose missing-page and table risks.
- Implemented section/token-aware chunks, dense vectors, BM25, rank fusion, reranking, filters and versioned incremental indexing because the assignment requires an independently usable search engine.
- Implemented separate extraction groups, addendum reconciliation, validator and report/Q&A roles with shared typed state and targeted bounded repairs.
- Added a configurable LLM adapter and JSONL traces; generation requires local endpoint configuration rather than hard-coded secrets.
- Added CLI and REST routes over shared services to avoid duplicated behavior.
- Tested parsing, real SKU relationships, HTML label retention, incremental updates, filter isolation, citation integrity, feedback bounds, malformed provider JSON, provider timeout and API validation.
- Prepared source-verified retrieval labels and actual benchmark outputs. See outputs/retrieval_evaluation.md for measurements and README for validation status.
- Kept OCR/UI/deployment bonuses outside scope. No live extraction or Q&A results will be claimed without an actual configured provider run.
- Verified editable package installation and retained the initial retrieval results. Final hybrid Recall@5 was 1.0000 and MRR@5 0.9583 on the 16-question regression partition. These are retrieval measurements; the partition was inspected for a parser bug and is not claimed to be an untouched benchmark.
- Final checks: 23 tests passed, dependency compatibility check passed, packaged CLI startup passed, and absent LLM configuration produced the intended actionable error. One upstream TestClient deprecation warning remains.

Failures observed during setup were handled explicitly: package/model downloads and pytest temporary fixture access required approved execution outside the sandbox. These restrictions are environment-specific, separate from application behavior.

React frontend follow-up: implemented the explicitly requested UI with React/TypeScript/Vite, dynamic bid discovery, search filters, citation inspection, question and extraction flows, saved records, JSON export, indexing, errors and responsive layout. Reasons are recorded in FRONTEND_DESIGN.md. Added API catalog/saved-record tests; all 24 tests and the frontend production build pass. Real browser search and missing-provider behavior were verified. Preview runs on port 5173 with API on 8000.

Environment repair: an existing Python 3.12 environment was overwritten by Python 3.14 while retaining cp312 compiled packages. Restored the Python 3.12 launcher/configuration with the available bundled interpreter; backend imports, all 24 tests, and pip dependency checks passed. Setup now explicitly selects Python 3.12 to prevent mixed binaries. Test configuration clears provider credentials so local .env settings cannot cause live calls or secret-bearing failure reports.

UI refresh: replaced the ivory/indigo palette with black/white/neutral grays and replaced serif typography with Inter plus system sans-serif fallbacks, following the user's design request. Simplified heading scale, removed the search form shadow, and improved passage typography. Desktop and 390px mobile views were inspected; no document-level horizontal overflow. Production build passed. Screenshot saved in docs/screenshots/monochrome-workspace.png.

Deployment packaging: added Loom demo link at README top; Dockerfiles for Python 3.12 CPU backend and production React/Nginx frontend; Compose with internal API networking, health checks, read-only bid mounts and persistent model/index/output volumes; build context exclusions prevent baking in .env, documents and traces. Added explicit CLI host selection for container networking while retaining localhost default. AWS EC2 guide explains private SSH preview, HTTPS load balancer/access control, backups, single-process constraints and reasons. Docker Compose configuration validates; actual image builds/runtime and AWS deployment remain unverified because Docker Desktop's Linux engine is not running.
