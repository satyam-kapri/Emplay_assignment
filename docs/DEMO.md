# Five-to-ten-minute live demo guide

1. Explain the architecture in PROJECT_PLAN.md and the decision record (one minute).
2. Show `index --bid Bid1` and `index --bid Bid2`, then repeat indexing to show skipped unchanged files (one minute).
3. Search a deadline and exact SKU with dense/hybrid/reranked modes; inspect file/page/quote provenance (one minute).
4. Show the measured evaluation table and discuss failures, dataset size and lack of external unseen corpus (one minute).
5. With a configured provider, run `python -m scripts.demo` in advance. Show both bid JSON files, all 20 fields, null reasons and the Addendum 2 deadline/change evidence (two minutes).
6. Show the generated sample Q&A log including a cross-bid warranty question (one minute).
7. Inspect one JSONL trace and a test demonstrating rejected-field repair; finish with known limitations (one minute).

The demo script makes paid/provider calls when configured. A demo recording has not been produced. Without a configured LLM, show search and tests and explicitly identify generation as unverified.
