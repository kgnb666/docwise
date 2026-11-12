"""用真实会话和隔离数据目录验证账号之间的访问边界。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.config import get_settings
from app.core.llm import LLMClient
from app.deps import get_rate_limiter
from app.main import app, create_app
from app.storage.persistence import save_document

PASSWORD = "test-passphrase-32"
HTTPS = "https://docwise.example"


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "agent_enabled", False)
    get_rate_limiter().reset()
    auth._login_by_account.reset()
    auth._login_total.reset()

    async def fake_completion(self, messages, tools=None):
        yield {"type": "delta", "content": "测试回答"}

    monkeypatch.setattr(LLMClient, "stream_chat", fake_completion)


def make_client(username: str) -> TestClient:
    from app.storage.accounts import create_account

    create_account(username, PASSWORD)
    client = TestClient(app, base_url=HTTPS)
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert {"httponly", "secure", "samesite=strict"} <= {
        flag.strip().lower() for flag in response.headers["set-cookie"].split(";")
    }
    return client


@pytest.mark.parametrize(
    ("method", "url", "kwargs"),
    [
        ("GET", "/api/documents", {}),
        ("GET", "/api/documents/stats", {}),
        ("GET", "/api/documents/some-doc/chunks", {}),
        ("DELETE", "/api/documents/some-doc", {}),
        ("POST", "/api/documents", {"files": {"file": ("notes.txt", b"hello", "text/plain")}}),
        ("POST", "/api/chat", {"json": {"query": "What does the document say?"}}),
        ("POST", "/api/chat/stream", {"json": {"query": "What does the document say?"}}),
    ],
)
def test_anonymous_cannot_use_workspace(method, url, kwargs):
    with TestClient(app, base_url=HTTPS) as client:
        assert client.request(method, url, **kwargs).status_code == 401


def test_two_accounts_only_use_their_own_documents_and_cache():
    alice = make_client("alice")
    bob = make_client("bob")
    alice_doc = alice.post(
        "/api/documents", files={"file": ("alice.txt", b"Alice project code is ALPHA.", "text/plain")}
    ).json()["doc_id"]
    bob_doc = bob.post(
        "/api/documents", files={"file": ("bob.txt", b"Bob project code is BETA.", "text/plain")}
    ).json()["doc_id"]
    question = {"query": "What is the project code?"}

    assert [doc["doc_id"] for doc in alice.get("/api/documents").json()["documents"]] == [alice_doc]
    assert [doc["doc_id"] for doc in bob.get("/api/documents").json()["documents"]] == [bob_doc]
    assert alice.get("/api/documents/stats").json() == {"documents": 1, "chunks": 1}
    assert bob.get("/api/documents/stats").json() == {"documents": 1, "chunks": 1}
    for client, own_id, other_id in [(alice, alice_doc, bob_doc), (bob, bob_doc, alice_doc)]:
        assert client.get(f"/api/documents/{own_id}/chunks").status_code == 200
        assert client.get(f"/api/documents/{other_id}/chunks").status_code == 404
        assert client.delete(f"/api/documents/{other_id}").status_code == 404
        answer = client.post("/api/chat", json=question)
        assert answer.status_code == 200, answer.text
        assert [item["doc_id"] for item in answer.json()["citations"]] == [own_id]
        stream = client.post("/api/chat/stream", json=question)
        assert stream.status_code == 200, stream.text
        events = [json.loads(line[6:]) for line in stream.text.splitlines()
                  if line.startswith("data: {")]
        citations = next(event["citations"] for event in events if event["type"] == "citations")
        assert [item["doc_id"] for item in citations] == [own_id]

    assert alice.delete(f"/api/documents/{alice_doc}").status_code == 200
    assert bob.get(f"/api/documents/{bob_doc}/chunks").status_code == 200
    restarted_app = create_app()
    with TestClient(restarted_app, base_url=HTTPS, cookies=bob.cookies) as client:
        assert client.get(f"/api/documents/{bob_doc}/chunks").status_code == 200
        assert client.get(f"/api/documents/{alice_doc}/chunks").status_code == 404


def test_session_logout_revokes_token_and_rejects_account_mismatch():
    from app.api.routes.auth import SESSION_COOKIE

    alice = make_client("alice")
    bob = make_client("bob")
    bob_id = bob.get("/api/auth/me").json()["id"]
    assert alice.get("/api/documents", headers={"X-DocWise-Account": bob_id}).status_code == 401
    assert alice.post("/api/auth/logout", headers={"Origin": "https://other.example"}).status_code == 403
    session_token = alice.cookies.get(SESSION_COOKIE)
    assert alice.post("/api/auth/logout").status_code == 204
    alice.cookies.set(SESSION_COOKIE, session_token, domain="docwise.example", path="/api")
    assert alice.get("/api/auth/me").status_code == 401
    assert alice.get("/api/documents").status_code == 401


def test_login_rejects_wrong_password_and_foreign_origin():
    from app.storage.accounts import create_account

    create_account("alice", PASSWORD)
    client = TestClient(app, base_url=HTTPS)
    correct = {"username": "alice", "password": PASSWORD}
    assert client.post("/api/auth/login", json=correct, headers={
        "Origin": "https://other.example",
    }).status_code == 403
    assert client.post("/api/auth/login", json={**correct, "password": "incorrect"}).status_code == 401
    assert client.post("/api/auth/login", json=correct, headers={"Origin": HTTPS}).status_code == 200


def test_session_expiry_requires_login_again(monkeypatch):
    from app.storage import accounts

    monkeypatch.setattr(accounts, "time", lambda: 1000)
    client = make_client("alice")
    assert client.get("/api/auth/me").status_code == 200

    expires_at = 1000 + get_settings().auth_session_seconds
    monkeypatch.setattr(accounts, "time", lambda: expires_at)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/documents").status_code == 401


def test_legacy_snapshot_is_visible_only_after_explicit_adoption():
    from app.storage.workspace import adopt_legacy_documents

    save_document("legacy", "legacy.txt", [{"index": 0, "text": "old data", "vector": [1.0]}])
    alice = make_client("alice")
    bob = make_client("bob")
    assert alice.get("/api/documents").json()["documents"] == []
    assert bob.get("/api/documents").json()["documents"] == []
    assert "stats" not in alice.get("/api/health").json()

    assert adopt_legacy_documents("alice") == 1
    assert adopt_legacy_documents("alice") == 0
    with pytest.raises(ValueError, match="已归属"):
        adopt_legacy_documents("bob")
    restarted_app = create_app()
    with TestClient(restarted_app, base_url=HTTPS, cookies=alice.cookies) as client:
        assert client.get("/api/documents/legacy/chunks").status_code == 200
        assert client.delete("/api/documents/legacy").status_code == 200
    with TestClient(restarted_app, base_url=HTTPS, cookies=bob.cookies) as client:
        assert client.get("/api/documents/legacy/chunks").status_code == 404
    assert adopt_legacy_documents("alice") == 0
    with TestClient(create_app(), base_url=HTTPS, cookies=alice.cookies) as client:
        assert client.get("/api/documents/legacy/chunks").status_code == 404


def test_cli_import_targets_account_with_non_utf8_output(tmp_path):
    alice = make_client("alice")
    bob = make_client("bob")
    note = tmp_path / "sample-😀.txt"
    note.write_text("Private CLI document", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "import_kb.py"
    result = subprocess.run(
        [sys.executable, str(script), "--account", "alice", "--embedding", "hash", str(note)],
        env={**os.environ, "DATA_DIR": str(tmp_path), "PYTHONIOENCODING": "cp936"},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode("cp936", errors="replace")
    assert [doc["name"] for doc in alice.get("/api/documents").json()["documents"]] == [note.name]
    assert bob.get("/api/documents").json()["documents"] == []
