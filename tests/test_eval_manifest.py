import pytest

from cityvision.pipeline.eval_gate import check_split_manifest


def test_missing_baseline_hash_returns_warning():
    warn = check_split_manifest("abc", {"overall": {"map50": 0.1}})
    assert warn is not None and "split_manifest yok" in warn


def test_matching_hash_is_silent():
    assert check_split_manifest("abc", {"split_manifest": "abc"}) is None


def test_mismatched_hash_raises():
    with pytest.raises(ValueError, match="split_manifest uyuşmuyor"):
        check_split_manifest("abc", {"split_manifest": "def"})


def test_no_baseline_is_ok():
    assert check_split_manifest("abc", None) is None
