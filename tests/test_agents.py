import asyncio
from rfp_intelligence.schemas import (Evidence, Citation, FieldValue, Extraction, Critique, ValidationIssue, FIELDS)
from rfp_intelligence.agents.validation import validate_fields
from rfp_intelligence.agents.workflow import Workflow
from conftest import write_bid


def test_citation_validation_rejects_fake_quote_and_wrong_bid():
    evidence = Evidence(id="e", bid_id="One", file="file.pdf", doc_type="rfp", page=1, text="Warranty 3 years", raw_text="Warranty 3 years")
    citation = Citation(chunk_id="e", file="file.pdf", page=1, quote="Warranty ten years")
    fields = {"Warranty": FieldValue(value="ten years", sources=[citation])}
    assert validate_fields(fields, {"e": evidence}, ["One"])
    citation.quote = "Warranty 3 years"
    assert validate_fields(fields, {"e": evidence}, ["Other"])
    assert not validate_fields(fields, {"e": evidence}, ["One"])


class FakeLLM:
    def __init__(self):
        self.repairs = 0

    async def generate(self, role, instruction, payload, schema, trace):
        if role == "validator":
            title = payload["fields"].get("Title")
            return Critique(issues=[ValidationIssue(field="Title", reason="Unsupported title")] if title and title["value"] == "invented" else [])
        if role == "report":
            return Extraction(fields={"Bid Summary": FieldValue()})
        fields = {n: FieldValue() for n in payload["requested_fields"]}
        if role == "product_identity":
            fields["Title"] = FieldValue(value="invented")
        if role == "repair_extraction":
            self.repairs += 1
        return Extraction(fields=fields)


def test_targeted_validator_feedback_loop(service, config):
    folder = write_bid(config.data_root)
    llm = FakeLLM()
    result = asyncio.run(Workflow(service, llm).extract(folder))
    assert llm.repairs == 1
    assert set(result["fields"]) == set(FIELDS)
    assert result["fields"]["Title"]["value"] is None
    assert sum(result["validation"].values()) == 20
    assert list((config.output_dir / "traces").glob("*.jsonl"))


def test_retry_budget_finalizes_rejected_field(service, config):
    class BadLLM(FakeLLM):
        async def generate(self, role, instruction, payload, schema, trace):
            if role == "repair_extraction":
                self.repairs += 1
                return Extraction(fields={"Title": FieldValue(value="invented")})
            return await super().generate(role, instruction, payload, schema, trace)
    llm = BadLLM()
    result = asyncio.run(Workflow(service, llm).extract(write_bid(config.data_root)))
    assert llm.repairs == config.repair_attempts
    assert result["validation"]["failed"] == 1
    assert result["fields"]["Title"]["value"] is None
