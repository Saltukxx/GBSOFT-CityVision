from cityvision.pipeline.dataset_split import (
    assign_splits,
    clip_of,
    timestamp_of,
)


def _frames(prefix: str, n: int, step_ms: int = 1000) -> list[str]:
    return [f"{prefix}_{i * step_ms:07d}ms.jpg" for i in range(n)]


def test_clip_and_timestamp_parsing():
    assert clip_of("clip1_0012000ms.jpg") == "clip1"
    assert clip_of("dji_fly_20260816_175412_0008630ms.jpg") == "dji_fly_20260816_175412"
    assert timestamp_of("clip1_0012000ms.jpg") == 12000
    assert timestamp_of("odd-name.jpg") == 0


def test_test_prefix_is_held_out_whole():
    names = _frames("clip3", 10) + _frames("clip1", 10)
    splits = assign_splits(names, test_prefix="clip3")
    assert {splits[n] for n in _frames("clip3", 10)} == {"test"}
    assert "test" not in {splits[n] for n in _frames("clip1", 10)}


def test_tail_goes_to_val_with_guard_gap():
    names = _frames("clip1", 10)
    splits = assign_splits(names, test_prefix=None, val_tail_frac=0.2, guard_frames=1)
    assert [splits[n] for n in names] == [
        "train", "train", "train", "train", "train", "train", "train",
        "drop",
        "val", "val",
    ]


def test_val_block_never_borders_train_block():
    names = _frames("clip1", 40)
    splits = assign_splits(names, test_prefix=None, val_tail_frac=0.25, guard_frames=2)
    ordered = [splits[n] for n in names]
    for i in range(len(ordered) - 1):
        pair = {ordered[i], ordered[i + 1]}
        assert pair != {"train", "val"}


def test_every_clip_is_represented_in_both_splits():
    names = _frames("clip1", 20) + _frames("clip2", 20)
    splits = assign_splits(names, test_prefix=None)
    for prefix in ("clip1", "clip2"):
        got = {splits[n] for n in names if n.startswith(prefix)}
        assert "train" in got and "val" in got


def test_short_clip_stays_entirely_in_train():
    names = _frames("dji_short", 3)
    splits = assign_splits(names, test_prefix=None, val_tail_frac=0.2, guard_frames=1)
    assert set(splits.values()) == {"train"}


def test_unsorted_input_is_ordered_by_timestamp():
    names = list(reversed(_frames("clip1", 10)))
    splits = assign_splits(names, test_prefix=None, val_tail_frac=0.2, guard_frames=1)
    assert splits["clip1_0009000ms.jpg"] == "val"
    assert splits["clip1_0000000ms.jpg"] == "train"


def test_split_manifest_sha_is_stable_and_order_independent(tmp_path):
    from cityvision.pipeline.dataset_split import split_manifest_sha

    d = tmp_path / "val"
    d.mkdir()
    (d / "clip1_0000000ms.jpg").write_bytes(b"a")
    (d / "clip1_0001000ms.jpg").write_bytes(b"b")
    first = split_manifest_sha(d)
    (d / "clip1_0000000ms.jpg").write_bytes(b"changed-bytes-same-name")
    assert split_manifest_sha(d) == first
    (d / "clip1_0002000ms.jpg").write_bytes(b"c")
    assert split_manifest_sha(d) != first
