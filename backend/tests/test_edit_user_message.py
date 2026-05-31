from __future__ import annotations

from fastapi.testclient import TestClient


def test_patch_user_message_truncates_tail_and_regenerates(api_client: TestClient) -> None:
    r = api_client.post(
        "/auth/register",
        json={"email": "edit@example.com", "password": "secret12", "display_name": "E"},
    )
    assert r.status_code == 200, r.text
    r = api_client.post(
        "/auth/login",
        json={"email": "edit@example.com", "password": "secret12"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = api_client.post("/conversations", json={"title": "t"}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = api_client.post(
        f"/conversations/{cid}/messages",
        json={"content": "first round"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    u1 = r.json()[0]
    assert u1["role"] == "user"

    r = api_client.post(
        f"/conversations/{cid}/messages",
        json={"content": "second round"},
        headers=h,
    )
    assert r.status_code == 200, r.text

    r = api_client.get(f"/conversations/{cid}", headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()["messages"]) == 4

    r = api_client.patch(
        f"/conversations/{cid}/messages/{u1['id']}",
        json={"content": "first round corrected"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert len(batch) == 2
    assert batch[0]["content"] == "first round corrected"
    assert batch[1]["role"] == "assistant"

    r = api_client.get(f"/conversations/{cid}", headers=h)
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["content"] == "first round corrected"
    assert msgs[1]["role"] == "assistant"

