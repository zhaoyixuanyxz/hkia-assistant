from __future__ import annotations

from app.prompts import PROFILE_DUAL_SOURCE_FUSE_MARKER
from app.llm import MockLLM
from app.report_integrated_profile import (
    build_integrated_profile_for_report,
    merge_dimension_pair,
    merge_structured_dual_source,
    rule_based_integrated_summary,
)
from app.survey_template import validate_survey_answers

from tests.test_survey_report import _full_answers


def test_merge_dimension_pair_prefers_more_specific_when_subset() -> None:
    assert merge_dimension_pair("常住香港（工作）", "香港") == "常住香港（工作）"


def test_merge_dimension_pair_concat_when_distinct() -> None:
    a = merge_dimension_pair("关注住院自付", "希望加强人寿")
    assert "住院" in a and "人寿" in a


def test_merge_structured_dual_source_fills_from_survey() -> None:
    a = validate_survey_answers(_full_answers())
    merged = merge_structured_dual_source(None, a)
    dims = merged.get("dimensions") or {}
    assert str(dims.get("life_stage") or "")
    assert merged.get("budget_hint")
    assert merged.get("profile_dual_source_integrated_at") == "report_generate"


def test_merge_structured_dual_source_complements_conversation() -> None:
    a = validate_survey_answers(_full_answers())
    struct = {
        "dimensions": {
            "finance": "",
            "family": "",
            "health": "",
            "goals": "对话侧：优先厘清住院与免赔",
            "risk_appetite": "",
            "life_stage": "",
            "values": "",
        }
    }
    merged = merge_structured_dual_source(struct, a)
    g = str(merged["dimensions"].get("goals") or "")
    assert "对话侧" in g or "住院" in g
    assert "medical" not in g.lower()


def test_build_integrated_profile_mock_llm_fuse_branch() -> None:
    """Fuse call must run even when MockLLM is configured with fixed report_json."""
    llm = MockLLM(report_json='{"oops":"not-report"}')
    a = validate_survey_answers(_full_answers())
    summ, merged, mode = build_integrated_profile_for_report(
        llm,
        conversation_profile_summary="会话侧简述：家庭医疗保障",
        conversation_structured={"dimensions": {"goals": "对话：医疗优先"}},
        survey_answers=a,
        survey_block="调查表摘录（测试）",
    )
    assert mode == "llm_dual_source_fuse"
    assert "测试双线融合" in summ
    assert merged.get("dimensions")


def test_rule_based_integrated_summary_includes_dimensions() -> None:
    merged = merge_structured_dual_source(None, validate_survey_answers(_full_answers()))
    text = rule_based_integrated_summary("", merged, "表内原文片段")
    assert "融合画像" in text or "结构化" in text
    assert "25-34" in text or "香港" in text


class BrokenFuseLLM(MockLLM):
    """LLM fuse returns invalid JSON → rule_fallback."""

    def complete_json_text(
        self, user_prompt: str, system: str, *, max_tokens: int | None = None
    ) -> str:
        if PROFILE_DUAL_SOURCE_FUSE_MARKER in system:
            return "{"
        return super().complete_json_text(user_prompt, system, max_tokens=max_tokens)


def test_build_integrated_profile_rule_fallback_on_bad_json() -> None:
    llm = BrokenFuseLLM()
    a = validate_survey_answers(_full_answers())
    summ, _merged, mode = build_integrated_profile_for_report(
        llm,
        conversation_profile_summary="",
        conversation_structured=None,
        survey_answers=a,
        survey_block="调查表内容",
    )
    assert mode == "rule_fallback"
    assert len(summ) >= 80

