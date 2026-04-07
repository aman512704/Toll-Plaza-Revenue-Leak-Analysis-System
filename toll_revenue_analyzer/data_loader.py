"""
data_loader.py — CSV Loading & Validation
Toll Plaza Revenue Leak Analysis System
"""

import csv
import sys
from datetime import datetime

REQUIRED_COLUMNS = {
    "date", "shift", "lane_id", "vehicle_type",
    "expected_fare", "collected_fare", "operator_id", "vehicle_count"
}

VALID_SHIFTS = {"morning", "afternoon", "night"}
VALID_VEHICLE_TYPES = {"car", "truck", "bus", "bike", "lcv"}


def load_csv(filepath: str) -> list[dict]:
    """Load and validate CSV file. Returns list of clean records."""
    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Strip whitespace from headers
            reader.fieldnames = [col.strip().lower() for col in reader.fieldnames]

            missing = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                print(f"\n[ERROR] CSV mein yeh columns missing hain: {', '.join(missing)}")
                print(f"  Required columns: {', '.join(sorted(REQUIRED_COLUMNS))}")
                sys.exit(1)

            records = []
            errors = []

            for i, row in enumerate(reader, start=2):  # row 1 = header
                row = {k.strip(): v.strip() for k, v in row.items()}
                record, err = validate_row(row, i)
                if err:
                    errors.append(err)
                else:
                    records.append(record)

            if errors:
                print(f"\n[WARNING] {len(errors)} rows skip ki gayi (invalid data):")
                for e in errors[:5]:
                    print(f"  {e}")
                if len(errors) > 5:
                    print(f"  ... aur {len(errors) - 5} aur errors")
                print()

            if not records:
                print("[ERROR] Koi valid data nahi mila CSV mein.")
                sys.exit(1)

            print(f"[OK] {len(records)} valid records loaded from '{filepath}'")
            return records

    except FileNotFoundError:
        print(f"\n[ERROR] File nahi mili: '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] CSV padhne mein problem: {e}")
        sys.exit(1)


def validate_row(row: dict, line_num: int) -> tuple[dict | None, str | None]:
    """Validate a single row. Returns (clean_record, error_message)."""
    try:
        # Date validation
        try:
            date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except ValueError:
            return None, f"Line {line_num}: Invalid date '{row['date']}' (expected YYYY-MM-DD)"

        # Shift
        shift = row["shift"].lower()
        if shift not in VALID_SHIFTS:
            return None, f"Line {line_num}: Invalid shift '{row['shift']}'"

        # Lane ID
        lane_id = row["lane_id"]
        if not lane_id:
            return None, f"Line {line_num}: lane_id empty hai"

        # Vehicle type
        vehicle_type = row["vehicle_type"].lower()
        if vehicle_type not in VALID_VEHICLE_TYPES:
            return None, f"Line {line_num}: Invalid vehicle_type '{row['vehicle_type']}'"

        # Numeric fields
        expected_fare = float(row["expected_fare"])
        collected_fare = float(row["collected_fare"])
        vehicle_count = int(row["vehicle_count"])

        if expected_fare < 0 or collected_fare < 0:
            return None, f"Line {line_num}: Fare negative nahi ho sakta"

        if vehicle_count < 0:
            return None, f"Line {line_num}: vehicle_count negative nahi ho sakta"

        operator_id = row["operator_id"]
        if not operator_id:
            return None, f"Line {line_num}: operator_id empty hai"

        return {
            "date": date,
            "shift": shift,
            "lane_id": lane_id,
            "vehicle_type": vehicle_type,
            "expected_fare": expected_fare,
            "collected_fare": collected_fare,
            "vehicle_count": vehicle_count,
            "operator_id": operator_id,
        }, None

    except (ValueError, KeyError) as e:
        return None, f"Line {line_num}: Data error — {e}"
