import random

from app.closing_probe import is_explicit_decline, pick_closing_probe, CLOSING_PROBE_POOL


def test_explicit_decline_detected_on_short_thanks():
    assert is_explicit_decline("谢谢") is True
    assert is_explicit_decline("没有了") is True


def test_explicit_decline_not_triggered_on_longer_message_containing_keyword():
    assert is_explicit_decline("谢谢，不过我还想问问血压怎么自测") is False


def test_pick_closing_probe_returns_pool_member_deterministically():
    rng = random.Random(0)
    result = pick_closing_probe(rng)
    assert result in CLOSING_PROBE_POOL
