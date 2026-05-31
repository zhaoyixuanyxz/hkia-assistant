from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db as db_mod
from app.config import get_settings
from app.embeddings import MockEmbeddingService
from app.llm import MockLLM
from app.models import Product
from app.rag.retriever import HybridProductRetriever
from app.routers.conversations import get_llm_dep
from app.schemas import ProductRetrievalRequest
from app.main import app


def _auth_headers(api_client: TestClient) -> dict[str, str]:
    api_client.post(
        "/auth/register",
        json={"email": "phase3@example.com", "password": "secret12", "display_name": "P3"},
    )
    r = api_client.post(
        "/auth/login",
        json={"email": "phase3@example.com", "password": "secret12"},
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_products() -> None:
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        for pid in (
            "prod-family",
            "prod-critical",
            "prod-saving",
            "prod-annuity",
            "prod-obsolete",
        ):
            row = s.get(Product, pid)
            if row is not None:
                s.delete(row)
        s.flush()
        s.add_all(
            [
                Product(
                    id="prod-family",
                    name="家庭守护医疗计划",
                    category="医疗",
                    highlights="家庭保障优先",
                    coverage_summary="住院与门诊保障",
                    target_audience="有子女家庭",
                    clause_summary="等待期与免赔额说明",
                    official_url="https://example.com/family",
                    source_note="seed",
                    review_status="active",
                    is_sample=False,
                ),
                Product(
                    id="prod-critical",
                    name="重疾守护计划",
                    category="重疾",
                    highlights="重疾一次性给付",
                    coverage_summary="覆盖重大疾病",
                    target_audience="中青年家庭",
                    clause_summary="疾病定义以条款为准",
                    official_url="https://example.com/critical",
                    source_note="seed",
                    review_status="active",
                    is_sample=False,
                ),
                Product(
                    id="prod-saving",
                    name="储蓄传承计划",
                    category="储蓄",
                    highlights="长期储蓄与财富传承",
                    coverage_summary="现金价值累积",
                    target_audience="高净值家庭",
                    clause_summary="分红非保证",
                    official_url="https://example.com/saving",
                    source_note="seed",
                    review_status="active",
                    is_sample=False,
                ),
                Product(
                    id="prod-annuity",
                    name="退休年金计划",
                    category="储蓄",
                    highlights="退休现金流管理",
                    coverage_summary="年金领取方案",
                    target_audience="临近退休人群",
                    clause_summary="领取年龄规则",
                    official_url="https://example.com/annuity",
                    source_note="seed",
                    review_status="active",
                    is_sample=False,
                ),
                Product(
                    id="prod-obsolete",
                    name="过时产品",
                    category="医疗",
                    highlights="obsolete",
                    coverage_summary="obsolete",
                    target_audience="obsolete",
                    clause_summary="obsolete",
                    official_url="https://example.com/obsolete",
                    source_note="seed",
                    review_status="obsolete",
                    is_sample=False,
                ),
            ]
        )
        s.commit()
    finally:
        s.close()


def test_phase3_knowledge_market_and_admin_flow(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _auth_headers(api_client)
    _seed_products()

    rk = api_client.get("/knowledge/products?q=家庭&mode=keyword")
    assert rk.status_code == 200
    items = rk.json()
    assert any(x["id"] == "prod-family" for x in items)
    assert all(x["review_status"] == "active" for x in items)

    rd = api_client.get("/knowledge/products/prod-family")
    assert rd.status_code == 200
    det = rd.json()
    assert det["id"] == "prod-family"
    assert det["highlights"] == "家庭保障优先"

    r404 = api_client.get("/knowledge/products/prod-obsolete")
    assert r404.status_code == 404

    rs = api_client.get("/knowledge/products?q=重疾&mode=semantic")
    assert rs.status_code == 200
    sem = rs.json()
    assert sem
    assert "match_reason" in sem[0]

    rr = api_client.post("/market/refresh", headers=headers)
    assert rr.status_code == 200
    body = rr.json()
    assert body["ok"] is True
    assert body["status"] == "success"
    assert body.get("job_id")

    ru = api_client.get("/market/updates", headers=headers)
    assert ru.status_code == 200
    updates = ru.json()
    assert updates
    assert updates[0]["job_type"] == "market_refresh"

    monkeypatch.setenv("ADMIN_API_KEY", "phase3-admin")
    get_settings.cache_clear()
    unauth = api_client.patch("/admin/products/prod-family", json={"review_status": "active"})
    assert unauth.status_code == 401
    ok = api_client.patch(
        "/admin/products/prod-family",
        headers={"X-Admin-Key": "phase3-admin"},
        json={"review_status": "pending_review"},
    )
    assert ok.status_code == 200
    assert ok.json()["review_status"] == "pending_review"


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("家庭保障与住院医疗", {"医疗"}),
        ("重疾医疗配置", {"重疾", "医疗"}),
        ("储蓄传承安排", {"储蓄"}),
        ("退休年金现金流", {"储蓄"}),
    ],
)
def test_phase3_retrieval_scenarios(goal: str, expected: set[str], api_client: TestClient) -> None:
    _seed_products()
    retriever = HybridProductRetriever(MockEmbeddingService())
    req = ProductRetrievalRequest(
        profile_summary=goal,
        goals=goal,
        product_categories=[],
    )
    out = retriever.retrieve(req, limit=6)
    assert out
    cats = {x.category for x in out}
    assert cats & expected
    assert all(x.product_id != "prod-obsolete" for x in out)


def test_phase3_report_pick_contains_source_url(api_client: TestClient) -> None:
    headers = _auth_headers(api_client)
    _seed_products()
    report_json = json.dumps(
        {
            "title": "phase3 report",
            "user_background": "bg",
            "insights": "insight",
            "allocation_direction": "dir",
            "product_category_suggestions": "cat",
            "risk_notes": "risk",
            "follow_up_questions": ["q1"],
            "charts": [{"type": "radar", "title": "t", "data": [{"name": "n", "value": 1}]}],
            "concrete_product_picks": [
                {"product_id": "prod-family", "name": "家庭守护医疗计划", "rationale": ""}
            ],
            "limited_data_notice": "notice",
            "disclaimer": "仅供参考，不构成持牌建议",
        },
        ensure_ascii=False,
    )
    app.dependency_overrides[get_llm_dep] = lambda: MockLLM(report_json=report_json)
    try:
        r = api_client.post("/conversations", json={"title": "p3"}, headers=headers)
        cid = r.json()["id"]
        api_client.post(
            f"/conversations/{cid}/messages",
            json={"content": "我想看家庭医疗产品推荐"},
            headers=headers,
        )
        r_survey = api_client.put(
            f"/conversations/{cid}/survey",
            json={
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
            },
            headers=headers,
        )
        assert r_survey.status_code == 200, r_survey.text
        rep = api_client.post(f"/conversations/{cid}/reports/generate", headers=headers)
        assert rep.status_code == 200, rep.text
        picks = rep.json()["body"]["concrete_product_picks"]
        assert picks and picks[0]["source_url"] == "https://example.com/family"
    finally:
        app.dependency_overrides[get_llm_dep] = lambda: MockLLM()
