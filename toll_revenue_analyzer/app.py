"""
app.py — Toll Plaza Revenue Leak Analysis System
Multi-file, Multi-toll Streamlit Dashboard

Supports:
  - Multiple file upload (ek saath kai tolls ka data)
  - FASTag format auto-detect & column mapping
  - Manual format (original CSV/Excel format)
  - Per-toll alag report + combined summary
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from anomaly_detector import RevenueLeakDetector, summarize_by_lane, summarize_by_shift

st.set_page_config(
    page_title="Toll Revenue Analyzer",
    layout="wide",
    page_icon="🛣️"
)

# ── Constants ──────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {
    "date", "shift", "lane_id", "vehicle_type",
    "expected_fare", "collected_fare", "operator_id", "vehicle_count"
}

# FASTag Excel format ke columns
FASTAG_COLUMNS = {
    "txn_id", "file_txn_id", "readerread_time", "trans_amount",
    "lane_id", "tran_status", "avc", "accepted_amount", "toll_id"
}

# AVC → simple vehicle type mapping
AVC_MAP = {
    "car / jeep / van":              "car",
    "light commercial vehicle 2-axle": "lcv",
    "light commercial vehicle 3-axle": "lcv",
    "truck 2 - axle":                "truck",
    "truck 4 - axle":                "truck",
    "truck 6 - axle":                "truck",
    "bus 2-axle":                    "bus",
    "bus 3-axle":                    "bus",
    "three - wheeler freight":       "lcv",
    "three-wheeler":                 "bike",
}

def get_shift(hour: int) -> str:
    if 6 <= hour < 14:
        return "morning"
    elif 14 <= hour < 22:
        return "afternoon"
    else:
        return "night"


# ── File Reading ───────────────────────────────────────────────────────────────

def read_file(uploaded_file) -> pd.DataFrame:
    """Any format file padhke DataFrame return karo."""
    uploaded_file.seek(0)
    name = getattr(uploaded_file, "name", "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    content = uploaded_file.read()

    if ext in ["csv", "txt"]:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                return pd.read_csv(BytesIO(content), encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(BytesIO(content), encoding="utf-8", errors="replace")

    if ext in ["xls", "xlsx"]:
        try:
            # FASTag files mein 'Details' sheet hoti hai
            xl = pd.ExcelFile(BytesIO(content))
            sheet = "Details" if "Details" in xl.sheet_names else xl.sheet_names[0]
            return pd.read_excel(BytesIO(content), sheet_name=sheet)
        except Exception as e:
            st.error(f"Excel read error ({name}): {e}")
            st.stop()

    st.error(f"Unsupported file: {name}. CSV, XLS, XLSX upload karo.")
    st.stop()


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


# ── Format Detection ───────────────────────────────────────────────────────────

def is_fastag_format(df: pd.DataFrame) -> bool:
    """Check karo ki ye FASTag official report format hai ya manual."""
    cols = set(df.columns)
    return len(FASTAG_COLUMNS & cols) >= 5


# ── FASTag Format → Standard Records ──────────────────────────────────────────

def fastag_to_records(df: pd.DataFrame) -> list[dict]:
    """FASTag Excel report ko standard records mein convert karo."""
    records = []

    for _, row in df.iterrows():
        try:
            # Date & Shift
            raw_time = str(row.get("readerread_time", ""))
            try:
                dt = datetime.strptime(raw_time.strip(), "%d/%m/%Y %H:%M:%S")
                rec_date = dt.date()
                shift = get_shift(dt.hour)
            except ValueError:
                continue  # Date parse nahi hua, skip

            # Lane
            lane_raw = str(row.get("lane_id", "")).strip().upper()
            digits = "".join(c for c in lane_raw if c.isdigit())
            lane_id = f"L{digits.zfill(2)}" if digits else lane_raw

            # Vehicle type
            avc_raw = str(row.get("avc", "")).strip().lower()
            vehicle_type = AVC_MAP.get(avc_raw, "car")

            # Fares
            trans_amount = float(row.get("trans_amount") or 0)
            accepted_amount = float(row.get("accepted_amount") or 0)
            tran_status = str(row.get("tran_status", "")).strip().upper()

            # DECLINED / FAILURE = collected 0
            if tran_status in ["DECLINED", "FAILURE"]:
                collected = 0.0
            else:
                collected = accepted_amount

            # Operator = bank ID (jo FASTag bank hai)
            op_raw = row.get("vehicle_bank_id", None)
            operator_id = f"BANK_{int(op_raw)}" if pd.notna(op_raw) else "BANK_UNKNOWN"

            # Toll ID
            toll_id = str(row.get("toll_id", "TOLL_UNKNOWN")).strip()

            records.append({
                "date":           rec_date,
                "shift":          shift,
                "lane_id":        lane_id,
                "vehicle_type":   vehicle_type,
                "expected_fare":  trans_amount,
                "collected_fare": collected,
                "vehicle_count":  1,
                "operator_id":    operator_id,
                "toll_id":        toll_id,
                "tran_status":    tran_status,
            })
        except Exception:
            continue

    return records


# ── Manual Format → Standard Records ──────────────────────────────────────────

def manual_to_records(df: pd.DataFrame, prices: dict) -> list[dict]:
    """Original manual CSV format ko records mein convert karo."""
    records = []
    for _, row in df.iterrows():
        r = {k.lower().strip(): v for k, v in row.items()}
        try:
            date_val = datetime.strptime(str(r["date"]), "%Y-%m-%d").date()
            expected = float(r.get("expected_fare") or prices.get(
                str(r.get("vehicle_type", "")).lower(), 0) * int(r.get("vehicle_count", 0)))
            collected = float(r.get("collected_fare") or 0)
            records.append({
                "date":           date_val,
                "shift":          str(r.get("shift", "")).lower(),
                "lane_id":        str(r.get("lane_id", "")),
                "vehicle_type":   str(r.get("vehicle_type", "")).lower(),
                "expected_fare":  expected,
                "collected_fare": collected,
                "vehicle_count":  int(r.get("vehicle_count", 0)),
                "operator_id":    str(r.get("operator_id", "")),
                "toll_id":        str(r.get("toll_id", "TOLL_001")),
            })
        except Exception:
            continue
    return records


# ── Analysis UI ────────────────────────────────────────────────────────────────

def show_analysis(toll_id: str, records: list[dict]):
    """Ek toll ka pura analysis dikhao."""
    detector = RevenueLeakDetector()
    result = detector.analyze(records)

    # KPI metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📋 Records",       f"{result.total_records:,}")
    col2.metric("💰 Expected",      f"₹{result.total_expected:,.0f}")
    col3.metric("✅ Collected",     f"₹{result.total_collected:,.0f}")
    col4.metric("🚨 Leak",          f"₹{result.total_leak:,.0f}")
    col5.metric("📉 Leak %",        f"{result.leak_percentage:.2f}%")

    st.progress(min(result.collection_efficiency / 100, 1.0),
                text=f"Collection Efficiency: {result.collection_efficiency:.1f}%")

    # Transaction status breakdown (FASTag data mein hoga)
    status_data = {}
    for r in records:
        s = r.get("tran_status", "ACCEPTED")
        status_data[s] = status_data.get(s, 0) + 1
    if len(status_data) > 1:
        st.markdown("**Transaction Status Breakdown**")
        st.dataframe(
            pd.DataFrame(list(status_data.items()), columns=["Status", "Count"])
            .sort_values("Count", ascending=False),
            use_container_width=True
        )

    # Lane-wise summary
    st.subheader("🛣️ Lane-wise Summary")
    lane_summary = summarize_by_lane(records)
    lane_df = pd.DataFrame([
        {
            "Lane": lane,
            "Records": d["count"],
            "Expected (₹)": round(d["expected"], 0),
            "Collected (₹)": round(d["collected"], 0),
            "Leak (₹)": round(d["expected"] - d["collected"], 0),
            "Efficiency %": round(d["collected"] / d["expected"] * 100, 1) if d["expected"] > 0 else 100,
        }
        for lane, d in sorted(lane_summary.items())
    ])
    st.dataframe(lane_df, use_container_width=True)

    # Shift-wise summary
    st.subheader("🕐 Shift-wise Summary")
    shift_summary = summarize_by_shift(records)
    shift_df = pd.DataFrame([
        {
            "Shift": shift.capitalize(),
            "Records": d["count"],
            "Expected (₹)": round(d["expected"], 0),
            "Collected (₹)": round(d["collected"], 0),
            "Leak (₹)": round(d["expected"] - d["collected"], 0),
            "Efficiency %": round(d["collected"] / d["expected"] * 100, 1) if d["expected"] > 0 else 100,
        }
        for shift, d in shift_summary.items()
    ])
    st.dataframe(shift_df, use_container_width=True)

    # Anomalies
    st.subheader(f"🚨 Anomalies Detected: {len(result.anomalies)}")
    if result.anomalies:
        anomaly_df = pd.DataFrame([{
            "Type":       a.anomaly_type,
            "Severity":   a.severity,
            "Date":       a.date,
            "Lane":       a.lane_id,
            "Shift":      a.shift,
            "Operator":   a.operator_id,
            "Expected":   f"₹{a.expected_fare:,.0f}",
            "Collected":  f"₹{a.collected_fare:,.0f}",
            "Leak":       f"₹{a.leak_amount:,.0f}",
            "Detail":     a.detail,
        } for a in result.anomalies])

        # Severity filter
        sev_filter = st.multiselect(
            "Severity filter", ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM"],
            key=f"sev_{toll_id}"
        )
        filtered = anomaly_df[anomaly_df["Severity"].isin(sev_filter)]
        st.dataframe(filtered, use_container_width=True)

        # Download
        csv_bytes = anomaly_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"⬇️ Download Anomalies CSV — {toll_id}",
            csv_bytes,
            f"anomalies_{toll_id}.csv",
            "text/csv",
            key=f"dl_{toll_id}"
        )
    else:
        st.success("✅ Koi anomaly nahi mili!")


# ── Main App ───────────────────────────────────────────────────────────────────

st.title("🛣️ Toll Plaza Revenue Leak Analysis System")
st.caption("Multiple tolls ka data ek saath analyze karo — FASTag & manual format dono support")

# Sidebar
st.sidebar.header("⚙️ Settings")
undercollection_pct = st.sidebar.slider(
    "Undercollection Threshold %", 5, 50, 10, 5,
    help="Kitne % kam collection pe anomaly flag ho"
) / 100

# Manual format ke liye vehicle prices
st.sidebar.markdown("---")
st.sidebar.markdown("**Vehicle Prices** *(manual format ke liye)*")
manual_prices = {
    "car":   st.sidebar.number_input("Car (₹)", value=40.0,  min_value=0.0),
    "truck": st.sidebar.number_input("Truck (₹)", value=140.0, min_value=0.0),
    "bus":   st.sidebar.number_input("Bus (₹)", value=100.0, min_value=0.0),
    "bike":  st.sidebar.number_input("Bike (₹)", value=20.0,  min_value=0.0),
    "lcv":   st.sidebar.number_input("LCV (₹)", value=65.0,  min_value=0.0),
}

# File Upload — Multiple files allowed
st.subheader("📁 Files Upload Karo")
uploaded_files = st.file_uploader(
    "Ek ya multiple files upload karo (alag toll = alag file)",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("👆 Files upload karo — ek toll ki ek file, ya multiple tolls ki multiple files")
    st.stop()

# ── Process All Files ──────────────────────────────────────────────────────────

all_records_by_toll: dict[str, list[dict]] = {}
file_meta = []

with st.spinner("Files process ho rahi hain..."):
    for uf in uploaded_files:
        df = read_file(uf)
        df = normalize_cols(df)

        if is_fastag_format(df):
            fmt = "🏷️ FASTag"
            records = fastag_to_records(df)
        else:
            fmt = "📝 Manual"
            records = manual_to_records(df, manual_prices)

        # Toll-wise group karo
        for r in records:
            tid = r.get("toll_id", "TOLL_UNKNOWN")
            all_records_by_toll.setdefault(tid, []).append(r)

        # Count tolls in this file
        toll_ids = list({r["toll_id"] for r in records})
        file_meta.append({
            "File": uf.name,
            "Format": fmt,
            "Records": len(records),
            "Tolls Found": ", ".join(toll_ids),
        })

# File summary table
st.subheader("📋 Uploaded Files Summary")
st.dataframe(pd.DataFrame(file_meta), use_container_width=True)

total_tolls = len(all_records_by_toll)
st.success(f"✅ {len(uploaded_files)} files loaded — **{total_tolls} toll(s)** detect hua")

# ── Tabs: Combined + Per Toll ──────────────────────────────────────────────────

tab_names = ["🌐 Combined Summary"] + [f"🛣️ Toll {tid}" for tid in all_records_by_toll]
tabs = st.tabs(tab_names)

# Combined Summary Tab
with tabs[0]:
    st.header("🌐 All Tolls Combined Analysis")
    all_records = [r for recs in all_records_by_toll.values() for r in recs]

    if all_records:
        detector = RevenueLeakDetector(undercollection_threshold=undercollection_pct)
        combined = detector.analyze(all_records)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📋 Total Records",  f"{combined.total_records:,}")
        c2.metric("💰 Total Expected", f"₹{combined.total_expected:,.0f}")
        c3.metric("✅ Total Collected",f"₹{combined.total_collected:,.0f}")
        c4.metric("🚨 Total Leak",     f"₹{combined.total_leak:,.0f}")
        c5.metric("📉 Leak %",         f"{combined.leak_percentage:.2f}%")

        st.progress(min(combined.collection_efficiency / 100, 1.0),
                    text=f"Overall Efficiency: {combined.collection_efficiency:.1f}%")

        # Toll-wise comparison table
        st.subheader("Toll-wise Comparison")
        toll_compare = []
        for tid, recs in all_records_by_toll.items():
            r = RevenueLeakDetector(undercollection_threshold=undercollection_pct).analyze(recs)
            toll_compare.append({
                "Toll ID":        tid,
                "Records":        r.total_records,
                "Expected (₹)":   round(r.total_expected, 0),
                "Collected (₹)":  round(r.total_collected, 0),
                "Leak (₹)":       round(r.total_leak, 0),
                "Efficiency %":   round(r.collection_efficiency, 1),
                "Anomalies":      len(r.anomalies),
            })
        st.dataframe(pd.DataFrame(toll_compare), use_container_width=True)

# Per-Toll Tabs
for i, (toll_id, records) in enumerate(all_records_by_toll.items(), start=1):
    with tabs[i]:
        st.header(f"🛣️ Toll ID: {toll_id}")
        st.caption(f"{len(records):,} records")
        detector = RevenueLeakDetector(undercollection_threshold=undercollection_pct)
        show_analysis(toll_id, records)