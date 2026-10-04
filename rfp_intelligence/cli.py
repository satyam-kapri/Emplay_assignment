import argparse
import asyncio
import json
import sys
from rfp_intelligence.config import Config
from rfp_intelligence.search.service import SearchService
from rfp_intelligence.schemas import SearchRequest
from rfp_intelligence.agents.workflow import Workflow
from rfp_intelligence.providers.llm import ProviderError


def main():
    parser = argparse.ArgumentParser(description="Evidence-grounded RFP search and extraction")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["index", "extract"]:
        sub.add_parser(command).add_argument("--bid", required=True)
    for command in ["search", "ask"]:
        p = sub.add_parser(command)
        p.add_argument("--query", required=True)
        p.add_argument("--bid-id", action="append", default=[])
        if command == "search":
            p.add_argument("--doc-type", action="append", default=[])
            p.add_argument("--addendum-number", action="append", type=int, default=[])
            p.add_argument("--top-k", type=int, default=5)
            p.add_argument("--mode", choices=["dense", "hybrid", "rerank"], default=None)
    sub.add_parser("serve").add_argument("--port", type=int, default=8000)
    sub.add_parser("evaluate").add_argument("--questions", default="eval/questions.json")
    args = parser.parse_args()
    config = Config.load()
    if args.command == "serve":
        import uvicorn
        from rfp_intelligence.api.app import create_app
        uvicorn.run(create_app(config), host="127.0.0.1", port=args.port)
        return
    service = SearchService(config)
    try:
        if args.command == "index":
            result = service.index(args.bid)
        elif args.command == "extract":
            result = asyncio.run(Workflow(service).extract(args.bid))
        elif args.command == "ask":
            result = asyncio.run(Workflow(service).ask(args.query, args.bid_id))
        elif args.command == "search":
            result = [e.model_dump() for e in service.search(SearchRequest(query=args.query, bid_ids=args.bid_id,
                doc_types=args.doc_type, addendum_numbers=args.addendum_number, top_k=args.top_k, mode=args.mode or config.search_mode))]
        else:
            from eval.run import evaluate
            result = evaluate(service, args.questions)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if isinstance(result, dict) and (result.get("errors") or result.get("status") == "partial"):
            sys.exit(2)
    except (ValueError, ProviderError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    finally:
        service.close()


if __name__ == "__main__":
    main()
