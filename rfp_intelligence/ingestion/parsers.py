import hashlib
import re
from collections import Counter
from pathlib import Path
import pdfplumber
from bs4 import BeautifulSoup
from rfp_intelligence.schemas import Evidence


def identifier_table(page, allow_continuation=False):
    """Recover borderless two-column identifier tables from word coordinates.

    Requires explicit headers, or a specs continuation with multiple aligned IDs.
    This is a document-layout rule, not a Dell model or bid-specific rule.
    """
    words = page.extract_words(x_tolerance=2, y_tolerance=2)
    header = next((w for w in words if w["text"].lower() in {"sku", "part", "part_no"}), None)
    description = next((w for w in words if w["text"].lower() == "description"), None)
    # A body phrase such as 'Routing SKU' is not a column header.
    if header and (not description or abs(header["top"] - description["top"]) > 12):
        header = None
    if not header and not allow_continuation:
        return []
    identifiers = [w for w in words if re.fullmatch(r"[A-Za-z0-9]{2,}[-][A-Za-z0-9]{2,}", w["text"])]
    if header:
        center = (header["x0"] + header["x1"]) / 2
        identifiers = [w for w in identifiers if w["x0"] - 8 <= center <= w["x1"] + 8 and w["top"] > header["bottom"]]
    elif len(identifiers) >= 3:
        centers = sorted((w["x0"] + w["x1"]) / 2 for w in identifiers)
        center = centers[len(centers) // 2]
        identifiers = [w for w in identifiers if abs((w["x0"] + w["x1"]) / 2 - center) < 18]
    if len(identifiers) < 3:
        return []
    identifiers.sort(key=lambda w: w["top"])
    right = center > page.width / 2
    edge = min(w["x0"] for w in identifiers) - 3 if right else max(w["x1"] for w in identifiers) + 3
    rows = ["SKU | Description"]
    for i, anchor in enumerate(identifiers):
        lower = (identifiers[i - 1]["top"] + anchor["top"]) / 2 if i else (header["bottom"] if header else max(0, anchor["top"] - 8))
        upper = (anchor["top"] + identifiers[i + 1]["top"]) / 2 if i + 1 < len(identifiers) else min(page.height, anchor["bottom"] + 18)
        selected = [w for w in words if lower <= w["top"] < upper and
                    (w["x1"] <= edge if right else w["x0"] >= edge)]
        selected.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))
        value = " ".join(w["text"] for w in selected)
        if value:
            rows.append(anchor["text"] + " | " + value)
    return rows if len(rows) > 1 else []


def clean(text: str) -> str:
    # Never dehyphenate identifiers: only repair lowercase prose split at a newline.
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def sections(text):
    heading, lines = "", []
    for line in text.splitlines():
        value = line.strip()
        is_heading = bool(re.match(r"^\d+(?:\.\d+)+\s+[A-Za-z]", value)) or (
            8 <= len(value) <= 90 and value.isupper() and not re.search(r"[@|]", value))
        if is_heading:
            if lines:
                yield heading, "\n".join(lines)
            heading, lines = value, [value]
        else:
            lines.append(line)
    if lines:
        yield heading, "\n".join(lines)


def classify(path: Path, text: str) -> tuple[str, int | None]:
    if path.suffix.lower() in {".html", ".htm"}:
        return "bid_page", None
    label = path.name + " " + text[:1500]
    match = re.search(r"addendum\s*(?:no\.?\s*)?(\d+)", label, re.I)
    if match:
        return "addendum", int(match.group(1))
    for pattern, kind in [(r"affidavit", "affidavit"), (r"specs|specification", "specs"),
                          (r"rfp|porfp|request for proposals?", "rfp")]:
        if re.search(pattern, label, re.I):
            return kind, None
    return "unknown", None


def parse(path: Path, bid_id: str) -> tuple[list[Evidence], list[str]]:
    warnings, blocks, original_pages = [], [], {}
    if path.suffix.lower() in {".html", ".htm"}:
        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        for element in soup.select("script, style, nav, footer, noscript, button, input, textarea, select, [role=dialog]"):
            element.decompose()
        root = soup.find("main") or soup.find("article") or soup.body or soup
        heading = ""
        for index, node in enumerate(root.find_all(["h1", "h2", "h3", "h4", "p", "li", "table", "div"])):
            if node.name.startswith("h"):
                heading = node.get_text(" ", strip=True)
            if node.find_parent(["table", "p", "li"]) is not None:
                continue
            if node.name == "div" and node.find(["div", "p", "table", "li", "h1", "h2", "h3"]):
                continue
            text = node.get_text("\n", strip=True)
            # Leaf values often live beside a label in a wrapping field container.
            # Preserve that relation without a portal-specific CSS selector.
            parent = node.parent
            for _ in range(4):
                if parent is None or parent == root:
                    break
                label = next((child for child in parent.find_all(["span", "label", "dt"], recursive=False)
                              if child.name in {"label", "dt"} or any("label" in c.lower() for c in child.get("class", []))), None)
                if label:
                    text = label.get_text(" ", strip=True) + ": " + text
                    break
                parent = parent.parent
            if node.name == "table":
                text = "\n".join(" | ".join(c.get_text(" ", strip=True) for c in row.find_all(["th", "td"]))
                                 for row in node.find_all("tr"))
            if text.strip():
                blocks.append((None, f"{node.name}[{index}]", heading, text))
        if not blocks:
            text = root.get_text("\n", strip=True)
            if text:
                blocks.append((None, "body", "", text))
    else:
        with pdfplumber.open(path) as pdf:
            # Only remove short repeated boundary lines; store original text regardless.
            texts = [p.extract_text(x_tolerance=2) or "" for p in pdf.pages]
            edges = Counter()
            for text in texts:
                lines = text.splitlines()
                edges.update(set(lines[:2] + lines[-2:]))
            repeated = {line for line, count in edges.items()
                        if len(texts) >= 3 and count >= max(3, len(texts) * .6) and len(line) < 100}
            for page, raw in zip(pdf.pages, texts):
                number = page.page_number
                original_pages[number] = raw
                if not raw.strip():
                    warnings.append(f"{path.name}: page {number}: empty or scanned; OCR deferred")
                    continue
                lines = raw.splitlines()
                text = "\n".join(line for i, line in enumerate(lines)
                                 if not (line in repeated and (i < 2 or i >= len(lines) - 2)))
                kind, addendum = classify(path, raw)
                # Uppercase amendment obligations are sentences, not independent headings.
                # Keep their context together and let the token chunker bound long pages.
                page_sections = [(f"Addendum {addendum}", text)] if kind == "addendum" else sections(text)
                for si, (heading, content) in enumerate(page_sections):
                    blocks.append((number, f"text/section[{si}]", heading, content))
                try:
                    # Retain geometry-derived row relationships rather than flattened columns.
                    tables = page.extract_tables()
                    for ti, table in enumerate(tables):
                        rows = [" | ".join(re.sub(r"\s+", " ", str(c or "")).strip() for c in row) for row in table
                                if any(str(c or "").strip() for c in row)]
                        if rows:
                            blocks.append((number, f"table[{ti}]", "table", "\n".join(rows)))
                    if not tables:
                        rows = identifier_table(page, allow_continuation=classify(path, raw)[0] == "specs")
                        if rows:
                            blocks.append((number, "table[borderless]", "identifier specifications", "\n".join(rows)))
                except Exception as exc:
                    warnings.append(f"{path.name}: page {number}: table extraction {type(exc).__name__}")
    text = "\n".join(b[3] for b in blocks)
    kind, addendum = classify(path, text)
    if kind == "unknown":
        warnings.append(f"{path.name}: uncertain document type")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    result = []
    date = re.search(r"(?:issue date|document date|issued on|publication(?: date)?)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-[A-Za-z]{3}-\d{4}|[A-Za-z]+ \d{1,2}, \d{4})", text, re.I)
    for i, (page, locator, heading, raw) in enumerate(blocks):
        result.append(Evidence(id=hashlib.sha256(f"{bid_id}/{path.name}/{digest}/{i}".encode()).hexdigest(),
                               bid_id=bid_id, file=path.name, doc_type=kind, page=page,
                               locator=locator, heading=heading, text=clean(raw),
                               raw_text=original_pages.get(page, raw) if locator.startswith("text/") else raw,
                               addendum_number=addendum, document_date=date.group(1) if date else None))
    if not result:
        warnings.append(f"{path.name}: no readable content")
    return result, warnings
