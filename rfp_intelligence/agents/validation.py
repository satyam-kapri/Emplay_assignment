import re
from rfp_intelligence.schemas import FieldValue, ValidationIssue, Citation


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def validate_sources(sources: list[Citation], evidence, bids) -> list[str]:
    errors = []
    for source in sources:
        block = evidence.get(source.chunk_id)
        if block is None:
            errors.append("Unknown evidence chunk")
            continue
        if block.bid_id not in bids or source.file != block.file or source.page != block.page or source.locator != block.locator:
            errors.append("Citation metadata or bid does not match source")
        if normalized(source.quote) not in normalized(block.text):
            errors.append("Citation quote is not present in retrieved text")
    return errors


def validate_fields(fields: dict[str, FieldValue], evidence, bids):
    issues = []
    for name, field in fields.items():
        reasons = validate_sources(field.sources, evidence, bids)
        if field.value is not None and not field.sources:
            reasons.append("Non-null value requires a source")
        if field.value is None and (field.sources or not field.notes):
            reasons.append("Null values require empty sources and a reason")
        if isinstance(field.value, str) and not field.value.strip():
            reasons.append("Empty strings must be represented as null")
        if reasons:
            issues.append(ValidationIssue(field=name, reason="; ".join(reasons)))
    return issues
