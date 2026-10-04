"""Index both supplied bids and run the three real retrieval configurations."""
import json
from rfp_intelligence.config import Config
from rfp_intelligence.search.service import SearchService
from eval.run import evaluate


def main():
    config = Config.load()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    service = SearchService(config)
    try:
        for bid in ["Bid1", "Bid2"]:
            report = service.index(bid)
            (config.output_dir / f"index_{bid}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(bid, report["status"], "indexed", len(report["indexed"]), "errors", len(report["errors"]), flush=True)
            if report["errors"]:
                raise RuntimeError("Indexing failed; refusing to benchmark a stale corpus")
        result = evaluate(service, "eval/questions.json")
        print(json.dumps(result["summary"], indent=2), flush=True)
    finally:
        service.close()


if __name__ == "__main__":
    main()
