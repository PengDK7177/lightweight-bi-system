import streamlit as st
import pandas as pd
from modules.analytics import (
    calculate_vat,
    basic_kpis,
    cash_flow_analysis,
    rfm_analysis,
    rfm_segment_summary,
)
from modules.auth import require_login

# 若用户未登录则阻止页面继续渲染
# Halt page rendering for unauthenticated users
require_login(logout_key="logout_analytics")

# 显示页面标题
# Display the page title
st.title("Analytics")

# 从会话状态读取数据集；若不存在则提示用户先前往数据导入页
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    st.warning("No dataset in session. Go to Data Import first.")
    st.stop()

# 筛选出所有整数或浮点数类型的列，作为可供分析的数值列列表
# Filter columns with integer or float dtypes to build the list of analysable numeric columns
num_cols = [c for c in df.columns if df[c].dtype.kind in "if"]
if not num_cols:
    st.error("No numeric column available for analysis.")
    st.stop()

# 候选日期列：名称命中常见日期关键词，或列值能够解析为日期
# Candidate date columns: name contains date-related keywords, or values can be parsed as dates
date_hint_cols = [c for c in df.columns if any(k in c.lower() for k in ["date", "time", "day"])]
date_like_cols = []
for c in df.columns:
    if df[c].dtype.kind in "if":
        continue
    sample = df[c].dropna().head(50)
    if len(sample) == 0:
        continue
    parsed = pd.to_datetime(sample.astype(str), errors="coerce")
    if parsed.notna().mean() >= 0.6:
        date_like_cols.append(c)
date_cols = list(dict.fromkeys(date_hint_cols + date_like_cols))

# 候选客户列：优先 customer_id / customer / client 等关键词
# Candidate customer columns: prefer names like customer_id / customer / client
customer_cols = [c for c in df.columns if any(k in c.lower() for k in ["customer", "client", "account"]) ]

# 候选状态列：用于现金流里的已支付/未支付区分
# Candidate status columns: used to distinguish paid vs unpaid cash flow
status_cols = [c for c in df.columns if any(k in c.lower() for k in ["status", "payment", "state"])]

with st.container(border=True):
    st.subheader("VAT Analysis")
    # 简短说明：帮助非技术用户理解本区块用途
    # Short description: helps non-technical users understand this section
    st.caption("Calculate VAT-adjusted values and view high-level KPI metrics.")

    # 让用户从数值列中选择用于 VAT 计算的金额列
    # Let the user select the amount column to use for VAT calculation
    amount_col = st.selectbox("Select amount column", num_cols)

    # 提供滑块让用户调整 VAT 税率（0%–30%，步长 1%，默认 20%）
    # Provide a slider for the user to adjust the VAT rate (0%–30%, step 1%, default 20%)
    vat_rate = st.slider("VAT Rate", 0.0, 0.30, 0.20, 0.01)

    # 按钮：执行 VAT 计算并将结果存回会话状态，供仪表盘等其他页面复用
    # Button: run VAT calculation and store the result in session state for reuse by other pages
    if st.button("Run VAT Analysis"):
        out = calculate_vat(df, amount_col=amount_col, vat_rate=vat_rate)
        # 将含新列的 DataFrame 写回会话状态
        # Write the enriched DataFrame back to session state
        st.session_state["df"] = out
        st.success("VAT columns added: vat_amount, amount_incl_vat")
        st.dataframe(out.head(30), use_container_width=True)

    # 计算所选金额列的基本 KPI 统计指标
    # Compute basic KPI statistics for the selected amount column
    k = basic_kpis(df, amount_col)

    # 以五列并排的方式展示各项 KPI 指标卡片
    # Display each KPI as a metric card arranged in five side-by-side columns
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rows", k["rows"])              # 总行数 / Total row count
    c2.metric("Sum", f"{k['sum']:.2f}")       # 总和 / Sum
    c3.metric("Avg", f"{k['avg']:.2f}")       # 平均值 / Mean
    c4.metric("Min", f"{k['min']:.2f}")       # 最小值 / Minimum
    c5.metric("Max", f"{k['max']:.2f}")       # 最大值 / Maximum

st.markdown("")

with st.container(border=True):
    st.subheader("Cash Flow Analysis")
    # 简短说明：显示每月已支付和未支付金额，方便现金流跟踪
    # Short description: show monthly paid and outstanding amounts for cash-flow tracking
    st.caption("Compare paid and outstanding amounts over time to monitor cash flow.")

    if not date_cols:
        st.info("No date-like column detected for cash flow analysis.")
    else:
        cash_date_col = st.selectbox("Cash flow date column", date_cols)
        cash_amount_col = st.selectbox("Cash flow amount column", num_cols, key="cash_amount_col")
        cash_status_col = st.selectbox("Payment status column (optional)", ["(none)"] + status_cols)

        if st.button("Run Cash Flow Analysis"):
            use_status_col = None if cash_status_col == "(none)" else cash_status_col
            cf = cash_flow_analysis(df, date_col=cash_date_col, amount_col=cash_amount_col, status_col=use_status_col)
            st.session_state["cash_flow_df"] = cf
            if cf.empty:
                st.warning("Cash flow analysis produced no rows. Check date/amount columns.")
            else:
                st.success("Cash flow analysis completed.")
                st.dataframe(cf, use_container_width=True)
                st.line_chart(cf.set_index("month")[["paid_amount", "outstanding_amount"]], use_container_width=True)

st.markdown("")

with st.container(border=True):
    st.subheader("Customer Payment Frequency")
    # 简短说明：展示客户出现次数，帮助识别高频客户
    # Short description: show customer occurrence counts to identify frequent customers
    st.caption("See how often each customer appears in your records (top 20).")

    if not customer_cols:
        st.info("No customer-like column detected for payment frequency analysis.")
    else:
        freq_customer_col = st.selectbox("Customer column", customer_cols, key="freq_customer_col")
        freq_series = (
            df[freq_customer_col]
            .dropna()
            .astype(str)
            .str.strip()
        )
        freq_series = freq_series[freq_series != ""]
        freq_table = freq_series.value_counts().head(20)

        if freq_table.empty:
            st.info("No valid customer values found in the selected column.")
        else:
            st.bar_chart(freq_table, use_container_width=True)
            st.dataframe(
                freq_table.rename("payment_count").reset_index().rename(columns={"index": "customer"}),
                use_container_width=True,
            )

st.markdown("")

with st.container(border=True):
    st.subheader("Payment Status Distribution")
    # 简短说明：展示支付状态分布，帮助快速发现未支付风险
    # Short description: display payment-status distribution to highlight unpaid risk quickly
    st.caption("View the distribution of payment statuses such as paid, pending, or overdue.")

    if not status_cols:
        st.info("No payment-status-like column detected.")
    else:
        status_col = st.selectbox("Payment status column", status_cols, key="status_distribution_col")
        status_series = df[status_col].dropna().astype(str).str.strip()
        status_series = status_series[status_series != ""]
        status_dist = status_series.value_counts()

        if status_dist.empty:
            st.info("No valid payment-status values found in the selected column.")
        else:
            st.bar_chart(status_dist, use_container_width=True)
            st.dataframe(
                status_dist.rename("count").reset_index().rename(columns={"index": "payment_status"}),
                use_container_width=True,
            )

st.markdown("")

with st.container(border=True):
    st.subheader("RFM Analysis (Simplified)")
    # 简短说明：按最近一次消费、消费频次和金额做客户分群
    # Short description: segment customers by recency, frequency, and monetary value
    st.caption("Group customers by recency, frequency, and monetary value for retention planning.")

    if not date_cols or not customer_cols:
        st.info("RFM needs both a customer column and a date-like column.")
    else:
        rfm_customer_col = st.selectbox("RFM customer column", customer_cols)
        rfm_date_col = st.selectbox("RFM date column", date_cols, key="rfm_date")
        rfm_amount_col = st.selectbox("RFM monetary column", num_cols, key="rfm_amount")

        if st.button("Run RFM Analysis"):
            rfm_df = rfm_analysis(df, customer_col=rfm_customer_col, date_col=rfm_date_col, amount_col=rfm_amount_col)
            st.session_state["rfm_df"] = rfm_df
            st.session_state["rfm_summary_df"] = rfm_segment_summary(rfm_df)
            if rfm_df.empty:
                st.warning("RFM analysis produced no rows. Check customer/date/amount columns.")
            else:
                st.success("RFM analysis completed.")
                st.dataframe(rfm_df.head(30), use_container_width=True)
                summary = st.session_state["rfm_summary_df"]
                if not summary.empty:
                    st.bar_chart(summary.set_index("segment")["customers"], use_container_width=True)