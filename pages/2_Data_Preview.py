# 引入 Streamlit 用于构建页面 UI
# Import Streamlit for building the page UI
import streamlit as st

# 引入 pandas 用于数据统计与类型检查
# Import pandas for data statistics and type inspection
import pandas as pd

# 引入登录守卫，确保只有已登录用户才能访问此页面
# Import the login guard to ensure only authenticated users can access this page
from modules.auth import require_login

# 若用户未登录则阻止页面继续渲染
# Halt page rendering for unauthenticated users
require_login(logout_key="logout_data_preview")

# 显示页面标题
# Display the page title
st.title("Data Preview")

# 从会话状态读取数据集；若不存在则提示用户先前往数据导入页
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    st.warning("No dataset in session. Go to Data Import first.")
    st.stop()

# 显示数据集的行列数，帮助用户快速了解数据规模
# Display the row and column count to give the user a quick overview of the dataset size
st.write(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")

# 渲染前 50 行数据，供用户直观浏览内容
# Render the first 50 rows so the user can visually inspect the data
st.dataframe(df.head(50), use_container_width=True)

# 可展开面板：显示每列的数据类型，便于判断是否需要类型转换
# Expandable panel: show each column's data type to help identify any needed type conversions
with st.expander("Column types"):
    st.dataframe(pd.DataFrame({"column": df.columns, "dtype": df.dtypes.astype(str)}), use_container_width=True)

# 可展开面板：统计并展示每列缺失值数量，按数量降序排列，辅助数据质量评估
# Expandable panel: count and display missing values per column (sorted descending) for data quality checks
with st.expander("Missing values"):
    miss = df.isna().sum().sort_values(ascending=False)
    st.dataframe(miss.rename("missing_count").reset_index().rename(columns={"index": "column"}), use_container_width=True)