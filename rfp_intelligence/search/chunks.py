import hashlib
import re
from rfp_intelligence.schemas import Evidence


def chunks(blocks: list[Evidence], tokenizer, size=350, overlap=50) -> list[Evidence]:
    """Token-counted chunks; tables split only at row boundaries when possible."""
    result = []
    for block in blocks:
        prefix = f"{block.doc_type}: {block.heading}\n"
        budget = min(size, tokenizer.model_max_length - len(tokenizer.encode(prefix)) - 8)
        if budget < 32:
            raise ValueError("Tokenizer context too small for chunking")
        units = block.text.splitlines() if "table[" in block.locator else re.split(r"\n\s*\n|(?<=[.!?])\s+", block.text)
        buffer, tokens = [], 0
        pieces = []
        for unit in units:
            ids = tokenizer.encode(unit, add_special_tokens=False)
            if tokens + len(ids) > budget and buffer:
                pieces.append("\n".join(buffer))
                # Repeat table header; use text overlap only for prose.
                carry = units[0] if "table[" in block.locator else tokenizer.decode(tokenizer.encode(buffer[-1], add_special_tokens=False)[-overlap:])
                buffer, tokens = [carry], len(tokenizer.encode(carry, add_special_tokens=False))
            if len(ids) > budget:
                if buffer:
                    pieces.append("\n".join(buffer))
                    buffer, tokens = [], 0
                for start in range(0, len(ids), budget - overlap):
                    pieces.append(tokenizer.decode(ids[start:start + budget]))
            else:
                buffer.append(unit)
                tokens += len(ids)
        if buffer:
            pieces.append("\n".join(buffer))
        for i, piece in enumerate(pieces):
            if not piece.strip():
                continue
            result.append(block.model_copy(update={"id": hashlib.sha256(f"{block.id}/{i}".encode()).hexdigest(),
                                                   "text": piece, "locator": f"{block.locator}/chunk[{i}]"}))
    return result
