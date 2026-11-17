#!/usr/bin/env python3
"""Summarize T970 direct-scanout cadence delta rows from an iPadOS syslog."""

import argparse
import json
import re
from pathlib import Path


MARKERS = {
    "scanout": "t970 scanout:",
    "cadence": "t970 cadence:",
    "gap_phase": "t970 gap-phase:",
}
PAIR = re.compile(r"\b([a-z][a-z0-9_]*)=([0-9]+)\b")
REQUIRED = {
    "scanout": {"span_s", "flips", "latched", "copy_fallback", "intervals", "mean_us", "over_budget"},
    "cadence": {"span_s", "gap_n", "gap_mean_us", "gap_over20", "ack_n", "ack_mean_us",
                "ack_over3", "ack_timeout", "gap_idle"},
    "gap_phase": {"span_s", "n", "arrival_mean_us", "arrival_over8", "post_mean_us", "post_over3",
                  "prequeued", "fence_n", "fence_mean_us", "fence_over8", "fence_slow250"},
}


def parse_rows(text):
    rows = {name: [] for name in MARKERS}
    malformed = {name: 0 for name in MARKERS}
    for line in text.splitlines():
        for name, marker in MARKERS.items():
            if marker not in line:
                continue
            values = {key: int(value) for key, value in PAIR.findall(line.split(marker, 1)[1])}
            # cadence-b's first device image called the existing >=250 ms
            # slow-wait counter a timeout. Accept that one recorded spelling.
            if name == "gap_phase" and "fence_slow250" not in values and "fence_timeout" in values:
                values["fence_slow250"] = values.pop("fence_timeout")
            if REQUIRED[name] <= values.keys():
                rows[name].append(values)
            else:
                malformed[name] += 1
            break
    return rows, malformed


def weighted_mean(rows, count_key, mean_key):
    count = sum(row[count_key] for row in rows)
    if not count:
        return None
    # The kernel delta row exposes the integer window mean, not its private
    # total. Weighting each window is therefore accurate to <1 us per sample.
    total = sum(row[count_key] * row[mean_key] for row in rows)
    return total / count


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def aggregate(rows, malformed):
    scanout = rows["scanout"]
    cadence = rows["cadence"]
    phases = rows["gap_phase"]
    result = {
        "format": 1,
        "rows": {"scanout": len(scanout), "cadence": len(cadence), "malformed": malformed},
        "scanout": {
            "span_seconds": sum(row["span_s"] for row in scanout),
            "flips": sum(row["flips"] for row in scanout),
            "latched": sum(row["latched"] for row in scanout),
            "copy_fallback": sum(row["copy_fallback"] for row in scanout),
            "intervals": sum(row["intervals"] for row in scanout),
            "mean_interval_us": weighted_mean(scanout, "intervals", "mean_us"),
            "over_budget": sum(row["over_budget"] for row in scanout),
        },
        "cadence": {
            "span_seconds": sum(row["span_s"] for row in cadence),
            "gap_samples": sum(row["gap_n"] for row in cadence),
            "gap_mean_us": weighted_mean(cadence, "gap_n", "gap_mean_us"),
            "gap_over_20ms": sum(row["gap_over20"] for row in cadence),
            "ack_samples": sum(row["ack_n"] for row in cadence),
            "ack_mean_us": weighted_mean(cadence, "ack_n", "ack_mean_us"),
            "ack_over_3ms": sum(row["ack_over3"] for row in cadence),
            "ack_timeout": sum(row["ack_timeout"] for row in cadence),
            "idle_gap_excluded": sum(row["gap_idle"] for row in cadence),
        },
        "gap_phase": {
            "span_seconds": sum(row["span_s"] for row in phases),
            "samples": sum(row["n"] for row in phases),
            "arrival_mean_us": weighted_mean(phases, "n", "arrival_mean_us"),
            "arrival_over_8ms": sum(row["arrival_over8"] for row in phases),
            "post_arrival_mean_us": weighted_mean(phases, "n", "post_mean_us"),
            "post_arrival_over_3ms": sum(row["post_over3"] for row in phases),
            "prequeued": sum(row["prequeued"] for row in phases),
            "fence_waits": sum(row["fence_n"] for row in phases),
            "fence_mean_us": weighted_mean(phases, "fence_n", "fence_mean_us"),
            "fence_over_8ms": sum(row["fence_over8"] for row in phases),
            "fence_slow_250ms": sum(row["fence_slow250"] for row in phases),
        },
    }
    c = result["cadence"]
    c["gap_over_20ms_rate"] = rate(c["gap_over_20ms"], c["gap_samples"])
    c["ack_over_3ms_rate"] = rate(c["ack_over_3ms"], c["ack_samples"])
    result["routing"] = routing_hint(c)
    p = result["gap_phase"]
    p["arrival_over_8ms_rate"] = rate(p["arrival_over_8ms"], p["samples"])
    p["post_arrival_over_3ms_rate"] = rate(p["post_arrival_over_3ms"], p["samples"])
    p["prequeued_rate"] = rate(p["prequeued"], p["samples"])
    p["fence_over_8ms_rate"] = rate(p["fence_over_8ms"], p["fence_waits"])
    result["gap_routing"] = gap_routing_hint(p)
    return result


def routing_hint(cadence):
    minimum = 30
    if cadence["gap_samples"] < minimum or cadence["ack_samples"] < minimum:
        return {
            "hint": "insufficient_samples",
            "reason": f"need at least {minimum} non-idle gap and confirmed ACK samples",
            "device_verified": False,
        }
    gap_slow = (cadence["gap_mean_us"] >= 20_000 or
                cadence["gap_over_20ms_rate"] >= 0.05)
    ack_slow = (cadence["ack_timeout"] > 0 or cadence["ack_mean_us"] >= 3_000 or
                cadence["ack_over_3ms_rate"] >= 0.05)
    if gap_slow and ack_slow:
        hint = "mixed_gap_and_ack"
    elif gap_slow:
        hint = "gpu_compositor_or_fence_gap"
    elif ack_slow:
        hint = "dpu_flush_or_ack"
    else:
        hint = "cadence_within_probe_thresholds"
    return {
        "hint": hint,
        "reason": "routing heuristic from 20 ms gap and 3 ms ACK thresholds; inspect raw rows before changing code",
        "device_verified": False,
    }


def gap_routing_hint(phase):
    minimum = 30
    if phase["samples"] < minimum:
        return {
            "hint": "insufficient_samples",
            "reason": f"need at least {minimum} accounted active gaps",
            "device_verified": False,
        }
    arrival_slow = (phase["arrival_mean_us"] >= 8_000 or
                    phase["arrival_over_8ms_rate"] >= 0.05)
    post_slow = (phase["post_arrival_mean_us"] >= 3_000 or
                 phase["post_arrival_over_3ms_rate"] >= 0.05)
    fence_slow = (phase["fence_slow_250ms"] > 0 or
                  (phase["fence_mean_us"] is not None and phase["fence_mean_us"] >= 3_000) or
                  (phase["fence_over_8ms_rate"] is not None and phase["fence_over_8ms_rate"] >= 0.05))
    if arrival_slow and post_slow:
        hint = "mixed_swap_arrival_and_post_arrival"
    elif arrival_slow:
        hint = "compositor_or_client_swap_arrival"
    elif post_slow and fence_slow:
        hint = "gpu_fence_after_swap_arrival"
    elif post_slow:
        hint = "display_queue_or_surface_mapping"
    else:
        hint = "gap_phases_within_probe_thresholds"
    return {
        "hint": hint,
        "reason": "routing heuristic from 8 ms arrival, 3 ms post-arrival and measured fence waits; inspect raw rows before changing code",
        "device_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("syslog", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows, malformed = parse_rows(args.syslog.read_text(errors="replace"))
    report = aggregate(rows, malformed)
    report["source"] = str(args.syslog)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0 if report["rows"]["cadence"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
