import unittest

from tests.five_phase_test_helpers import make_field_state
from world_engine.contracts import ProjectionFrame
from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.five_phase_patterns import detect_five_phase_patterns
from world_engine.five_phase_traces import attach_five_phase_trace_summary, build_five_phase_trace


def _grid() -> list[list[float]]:
    grid = [[0.0 for _ in range(10)] for _ in range(10)]
    for row in range(3, 7):
        for col in range(3, 7):
            grid[row][col] = 0.8
    return grid


def _frame(tick: int) -> ProjectionFrame:
    return ProjectionFrame(
        frame_id=f"projection-frame::five-phase::{tick}",
        tick=tick,
        observer_id="observer::trace-test",
        image_plane={"schema": "test_image_plane_v1"},
        samples=[],
        phenomena_overlays=[],
        source_state_ticks=[tick],
        source_object_ids=[],
        source_record_ids=["field-state::trace-test"],
        is_authority_state=False,
        audit={
            "projection_semantics": "observer_projection_not_authority",
            "no_persistent_light_object": True,
            "no_material_asset_authority": True,
            "no_global_raindrop_authority_state": True,
        },
        payload={
            "event_timeline": {
                "tick": tick,
                "event_kinds": [],
                "interaction_record_ids": [],
                "wave_step_record_ids": [],
                "field_structure_event_ids": [],
                "source_record_ids": ["field-state::trace-test"],
                "observer_id": "observer::trace-test",
                "is_authority_state": False,
            }
        },
    )


class FivePhaseTraceTests(unittest.TestCase):
    def test_trace_is_observer_specific_with_projection_loss_manifest(self) -> None:
        state = make_field_state(_grid(), previous_grid=_grid(), tick=0, field_state_id="field-state::trace-test")
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)

        low = build_five_phase_trace(patterns[0], phase, observer_id="observer::low", frequency_window={"band": "low"})
        high = build_five_phase_trace(patterns[0], phase, observer_id="observer::high", frequency_window={"band": "high"})

        self.assertFalse(low.is_authority_state)
        self.assertEqual("five_phase_projection_loss_manifest_v1", low.projection_loss_manifest["schema"])
        self.assertNotEqual(low.phase_response.to_dict(), high.phase_response.to_dict())
        self.assertIn(patterns[0].record_id, low.source_record_ids)

    def test_trace_summary_attaches_to_projection_without_authority(self) -> None:
        state = make_field_state(_grid(), previous_grid=_grid(), tick=0, field_state_id="field-state::trace-summary")
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)
        trace = build_five_phase_trace(patterns[0], phase, observer_id="observer::trace-test", frequency_window={"band": "wide"})

        attached = attach_five_phase_trace_summary(_frame(0), [trace])

        summary = attached.payload["five_phase_trace_summary"]
        self.assertFalse(summary["is_authority_state"])
        self.assertIn(trace.record_id, summary["trace_ids"])
        self.assertIn(trace.record_id, attached.source_record_ids)


if __name__ == "__main__":
    unittest.main()
