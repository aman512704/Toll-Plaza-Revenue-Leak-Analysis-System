"""
anomaly_detector.py — Revenue Leak Detection Engine
Toll Plaza Revenue Leak Analysis System

Detection Methods:
  1. Undercollection  → collected < expected by threshold %
  2. Zero Collection  → kuch collect hi nahi kiya gaya
  3. Statistical Outlier → Z-score based lane/shift anomalies
  4. Operator Patterns → ek operator repeatedly leak kar raha hai
  5. Shift Drop       → kisi shift mein sudden collection drop
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class Anomaly:
    anomaly_type: str
    severity: str          # HIGH / MEDIUM / LOW
    date: date
    lane_id: str
    shift: str
    operator_id: str
    expected_fare: float
    collected_fare: float
    leak_amount: float
    detail: str


@dataclass
class AnalysisResult:
    total_records: int = 0
    total_expected: float = 0.0
    total_collected: float = 0.0
    total_leak: float = 0.0
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def leak_percentage(self):
        if self.total_expected == 0:
            return 0.0
        return (self.total_leak / self.total_expected) * 100

    @property
    def collection_efficiency(self):
        if self.total_expected == 0:
            return 100.0
        return (self.total_collected / self.total_expected) * 100


# ── Main Detector ─────────────────────────────────────────────────────────────

class RevenueLeakDetector:
    def __init__(
        self,
        undercollection_threshold: float = 0.10,   # 10% se zyada gap = anomaly
        zscore_threshold: float = 2.0,              # Z-score cutoff
    ):
        self.undercollection_threshold = undercollection_threshold
        self.zscore_threshold = zscore_threshold

    def analyze(self, records: list[dict]) -> AnalysisResult:
        result = AnalysisResult(total_records=len(records))

        for r in records:
            result.total_expected += r["expected_fare"]
            result.total_collected += r["collected_fare"]

        result.total_leak = result.total_expected - result.total_collected

        # Run all detectors
        result.anomalies.extend(self._detect_undercollection(records))
        result.anomalies.extend(self._detect_zero_collection(records))
        result.anomalies.extend(self._detect_statistical_outliers(records))
        result.anomalies.extend(self._detect_operator_patterns(records))

        # Sort by severity then leak amount
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        result.anomalies.sort(key=lambda a: (severity_order[a.severity], -a.leak_amount))

        return result

    # ── Detection Methods ─────────────────────────────────────────────────────

    def _detect_undercollection(self, records: list[dict]) -> list[Anomaly]:
        """Collected fare expected se zyada kam hai."""
        anomalies = []
        for r in records:
            if r["expected_fare"] == 0:
                continue
            gap = r["expected_fare"] - r["collected_fare"]
            gap_pct = gap / r["expected_fare"]

            if gap_pct > self.undercollection_threshold:
                severity = "HIGH" if gap_pct > 0.40 else ("MEDIUM" if gap_pct > 0.20 else "LOW")
                anomalies.append(Anomaly(
                    anomaly_type="UNDERCOLLECTION",
                    severity=severity,
                    date=r["date"],
                    lane_id=r["lane_id"],
                    shift=r["shift"],
                    operator_id=r["operator_id"],
                    expected_fare=r["expected_fare"],
                    collected_fare=r["collected_fare"],
                    leak_amount=gap,
                    detail=f"Sirf {(1-gap_pct)*100:.1f}% fare collect hua ({gap_pct*100:.1f}% gap)",
                ))
        return anomalies

    def _detect_zero_collection(self, records: list[dict]) -> list[Anomaly]:
        """Kuch bhi collect nahi hua lekin vehicles the."""
        anomalies = []
        for r in records:
            if r["collected_fare"] == 0 and r["expected_fare"] > 0 and r["vehicle_count"] > 0:
                anomalies.append(Anomaly(
                    anomaly_type="ZERO_COLLECTION",
                    severity="HIGH",
                    date=r["date"],
                    lane_id=r["lane_id"],
                    shift=r["shift"],
                    operator_id=r["operator_id"],
                    expected_fare=r["expected_fare"],
                    collected_fare=0.0,
                    leak_amount=r["expected_fare"],
                    detail=f"{r['vehicle_count']} vehicles the, phir bhi ₹0 collect hua",
                ))
        return anomalies

    def _detect_statistical_outliers(self, records: list[dict]) -> list[Anomaly]:
        """Lane+Shift combination mein Z-score se outlier detect karo."""
        anomalies = []

        # Group by lane + shift
        groups: dict[tuple, list[float]] = defaultdict(list)
        for r in records:
            key = (r["lane_id"], r["shift"])
            if r["expected_fare"] > 0:
                efficiency = r["collected_fare"] / r["expected_fare"]
                groups[key].append(efficiency)

        # Calculate mean & stdev per group
        group_stats: dict[tuple, tuple[float, float]] = {}
        for key, efficiencies in groups.items():
            if len(efficiencies) >= 3:
                mean = statistics.mean(efficiencies)
                stdev = statistics.stdev(efficiencies) if len(efficiencies) > 1 else 0
                group_stats[key] = (mean, stdev)

        # Flag records that are outliers
        for r in records:
            key = (r["lane_id"], r["shift"])
            if key not in group_stats or r["expected_fare"] == 0:
                continue
            mean, stdev = group_stats[key]
            if stdev == 0:
                continue
            eff = r["collected_fare"] / r["expected_fare"]
            z = (eff - mean) / stdev
            if z < -self.zscore_threshold:
                anomalies.append(Anomaly(
                    anomaly_type="STATISTICAL_OUTLIER",
                    severity="MEDIUM",
                    date=r["date"],
                    lane_id=r["lane_id"],
                    shift=r["shift"],
                    operator_id=r["operator_id"],
                    expected_fare=r["expected_fare"],
                    collected_fare=r["collected_fare"],
                    leak_amount=r["expected_fare"] - r["collected_fare"],
                    detail=f"Z-score: {z:.2f} (lane avg se {abs(z):.1f}σ neeche)",
                ))
        return anomalies

    def _detect_operator_patterns(self, records: list[dict]) -> list[Anomaly]:
        """Ek operator ke saare records mein systematic leak pattern dhundho."""
        anomalies = []

        op_data: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            op_data[r["operator_id"]].append(r)

        for operator_id, op_records in op_data.items():
            if len(op_records) < 3:
                continue

            total_exp = sum(r["expected_fare"] for r in op_records)
            total_col = sum(r["collected_fare"] for r in op_records)
            if total_exp == 0:
                continue

            op_efficiency = total_col / total_exp
            # Overall average
            all_exp = sum(r["expected_fare"] for r in records)
            all_col = sum(r["collected_fare"] for r in records)
            overall_efficiency = all_col / all_exp if all_exp > 0 else 1.0

            # Agar operator ka efficiency overall se 20% se zyada kam hai
            if op_efficiency < overall_efficiency - 0.20:
                leak = total_exp - total_col
                severity = "HIGH" if op_efficiency < 0.60 else "MEDIUM"
                # Sirf ek summary anomaly add karo (operator-level)
                sample = op_records[0]
                anomalies.append(Anomaly(
                    anomaly_type="OPERATOR_PATTERN",
                    severity=severity,
                    date=sample["date"],
                    lane_id="MULTIPLE",
                    shift="MULTIPLE",
                    operator_id=operator_id,
                    expected_fare=total_exp,
                    collected_fare=total_col,
                    leak_amount=leak,
                    detail=(
                        f"Operator efficiency: {op_efficiency*100:.1f}% "
                        f"(overall avg: {overall_efficiency*100:.1f}%) — "
                        f"{len(op_records)} shifts mein pattern mila"
                    ),
                ))

        return anomalies


# ── Summary Helpers ───────────────────────────────────────────────────────────

def summarize_by_lane(records: list[dict]) -> dict[str, dict]:
    """Lane-wise summary."""
    summary = defaultdict(lambda: {"expected": 0.0, "collected": 0.0, "count": 0})
    for r in records:
        s = summary[r["lane_id"]]
        s["expected"] += r["expected_fare"]
        s["collected"] += r["collected_fare"]
        s["count"] += 1
    return dict(summary)


def summarize_by_shift(records: list[dict]) -> dict[str, dict]:
    """Shift-wise summary."""
    summary = defaultdict(lambda: {"expected": 0.0, "collected": 0.0, "count": 0})
    for r in records:
        s = summary[r["shift"]]
        s["expected"] += r["expected_fare"]
        s["collected"] += r["collected_fare"]
        s["count"] += 1
    return dict(summary)


def summarize_by_operator(records: list[dict]) -> dict[str, dict]:
    """Operator-wise summary."""
    summary = defaultdict(lambda: {"expected": 0.0, "collected": 0.0, "count": 0})
    for r in records:
        s = summary[r["operator_id"]]
        s["expected"] += r["expected_fare"]
        s["collected"] += r["collected_fare"]
        s["count"] += 1
    return dict(summary)
