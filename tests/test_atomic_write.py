import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.registry.atomic_write import atomic_write_json


def test_writes_payload(tmp_path: Path):
    target = tmp_path / "out.json"
    payload = {"a": 1, "b": [1, 2, 3], "zh": "中文"}
    atomic_write_json(target, payload)
    assert target.exists()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == payload


def test_overwrites_existing(tmp_path: Path):
    target = tmp_path / "out.json"
    atomic_write_json(target, {"v": 1})
    atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 2}


def test_creates_missing_parent_dirs(tmp_path: Path):
    nested = tmp_path / "deep" / "nested" / "out.json"
    atomic_write_json(nested, {"ok": True})
    assert nested.exists()


def test_crash_preserves_original(tmp_path: Path):
    target = tmp_path / "out.json"
    atomic_write_json(target, {"version": "original"})

    with patch("scripts.registry.atomic_write.os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            atomic_write_json(target, {"version": "new"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"version": "original"}
    leftover_tmps = list(tmp_path.glob("*.tmp"))
    assert leftover_tmps == []


def test_unserializable_raises_and_leaves_original(tmp_path: Path):
    target = tmp_path / "out.json"
    atomic_write_json(target, {"v": 1})

    class NotSerializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": NotSerializable()})

    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert list(tmp_path.glob("*.tmp")) == []


def test_utf8_no_ascii_escape(tmp_path: Path):
    target = tmp_path / "zh.json"
    atomic_write_json(target, {"name": "診前問卷工具"})
    raw = target.read_text(encoding="utf-8")
    assert "診前問卷工具" in raw
    assert "\\u" not in raw
