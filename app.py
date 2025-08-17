# app.py  — CFO_Agent_Full_Repo
import os
import tempfile
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF

# ---------- Page ----------
st.set_page_config(page_title="CFO_Agent_Full_Repo", layout="wide")
st.title("🤖 CFO_Agent_Full_Repo")

st.write(
    "Upload a **CSV** or **Excel (.xlsx/.xls)**. "
    "Then choose which columns are the **Period/Date** and the **Amount**. "
    "We'll compute KPIs, show a trend, and generate a simple board-pack PDF with your commentary."
)

# ---------- Helpers ----------
def load_df(file) -> pd.DataFrame | None:
    if file is None:
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

# ---------- Upload ----------
uploaded = st.file_uploader("📥 Upload file", type=["csv", "xlsx", "xls"])

if uploaded:
    try:
        df = load_df(uploaded)
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()

    # Clean/preview
    df = df.dropna(how="all")
    if df.shape[1] < 2:
        st.error("File must have at least two columns.")
        st.stop()

    st.subheader("Preview")
    st.dataframe(df.head(50), use_container_width=True)

    # ---------- Select columns ----------
    st.subheader("Select Columns")
    cols = list(df.columns)
    left, right = st.columns(2)
    with left:
        period_col = st.selectbox("Period / Date column", cols, index=0)
    with right:
        # try to choose a column that looks numeric by default
        numeric_guess = 1 if df.shape[1] > 1 else 0
        amount_col = st.selectbox("Amount (numeric) column", cols, index=numeric_guess)

    # Parse date + numeric
    with st.expander("Parsing details"):
        st.write("Trying to parse the **Period/Date** column as dates. If it isn't a date, it's kept as is.")
    try:
        parsed_period = pd.to_datetime(df[period_col], errors="ignore", infer_datetime_format=True)
        df[period_col] = parsed_period
    except Exception:
        pass

    vals = coerce_numeric(df[amount_col])
    if vals.isna().all():
        st.error(f"The selected Amount column ('{amount_col}') must contain numbers.")
        st.stop()

    # ---------- KPIs ----------
    total = float(vals.sum())
    avg = float(vals.mean())
    maxv = float(vals.max())
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", f"{total:,.2f}")
    c2.metric("Average", f"{avg:,.2f}")
    c3.metric("Max", f"{maxv:,.2f}")

    # ---------- Trend ----------
    st.subheader("Trend")
    try:
        # group by the selected period column (string or datetime both okay)
        tmp = df[[period_col, amount_col]].copy()
        tmp[amount_col] = coerce_numeric(tmp[amount_col])
        trend = tmp.groupby(period_col)[amount_col].sum()

        # if the index is datetime-like, sort
        try:
            trend.index = pd.to_datetime(trend.index)
            trend = trend.sort_index()
        except Exception:
            pass

        st.line_chart(trend)
    except Exception as e:
        st.warning(f"Could not plot trend: {e}")
        trend = None

    # ---------- CFO commentary & risks ----------
    st.subheader("CFO Commentary (optional)")
    commentary = st.text_area(
        "Add narrative (drivers, risks, opportunities, next actions):",
        placeholder="Example: Revenue up 6% MoM driven by UK launch; Gross margin +1.2pp from mix shift; FX headwind easing...",
        height=140,
    )

    st.subheader("Top Risks & Actions (optional)")
    default_rows = [
        {"Risk": "", "Action": "", "Owner": "", "Due": ""},
        {"Risk": "", "Action": "", "Owner": "", "Due": ""},
    ]
    risks_df = st.data_editor(
        pd.DataFrame(default_rows),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Risk": st.column_config.TextColumn("Risk"),
            "Action": st.column_config.TextColumn("Action"),
            "Owner": st.column_config.TextColumn("Owner"),
            "Due": st.column_config.TextColumn("Due (YYYY-MM-DD)"),
        },
        key="risks_editor",
    )

    # ---------- PDF ----------
    class BoardPDF(FPDF):
        def header(self):
            pass  # clean header for now

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

    def build_board_pack(
        df: pd.DataFrame,
        period_col: str,
        amount_col: str,
        total: float,
        avg: float,
        maxv: float,
        trend_series: pd.Series | None,
        commentary: str,
        risks_df: pd.DataFrame,
    ) -> str:
        pdf = BoardPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # COVER
        pdf.add_page()
        pdf.set_font("Arial", "B", 22)
        pdf.cell(0, 15, "CFO Executive Board Pack", ln=1, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.ln(4)
        pdf.multi_cell(0, 7, "Generated by CFO_Agent_Full_Repo")

        # EXEC SUMMARY
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Executive Summary", ln=1)
        pdf.set_font("Arial", "", 12)
        # Use ASCII dashes (avoid unicode bullets)
        pdf.multi_cell(
            0,
            7,
            (
                f"- Total:   {total:,.2f}\n"
                f"- Average: {avg:,.2f}\n"
                f"- Max:     {maxv:,.2f}\n"
            ),
        )

        # Commentary
        if commentary.strip():
            pdf.ln(2)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 9, "CFO Commentary", ln=1)
            pdf.set_font("Arial", "", 12)
            for line in commentary.splitlines():
                pdf.multi_cell(0, 7, line if line.strip() else " ")

        # MoM variance highlights
        try:
            df2 = df[[period_col, amount_col]].copy()
            df2[amount_col] = coerce_numeric(df2[amount_col])
            df2 = df2.dropna(subset=[amount_col])
            df2 = df2.sort_values(by=period_col)
            df2["MoM_Change"] = df2[amount_col].diff()
            ups = df2.nlargest(3, "MoM_Change")[[period_col, "MoM_Change"]].dropna()
            downs = df2.nsmallest(3, "MoM_Change")[[period_col, "MoM_Change"]].dropna()

            pdf.ln(2)
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 9, "Variance Highlights (MoM)", ln=1)
            pdf.set_font("Arial", "", 12)
            if not ups.empty:
                pdf.cell(0, 7, "Largest increases:", ln=1)
                for _, r in ups.iterrows():
                    pdf.cell(0, 7, f"  - {r[period_col]}: +{float(r['MoM_Change']):,.2f}", ln=1)
            if not downs.empty:
                pdf.cell(0, 7, "Largest decreases:", ln=1)
                for _, r in downs.iterrows():
                    pdf.cell(0, 7, f"  - {r[period_col]}: {float(r['MoM_Change']):,.2f}", ln=1)
        except Exception:
            pdf.ln(2)
            pdf.cell(0, 7, "Variance section unavailable for this dataset.", ln=1)

        # Risks & Actions
        try:
            clean = risks_df.fillna("").astype(str)
            nonempty = clean[(clean["Risk"].str.strip() != "") | (clean["Action"].str.strip() != "")]
            if not nonempty.empty:
                pdf.ln(2)
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 9, "Top Risks & Actions", ln=1)
                pdf.set_font("Arial", "", 12)
                for _, r in nonempty.iterrows():
                    pdf.multi_cell(0, 7, f"- Risk: {r['Risk']}")
                    pdf.multi_cell(0, 7, f"  Action: {r['Action']}")
                    owner = r.get("Owner", "")
                    due = r.get("Due", "")
                    if owner or due:
                        pdf.multi_cell(0, 7, f"  Owner: {owner}   Due: {due}")
                    pdf.ln(1)
        except Exception:
            pass

        # Trend image
        img_path = save_trend_image(trend_series) if trend_series is not None else None
        if img_path and os.path.exists(img_path):
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 9, "Trend", ln=1)
            pdf.image(img_path, w=180)
            try:
                os.remove(img_path)
            except Exception:
                pass

        # Appendix: first 20 rows
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 9, "Appendix: Sample Data (first 20 rows)", ln=1)
        pdf.set_font("Arial", "", 10)
        sample = df.head(20).copy()
        for _, row in sample.iterrows():
            line = " | ".join(str(x) for x in row.tolist())
            pdf.multi_cell(0, 6, line)

        out_path = "board_pack.pdf"
        pdf.output(out_path)
        return out_path

    st.divider()
    if st.button("📘 Create Board-Pack PDF (Pro)"):
        try:
            pdf_path = build_board_pack(
                df=df,
                period_col=period_col,
                amount_col=amount_col,
                total=total,
                avg=avg,
                maxv=maxv,
                trend_series=trend,
                commentary=commentary,
                risks_df=risks_df,
            )
            with open(pdf_path, "rb") as f:
                st.download_button("Download Board-Pack PDF", f, file_name="board_pack.pdf")
        except Exception as e:
            st.error(f"Could not create PDF: {e}")

else:
    st.info("Upload a CSV or Excel file to continue.")
