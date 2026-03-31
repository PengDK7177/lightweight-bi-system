# 引入 Streamlit 用于构建页面 UI
# Import Streamlit for building the page UI
import streamlit as st

# 从分析模块引入增值税计算和 KPI 统计函数
# Import VAT calculation and KPI aggregation functions from the analytics module
from modules.analytics import calculate_vat, basic_kpis

# 引入登录守卫，确保只有已登录用户才能访问此页面
# Import the login guard to ensure only authenticated users can access this page
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