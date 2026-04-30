# 引入 Streamlit 用于构建页面 UI
# Import Streamlit for building the page UI
import streamlit as st

# 引入 pandas 用于数值转换，确保图表和 KPI 不因脏数据崩溃
# Import pandas for numeric coercion to prevent chart/KPI crashes on dirty values
import pandas as pd

# 引入登录守卫，确保只有已登录用户才能访问此页面
# Import the login guard to ensure only authenticated users can access this page
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

# 筛选出所有整数或浮点数类型的列，用于图表绘制和 KPI 计算
# Filter integer and float columns to use for charts and KPI calculations
num_cols = [c for c in df.columns if df[c].dtype.kind in "if"]
if not num_cols:
    st.info("No numeric data available for charts.")
    st.stop()

# 让用户从数值列中选择要展示的指标列
# Let the user choose which numeric column to visualise as the main metric
metric_col = st.selectbox("Metric for chart", num_cols)

with st.container(border=True):
    # ---- KPI 区域 ----
    # ---- KPI Section ----
    st.subheader("KPI Overview")
    # 简短说明：帮助用户理解 KPI 区域显示的是汇总值
    # Short description: explain that this section shows summary totals
    st.caption("Quick summary of the selected metric to understand overall scale.")

    # 将所选列强制转换为数值类型后求和，非数值内容填 0，防止因脏数据报错
    # Coerce the selected column to numeric (filling non-numeric with 0) before summing to avoid crashes
    st.metric("Total", f"{pd.to_numeric(df[metric_col], errors='coerce').fillna(0).sum():.2f}")

st.markdown("")

with st.container(border=True):
    # ---- 分布图区域 ----
    # ---- Distribution Chart Section ----
    st.subheader("Distribution")
    # 简短说明：帮助用户理解图表展示的是前 50 条记录分布
    # Short description: clarify that this chart shows distribution for the first 50 records
    st.caption("Distribution of the selected metric across the first 50 rows.")

    # 取前 50 行绘制柱状图，展示所选指标的分布情况
    # Plot a bar chart of the first 50 rows to visualise the distribution of the selected metric
    st.bar_chart(df[metric_col].head(50), use_container_width=True)

st.markdown("")

with st.container(border=True):
    # ---- 数据表区域 ----
    # ---- Data Table Section ----
    st.subheader("Data Table")
    # 简短说明：便于用户核查图表背后的原始记录
    # Short description: helps users verify the raw records behind the charts
    st.caption("Preview the first 100 rows used in this dashboard.")

    # 展示前 100 行原始数据，方便用户核查具体数值
    # Display the first 100 rows of raw data so users can inspect individual values
    st.dataframe(df.head(100), use_container_width=True)