from app.prompts import (
    build_insurance_expert_system,
    chat_body_rewrite_system,
    profile_structured_json_system,
    rolling_summary_system,
    profile_dual_source_fuse_system,
    report_json_system,
)


def test_expert_system_en_has_output_language_not_forced_zh() -> None:
    s = build_insurance_expert_system(200, 1200, locale="en")
    assert "English" in s or "Output language" in s
    assert "必须使用**简体中文**" not in s
    # must not contain the old hard-coded rewrite-only phrase as the sole language rule
    assert "改写成一段专业、审慎的中文" not in s


def test_rewrite_system_follows_locale() -> None:
    zh = chat_body_rewrite_system(200, 1200, locale="zh-CN")
    en = chat_body_rewrite_system(200, 1200, locale="en")
    assert "简体" in zh or "中文" in zh
    assert "English" in en or "英文" in en


def test_report_json_system_en() -> None:
    s = report_json_system(locale="en")
    assert "English" in s or "Output language" in s
    assert "均为中文内容字符串" not in s
    assert "report-writing assistant" in s or "You are the" in s