"""
report_generator.py — Terminal & CSV Report Output
Toll Plaza Revenue Leak Analysis System
"""

import csv
import os
from datetime import datetime

from anomaly_detector import AnalysisResult, Anomaly, summarize_by_lane, summarize_by_shift, summarize_by_operator

# ── ANSI Colors ───────────────────────────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

SEV_COLOR = {"HIGH": RED, "MEDIUM": YELLOW, "LOW": DIM}
SEV_ICON  = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}


def print_report(result: AnalysisResult, records: list[dict], csv_output: str | None = None):
    """Print full analysis report to terminal."""

    width = 72
    print()
    print(BOLD + CYAN + "═" * width + RESET)
    print(BOLD + CYAN + " TOLL PLAZA REVENUE LEAK ANALYSIS REPORT".center(width) + RESET)
    print(BOLD + CYAN + f" Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(width) + RESET)
    print(BOLD + CYAN + "═" * width + RESET)

    # ── Overview ─────────────────────────────────────────────────────────────
    print()
    print(BOLD + "  📊 OVERVIEW" + RESET)
    print("  " + "─" * 50)
    print(f"  Total Records Analyzed : {result.total_records:,}")
    print(f"  Expected Revenue       : ₹{result.total_expected:,.2f}")
    print(f"  Collected Revenue      : ₹{result.total_collected:,.2f}")

    leak_color = RED if result.leak_percentage > 15 else (YELLOW if result.leak_percentage > 5 else GREEN)
    print(f"  Revenue Leaked         : {leak_color}₹{result.total_leak:,.2f} ({result.leak_percentage:.2f}%){RESET}")
    print(f"  Collection Efficiency  : {GREEN}{result.collection_efficiency:.2f}%{RESET}")
    print(f"  Anomalies Detected     : {len(result.anomalies)}")

    # ── Lane Summary ──────────────────────────────────────────────────────────
    lane_summary = summarize_by_lane(records)
    print()
    print(BOLD + "  🛣️  LANE-WISE SUMMARY" + RESET)
    print("  " + "─" * 62)
    print(f"  {'Lane':<10} {'Expected':>12} {'Collected':>12} {'Leak':>10} {'Efficiency':>12}")
    print("  " + "─" * 62)
    for lane, s in sorted(lane_summary.items()):
        eff = (s["collected"] / s["expected"] * 100) if s["expected"] > 0 else 0
        leak = s["expected"] - s["collected"]
        color = RED if eff < 75 else (YELLOW if eff < 90 else GREEN)
        print(f"  {lane:<10} ₹{s['expected']:>10,.0f} ₹{s['collected']:>10,.0f} "
              f"₹{leak:>8,.0f} {color}{eff:>10.1f}%{RESET}")

    # ── Shift Summary ─────────────────────────────────────────────────────────
    shift_summary = summarize_by_shift(records)
    print()
    print(BOLD + "  🕐 SHIFT-WISE SUMMARY" + RESET)
    print("  " + "─" * 62)
    print(f"  {'Shift':<12} {'Expected':>12} {'Collected':>12} {'Leak':>10} {'Efficiency':>12}")
    print("  " + "─" * 62)
    for shift, s in sorted(shift_summary.items()):
        eff = (s["collected"] / s["expected"] * 100) if s["expected"] > 0 else 0
        leak = s["expected"] - s["collected"]
        color = RED if eff < 75 else (YELLOW if eff < 90 else GREEN)
        print(f"  {shift:<12} ₹{s['expected']:>10,.0f} ₹{s['collected']:>10,.0f} "
              f"₹{leak:>8,.0f} {color}{eff:>10.1f}%{RESET}")

    # ── Operator Summary ──────────────────────────────────────────────────────
    op_summary = summarize_by_operator(records)
    print()
    print(BOLD + "  👤 OPERATOR-WISE SUMMARY" + RESET)
    print("  " + "─" * 62)
    print(f"  {'Operator':<14} {'Expected':>12} {'Collected':>12} {'Leak':>10} {'Efficiency':>12}")
    print("  " + "─" * 62)
    for op, s in sorted(op_summary.items(), key=lambda x: x[1]["collected"] / max(x[1]["expected"], 1)):
        eff = (s["collected"] / s["expected"] * 100) if s["expected"] > 0 else 0
        leak = s["expected"] - s["collected"]
        color = RED if eff < 75 else (YELLOW if eff < 90 else GREEN)
        print(f"  {op:<14} ₹{s['expected']:>10,.0f} ₹{s['collected']:>10,.0f} "
              f"₹{leak:>8,.0f} {color}{eff:>10.1f}%{RESET}")

    # ── Anomaly List ──────────────────────────────────────────────────────────
    print()
    print(BOLD + "  ⚠️  ANOMALIES DETECTED" + RESET)
    print("  " + "─" * 70)

    if not result.anomalies:
        print(f"  {GREEN}✅ Koi anomaly detect nahi hua! Revenue collection normal lag raha hai.{RESET}")
    else:
        type_counts = {}
        for a in result.anomalies:
            type_counts[a.anomaly_type] = type_counts.get(a.anomaly_type, 0) + 1

        print(f"  Anomaly breakdown: " +
              " | ".join(f"{k}: {v}" for k, v in type_counts.items()))
        print()

        for i, a in enumerate(result.anomalies, 1):
            c = SEV_COLOR[a.severity]
            icon = SEV_ICON[a.severity]
            print(f"  {icon} [{i:02d}] {c}{BOLD}{a.severity}{RESET} — {BOLD}{a.anomaly_type}{RESET}")
            print(f"       Date: {a.date}  |  Lane: {a.lane_id}  |  Shift: {a.shift.upper()}")
            print(f"       Operator: {a.operator_id}")
            print(f"       Expected: ₹{a.expected_fare:,.2f}  |  Collected: ₹{a.collected_fare:,.2f}")
            print(f"       {c}Leak: ₹{a.leak_amount:,.2f}{RESET}")
            print(f"       {DIM}{a.detail}{RESET}")
            print()

    # ── Footer ────────────────────────────────────────────────────────────────
    print(BOLD + CYAN + "═" * width + RESET)

    # ── CSV Export ────────────────────────────────────────────────────────────
    if csv_output:
        export_csv(result.anomalies, csv_output)


def export_csv(anomalies: list[Anomaly], filepath: str):
    """Export anomalies to CSV file."""
    fieldnames = [
        "severity", "anomaly_type", "date", "lane_id", "shift",
        "operator_id", "expected_fare", "collected_fare", "leak_amount", "detail"
    ]
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for a in anomalies:
                writer.writerow({
                    "severity": a.severity,
                    "anomaly_type": a.anomaly_type,
                    "date": a.date,
                    "lane_id": a.lane_id,
                    "shift": a.shift,
                    "operator_id": a.operator_id,
                    "expected_fare": round(a.expected_fare, 2),
                    "collected_fare": round(a.collected_fare, 2),
                    "leak_amount": round(a.leak_amount, 2),
                    "detail": a.detail,
                })
        print(f"\n  📁 Anomaly report saved: {os.path.abspath(filepath)}")
    except Exception as e:
        print(f"\n  [WARNING] CSV export failed: {e}")
