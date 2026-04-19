import streamlit as st
import pandas as pd
from modules.auth import require_login

# 若用户未登录则阻止页面继续渲染
# Halt page rendering for unauthenticated users
require_login(logout_key="logout_dashboard")

# 显示页面标题
# Display the page title
st.title("Dashboard")

# 从会话状态读取数据集；若不存在则提示用户先前往数据导入页
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    st.warning("No dataset in session. Go to Data Import first.")
    st.stop()

# NFR4 隐私验证：若用户已在清洗页对 PII 执行脱敏，则展示提醒，确认敏感字段不会在此处暴露原始值
# NFR4 privacy verification: if PII masking was applied in the Cleaning page, show a notice
# confirming that sensitive fields are not exposed in their original form here
if st.session_state.get("pii_masked"):
    st.info("PII notice: email and phone fields in this dataset have been masked. "
            "Raw sensitive values are not displayed here.")

# 筛选出所有整数或浮点数类型的列，用于图表绘制和 KPI 计算
# Filter integer and float columns to use for charts and KPI calculations
num_cols = [c for c in df.columns if df[c].dtype.kind in "if"]
if not num_cols:
    st.info("No numeric data available for charts.")
    st.stop()

# 让用户从数值列中选择要展示的指标列
# Let the user choose which numeric column to visualise as the main metric
metric_col = st.selectbox("Metric for chart", num_cols)

# ---- KPI 区域 ----
# ---- KPI Section ----
st.subheader("KPI")

# 将所选列强制转换为数值类型后求和，非数值内容填 0，防止因脏数据报错
# Coerce the selected column to numeric (filling non-numeric with 0) before summing to avoid crashes
st.metric("Total", f"{pd.to_numeric(df[metric_col], errors='coerce').fillna(0).sum():.2f}")

# ---- 图表区域（bar / line / pie） ----
# ---- Chart Section (bar / line / pie) ----
st.subheader("Charts")

chart_type = st.radio("Chart type", ["Bar", "Line", "Pie"], horizontal=True)

# 候选分组列：优先非数值列，也允许日期列作为时间轴
# Candidate group columns: prefer non-numeric columns and also allow date columns as timeline
group_cols = [c for c in df.columns if c not in num_cols]

if group_cols:
    group_col = st.selectbox("Group by", group_cols)
    agg_df = df.copy()
    agg_df[metric_col] = pd.to_numeric(agg_df[metric_col], errors="coerce").fillna(0.0)

    if chart_type == "Line":
        # 折线图优先将分组列解析为日期并按月汇总；失败则按类别汇总
        # For line charts, try date parsing and monthly aggregation first; otherwise aggregate by category
        parsed = pd.to_datetime(agg_df[group_col], errors="coerce")
        if parsed.notna().mean() >= 0.6:
            agg_df["_x"] = parsed.dt.to_period("M").dt.to_timestamp()
            line_df = agg_df.groupby("_x", as_index=False)[metric_col].sum().sort_values("_x")
            st.line_chart(line_df.set_index("_x")[metric_col], use_container_width=True)
        else:
            line_df = agg_df.groupby(group_col, as_index=False)[metric_col].sum().sort_values(metric_col, ascending=False).head(30)
            st.line_chart(line_df.set_index(group_col)[metric_col], use_container_width=True)

    elif chart_type == "Pie":
        pie_df = agg_df.groupby(group_col, as_index=False)[metric_col].sum().sort_values(metric_col, ascending=False).head(10)
        st.vega_lite_chart(
            pie_df,
            {
                "mark": {"type": "arc", "outerRadius": 120},
                "encoding": {
                    "theta": {"field": metric_col, "type": "quantitative"},
                    "color": {"field": group_col, "type": "nominal"},
                    "tooltip": [
                        {"field": group_col, "type": "nominal"},
                        {"field": metric_col, "type": "quantitative"},
                    ],
                },
            },
            use_container_width=True,
        )

    else:
        bar_df = agg_df.groupby(group_col, as_index=False)[metric_col].sum().sort_values(metric_col, ascending=False).head(30)
        st.bar_chart(bar_df.set_index(group_col)[metric_col], use_container_width=True)
else:
    st.info("No categorical/group column found; showing default distribution view.")
    st.bar_chart(df[metric_col].head(50), use_container_width=True)


# ---- 分析结果联动展示 ----
# ---- Integrated Outputs from Analytics Page ----
if "cash_flow_df" in st.session_state and st.session_state["cash_flow_df"] is not None:
    cash_flow_df = st.session_state["cash_flow_df"]
    if not cash_flow_df.empty:
        st.subheader("Cash Flow Trend")
        st.line_chart(cash_flow_df.set_index("month")[["paid_amount", "outstanding_amount"]], use_container_width=True)
        st.dataframe(cash_flow_df, use_container_width=True)

if "rfm_summary_df" in st.session_state and st.session_state["rfm_summary_df"] is not None:
    rfm_summary_df = st.session_state["rfm_summary_df"]
    if not rfm_summary_df.empty:
        st.subheader("RFM Segment Distribution")
        st.bar_chart(rfm_summary_df.set_index("segment")["customers"], use_container_width=True)
        st.vega_lite_chart(
            rfm_summary_df,
            {
                "mark": {"type": "arc", "outerRadius": 120},
                "encoding": {
                    "theta": {"field": "customers", "type": "quantitative"},
                    "color": {"field": "segment", "type": "nominal"},
                    "tooltip": [
                        {"field": "segment", "type": "nominal"},
                        {"field": "customers", "type": "quantitative"},
                    ],
                },
            },
            use_container_width=True,
        )
        st.dataframe(rfm_summary_df, use_container_width=True)

# ---- 数据表区域 ----
# ---- Data Table Section ----
st.subheader("Data Table")

# 展示前 100 行原始数据，方便用户核查具体数值
# Display the first 100 rows of raw data so users can inspect individual values
st.dataframe(df.head(100), use_container_width=True)