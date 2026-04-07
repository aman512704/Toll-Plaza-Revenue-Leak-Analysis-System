"""
generate_sample.py — Test CSV Data Generator
Generates realistic toll plaza data WITH injected anomalies for testing.

Usage:
  python generate_sample.py
  python generate_sample.py --rows 500 --output my_data.csv
"""

import csv
import random
import argparse
from datetime import date, timedelta

VEHICLE_FARES = {
    "car": 65,
    "bike": 30,
    "lcv": 110,
    "bus": 180,
    "truck": 230,
}
LANES = ["LANE-01", "LANE-02", "LANE-03", "LANE-04"]
SHIFTS = ["morning", "afternoon", "night"]
OPERATORS = ["OP001", "OP002", "OP003", "OP004", "OP005"]

# OP003 will be a "leaky" operator for testing
LEAKY_OPERATOR = "OP003"


def random_date(start: date, days: int) -> date:
    return start + timedelta(days=random.randint(0, days))


def generate_record(d: date, lane: str, shift: str, operator: str, inject_anomaly: bool = False) -> dict:
    vehicle_type = random.choices(
        list(VEHICLE_FARES.keys()),
        weights=[40, 20, 15, 10, 15],
        k=1
    )[0]
    vehicle_count = random.randint(50, 300)
    base_fare = VEHICLE_FARES[vehicle_type]
    expected_fare = base_fare * vehicle_count

    # Normal: 95–100% collection
    collection_ratio = random.uniform(0.95, 1.00)

    if inject_anomaly:
        anomaly_type = random.choices(
            ["zero", "heavy_leak", "moderate_leak"],
            weights=[10, 20, 70]
        )[0]
        if anomaly_type == "zero":
            collection_ratio = 0.0
        elif anomaly_type == "heavy_leak":
            collection_ratio = random.uniform(0.40, 0.60)
        else:
            collection_ratio = random.uniform(0.70, 0.85)
    elif operator == LEAKY_OPERATOR:
        # Leaky operator: systematically 70–80% efficient
        collection_ratio = random.uniform(0.70, 0.80)

    collected_fare = round(expected_fare * collection_ratio, 2)

    return {
        "date": d.isoformat(),
        "shift": shift,
        "lane_id": lane,
        "vehicle_type": vehicle_type,
        "expected_fare": expected_fare,
        "collected_fare": collected_fare,
        "operator_id": operator,
        "vehicle_count": vehicle_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate sample toll plaza CSV data")
    parser.add_argument("--rows", type=int, default=300, help="Number of rows (default: 300)")
    parser.add_argument("--output", type=str, default="sample_toll_data.csv", help="Output filename")
    parser.add_argument("--anomaly-pct", type=float, default=0.12, help="Fraction of rows with anomalies (default: 0.12)")
    args = parser.parse_args()

    start_date = date(2024, 1, 1)
    rows = []

    for _ in range(args.rows):
        d = random_date(start_date, 90)
        lane = random.choice(LANES)
        shift = random.choice(SHIFTS)
        operator = random.choice(OPERATORS)
        inject = random.random() < args.anomaly_pct

        rows.append(generate_record(d, lane, shift, operator, inject_anomaly=inject))

    # Sort by date
    rows.sort(key=lambda r: r["date"])

    fieldnames = ["date", "shift", "lane_id", "vehicle_type",
                  "expected_fare", "collected_fare", "operator_id", "vehicle_count"]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Sample data generated: '{args.output}'")
    print(f"   Rows: {args.rows}")
    print(f"   Anomaly injection rate: {args.anomaly_pct * 100:.0f}%")
    print(f"   Leaky operator: {LEAKY_OPERATOR} (systematic 70-80% efficiency)")
    print(f"\nAb run karo:")
    print(f"   python main.py {args.output}")
    print(f"   python main.py {args.output} --export anomalies.csv")


if __name__ == "__main__":
    main()
