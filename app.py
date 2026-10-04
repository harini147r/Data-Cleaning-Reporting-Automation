"""
app.py — Interactive Web Dashboard for Data Cleaning & Reporting Automation.
Run with: streamlit run app.py
"""

import io
import time
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Pipeline modules
from src.config import (
    DATA_RAW_DIR,
    DATA_SAMPLE_DIR,
    DATA_CLEANED_DIR,
    REPORTS_DIR,
    POWERBI_DIR,
)
from src import loader, validator, cleaner, standardizer, metrics, reporter, exporter

# Set page configuration
st.set_page_config(
    page_title="Data Clean & Report Automation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1F4E79;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #F0F4F8;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1F4E79;
    }
    .success-card {
        background: #EAF7EC;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #28A745;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        border-radius: 6px 6px 0 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown('<div class="main-header">⚡ Data Cleaning & Reporting Automation</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Automate data validation, multi-step cleaning, quality auditing, and Power BI-ready exports.</div>',
        unsafe_allow_html=True,
    )

    # ──────────────── Sidebar Controls ────────────────
    with st.sidebar:
        st.header("📁 Data Ingestion")
        uploaded_file = st.file_uploader(
            "Upload raw Excel or CSV",
            type=["csv", "xlsx", "xls"],
            help="Upload your raw business data for automated cleaning and profiling.",
        )

        use_sample = st.checkbox("Use Demo Sales Dataset (1,200 rows)", value=False if uploaded_file else True)

        st.markdown("---")
        st.header("⚙️ Pipeline Options")
        run_sqlite = st.checkbox("Export to SQLite DB", value=True)
        flag_outliers = st.checkbox("Flag Outliers (IQR Method)", value=True)

        st.markdown("---")
        process_btn = st.button("🚀 Run Cleaning & Reporting", type="primary", use_container_width=True)

    # ──────────────── Load Input Data ────────────────
    raw_df = None
    metadata = {}

    if uploaded_file is not None:
        filename = uploaded_file.name
        ext = Path(filename).suffix.lower()
        try:
            if ext == ".csv":
                raw_df = pd.read_csv(uploaded_file, low_memory=False)
            else:
                raw_df = pd.read_excel(uploaded_file)
            metadata = {
                "filename": filename,
                "extension": ext,
                "raw_rows": len(raw_df),
                "raw_cols": len(raw_df.columns),
                "file_size_kb": round(uploaded_file.size / 1024, 2),
                "columns": list(raw_df.columns),
            }
        except Exception as e:
            st.error(f"Error reading uploaded file: {e}")
            return
    elif use_sample:
        sample_path = DATA_SAMPLE_DIR / "sample_sales_data.csv"
        if sample_path.exists():
            raw_df, metadata = loader.load_file(sample_path)
        else:
            st.warning("Sample dataset not found. Generating sample data...")
            import generate_sample_data
            df_gen = generate_sample_data.generate()
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            df_gen.to_csv(sample_path, index=False, encoding="utf-8-sig")
            raw_df, metadata = loader.load_file(sample_path)

    if raw_df is None:
        st.info("👋 Upload a file or enable 'Use Demo Sales Dataset' from the sidebar to begin.")
        return

    # ──────────────── Pipeline Execution ────────────────
    # Cache results in session_state
    if process_btn or "pipeline_results" not in st.session_state:
        with st.spinner("Processing pipeline: Validating → Cleaning → Auditing → Exporting..."):
            t_start = time.time()

            # 1. Profile raw
            before_profile = validator.profile_dataframe(raw_df, label="Before Cleaning")

            # 2. Clean
            cleaned_df, cleaning_log = cleaner.clean(raw_df)

            # 3. Post-validate
            after_profile = validator.profile_dataframe(cleaned_df, label="After Cleaning")
            passed, val_results = standardizer.validate(cleaned_df)

            # 4. Metrics
            biz_metrics = metrics.compute_metrics(cleaned_df)

            # 5. Generate Excel / HTML reports
            report_path = reporter.generate_quality_report(
                before_profile, after_profile, val_results, cleaning_log, metadata
            )

            # 6. Export files
            export_paths = exporter.export_all(cleaned_df, biz_metrics, metadata)

            duration = round(time.time() - t_start, 2)

            st.session_state["pipeline_results"] = {
                "raw_df": raw_df,
                "cleaned_df": cleaned_df,
                "before_profile": before_profile,
                "after_profile": after_profile,
                "val_results": val_results,
                "passed": passed,
                "cleaning_log": cleaning_log,
                "biz_metrics": biz_metrics,
                "metadata": metadata,
                "duration": duration,
                "export_paths": export_paths,
            }

    results = st.session_state["pipeline_results"]
    cleaned_df = results["cleaned_df"]
    before_p = results["before_profile"]
    after_p = results["after_profile"]
    biz_m = results["biz_metrics"]

    # ──────────────── Top KPI Summary Banner ────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Cleaned Rows", f"{len(cleaned_df):,}", delta=f"{len(cleaned_df) - len(raw_df)} dropped")
    with c2:
        st.metric("Data Completeness", f"{after_p['completeness_score']}%", delta=f"+{round(after_p['completeness_score'] - before_p['completeness_score'], 1)}%")
    with c3:
        st.metric("Duplicates Removed", f"{before_p['duplicate_rows']:,}")
    with c4:
        st.metric("Missing Cells Fixed", f"{before_p['total_missing_cells'] - after_p['total_missing_cells']:,}")
    with c5:
        st.metric("Processing Time", f"{results['duration']}s")

    # ──────────────── Main Interactive Tabs ────────────────
    tab_dash, tab_audit, tab_data, tab_export = st.tabs([
        "📈 Business Dashboard",
        "🔍 Data Quality Audit",
        "🧹 Cleaned Dataset",
        "📥 Download & Power BI",
    ])

    # ── Tab 1: Business Dashboard ──────────────────────────
    with tab_dash:
        st.subheader("Key Business Metrics")
        kpi = biz_m.get("summary", {})

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            rev = kpi.get("Total Revenue", 0)
            st.metric("Total Revenue", f"${rev:,.2f}" if isinstance(rev, (int, float)) else str(rev))
        with k2:
            aov = kpi.get("Avg Order Value", 0)
            st.metric("Avg Order Value", f"${aov:,.2f}" if isinstance(aov, (int, float)) else str(aov))
        with k3:
            units = kpi.get("Total Units Sold", 0)
            st.metric("Units Sold", f"{units:,}" if isinstance(units, (int, float)) else str(units))
        with k4:
            st.metric("Date Coverage", f"{kpi.get('Days Covered', 0)} days", help=f"From {kpi.get('Date From')} to {kpi.get('Date To')}")

        st.markdown("---")

        col_left, col_right = st.columns([6, 4])
        with col_left:
            monthly_df = biz_m.get("monthly_trend")
            if monthly_df is not None and not monthly_df.empty and "total_revenue" in monthly_df.columns:
                fig_monthly = px.area(
                    monthly_df,
                    x="Month",
                    y="total_revenue",
                    title="<b>Monthly Revenue Trend</b>",
                    markers=True,
                    color_discrete_sequence=["#1F4E79"],
                    labels={"total_revenue": "Revenue ($)", "Month": "Month"},
                )
                fig_monthly.update_layout(height=360, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_monthly, use_container_width=True)

        with col_right:
            status_df = biz_m.get("status_breakdown")
            if status_df is not None and not status_df.empty:
                fig_status = px.pie(
                    status_df,
                    names="Status",
                    values="Count",
                    title="<b>Order Status Breakdown</b>",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Safe,
                )
                fig_status.update_layout(height=360, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_status, use_container_width=True)

        col_cat, col_reg = st.columns(2)
        with col_cat:
            cat_df = biz_m.get("category_breakdown")
            if cat_df is not None and not cat_df.empty and "Total Revenue" in cat_df.columns:
                fig_cat = px.bar(
                    cat_df,
                    x="Category",
                    y="Total Revenue",
                    title="<b>Revenue by Product Category</b>",
                    color="Total Revenue",
                    color_continuous_scale="Blues",
                )
                fig_cat.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_cat, use_container_width=True)

        with col_reg:
            reg_df = biz_m.get("region_breakdown")
            if reg_df is not None and not reg_df.empty and "Total Revenue" in reg_df.columns:
                fig_reg = px.bar(
                    reg_df,
                    x="Region",
                    y="Total Revenue",
                    title="<b>Regional Revenue Contribution</b>",
                    color="Region",
                    color_discrete_sequence=px.colors.qualitative.Bold,
                )
                fig_reg.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_reg, use_container_width=True)

    # ── Tab 2: Data Quality Audit ──────────────────────────
    with tab_audit:
        st.subheader("Data Quality Assessment (Before vs. After)")

        # Summary comparison table
        b_sum = validator.build_summary_row(before_p)
        a_sum = validator.build_summary_row(after_p)
        comp_df = pd.DataFrame([b_sum, a_sum])
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Post-Cleaning Standardizer Checks")
        val_df = pd.DataFrame(results["val_results"])

        def style_status(val):
            color = "#28a745" if val == "PASS" else ("#ffc107" if val == "WARN" else "#dc3545")
            return f"color: {color}; font-weight: bold"

        st.dataframe(
            val_df.style.map(style_status, subset=["Status"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("Column-Level Quality Profiles")
        prof_col1, prof_col2 = st.columns(2)
        with prof_col1:
            st.markdown("**Raw Data Columns (Before)**")
            st.dataframe(validator.profile_to_dataframe(before_p), use_container_width=True, hide_index=True)
        with prof_col2:
            st.markdown("**Cleaned Data Columns (After)**")
            st.dataframe(validator.profile_to_dataframe(after_p), use_container_width=True, hide_index=True)

    # ── Tab 3: Cleaned Dataset Preview ──────────────────────
    with tab_data:
        st.subheader("Cleaned Dataset Explorer")
        st.caption(f"Displaying {len(cleaned_df):,} records with {len(cleaned_df.columns)} standardized columns.")

        # Quick filter by category if present
        if "product_category" in cleaned_df.columns:
            categories = ["All"] + sorted(list(cleaned_df["product_category"].dropna().unique()))
            selected_cat = st.selectbox("Filter by Category", categories)
            view_df = cleaned_df if selected_cat == "All" else cleaned_df[cleaned_df["product_category"] == selected_cat]
        else:
            view_df = cleaned_df

        st.dataframe(view_df.head(200), use_container_width=True)

        if any("_outlier" in c for c in cleaned_df.columns):
            st.markdown("---")
            st.subheader("Outlier Detection Flags")
            outlier_cols = [c for c in cleaned_df.columns if "_outlier" in c]
            st.write("Identified outliers via statistical IQR factor without discarding valid transactions:")
            for col in outlier_cols:
                cnt = cleaned_df[col].sum()
                st.write(f"• **{col}**: {cnt} flagged records ({round(cnt/len(cleaned_df)*100, 2)}%)")

    # ── Tab 4: Downloads & Power BI ─────────────────────────
    with tab_export:
        st.subheader("📥 Export & Integration Hub")
        st.write("Download cleaned datasets, quality audit reports, or load directly into Power BI.")

        d1, d2, d3 = st.columns(3)

        with d1:
            st.markdown("### 📊 Clean Datasets")
            csv_data = cleaned_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="⬇️ Download Cleaned CSV",
                data=csv_data,
                file_name="cleaned_data.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # Excel download
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as wr:
                cleaned_df.to_excel(wr, sheet_name="Cleaned Data", index=False)
            st.download_button(
                label="⬇️ Download Cleaned Excel",
                data=excel_buffer.getvalue(),
                file_name="cleaned_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with d2:
            st.markdown("### 📑 Audit Reports")
            report_file = REPORTS_DIR / "data_quality_report.xlsx"
            if report_file.exists():
                with open(report_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Quality Audit Report (Excel)",
                        data=f.read(),
                        file_name="data_quality_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

            metrics_file = REPORTS_DIR / "business_metrics.xlsx"
            if metrics_file.exists():
                with open(metrics_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Business Metrics (Excel)",
                        data=f.read(),
                        file_name="business_metrics.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

        with d3:
            st.markdown("### ⚡ Power BI Model")
            pbi_file = POWERBI_DIR / "dashboard_data.xlsx"
            if pbi_file.exists():
                with open(pbi_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Power BI Data Source",
                        data=f.read(),
                        file_name="dashboard_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            st.caption("Includes all 6 modeled sheets: CleanedData, MetricsSummary, MonthlyTrend, CategoryBreakdown, RegionBreakdown, StatusBreakdown.")

        st.markdown("---")
        st.markdown("""
        #### 🔌 Quick Power BI Desktop Instructions:
        1. Open **Power BI Desktop**.
        2. Choose **Get Data** &rarr; **Excel Workbook**.
        3. Select `powerbi/dashboard_data.xlsx` (or the downloaded file).
        4. Select all 6 sheets and click **Load**.
        """)


if __name__ == "__main__":
    main()
