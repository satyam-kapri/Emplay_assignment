"""Materialize manually chosen source-passage labels and verify against parsed sources."""
import json
from pathlib import Path
from rfp_intelligence.ingestion.parsers import parse

# File/page/quotes selected from source review. No model creates the ground truth.
CASES = [
    ("Bid1", "Addendum 2*.pdf", 1, "July 9, 2024 at 2:00 PM CST", "What is Bid1's submission deadline after all addendums?"),
    ("Bid1", "Addendum 2*.pdf", 1, "Please sign this addendum", "Must bidders sign and return Addendum 2?"),
    ("Bid1", "Addendum 1*.pdf", 1, "USB 3.1 is a minimum requirement", "What USB version is the minimum requirement for the non-touch display?"),
    ("Bid1", "Addendum 1*.pdf", 1, "only require etching on Laptops", "Which devices require etching after clarification?"),
    ("Bid1", "Addendum 1*.pdf", 1, "one-year warranty", "What warranty is required for student Chromebooks?"),
    ("Bid1", "JA-*.pdf", 2, "three (3) year agreement", "What is the initial contract term and what renewal extensions are allowed?"),
    ("Bid1", "JA-*.pdf", 2, "JALZATE@dallasisd.org", "What is the procurement buyer's email address?"),
    ("Bid1", "JA-*.pdf", 2, "10-JUN-2024 14:00:00", "When is the pre-proposal meeting?"),
    ("Bid1", "JA-*.pdf", 3, "asset decaling", "What white glove deployment services are required?"),
    ("Bid1", "JA-*.pdf", 4, "Minimum 8GB DDR5 Memory", "What minimum RAM is required for Tier 1 student Chromebooks?"),
    ("Bid2", "PORFP*.pdf", 1, "060B5400007", "Which master contract must eligible bidders be awarded under?"),
    ("Bid2", "PORFP*.pdf", 1, "e-Procurement system", "How must the Dell laptop bid be submitted?"),
    ("Bid2", "PORFP*.pdf", 2, "provide a Mercury Affidavit", "Which mercury documentation must the master contractor provide?"),
    ("Bid2", "PORFP*.pdf", 2, "Delivery within 45 days of Award", "How soon after award must the Dell equipment be delivered?"),
    ("Bid2", "PORFP*.pdf", 2, "authorized reseller for Dell", "What manufacturer authorization is required of the contractor?"),
    ("Bid2", "PORFP*.pdf", 2, "within 10 days of delivering", "When must invoices be submitted after equipment delivery?"),
    ("Bid2", "PORFP*.pdf", 3, "Tamaira Hawkins", "Who is the agency point of contact?"),
    ("Bid2", "PORFP*.pdf", 3, "Dell Limited Hardware Warranty", "What extended warranty is required for the Dell machines?"),
    ("Bid2", "Dell_Laptop_Specs.pdf", 1, "370-BBTL | 16 GB:", "What memory specification corresponds to SKU 370-BBTL?"),
    ("Bid2", "Dell_Laptop_Specs.pdf", 1, "379-BFNZ | Intel Core Ultra 5", "What processor corresponds to SKU 379-BFNZ?"),
    ("Bid2", "*.html", None, "Closing Date: 06/10/2024 02:00 PM EDT", "What closing date and timezone are shown on the Dell bid portal?"),
    ("Bid1", "JA-*.pdf", 3, "factory-authorized repair and maintenance", "What certifications must proposing resellers submit?")]


def main():
    output, cache = [], {}
    for i, (bid, pattern, page, quote, question) in enumerate(CASES, 1):
        path = next(Path(bid).glob(pattern))
        if path not in cache:
            cache[path] = parse(path, bid)[0]
        assert any(e.page == page and quote.lower() in e.text.lower() for e in cache[path]), (path, page, quote)
        output.append({"id": f"q{i:02}", "bid_id": bid, "question": question,
                       "split": "development" if i in {1, 3, 6, 11, 14, 19} else "held_out",
                       "expected": [{"file": path.name, "page": page, "quote": quote}]})
    Path("eval/questions.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Verified {len(output)} manually specified question/source labels")


if __name__ == "__main__":
    main()
