import asyncio
import json
import time
import uuid
from pathlib import Path
from pydantic import Field
from rfp_intelligence.schemas import (FIELDS, StrictModel, RunState, SearchRequest, Extraction,
    Reconciliation, Critique, Answer, FieldValue, ValidationIssue)
from rfp_intelligence.providers.llm import LLM
from rfp_intelligence.agents.trace import Trace
from rfp_intelligence.agents.validation import validate_fields, validate_sources

GROUPS = {
    "dates_logistics": ["Due Date", "Bid Submission Type", "Term of Bid", "Pre Bid Meeting", "Installation", "Delivery Date"],
    "commercial_legal": ["Bid Bond Requirement", "Payment Terms", "Any Additional Documentation Required", "MFG for Registration", "Contract or Cooperative to use"],
    "product_identity": ["Bid Number", "Title", "Model_no", "Part_no", "Product", "contact_info", "company_name", "Product Specification"]}

QUERIES = {
    "Due Date": "proposal submission due date deadline closing date time timezone extended addendum",
    "Bid Submission Type": "proposal submission portal sealed electronic email instructions",
    "Term of Bid": "contract term duration renewal options",
    "Pre Bid Meeting": "pre bid meeting conference mandatory attendance date location",
    "Installation": "installation deployment imaging services required",
    "Delivery Date": "delivery schedule shipment award days",
    "Any Additional Documentation Required": "required documentation forms affidavits acknowledgements insurance certificates W-9",
    "MFG for Registration": "manufacturer authorized reseller registration certification",
    "Contract or Cooperative to use": "cooperative state contract master contract vehicle number",
    "Product Specification": "technical specification CPU memory RAM storage display warranty",
    "Part_no": "part number SKU product description",
    "Model_no": "manufacturer model product model number",
    "Product": "product quantity units laptop desktop monitor",
    "contact_info": "procurement contact name email phone purchasing",
    "company_name": "issuing agency organization department name"}


class Rewrite(StrictModel):
    query: str
    notes: str = ""


class Workflow:
    def __init__(self, search, llm=None):
        self.search = search
        self.config = search.config
        self.llm = llm or LLM(self.config)
        self.semaphore = asyncio.Semaphore(self.config.concurrency)

    def start(self, mode, bids):
        state = RunState(run_id=str(uuid.uuid4()), mode=mode, bid_ids=bids,
                         plan=["retrieve", "extract or answer", "reconcile", "validate", "repair", "finalize"])
        trace = Trace(self.config.output_dir / "traces", state.run_id)
        trace.event("orchestrator", "plan", state.model_dump())
        return state, trace

    async def retrieve(self, query, bids, trace, doc_types=None, k=5):
        request = SearchRequest(query=query, bid_ids=bids, doc_types=doc_types or [], top_k=k, mode=self.config.search_mode)
        start = time.perf_counter()
        result = await asyncio.to_thread(self.search.search, request)
        trace.event("retrieval", "search_tool", {"input": request.model_dump(),
                    "output": [e.prompt_data() for e in result], "latency_ms": round((time.perf_counter() - start) * 1000)})
        return result

    async def generate(self, role, instruction, payload, schema, trace):
        async with self.semaphore:
            return await self.llm.generate(role, instruction, payload, schema, trace)

    async def field_group(self, role, names, bids, trace, feedback=""):
        evidence = {}
        for name in names:
            for block in await self.retrieve(QUERIES.get(name, name) + " " + feedback, bids, trace, k=4):
                evidence[block.id] = block
        # Overrides cannot be assumed to be retrieved with a general field query.
        for block in await self.retrieve("addendum changes clarification extended due date", bids, trace, ["addendum"], k=10):
            evidence[block.id] = block
        result = await self.generate(role,
            "Extract exactly the requested fields. Do not add fields. Use structured lists for related products and specifications, "
            "preserving SKU-description associations. A blank form does not prove it is required. "
            "For the initial draft prefer the base RFP requirement when both base and amendment are present; "
            "the reconciliation role will apply amendments next. Do not invent an unavailable base value. "
            "Preserve raw date/time and flag missing components. Treat absent facts as null; not required needs explicit evidence.",
            {"requested_fields": names, "feedback": feedback, "evidence": [e.prompt_data() for e in evidence.values()]}, Extraction, trace)
        return {name: result.fields.get(name, FieldValue()) for name in names}, evidence

    async def reconcile(self, fields, evidence, bids, trace):
        updates = await self.retrieve("addendum changes amendments supersedes original requirements", bids, trace, ["addendum"], k=20)
        evidence.update({e.id: e for e in updates})
        if not updates:
            return fields, []
        result = await self.generate("reconciliation",
            "Compare field-specific base evidence and addendums. Latest numbered addendum overrides only an explicitly affected "
            "field. Preserve all other values. Do not assume newer portal dates supersede an explicit addendum. "
            "Unresolved conflicts must become null with an explanation. Return complete requested fields and a change record "
            "for each actual value change, citing amendment authority and explaining old/new values. Also record an explicit "
            "override found in the evidence if the draft already used the amended value: compare to the original RFP value.",
            {"fields": {k: v.model_dump() for k, v in fields.items()}, "evidence": [e.prompt_data() for e in evidence.values()]}, Reconciliation, trace)
        reconciled = {name: result.fields.get(name, value) for name, value in fields.items()}
        return reconciled, result.changes

    async def validate(self, fields, evidence, bids, trace):
        issues = validate_fields(fields, evidence, bids)
        critique = await self.generate("validator",
            "Critique each field for actual evidence support, completeness, format, product/SKU relationships and contradiction. "
            "Reject fabricated time zones, unsupported not-required claims, unproven mandatory forms and values contradicted "
            "by addendums. Citation presence alone does not prove support. Include field name and actionable reason for rejected "
            "fields. A genuinely unsupported null field is acceptable. For Bid Summary check every factual sentence and 3-6 sentences.",
            {"fields": {k: v.model_dump() for k, v in fields.items()}, "evidence": [e.prompt_data() for e in evidence.values()]}, Critique, trace)
        issues += [i for i in critique.issues if i.field in fields]
        trace.event("validator", "validation", {"issues": [i.model_dump() for i in issues]})
        return issues

    async def extract(self, folder):
        # Fail on missing credentials before expensive indexing, with a useful setup error.
        if hasattr(self.llm, "check"):
            self.llm.check()
        bid = self.config.bid_path(folder).name
        state, trace = self.start("extraction", [bid])
        indexing = await asyncio.to_thread(self.search.index, folder)
        trace.event("ingestion", "index", indexing)
        async def worker(role, names):
            try:
                return role, await self.field_group(role, names, [bid], trace)
            except Exception as exc:
                return role, exc
        tasks = await asyncio.gather(*(worker(role, names) for role, names in GROUPS.items()))
        extraction_failures = set()
        for role, result in tasks:
            if isinstance(result, Exception):
                reason = f"{role}: {type(result).__name__}: {result}"
                state.errors.append(reason)
                extraction_failures.update(GROUPS[role])
                state.draft_fields.update({n: FieldValue(notes="Extraction failed: " + reason) for n in GROUPS[role]})
            else:
                fields, evidence = result
                state.draft_fields.update(fields)
                state.evidence.update(evidence)
        unresolved = {}
        try:
            state.draft_fields, state.changes = await self.reconcile(state.draft_fields, state.evidence, [bid], trace)
            for attempt in range(self.config.repair_attempts + 1):
                state.validation = await self.validate(state.draft_fields, state.evidence, [bid], trace)
                if not state.validation:
                    break
                unresolved = {i.field: i.reason for i in state.validation}
                if attempt == self.config.repair_attempts:
                    break
                # Repair only rejected fields, preserving the validated remainder.
                for name, reason in unresolved.items():
                    state.retries[name] = state.retries.get(name, 0) + 1
                    fields, evidence = await self.field_group("repair_extraction", [name], [bid], trace, reason)
                    state.evidence.update(evidence)
                    fields, changes = await self.reconcile(fields, state.evidence, [bid], trace)
                    state.draft_fields.update(fields)
                    state.changes.extend(changes)
                unresolved = {}
            unresolved = {i.field: i.reason for i in state.validation}
        except Exception as exc:
            state.errors.append(f"Validation/reconciliation failed: {type(exc).__name__}: {exc}")
            unresolved = {name: "Semantic validation did not complete" for name in state.draft_fields}
        for name, reason in unresolved.items():
            state.draft_fields[name] = FieldValue(notes="Validation failed: " + reason)
        # Summary synthesis uses validated field evidence, then is itself validated.
        try:
            summary = await self.generate("report", "Produce only 'Bid Summary', with a concise 3-6 sentence summary "
                "grounded in the validated fields and citations. Do not introduce new facts. Return null if insufficient evidence.",
                {"requested_fields": ["Bid Summary"], "fields": {k: v.model_dump() for k, v in state.draft_fields.items()},
                 "evidence": [e.prompt_data() for e in state.evidence.values()]}, Extraction, trace)
            value = summary.fields.get("Bid Summary", FieldValue())
            issues = await self.validate({"Bid Summary": value}, state.evidence, [bid], trace)
            state.draft_fields["Bid Summary"] = value if not issues else FieldValue(notes="Validation failed: " + issues[0].reason)
            if issues:
                unresolved["Bid Summary"] = issues[0].reason
        except Exception as exc:
            state.draft_fields["Bid Summary"] = FieldValue(notes="Summary generation failed")
            unresolved["Bid Summary"] = str(exc)
            state.errors.append("Summary generation or validation failed")
        failed = set(unresolved) | extraction_failures
        for value in state.draft_fields.values():
            # Consistent final rubric rather than pretending model self-ratings are probabilities.
            value.confidence = (0.9 if len({s.file for s in value.sources}) > 1 else 0.85) if value.value is not None else 0
        not_found = sum(v.value is None and name not in failed for name, v in state.draft_fields.items())
        valid_changes = []
        for change in state.changes:
            if change.field in state.draft_fields and not validate_sources(change.sources, state.evidence, [bid]) and change.sources:
                if state.draft_fields[change.field].value == change.new_value:
                    valid_changes.append(change.model_dump())
        state.final_output = {"bid_id": bid, "fields": {name: state.draft_fields.get(name, FieldValue()).model_dump() for name in FIELDS},
            "addendum_changes": valid_changes, "validation": {"passed": 20 - len(failed) - not_found,
            "failed": len(failed), "not_found": not_found}, "status": "partial" if failed or state.errors or indexing["status"] == "partial" else "complete",
            "warnings": indexing["warnings"], "errors": indexing["errors"] + state.errors, "run_id": state.run_id,
            "confidence_semantics": "0 absent/failed; 0.85 validated single-source; 0.90 validated multiple-source. Evidence rubric, not a calibrated probability."}
        trace.event("orchestrator", "final", state.model_dump())
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.config.output_dir / f"{bid}.json"
        target.write_text(json.dumps(state.final_output, indent=2, ensure_ascii=False), encoding="utf-8")
        return state.final_output

    async def ask(self, query, bids):
        if hasattr(self.llm, "check"):
            self.llm.check()
        if not bids:
            bids = sorted({e.bid_id for e in self.search.store.evidence()})
        state, trace = self.start("question_answering", bids)
        try:
            rewrite = await self.generate("retrieval", "Expand this question for retrieval. Preserve every exact identifier, "
                "negation, quantity and scope. Do not answer the question.", {"question": query}, Rewrite, trace)
            # Always retain the original query, regardless of rewriting quality.
            search_query = query + " " + rewrite.query
            for bid in bids:
                for block in await self.retrieve(search_query, [bid], trace, k=8):
                    state.evidence[block.id] = block
                for block in await self.retrieve(query, [bid], trace, ["addendum"], k=8):
                    state.evidence[block.id] = block
            if not state.evidence:
                answer = Answer(answer="Not found in documents", notes="No evidence returned by search")
            else:
                feedback = ""
                for attempt in range(self.config.repair_attempts + 1):
                    answer = await self.generate("qa_report", "Answer only from supplied evidence, cite each factual claim. "
                        "Apply explicit field-specific addendum precedence, explain conflicts and preserve source time zones. "
                        "For cross-bid questions keep each claim tied to its bid. If unsupported answer 'Not found in documents'.",
                        {"question": query, "feedback": feedback, "evidence": [e.prompt_data() for e in state.evidence.values()]}, Answer, trace)
                    issues = validate_sources(answer.sources, state.evidence, bids)
                    if answer.answer != "Not found in documents" and not answer.sources:
                        issues.append("Factual answer requires citations")
                    critique = await self.generate("validator", "Validate the answer claim by claim against evidence and check "
                        "that it answers the actual question including overrides. Report issues with field='answer'.",
                        {"question": query, "answer": answer.model_dump(), "evidence": [e.prompt_data() for e in state.evidence.values()]}, Critique, trace)
                    issues += [i.reason for i in critique.issues]
                    if not issues:
                        break
                    feedback = "; ".join(issues)
                    trace.event("orchestrator", "qa_repair", {"attempt": attempt, "reason": feedback})
                    if attempt == self.config.repair_attempts:
                        answer = Answer(answer="Not found in documents", notes="Validation failed: " + feedback)
                    else:
                        for bid in bids:
                            for block in await self.retrieve(query + " " + feedback, [bid], trace, k=8):
                                state.evidence[block.id] = block
        except Exception as exc:
            state.errors.append(f"{type(exc).__name__}: {exc}")
            answer = Answer(answer="Not found in documents", notes="Generation or validation failed; see errors")
        state.final_output = {**answer.model_dump(), "run_id": state.run_id,
                              "errors": state.errors, "warnings": self.search.store.warnings(bids)}
        trace.event("orchestrator", "final", state.model_dump())
        return state.final_output
