from fastapi.testclient import TestClient
from rfp_intelligence.api.app import create_app
from conftest import write_bid
import json


def test_api_shared_search_and_path_validation(config, service, monkeypatch):
    monkeypatch.setattr("rfp_intelligence.api.app.SearchService", lambda config: service)
    folder = write_bid(config.data_root)
    with TestClient(create_app(config)) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/index", json={"folder": str(folder)}).status_code == 200
        result = client.get("/search", params={"q": "ABC-123", "bid_id": "Example", "mode": "hybrid"})
        assert result.status_code == 200
        assert all(e["bid_id"] == "Example" for e in result.json())
        assert client.get("/search", params={"q": "x", "top_k": 0}).status_code == 422
        assert client.post("/index", json={"folder": str(config.data_root.parent)}).status_code == 400
        assert client.post("/ask", json={"question": "deadline"}).status_code == 503


def test_bid_catalog_and_saved_extraction(config, service, monkeypatch):
    monkeypatch.setattr("rfp_intelligence.api.app.SearchService", lambda config: service)
    folder = write_bid(config.data_root)
    application = write_bid(config.data_root, "frontend")
    (application / "package.json").write_text("{}")
    with TestClient(create_app(config)) as client:
        catalog = client.get("/bids").json()
        assert [bid["id"] for bid in catalog] == ["Example"]
        assert catalog[0]["indexed_files"] == 0
        assert not catalog[0]["has_extraction"]
        assert client.get("/bids/Example/extraction").status_code == 404
        client.post("/index", json={"folder": str(folder)})
        assert client.get("/bids").json()[0]["indexed_files"] == 1
        config.output_dir.mkdir(exist_ok=True)
        saved = {"bid_id": "Example", "fields": {}}
        target = config.output_dir / "Example.json"
        target.write_text(json.dumps(saved))
        assert client.get("/bids").json()[0]["has_extraction"]
        assert client.get("/bids/Example/extraction").json() == saved
        assert client.get("/bids/Unknown/extraction").status_code == 404
        target.write_text("invalid json")
        assert client.get("/bids/Example/extraction").status_code == 500
