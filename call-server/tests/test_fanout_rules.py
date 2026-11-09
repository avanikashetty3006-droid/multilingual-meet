import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_monitor import (
    compute_lane_for_participant,
    should_want_audio,
    should_drop_overlap_for_queue,
)


def test_lane_computation_holder():
    lane = compute_lane_for_participant(
        pid="p-1",
        holder="p-1",
        overlap=["p-2", "p-3"],
        last_lane=None,
        max_overlap=2,
    )
    assert lane == "main"


def test_lane_computation_overlap_within_max():
    # 1st overlap participant (index 0 < 2)
    lane1 = compute_lane_for_participant(
        pid="p-2",
        holder="p-1",
        overlap=["p-2", "p-3", "p-4"],
        last_lane=None,
        max_overlap=2,
    )
    assert lane1 == "overlap"

    # 2nd overlap participant (index 1 < 2)
    lane2 = compute_lane_for_participant(
        pid="p-3",
        holder="p-1",
        overlap=["p-2", "p-3", "p-4"],
        last_lane=None,
        max_overlap=2,
    )
    assert lane2 == "overlap"


def test_lane_computation_beyond_max_overlap():
    # 3rd overlap participant (index 2 >= max_overlap=2) -> None (ignored)
    lane = compute_lane_for_participant(
        pid="p-4",
        holder="p-1",
        overlap=["p-2", "p-3", "p-4"],
        last_lane=None,
        max_overlap=2,
    )
    assert lane is None


def test_lane_computation_absent_keeps_last_lane():
    # If participant is not in holder and not in overlap, keep last_lane
    lane = compute_lane_for_participant(
        pid="p-released",
        holder="p-new-holder",
        overlap=[],
        last_lane="main",
        max_overlap=2,
    )
    assert lane == "main"


def test_want_audio_policy():
    # Main lane with audio listener -> True
    assert should_want_audio(lane="main", is_any_listener_audio=True) is True

    # Main lane with subtitle-only listeners -> False
    assert should_want_audio(lane="main", is_any_listener_audio=False) is False

    # Overlap lane is ALWAYS False (even if listeners are in audio mode)
    assert should_want_audio(lane="overlap", is_any_listener_audio=True) is False
    assert should_want_audio(lane="overlap", is_any_listener_audio=False) is False

    # No lane -> False
    assert should_want_audio(lane=None, is_any_listener_audio=True) is False


def test_drop_overlap_for_queue():
    # Overlap chunk dropped when in_flight >= max_queue_depth (8)
    assert should_drop_overlap_for_queue(lane="overlap", in_flight=8, queue_depth=0, max_queue_depth=8) is True

    # Overlap chunk dropped when speech service queue_depth > max_queue_depth (8)
    assert should_drop_overlap_for_queue(lane="overlap", in_flight=2, queue_depth=9, max_queue_depth=8) is True

    # Overlap chunk allowed when normal queue
    assert should_drop_overlap_for_queue(lane="overlap", in_flight=2, queue_depth=3, max_queue_depth=8) is False

    # MAIN lane chunk is NEVER dropped for queue load reasons
    assert should_drop_overlap_for_queue(lane="main", in_flight=12, queue_depth=20, max_queue_depth=8) is False
