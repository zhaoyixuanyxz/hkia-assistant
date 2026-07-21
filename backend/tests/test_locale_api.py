from __future__ import annotations

from fastapi.testclient import TestClient

from app.compliance import disclaimer_for


def _auth_headers(api_client: TestClient, email: str) -> dict[str, str]:
    r = api_client.post(
        "/auth/register",
        json={"email": email, "password": "secret12", "display_name": "L"},
    )
    assert r.status_code == 200, r.text
    r = api_client.post(
        "/auth/login",
        json={"email": email, "password": "secret12"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _minimal_survey_body() -> dict:
    return {
        "answers": {
            "age_band": "25-34",
            "residency_region": "香港",
            "marital_dependents_summary": "单身无供养",
            "occupation_category": "雇员（办公室）",
            "income_band": "每月可动用收入：2万-5万港币",
            "premium_afford_ratio_band": "10%-20%",
            "primary_goals": ["critical_illness", "medical_hospital"],
        },
        "status": "saved",
        "merge_to_profile": False,
        "sync_to_user_library": False,
    }


def test_post_message_accepts_locale_en(api_client: TestClient) -> None:
    h = _auth_headers(api_client, "locale-en@example.com")
    r = api_client.post("/conversations", json={"title": "en"}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = api_client.post(
        f"/conversations/{cid}/messages",
        json={"content": "Hello, focus on hospital cover", "locale": "en"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    assert len(batch) == 2
    assistant = batch[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"].endswith(disclaimer_for("en"))
    assert disclaimer_for("zh-CN") not in assistant["content"]


def test_post_message_without_locale_uses_zh_cn_disclaimer(
    api_client: TestClient,
) -> None:
    h = _auth_headers(api_client, "locale-default@example.com")
    r = api_client.post("/conversations", json={"title": "zh"}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = api_client.post(
        f"/conversations/{cid}/messages",
        json={"content": "关注家庭保障与预算"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assistant = r.json()[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"].endswith(disclaimer_for("zh-CN"))


def test_generate_report_accepts_locale_en_body(api_client: TestClient) -> None:
    h = _auth_headers(api_client, "locale-report@example.com")
    r = api_client.post("/conversations", json={"title": "rep"}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r = api_client.post(
        f"/conversations/{cid}/messages",
        json={"content": "Need a report on medical cover", "locale": "en"},
        headers=h,
    )
    assert r.status_code == 200, r.text

    r = api_client.put(
        f"/conversations/{cid}/survey",
        json=_minimal_survey_body(),
        headers=h,
    )
    assert r.status_code == 200, r.text

    r = api_client.post(
        f"/conversations/{cid}/reports/generate",
        json={"locale": "en"},
        headers=h,
    )
    assert r.status_code != 422, r.text
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["disclaimer_text"] == disclaimer_for("en") or rep[
        "disclaimer_text"
    ].endswith(disclaimer_for("en"))
