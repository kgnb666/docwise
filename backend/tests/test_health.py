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
    # 系统状态概览：统计与配置
    assert "stats" in body
    assert "documents" in body["stats"]
    assert "chunks" in body["stats"]
    assert body["config"]["embedding_provider"] == "hash"  # conftest 强制离线
    assert "tokenizer" in body["config"]


def test_root_ok():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "docs" in resp.json()
