import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze-t970-cadence.py"
SPEC = importlib.util.spec_from_file_location("analyze_t970_cadence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CadenceAnalysisTests(unittest.TestCase):
    def analyze(self, lines):
        rows, malformed = MODULE.parse_rows("\n".join(lines))
        return MODULE.aggregate(rows, malformed)

    def test_weighted_gap_routes_to_gpu_side(self):
        report = self.analyze([
            "x t970 scanout: state=2 smmu=1 span_s=2 flips=20 latched=20 copy_fallback=0 intervals=20 mean_us=25000 over_budget=12",
            "x t970 cadence: span_s=2 gap_n=20 gap_mean_us=30000 gap_over20=10 ack_n=20 ack_mean_us=500 ack_over3=0 ack_timeout=0 gap_idle=1",
            "x t970 cadence: span_s=2 gap_n=20 gap_mean_us=10000 gap_over20=0 ack_n=20 ack_mean_us=700 ack_over3=0 ack_timeout=0 gap_idle=0",
        ])
        self.assertEqual(report["cadence"]["gap_mean_us"], 20000)
        self.assertEqual(report["routing"]["hint"], "gpu_compositor_or_fence_gap")

    def test_ack_timeout_routes_to_display_side(self):
        line = ("x t970 cadence: span_s=2 gap_n=40 gap_mean_us=10000 gap_over20=0 "
                "ack_n=39 ack_mean_us=400 ack_over3=0 ack_timeout=1 gap_idle=0")
        report = self.analyze([line])
        self.assertEqual(report["routing"]["hint"], "dpu_flush_or_ack")

    def test_requires_both_sample_sets_and_counts_malformed_rows(self):
        report = self.analyze([
            "x t970 cadence: span_s=2 gap_n=40",
            "x t970 cadence: span_s=2 gap_n=40 gap_mean_us=10 gap_over20=0 ack_n=0 ack_mean_us=0 ack_over3=0 ack_timeout=0 gap_idle=2",
        ])
        self.assertEqual(report["rows"]["malformed"]["cadence"], 1)
        self.assertEqual(report["routing"]["hint"], "insufficient_samples")

    def test_gap_phase_routes_fence_after_arrival(self):
        line = ("x t970 gap-phase: span_s=2 n=40 arrival_mean_us=1000 arrival_over8=0 "
                "post_mean_us=6000 post_over3=30 prequeued=5 fence_n=30 fence_mean_us=5000 "
                "fence_over8=8 fence_slow250=0")
        report = self.analyze([line])
        self.assertEqual(report["gap_routing"]["hint"], "gpu_fence_after_swap_arrival")
        self.assertEqual(report["gap_phase"]["prequeued_rate"], 0.125)

    def test_gap_phase_routes_swap_arrival(self):
        line = ("x t970 gap-phase: span_s=2 n=40 arrival_mean_us=12000 arrival_over8=30 "
                "post_mean_us=500 post_over3=0 prequeued=0 fence_n=0 fence_mean_us=0 "
                "fence_over8=0 fence_slow250=0")
        report = self.analyze([line])
        self.assertEqual(report["gap_routing"]["hint"], "compositor_or_client_swap_arrival")


if __name__ == "__main__":
    unittest.main()
