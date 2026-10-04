from fastapi.testclient import TestClient
from rfp_intelligence.api.app import create_app
from conftest import write_bid


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
