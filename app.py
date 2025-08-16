import streamlit as st
import pandas as pd
from fpdf import FPDF

st.set_page_config(page_title="CFO Agent Dashboard", layout="wide")
st.title("🤖 CFO Agent Dashboard")

st.write("Upload a CSV with two columns: a date/period column and a numeric amount column.")

uploaded = st.file_uploader("📥 Upload CSV", type="csv")

if uploaded:
    df = pd.read_csv(uploaded)
    st.subheader("Preview")
    st.dataframe(df.head())

    # Basic KPIs using the 2nd column as values
    if df.shape[1] >= 2:
        values = df.iloc[:, 1]
        total = float(values.sum())
        avg = float(values.mean())
        maxv = float(values.max())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", f"{total:,.2f}")
        c2.metric("Average", f"{avg:,.2f}")
        c3.metric("Max", f"{maxv:,.2f}")

    # Simple trend chart: group by first column (period/date)
    try:
        trend = df.groupby(df.columns[0])[df.columns[1]].sum()
        st.subheader("Trend")
        st.line_chart(trend)
    except Exception as e:
        st.warning(f"Could not plot trend: {e}")

    # PDF summary download
    def pdf_report(text, out_path="report.pdf"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in text.splitlines():
            pdf.multi_cell(0, 8, line)
        pdf.output(out_path)
        return out_path

    if st.button("📝 Create PDF Summary"):
        summary = f"Total: {total:,.2f}\nAverage: {avg:,.2f}\nMax: {maxv:,.2f}"
        path = pdf_report(summary)
        with open(path, "rb") as f:
            st.download_button("Download PDF", f, file_name="finance_report.pdf")
else:
    st.info("Upload a CSV to continue.")
