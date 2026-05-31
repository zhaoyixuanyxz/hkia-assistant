from __future__ import annotations

from fastapi.testclient import TestClient

from app.chart_spec import GLOBAL_MAX_REPORT_CHARTS


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


def test_mvp_flow_registers_chat_report_stubs(api_client: TestClient) -> None:
    r = api_client.post(
        "/auth/register",
        json={"email": "u@example.com", "password": "secret12", "display_name": "U"},
    )
    assert r.status_code == 200, r.text

    r = api_client.post(
        "/auth/login",
        json={"email": "u@example.com", "password": "secret12"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    r = api_client.get("/auth/me", headers=h)
    assert r.status_code == 200

    r = api_client.post("/conversations", json={"title": "规划"}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    for i in range(10):
        r = api_client.post(
            f"/conversations/{cid}/messages",
            json={"content": f"第{i + 1}轮：关注家庭保障与预算"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        batch = r.json()
        assert len(batch) == 2
        assistant = batch[1]
        assert assistant["role"] == "assistant"
        text = assistant["content"]
        assert "不构成持牌" in text or "仅供参考" in text

    r = api_client.put(
        f"/conversations/{cid}/survey",
        json=_minimal_survey_body(),
        headers=h,
    )
    assert r.status_code == 200, r.text

    r = api_client.post(f"/conversations/{cid}/reports/generate", headers=h)
    assert r.status_code == 200, r.text
    rep = r.json()
    body = rep["body"]
    for key in (
        "user_background",
        "insights",
        "allocation_direction",
        "product_category_suggestions",
        "risk_notes",
        "disclaimer",
        "concrete_product_picks",
    ):
        assert key in body and str(body[key]).strip() != "", key
    charts = body["charts"]
    assert 1 <= len(charts) <= GLOBAL_MAX_REPORT_CHARTS
    assert len({c["type"] for c in charts}) >= 2
    assert "不构成持牌" in rep["disclaimer_text"] or "仅供参考" in rep["disclaimer_text"]

    r = api_client.get(f"/conversations/{cid}/reports/latest", headers=h)
    assert r.status_code == 200

    r = api_client.get("/knowledge/products?q=示例")
    assert r.status_code == 200
    products = r.json()
    assert products
    assert all("source_url" in p and p.get("is_sample") is True for p in products)

    rs = api_client.get("/knowledge/products/sample-prod-1")
    assert rs.status_code == 200
    assert rs.json()["id"] == "sample-prod-1"

    r = api_client.get("/market/indicators")
    assert r.status_code == 200
    rows = r.json()
    assert rows
    assert all("source_url" in x for x in rows)

    r = api_client.post("/market/refresh")
    assert r.status_code == 200
    assert r.json().get("ok") is True
