from rfp_intelligence.schemas import Evidence
from rfp_intelligence.search.chunks import chunks
from conftest import Tokenizer


def test_long_units_stay_under_budget_and_keep_page_provenance():
    block = Evidence(id="e", bid_id="Any", file="long.pdf", doc_type="rfp", page=7,
                     text=" ".join(f"word{i}" for i in range(1200)), raw_text="original", heading="Terms")
    result = chunks([block], Tokenizer())
    assert len(result) > 1
    assert all(len(e.text.split()) <= 350 and e.page == 7 for e in result)
    assert any("word1199" in e.text for e in result)
