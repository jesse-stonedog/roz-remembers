"""What `Store` does when the filesystem does not cooperate.

Every case here was REPRODUCED against the previous implementation before being
fixed, which is why they are phrased as behaviours rather than as regressions.
The one that matters most is the first: a save that failed part-way left an
empty file where the state used to be, destroying data that was already safe.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest import mock

import pytest

from stonedog_remembers import MISSING, Store


# ── save() is atomic ─────────────────────────────────────────────────────────

def test_a_failed_save_leaves_the_previous_state_intact(tmp_path: Path) -> None:
    """The defect this file exists for.

    `open(target, "w")` truncates before writing, so anything that goes wrong
    after it — a full disk, a killed process, an unserialisable value — used to
    leave an EMPTY file. Measured: `{"important": "previous state"}` became `''`.
    """
    target = tmp_path / "state.json"
    target.write_text('{"important": "previous state"}')

    with mock.patch("json.dump", side_effect=OSError("no space left on device")):
        with pytest.raises(OSError):
            Store({"new": "value"}).save(str(target))

    assert json.loads(target.read_text()) == {"important": "previous state"}


def test_a_failed_save_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    """Otherwise every failed save litters the directory it could not write to."""
    target = tmp_path / "state.json"
    target.write_text("{}")

    with mock.patch("json.dump", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            Store({"a": 1}).save(str(target))

    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_the_temporary_file_is_in_the_targets_own_directory(tmp_path: Path) -> None:
    """`os.replace` across filesystems fails with EXDEV.

    A temp file in the system temp directory works on a laptop and fails on any
    host where the state lives on a different mount — which is precisely where
    it would be discovered. This asserts the directory rather than the outcome,
    because on a single-filesystem test machine the outcome is identical either
    way and would prove nothing.
    """
    target = tmp_path / "nested" / "state.json"
    target.parent.mkdir()
    seen: list[str] = []

    real_mkstemp = __import__("tempfile").mkstemp

    def spy(*args, **kwargs):
        seen.append(kwargs.get("dir", ""))
        return real_mkstemp(*args, **kwargs)

    with mock.patch("tempfile.mkstemp", side_effect=spy):
        Store({"a": 1}).save(str(target))

    assert seen and os.path.abspath(seen[0]) == os.path.abspath(target.parent)


def test_a_successful_save_round_trips(tmp_path: Path) -> None:
    """The positive control. Every assertion above is satisfied by a save that
    never writes anything at all."""
    target = tmp_path / "state.json"
    Store({"job": {"bins": 10}}).save(str(target))

    assert json.loads(target.read_text()) == {"job": {"bins": 10}}
    assert Store(state_file=str(target)).get("job.bins") == 10


def test_save_still_raises_when_it_cannot_write(tmp_path: Path) -> None:
    """It must NOT swallow this.

    A save that cannot write is a fact the caller needs. A library that hid it
    would lose data silently for every future consumer in order to spare one of
    them a try/except — and the caller for whom persistence is a convenience is
    the one that should be catching it.
    """
    directory = tmp_path / "readonly"
    directory.mkdir()
    os.chmod(directory, stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(OSError):
            Store({"a": 1}).save(str(directory / "state.json"))
    finally:
        os.chmod(directory, stat.S_IRWXU)


# ── load() degrades rather than raising ──────────────────────────────────────

def test_a_missing_file_starts_empty(tmp_path: Path) -> None:
    assert Store(state_file=str(tmp_path / "absent.json")).get_state() == {}


def test_a_directory_where_a_file_was_expected_starts_empty(tmp_path: Path) -> None:
    """`IsADirectoryError` is an `OSError`, not a `FileNotFoundError`, so it used
    to escape from inside `__init__` — a constructor every caller would then
    have to wrap."""
    directory = tmp_path / "adir"
    directory.mkdir()

    assert Store(state_file=str(directory)).get_state() == {}


def test_an_unreadable_file_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}")
    os.chmod(path, 0)
    try:
        assert Store(state_file=str(path)).get_state() == {}
    finally:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def test_malformed_json_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not json")

    assert Store(state_file=str(path)).get_state() == {}


@pytest.mark.parametrize("document", ["[1, 2, 3]", '"hello"', "42", "null"])
def test_json_that_is_not_an_object_starts_empty(tmp_path: Path, document: str) -> None:
    """It used to be ACCEPTED, and the result was a store that had quietly
    stopped storing: `set()` returned False forever and `get()` always returned
    the default, with a warning nobody reads."""
    path = tmp_path / "state.json"
    path.write_text(document)

    store = Store(state_file=str(path))
    assert store.get_state() == {}
    assert store.set("a.b", 1) is True
    assert store.get("a.b") == 1


def test_a_valid_object_is_loaded(tmp_path: Path) -> None:
    """The positive control for every degradation case above."""
    path = tmp_path / "state.json"
    path.write_text('{"job": {"bins": 7}}')

    assert Store(state_file=str(path)).get("job.bins") == 7


# ── get() distinguishes missing from stored-None ─────────────────────────────

def test_a_stored_none_is_returned_rather_than_the_default() -> None:
    """"Missing" and "explicitly nothing" are different facts.

    A stored `None` usually means somebody decided, and the answer was nothing.
    Returning the caller's default for it silently replaces a decision.
    """
    store = Store({"answer": None})

    assert store.get("answer", "DEFAULT") is None
    assert store.has("answer") is True


def test_a_missing_path_still_returns_the_default() -> None:
    store = Store({"answer": None})

    assert store.get("nothing.here", "DEFAULT") == "DEFAULT"
    assert store.has("nothing.here") is False


@pytest.mark.parametrize("value", [0, False, "", [], {}])
def test_falsy_values_survive_a_get(value: object) -> None:
    """These were never broken, and are asserted so a sentinel fix cannot break
    them on the way past."""
    store = Store({"v": value})

    assert store.get("v", "DEFAULT") == value


def test_the_sentinel_is_not_something_a_caller_can_store_by_accident() -> None:
    assert MISSING is not None
    assert bool(MISSING) is False
