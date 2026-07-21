from app.locale_support import normalize_locale, output_language_instruction


def test_normalize_locale_accepts_supported() -> None:
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("en") == "en"
    assert normalize_locale("zh-TW") == "zh-TW"


def test_normalize_locale_defaults() -> None:
    assert normalize_locale(None) == "zh-CN"
    assert normalize_locale("") == "zh-CN"
    assert normalize_locale("fr") == "zh-CN"
    assert normalize_locale("EN") == "zh-CN"  # exact match only; no case fold


def test_output_language_instruction_en_mentions_english() -> None:
    text = output_language_instruction("en")
    assert "English" in text
    assert "简体中文" not in text


def test_output_language_instruction_zh_tw() -> None:
    text = output_language_instruction("zh-TW")
    assert "繁體中文" in text
