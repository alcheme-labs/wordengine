import tempfile
import unittest
from pathlib import Path

from scripts.run_five_phase_live_world_validation import run_five_phase_live_world_validation


class FivePhaseLiveValidationRunnerTests(unittest.TestCase):
    def test_runner_emits_pass_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_five_phase_live_world_validation(output_dir=Path(tmp), ticks=4)

            self.assertEqual("passed", report["overall_status"])
            self.assertEqual(1, report["expected_case_count"])
            self.assertEqual(1, report["case_count"])
            self.assertEqual(1, report["cases_passed"])
            self.assertEqual("passed", report["completion"]["overall_status"])
            self.assertEqual(report["projection_frame_count"], report["five_phase_live_step_count"])
            self.assertTrue((Path(tmp) / "five_phase_live_world_report.json").exists())
            self.assertTrue((Path(tmp) / "viewer" / "projection_frames.jsonl").exists())
            self.assertTrue((Path(tmp) / "viewer" / "viewer.html").exists())


if __name__ == "__main__":
    unittest.main()
