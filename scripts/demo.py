"""Generate the required real outputs after configuring an LLM endpoint."""
import asyncio
import json
from pathlib import Path
from rfp_intelligence.config import Config
from rfp_intelligence.search.service import SearchService
from rfp_intelligence.agents.workflow import Workflow

QUESTIONS = [
    (["Bid1"], "What is the submission deadline after all addendums?"),
    (["Bid1"], "What changed in Addendum 2 compared with the original RFP?"),
    (["Bid1"], "What is the contract duration and what renewal options are available?"),
    (["Bid1"], "Which devices require etching?"),
    (["Bid1"], "When is the pre-proposal meeting and is attendance mandatory?"),
    (["Bid2"], "Which affidavits are required for the Dell laptop bid?"),
    (["Bid2"], "What products and quantities are requested?"),
    (["Bid2"], "What CPU and RAM are specified for Dell Latitude 5550?"),
    (["Bid2"], "What is the delivery window after award?"),
    (["Bid1", "Bid2"], "Compare the warranty requirements of both bids."),
    (["Bid1", "Bid2"], "Is a bid bond required, and if so how much?")]


async def run():
    config = Config.load()
    service = SearchService(config)
    workflow = Workflow(service)
    try:
        for bid in ["Bid1", "Bid2"]:
            result = await workflow.extract(bid)
            print(bid, result["status"], result["validation"], flush=True)
        answers = []
        for bids, question in QUESTIONS:
            answer = await workflow.ask(question, bids)
            answers.append({"question": question, "bid_ids": bids, **answer})
            print(question, "errors:", len(answer["errors"]), flush=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)
        (config.output_dir / "sample_qa.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    finally:
        service.close()


if __name__ == "__main__":
    asyncio.run(run())
