from pathlib import Path
from rfp_intelligence.ingestion.parsers import parse, clean, classify
from rfp_intelligence.search.chunks import chunks
from conftest import Tokenizer


def test_html_tables_and_navigation(tmp_path):
    path = tmp_path / "portal.html"
    path.write_text("<nav>Noise</nav><main><h1>Specs</h1><table><tr><th>SKU</th><th>Description</th></tr>"
                    "<tr><td>ABC-123</td><td>16GB RAM</td></tr></table></main>")
    result, warnings = parse(path, "Unseen")
    text = "\n".join(e.text for e in result)
    assert "Noise" not in text
    assert "ABC-123 | 16GB RAM" in text
    assert all(e.page is None and e.locator for e in result)


def test_prose_cleanup_preserves_identifiers():
    assert clean("com-\nputing ABC-123") == "computing ABC-123"


def test_actual_addendum_page_and_classification():
    path = next(Path("Bid1").glob("Addendum 2*.pdf"))
    blocks, warnings = parse(path, "Bid1")
    assert any("July 9, 2024" in e.text and e.page == 1 for e in blocks)
    assert all(e.doc_type == "addendum" and e.addendum_number == 2 for e in blocks)
    assert any("Please sign this addendum" in e.text and "ACKNOWLEDGE AND RETURN" in e.text for e in blocks)


def test_chunks_do_not_drop_table_rows(tmp_path):
    path = tmp_path / "table.html"
    path.write_text("<table><tr><th>SKU</th><th>RAM</th></tr>" +
                    "".join(f"<tr><td>ABC-{i}</td><td>16 GB</td></tr>" for i in range(30)) + "</table>")
    blocks, _ = parse(path, "Unseen")
    result = chunks(blocks, Tokenizer(), size=40, overlap=5)
    assert all(any(f"ABC-{i} | 16 GB" in e.text for e in result) for i in range(30))
    assert all(e.page is None for e in result)


def test_unknown_classification():
    assert classify(Path("unknown.pdf"), "miscellaneous material") == ("unknown", None)


def test_html_preserves_label_value_relationship(tmp_path):
    path = tmp_path / "portal.html"
    path.write_text('<main><div><span class="field-label">Closing Date</span><div><p>June 10, 2 PM EDT</p></div></div></main>')
    blocks, _ = parse(path, "Unseen")
    assert any("Closing Date: June 10, 2 PM EDT" in e.text for e in blocks)


def test_document_date_metadata_does_not_use_submission_deadline(tmp_path):
    path = tmp_path / "portal.html"
    path.write_text('<main><p>Closing Date: June 10, 2024</p><p>Issue Date: 26-MAY-2024</p></main>')
    blocks, _ = parse(path, "Unseen")
    assert all(e.document_date == "26-MAY-2024" for e in blocks)


def test_actual_borderless_sku_relationship():
    blocks, warnings = parse(Path("Bid2/Dell_Laptop_Specs.pdf"), "Unseen")
    rows = "\n".join(e.text for e in blocks if "table[" in e.locator)
    assert "370-BBTL | 16 GB:" in rows
    assert "400-BRFT | 256 GB," in rows
    assert "379-BFNZ | Intel Core Ultra 5" in rows
    assert "366-0135 | Custom Asset Report" in rows
