from app.self_check import run_self_check
from app.schemas import KBEntry
from tests.fakes import FakeLLMClient


def _entry():
    return KBEntry(id="a", sub_type="lifestyle_education", question_topic="钾",
                    keywords=["钾"], answer_body="香蕉橙子菠菜富含钾", source_note="演示数据")


def test_run_self_check_passes_when_llm_says_all_pass():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    result = run_self_check("含钾食物有香蕉橙子", _entry(), "lifestyle_education", llm)
    assert result.overall_pass is True


def test_run_self_check_fails_when_llm_flags_grounding():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": False,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": False, "violations": ["提到的具体数值在条目中找不到依据"]})
    result = run_self_check("每天应补钾3500mg", _entry(), "lifestyle_education", llm)
    assert result.overall_pass is False
    assert result.grounding_pass is False
    assert result.violations


def test_run_self_check_forces_format_fail_on_overlong_reply():
    llm = FakeLLMClient()
    llm.queue_json({"compliance_pass": True, "grounding_pass": True,
                     "disclaimer_pass": True, "format_pass": True,
                     "overall_pass": True, "violations": []})
    long_reply = "香蕉橙子富含钾。" * 60  # far over 320 chars
    result = run_self_check(long_reply, _entry(), "lifestyle_education", llm)
    assert result.format_pass is False
    assert result.overall_pass is False
    assert any("320" in v for v in result.violations)
