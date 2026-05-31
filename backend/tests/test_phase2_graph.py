from __future__ import annotations

from unittest.mock import MagicMock

from app.agents.conversation_runner import run_conversation_turn
from app.agents.report_graph import build_report_graph
from app.embeddings import MockEmbeddingService
from app.llm import LLMService
from app.rag.retriever import HybridProductRetriever


def test_conversation_runner_skips_profile_when_not_scheduled() -> None:
    llm = MagicMock(spec=LLMService)
    llm.chat.return_value = (
        "您好。我们先从你最关心的保障缺口谈起：是更担心住院医疗费用、重疾一次性给付，"
        "还是家庭支柱的身故风险？请先选一项主关切，我再结合你的情况建议讨论的先后次序，"
        "避免信息分散。若你已有公司团险或自愿医保，也可一并说明，便于判断重叠与缺口。\n\n"
        "以上内容仅供一般信息参考，不构成持牌财务、保险、税务或法律建议；"
        "具体条款以保险公司正式文件及合资格专业人士意见为准。"
    )
    llm.complete_json_text.return_value = (
        '{"summary_text":"结构化摘要","dimensions":{"finance":"","family":"","health":"",'
        '"goals":"","risk_appetite":"","life_stage":"","values":""},'
        '"key_memories":["偏好稳健"],"product_focus_categories":["医疗"],"budget_hint":""}'
    )

    def _rewrite(body: str, min_len: int, max_len: int) -> str:
        s = body.strip()
        if min_len <= len(s) <= max_len:
            return s
        if len(s) > max_len:
            return s[:max_len]
        return (
            "收到。测试侧将顾问正文重写至区间内以便覆盖篇幅规则，"
            "并保留专业审慎语气与一条可执行追问，便于集成断言。"
            "如需更贴切可补充保障责任或预算与已有保单线索，便于细化配置判断。"
        )

    llm.rewrite_chat_body_to_length.side_effect = _rewrite
    llm.complete_json_text.reset_mock()
    out = run_conversation_turn(
        {
            "conversation_id": 1,
            "user_id": 1,
            "user_message": "hello",
            "messages_history": [{"role": "user", "content": "hello"}],
            "profile_summary": "",
            "profile_structured": None,
            "key_memories": [],
            "retrieval_context": "",
            "run_profile_architect": False,
            "rolling_summary": "",
        },
        llm,
    )
    assert out.get("assistant_reply")
    assert out.get("profile_refresh_done") is False
    llm.complete_json_text.assert_not_called()

    llm.complete_json_text.reset_mock()
    out = run_conversation_turn(
        {
            "conversation_id": 1,
            "user_id": 1,
            "user_message": "again",
            "messages_history": [{"role": "user", "content": "again"}],
            "profile_summary": "",
            "profile_structured": {"summary_text": "x"},
            "key_memories": [],
            "retrieval_context": "",
            "run_profile_architect": True,
            "rolling_summary": "",
        },
        llm,
    )
    assert out.get("profile_refresh_done") is True
    llm.complete_json_text.assert_called_once()


def test_report_graph_produces_candidates_and_body() -> None:
    from app.llm import MockLLM

    llm = MockLLM()
    retriever = HybridProductRetriever(MockEmbeddingService())
    rg = build_report_graph(llm, retriever)
    out = rg.invoke(
        {
            "conversation_id": 7,
            "transcript": "user: 关注医疗保障\nassistant: 收到",
            "profile_summary": "关注医疗保障",
            "profile_structured": {"product_focus_categories": ["医疗"]},
        }
    )
    assert out.get("candidates")
    body = out.get("report_payload_dict") or {}
    assert body.get("charts")
    assert "concrete_product_picks" in body
