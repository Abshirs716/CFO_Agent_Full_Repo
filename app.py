import streamlit as st
import pandas as pd
from fpdf import FPDF

st.set_page_config(page_title="CFO Agent Dashboard", layout="wide")
st.title("🤖 CFO Agent Dashboard")

st.write(
    "Upload a **CSV** or **Excel (.xlsx/.xls)** with two columns: "
    "a date/period column and a numeric amount column."
)

# ---- File upload (CSV + Excel) ----
uploaded = st.file_uploader("📥 Upload file", type=["csv", "xlsx", "xls"])

def load_df(file) -> pd.DataFrame:
    """Load CSV or Excel into a DataFrame."""
    if file is None:
        return None
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        # openpyxl must be in requirements.txt for .xlsx
        return pd.read_excel(file, engine="openpyxl")
    else:
        raise ValueError("Unsupported file type. Please upload CSV or Excel (.xlsx/.xls).")

def coerce_numeric(series: pd.Series) -> pd.Series:
    """Try to convert a series to numeric, keep NaN if not possible."""
    return pd.to_numeric(series, errors="coerce")

# ---- Main flow ----
if uploaded:
    # Load
    try:
        df = load_df(uploaded)
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()

    # Basic cleaning
    df = df.dropna(how="all")  # drop totally empty rows
    if df.shape[1] < 2:
        st.error("File must have at least two columns.")
        st.stop()

    # Column roles
    period_col = df.columns[0]
    value_col = df.columns[1]

    # Coerce numeric values
    vals = coerce_numeric(df[value_col])
    if vals.isna().all():
        st.error(f"Second column (‘{value_col}’) must contain numbers.")
        st.stop()

    # Try to parse first column as dates (won't error if not a date)
    try:
        period_parsed = pd.to_datetime(df[period_col], errors="ignore")
        df[period_col] = period_parsed
    except Exception:
        pass

    # Preview
    st.subheader("Preview")
    st.dataframe(df.head())

    # KPIs
    total = float(vals.sum())
    avg = float(vals.mean())
    maxv = float(vals.max())
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", f"{total:,.2f}")
    c2.metric("Average", f"{avg:,.2f}")
    c3.metric("Max", f"{maxv:,.2f}")

    # Trend chart (group by period column)
    try:
        trend = df.groupby(period_col)[value_col].apply(lambda s: coerce_numeric(s).sum())
        # If date-like, sort chronologically
        try:
            trend.index = pd.to_datetime(trend.index)
            trend = trend.sort_index()
        except Exception:
            pass
        st.subheader("Trend")
        st.line_chart(trend)
    except Exception as e:
        st.warning(f"Could not plot trend: {e}")

    # ---- PDF summary download ----
    def pdf_report(text: str, out_path: str = "report.pdf") -> str:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in text.splitlines():
            pdf.multi_cell(0, 8, line)
        pdf.output(out_path)
        return out_path

    if st.button("📝 Create PDF Summary"):
        summary = (
            f"Finance Summary\n\n"
            f"Total:  {total:,.2f}\n"
            f"Average:{avg:,.2f}\n"
            f"Max:    {maxv:,.2f}\n"
        )
        path = pdf_report(summary)
        with open(path, "rb") as f:
            st.download_button("Download PDF", f, file_name="finance_report.pdf")
else:
    st.info("Upload a CSV or Excel file to continue.")
