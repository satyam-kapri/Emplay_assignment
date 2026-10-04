import asyncio
from rfp_intelligence.schemas import (Evidence, FieldValue, Citation, Reconciliation, ChangeRecord, SearchRequest)
from rfp_intelligence.agents.workflow import Workflow
from rfp_intelligence.agents.trace import Trace
from rfp_intelligence.agents.validation import validate_fields


def test_reconciliation_preserves_unaffected_fields(service, config, monkeypatch):
    base = Evidence(id="base", bid_id="One", file="original.pdf", doc_type="rfp", page=1,
                    text="Deadline June 27. Term three years.", raw_text="Deadline June 27. Term three years.")
    amendment = Evidence(id="amend", bid_id="One", file="addendum.pdf", doc_type="addendum", page=1,
                         addendum_number=2, text="Deadline July 9. All other terms unchanged.", raw_text="Deadline July 9. All other terms unchanged.")
    source = Citation(chunk_id="amend", file="addendum.pdf", page=1, quote="Deadline July 9.")
    term = FieldValue(value="three years", sources=[Citation(chunk_id="base", file="original.pdf", page=1, quote="Term three years.")])
    class Model:
        async def generate(self, role, instruction, payload, schema, trace):
            assert role == "reconciliation"
            assert "field" in instruction and "original RFP" in instruction
            return Reconciliation(fields={"Due Date": FieldValue(value="July 9", sources=[source]), "Term of Bid": term},
                changes=[ChangeRecord(field="Due Date", old_value="June 27", new_value="July 9", sources=[source], reason="Explicit Addendum 2 extension")])
    monkeypatch.setattr(service, "search", lambda req: [amendment])
    workflow = Workflow(service, Model())
    fields, changes = asyncio.run(workflow.reconcile({"Due Date": FieldValue(value="June 27"), "Term of Bid": term},
                                                    {"base": base}, ["One"], Trace(config.output_dir, "test")))
    assert fields["Due Date"].value == "July 9"
    assert fields["Term of Bid"].value == "three years"
    assert changes[0].old_value == "June 27"


def test_null_silence_is_distinct_from_explicit_not_required():
    block = Evidence(id="e", bid_id="One", file="terms.pdf", doc_type="rfp", page=1,
                     text="No bid bond is required.", raw_text="No bid bond is required.")
    explicit = FieldValue(value="Not required", sources=[Citation(chunk_id="e", file="terms.pdf", page=1, quote=block.text)])
    assert not validate_fields({"Bid Bond Requirement": explicit}, {"e": block}, ["One"])
    assert not validate_fields({"Bid Bond Requirement": FieldValue()}, {}, ["One"])
    assert validate_fields({"Bid Bond Requirement": FieldValue(value="Not required")}, {}, ["One"])
