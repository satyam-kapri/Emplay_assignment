import pytest
from rfp_intelligence.schemas import SearchRequest
from rfp_intelligence.search.service import tokenize, rrf
from conftest import write_bid


def test_identifier_tokenization_and_fusion():
    assert "abc-123" in tokenize("SKU ABC-123")
    ranking, scores = rrf([["a", "b"], ["b", "c"]])
    assert ranking[0] == "b"


def test_index_search_filters_and_incremental_updates(service, config):
    one = write_bid(config.data_root)
    two = write_bid(config.data_root, "Other", "Warranty ten years, SKU XYZ-456")
    assert service.index(one)["indexed"] == ["portal.html"]
    assert service.index(one)["skipped"] == ["portal.html"]
    service.index(two)
    result = service.search(SearchRequest(query="ABC-123", bid_ids=["Example"], mode="hybrid"))
    assert result and all(e.bid_id == "Example" for e in result)
    assert "ABC-123" in result[0].text
    assert service.search(SearchRequest(query="warranty", doc_types=["specs"])) == []
    (one / "portal.html").write_text("<p>Replacement SKU NEW-999</p>")
    assert service.index(one)["indexed"]
    assert all("ABC-123" not in e.text for e in service.store.evidence(["Example"]))
    (one / "second.html").write_text("<p>Warranty updated</p>")
    service.index(one)
    (one / "portal.html").unlink()
    assert service.index(one)["deleted"] == ["portal.html"]
    assert all(e.file == "second.html" for e in service.store.evidence(["Example"]))


def test_failed_file_preserves_previous_generation(service, config):
    folder = write_bid(config.data_root)
    service.index(folder)
    ids = {e.id for e in service.store.evidence()}
    (folder / "portal.html").write_text("")
    assert service.index(folder)["status"] == "partial"
    assert {e.id for e in service.store.evidence()} == ids


def test_folder_outside_root_is_rejected(service, tmp_path):
    with pytest.raises(ValueError):
        service.index(tmp_path.parent)


def test_bad_file_does_not_crash_remaining_ingestion(service, config):
    folder = write_bid(config.data_root)
    (folder / "broken.pdf").write_bytes(b"not a PDF")
    result = service.index(folder)
    assert result["status"] == "partial"
    assert result["errors"][0]["file"] == "broken.pdf"
    assert result["indexed"] == ["portal.html"]
