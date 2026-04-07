"""
main.py — CLI Entry Point
Toll Plaza Revenue Leak Analysis System

Usage:
  python main.py data.csv
  python main.py data.csv --threshold 0.15
  python main.py data.csv --export report.csv
  python main.py data.csv --threshold 0.20 --export anomalies.csv
"""

import argparse
import sys

from data_loader import load_csv
from anomaly_detector import RevenueLeakDetector
from report_generator import print_report


BANNER = r"""
  ╔══════════════════════════════════════════════════════════╗
  ║     TOLL PLAZA REVENUE LEAK ANALYSIS SYSTEM v1.0        ║
  ║     Python CLI | Anomaly Detection Engine               ║
  ╚══════════════════════════════════════════════════════════╝
"""


def parse_args():
    parser = argparse.ArgumentParser(
        prog="toll-analyzer",
        description="Toll Plaza Revenue Leak Detector — Anomaly Analysis CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py toll_data.csv
  python main.py toll_data.csv --threshold 0.15
  python main.py toll_data.csv --export anomalies.csv
  python main.py toll_data.csv --threshold 0.20 --zscore 2.5 --export report.csv
        """
    )

    parser.add_argument(
        "filepath",
        help="Path to toll data CSV file"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.10,
        metavar="FLOAT",
        help="Undercollection threshold (0.0–1.0). Default: 0.10 (10%%)"
    )
    parser.add_argument(
        "--zscore", "-z",
        type=float,
        default=2.0,
        metavar="FLOAT",
        help="Z-score cutoff for statistical outlier detection. Default: 2.0"
    )
    parser.add_argument(
        "--export", "-e",
        type=str,
        default=None,
        metavar="FILE",
        help="Export anomalies to a CSV file (e.g., anomalies.csv)"
    )

    return parser.parse_args()


def main():
    print(BANNER)

    args = parse_args()

    # Validate args
    if not (0.0 < args.threshold < 1.0):
        print("[ERROR] --threshold must be between 0.0 and 1.0 (e.g., 0.10 for 10%)")
        sys.exit(1)

    if args.zscore <= 0:
        print("[ERROR] --zscore must be a positive number")
        sys.exit(1)

    print(f"  📂 Input file     : {args.filepath}")
    print(f"  ⚙️  Threshold      : {args.threshold * 100:.0f}%")
    print(f"  ⚙️  Z-score cutoff : {args.zscore}")
    if args.export:
        print(f"  📁 CSV export     : {args.export}")
    print()

    # Step 1: Load & validate CSV
    records = load_csv(args.filepath)

    # Step 2: Run analysis
    print(f"[...] Anomaly detection chal rahi hai...")
    detector = RevenueLeakDetector(
        undercollection_threshold=args.threshold,
        zscore_threshold=args.zscore,
    )
    result = detector.analyze(records)

    # Step 3: Print report
    print_report(result, records, csv_output=args.export)


if __name__ == "__main__":
    main()
