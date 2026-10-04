# Retrieval evaluation

Actual measurements; no LLM required.

| Mode | Split | Bid | Questions | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|---|---|---|---:|---:|---:|---:|---:|
| dense | development | all | 6 | 0.3333 | 0.5 | 1.0 | 0.5417 |
| dense | development | Bid1 | 3 | 0.3333 | 0.3333 | 1.0 | 0.5 |
| dense | development | Bid2 | 3 | 0.3333 | 0.6667 | 1.0 | 0.5833 |
| dense | held_out | all | 16 | 0.375 | 0.8125 | 0.875 | 0.5781 |
| dense | held_out | Bid1 | 8 | 0.5 | 0.875 | 1.0 | 0.6979 |
| dense | held_out | Bid2 | 8 | 0.25 | 0.75 | 0.75 | 0.4583 |
| hybrid | development | all | 6 | 0.5 | 0.8333 | 0.8333 | 0.6389 |
| hybrid | development | Bid1 | 3 | 0.3333 | 0.6667 | 0.6667 | 0.4444 |
| hybrid | development | Bid2 | 3 | 0.6667 | 1.0 | 1.0 | 0.8333 |
| hybrid | held_out | all | 16 | 0.9375 | 1.0 | 1.0 | 0.9583 |
| hybrid | held_out | Bid1 | 8 | 1.0 | 1.0 | 1.0 | 1.0 |
| hybrid | held_out | Bid2 | 8 | 0.875 | 1.0 | 1.0 | 0.9167 |
| rerank | development | all | 6 | 0.3333 | 1.0 | 1.0 | 0.6389 |
| rerank | development | Bid1 | 3 | 0.0 | 1.0 | 1.0 | 0.4444 |
| rerank | development | Bid2 | 3 | 0.6667 | 1.0 | 1.0 | 0.8333 |
| rerank | held_out | all | 16 | 0.5 | 0.75 | 0.875 | 0.6427 |
| rerank | held_out | Bid1 | 8 | 0.375 | 0.75 | 0.875 | 0.5667 |
| rerank | held_out | Bid2 | 8 | 0.625 | 0.75 | 0.875 | 0.7188 |