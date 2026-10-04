import hashlib
import json
from pathlib import Path
from rfp_intelligence.schemas import SearchRequest


def relevant(hit, expected):
    return hit.file == expected["file"] and hit.page == expected["page"] and expected["quote"].lower() in hit.text.lower()


def metrics(hits, expected):
    ranks = [next((i for i, hit in enumerate(hits, 1) if relevant(hit, passage)), None) for passage in expected]
    return {**{f"recall@{k}": sum(rank is not None and rank <= k for rank in ranks) / len(ranks) for k in [1, 3, 5]},
            "mrr@5": 1 / min(r for r in ranks if r is not None) if any(r is not None for r in ranks) else 0}


def evaluate(service, questions):
    labels = json.loads(Path(questions).read_text(encoding="utf-8"))
    records = []
    for mode in ["dense", "hybrid", "rerank"]:
        for question in labels:
            hits = service.search(SearchRequest(query=question["question"], bid_ids=[question["bid_id"]], mode=mode, top_k=5))
            records.append({"mode": mode, "id": question["id"], "bid_id": question["bid_id"],
                            "split": question.get("split", "held_out"), **metrics(hits, question["expected"]),
                            "hits": [{"id": h.id, "file": h.file, "page": h.page} for h in hits]})
    summary = []
    for mode in ["dense", "hybrid", "rerank"]:
        for split in ["development", "held_out"]:
            for bid in ["all", "Bid1", "Bid2"]:
                rows = [r for r in records if r["mode"] == mode and r["split"] == split and (bid == "all" or r["bid_id"] == bid)]
                if rows:
                    summary.append({"mode": mode, "split": split, "bid": bid, "questions": len(rows),
                                    **{key: round(sum(r[key] for r in rows) / len(rows), 4) for key in ["recall@1", "recall@3", "recall@5", "mrr@5"]}})
    corpus = "\n".join(sorted(e.id for e in service.store.evidence()))
    report = {"embedding_model": service.config.embedding_model, "rerank_model": service.config.rerank_model,
              "corpus_sha256": hashlib.sha256(corpus.encode()).hexdigest(), "summary": summary, "per_question": records,
              "limitations": "Small manually labeled set; no external unseen corpus; relevance uses specified passage substrings. The held_out partition was inspected for a parser correctness repair and is now a regression set, not an untouched test set."}
    output = service.config.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "retrieval_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Retrieval evaluation", "", "Actual measurements; no LLM required.", "",
             "| Mode | Split | Bid | Questions | Recall@1 | Recall@3 | Recall@5 | MRR@5 |",
             "|---|---|---|---:|---:|---:|---:|---:|"]
    for row in summary:
        lines.append("| " + " | ".join(str(row[k]) for k in ["mode", "split", "bid", "questions", "recall@1", "recall@3", "recall@5", "mrr@5"]) + " |")
    (output / "retrieval_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    return report
