from eval.run import metrics
from rfp_intelligence.schemas import Evidence


def test_multiple_passage_recall_and_mrr():
    hits = [Evidence(id="x", bid_id="One", file="x.pdf", doc_type="rfp", page=1, text="wrong", raw_text="wrong"),
            Evidence(id="y", bid_id="One", file="y.pdf", doc_type="rfp", page=2, text="right passage", raw_text="right passage")]
    result = metrics(hits, [{"file": "y.pdf", "page": 2, "quote": "right"}, {"file": "z.pdf", "page": 1, "quote": "missing"}])
    assert result["recall@1"] == 0
    assert result["recall@3"] == .5
    assert result["mrr@5"] == .5
