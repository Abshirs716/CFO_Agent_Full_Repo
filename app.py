# app.py — CFO Agent Dashboard (v0.3) — column selectors + PDF
import os
import tempfile
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF

APP_VERSION = "v0.3 – Column Selectors enabled"

st.set_page_config(page_title="CFO Agent Dashboard", layout="wide")
st.title("🤖 CFO Agent Dashboard")
st.caption(f"Build {APP_VERSION}")

st.write(
    "Upload a **CSV** or **Excel (.xlsx/.xls)**. Then choose which columns are the "
    "**Period/Date** and the **Amount**. We'll compute KPIs, show a trend chart, and "
    "generate a simple board-pack PDF."
)

def load_df(file) -> pd.DataFrame | None:
    if not file:
        return None
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(file, engine="openpyxl")
    else:
        raise ValueError("Unsupported file type. Please upload CSV or Excel (.xlsx/.xls).")

def coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")

def guess_period_candidates(df: pd.DataFrame) -> list[str]:
    candidates = []
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() >= max(3, int(0.5 * len(df))):
                candidates.append(col)
        except Exception:
            pass
    return candidates

def guess_value_candidates(df: pd.DataFrame) -> list[str]:
    cands = []
    for col in df.columns:
        nums = pd.to_numeric(df[col], errors="coerce")
        if nums.notna().mean() >= 0.6:
            cands.append(col)
    return cands

uploaded = st.file_uploader("📥 Upload file", type=["csv", "xlsx", "xls"])

if not uploaded:
    st.info("Upload a CSV or Excel file to continue.")
    st.stop()

try:
    df = load_df(uploaded)
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

if df is None or df.empty:
    st.error("The file is empty.")
    st.stop()

df = df.dropna(how="all")
if df.shape[1] < 2:
    st.error("File must have at least two columns.")
    st.stop()

st.subheader("Preview")
st.dataframe(df.head(20), use_container_width=True)

st.subheader("Select Columns")

period_guess = guess_period_candidates(df)
value_guess = guess_value_candidates(df)

col1, col2 = st.columns(2)
with col1:
    period_col = st.selectbox(
        "Period / Date column",
        options=list(df.columns),
        index=(df.columns.get_loc(period_guess[0]) if period_guess else 0),
        help="Pick the column that represents dates, months, or periods.",
        key="period_col_select",
    )
with col2:
    default_val_idx = (df.columns.get_loc(value_guess[0]) if value_guess else min(1, df.shape[1]-1))
    value_col = st.selectbox(
        "Amount (numeric) column",
        options=list(df.columns),
        index=default_val_idx,
        help="Pick the numeric amount column.",
        key="amount_col_select",
    )

try:
    period_dt = pd.to_datetime(df[period_col], errors="coerce")
except Exception:
    period_dt = None

vals = coerce_numeric(df[value_col])
if vals.isna().all():
    st.error(f"Selected amount column '{value_col}' does not contain numeric values.")
    st.stop()

with st.expander("Parsing details", expanded=False):
    if period_dt is not None and period_dt.notna().any():
        ok_ratio = period_dt.notna().mean()
        st.write(f"Period column '{period_col}': {ok_ratio:.0%} parsed as dates.")
    else:
        st.write(f"Period column '{period_col}' is treated as categorical (not parsed as dates).")
    num_ratio = vals.notna().mean()
    st.write(f"Amount column '{value_col}': {num_ratio:.0%} numeric/convertible.")

total = float(vals.sum())
avg = float(vals.mean())
maxv = float(vals.max())

c1, c2, c3 = st.columns(3)
c1.metric("Total", f"{total:,.2f}")
c2.metric("Average", f"{avg:,.2f}")
c3.metric("Max", f"{maxv:,.2f}")

st.subheader("Trend")
try:
    df2 = df[[period_col, value_col]].copy()
    df2[value_col] = coerce_numeric(df2[value_col])
    if period_dt is not None and period_dt.notna().any():
        df2[period_col] = period_dt
        trend = df2.groupby(period_col, dropna=True)[value_col].sum().sort_index()
    else:
        trend = df2.groupby(period_col, dropna=True)[value_col].sum().sort_values()
    st.line_chart(trend, use_container_width=True)
except Exception as e:
    st.warning(f"Could not plot trend: {e}")
    trend = None

class BoardPDF(FPDF):
    def header(self):
        pass
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")

def save_trend_image(series: pd.Series) -> str | None:
    if series is None or series.empty:
        return None
    fig, ax = plt.subplots()
    ax.plot(series.index, series.values)
    ax.set_title("Trend")
    ax.set_xlabel(str(series.index.name) if series.index.name else "Period")
    ax.set_ylabel("Amount")
    fig.tight_layout()
    tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    fig.savefig(tmp_img.name, dpi=150)
    plt.close(fig)
    return tmp_img.name

def build_board_pack(df: pd.DataFrame,
                     period_col: str,
                     value_col: str,
                     total: float,
                     avg: float,
                     maxv: float,
                     trend_series: pd.Series | None) -> str:
    pdf = BoardPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font("Arial", "B", 22)
    pdf.cell(0, 15, "CFO Executive Board Pack", ln=1, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(5)
    pdf.multi_cell(0, 8, "Generated by CFO Agent Dashboard")

    pdf.add_page()
    pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "Executive Summary", ln=1)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 8,
        "Key KPIs:\n"
        f"- Total: {total:,.2f}\n"
        f"- Average: {avg:,.2f}\n"
        f"- Max: {maxv:,.2f}\n"
    )

    try:
        dfv = df[[period_col, value_col]].copy()
        dfv[value_col] = coerce_numeric(dfv[value_col])
        try:
            dfv[period_col] = pd.to_datetime(dfv[period_col], errors="coerce")
            dfv = dfv.dropna(subset=[period_col])
        except Exception:
            pass
        dfv = dfv.sort_values(by=period_col)
        dfv["MoM_Delta"] = dfv[value_col].diff()
        top_ups = dfv.nlargest(3, "MoM_Delta")[[period_col, "MoM_Delta"]].dropna()
        top_downs = dfv.nsmallest(3, "MoM_Delta")[[period_col, "MoM_Delta"]].dropna()

        pdf.ln(2)
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "Variance Highlights (MoM)", ln=1)
        pdf.set_font("Arial", "", 12)
        if not top_ups.empty:
            pdf.cell(0, 8, "Largest increases:", ln=1)
            for _, r in top_ups.iterrows():
                pdf.cell(0, 8, f"- {r[period_col]}: +{float(r['MoM_Delta']):,.2f}", ln=1)
        if not top_downs.empty:
            pdf.cell(0, 8, "Largest decreases:", ln=1)
            for _, r in top_downs.iterrows():
                pdf.cell(0, 8, f"- {r[period_col]}: {float(r['MoM_Delta']):,.2f}", ln=1)
    except Exception:
        pdf.cell(0, 8, "Variance section unavailable for this dataset.", ln=1)

    img_path = save_trend_image(trend_series)
    if img_path and os.path.exists(img_path):
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "Trend", ln=1)
        pdf.image(img_path, w=180)
        try:
            os.remove(img_path)
        except Exception:
            pass

    pdf.add_page()
    pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "Appendix: Sample Data (first 20 rows)", ln=1)
    pdf.set_font("Arial", "", 10)
    sample = df[[period_col, value_col]].head(20).copy()
    for _, row in sample.iterrows():
        pdf.multi_cell(0, 6, f"{row[period_col]} | {row[value_col]}")

    out_path = "board_pack.pdf"
    pdf.output(out_path)
    return out_path

st.divider()
if st.button("📘 Create Board-Pack PDF"):
    try:
        tmp = df[[period_col, value_col]].copy()
        tmp[value_col] = coerce_numeric(tmp[value_col])
        if period_dt is not None and period_dt.notna().any():
            tmp[period_col] = period_dt
            trend_series = tmp.groupby(period_col, dropna=True)[value_col].sum().sort_index()
        else:
            trend_series = tmp.groupby(period_col, dropna=True)[value_col].sum().sort_values()

        pdf_path = build_board_pack(df, period_col, value_col, total, avg, maxv, trend_series)
        with open(pdf_path, "rb") as f:
            st.download_button("Download Board-Pack PDF", f, file_name="board_pack.pdf")
    except Exception as e:
        st.error(f"Could not create PDF: {e}")
