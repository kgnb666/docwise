"""健康检查接口测试。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "DocWise"
    assert "stats" not in body
    assert body["config"]["embedding_provider"] == "hash"  # conftest 强制离线
    assert "tokenizer" in body["config"]


def test_root_ok():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "docs" in resp.json()
