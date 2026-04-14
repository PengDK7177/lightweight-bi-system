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

# ---- 分布图区域 ----
# ---- Distribution Chart Section ----
st.subheader("Distribution")

# 取前 50 行绘制柱状图，展示所选指标的分布情况
# Plot a bar chart of the first 50 rows to visualise the distribution of the selected metric
st.bar_chart(df[metric_col].head(50), use_container_width=True)

# ---- 数据表区域 ----
# ---- Data Table Section ----
st.subheader("Data Table")

# 展示前 100 行原始数据，方便用户核查具体数值
# Display the first 100 rows of raw data so users can inspect individual values
st.dataframe(df.head(100), use_container_width=True)