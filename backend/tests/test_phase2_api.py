from __future__ import annotations

from fastapi.testclient import TestClient


def test_pin_soft_delete_and_detail_profile_fields(api_client: TestClient) -> None:
    r = api_client.post(
        "/auth/register",
        json={"email": "phase2@example.com", "password": "secret12", "display_name": "P"},
    )
    assert r.status_code == 200, r.text
    r = api_client.post(
        "/auth/login",
        json={"email": "phase2@example.com", "password": "secret12"},
    )
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = api_client.post("/conversations", json={"title": "t"}, headers=h)
    cid = r.json()["id"]

    r = api_client.patch(f"/conversations/{cid}", json={"is_pinned": True}, headers=h)
    assert r.status_code == 200
    row = r.json()
    assert row["is_pinned"] is True
    assert row.get("pinned_at")

    r = api_client.get("/conversations", headers=h)
    assert r.status_code == 200
    assert any(c["id"] == cid and c["is_pinned"] for c in r.json())

    r = api_client.delete(f"/conversations/{cid}", headers=h)
    assert r.status_code == 200

    r = api_client.get(f"/conversations/{cid}", headers=h)
    assert r.status_code == 404

    r = api_client.get("/conversations", headers=h)
    assert all(c["id"] != cid for c in r.json())
