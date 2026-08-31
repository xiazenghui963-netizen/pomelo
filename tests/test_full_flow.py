import os
import time

os.environ["DATABASE_URL"] = "sqlite:///./test_pomelo.db"
os.environ["SECRET_KEY"] = "test_secret_key_long_enough_for_hmac_sha_256"

from fastapi.testclient import TestClient

from app.main import app

try:
    os.remove("test_pomelo.db")
except FileNotFoundError:
    pass

_token: str | None = None


def _poll_task(client, task_id: int, token: str, timeout: int = 30):
    h = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/tasks/{task_id}", headers=h)
        assert res.status_code == 200
        t = res.json()["data"]
        if t["status"] in ("success", "failed"):
            return t
        time.sleep(0.5)
    raise TimeoutError("task timeout")


def test_full_flow():
    global _token
    with TestClient(app) as client:
        r = client.post("/api/auth/register", json={"username": "tester01", "password": "test123456"})
        assert r.status_code == 200, r.text
        _token = r.json()["data"]["token"]
        assert r.json()["data"]["user"]["points"] == 100

        r = client.post("/api/auth/register", json={"username": "tester01", "password": "test123456"})
        assert r.status_code != 200

        r = client.post("/api/auth/login", json={"username": "tester01", "password": "test123456"})
        assert r.status_code == 200
        _token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {_token}"}

        # materials
        r = client.post("/api/materials", json={"title": "我的素材", "content": "我是一名自由职业自媒体人。"}, headers=h)
        assert r.status_code == 200, r.text
        material_id = r.json()["data"]["id"]

        r = client.get("/api/materials", headers=h)
        assert r.status_code == 200
        assert any(m["id"] == material_id for m in r.json()["data"])

        # create task
        r = client.post(
            "/api/tasks",
            json={
                "task_type": "create_content",
                "text": "新手如何开始做小红书自媒体",
                "use_materials": True,
                "material_ids": [material_id],
                "draw_image": False,
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        task_id = r.json()["data"]["task_id"]

        t = _poll_task(client, task_id, _token)
        assert t["status"] == "success", t
        assert t["result"]["titles"]
        assert t["result"]["note"]
        assert t["result"]["tags"]
        assert t["result"]["decompose"]

        # history list
        r = client.get("/api/tasks", headers=h)
        assert r.status_code == 200
        assert len(r.json()["data"]["items"]) >= 1

        # points deducted & user isolation
        r = client.get("/api/tasks/{invalid}".format(invalid=task_id), headers={"Authorization": "Bearer bad"})
        assert r.status_code in (401, 403) or r.json().get("code") != 0

        # member activate then rewrite flow (rewrite is member-only)
        r = client.post("/api/member/activate", json={}, headers=h)
        assert r.status_code == 200
        r = client.post(
            "/api/tasks",
            json={"task_type": "rewrite", "text": "今天天气很好，我去公园散步，看到很多花。"},
            headers=h,
        )
        assert r.status_code == 200
        rt = _poll_task(client, r.json()["data"]["task_id"], _token)
        assert rt["status"] == "success"
        assert "rewrite" in rt["result"]

        # delete task
        r = client.delete(f"/api/tasks/{task_id}", headers=h)
        assert r.status_code == 200

        # skills list
        r = client.get("/api/skills", headers=h)
        assert r.status_code == 200
        assert any(s["name"] == "skill_rewrite_note" for s in r.json()["data"])