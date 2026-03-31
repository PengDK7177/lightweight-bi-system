# 引入 Streamlit 用于构建页面 UI
# Import Streamlit for building the page UI
import streamlit as st

# 从清洗模块引入三个核心清洗函数
# Import the three core cleaning functions from the cleaning module
from modules.cleaning import remove_duplicates, fill_missing, standardize_columns

# 引入登录守卫，确保只有已登录用户才能访问此页面
# Import the login guard to ensure only authenticated users can access this page
from modules.auth import require_login

# 若用户未登录则阻止页面继续渲染
# Halt page rendering for unauthenticated users
require_login(logout_key="logout_data_cleaning")

# 显示页面标题
# Display the page title
st.title("Data Cleaning")

# 从会话状态读取数据集；若不存在则提示用户先前往数据导入页
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    st.warning("No dataset in session. Go to Data Import first.")
    st.stop()

# 显示当前数据集的行列数，便于对比清洗前后的变化
# Show the current shape so users can compare before and after cleaning
st.write("Current shape:", df.shape)

# 按钮：将列名标准化为小写 snake_case，规范化后有助于后续匹配和转换操作
# Button: normalise column names to lowercase snake_case to improve downstream matching
if st.button("Standardize Column Names"):
    df = standardize_columns(df)
    # 将标准化后的 DataFrame 写回会话状态，使其对所有页面可见
    # Write the standardised DataFrame back to session state so all pages see the update
    st.session_state["df"] = df
    st.success("Column names standardized.")

# 按钮：删除重复行，并展示删除了多少行
# Button: remove duplicate rows and report how many were dropped
if st.button("Remove Duplicates"):
    before = len(df)
    df = remove_duplicates(df)
    st.session_state["df"] = df
    st.success(f"Removed {before - len(df)} duplicate rows.")

# 下拉框：让用户选择处理缺失值的策略（删除 / 填零 / 前向填充）
# Selectbox: let the user choose a missing-value handling strategy (drop / zero / ffill)
strategy = st.selectbox("Missing value handling", ["drop", "zero", "ffill"])

# 按钮：应用所选策略并将结果存回会话状态
# Button: apply the chosen strategy and persist the result to session state
if st.button("Apply Missing Value Strategy"):
    df = fill_missing(df, strategy=strategy)
    st.session_state["df"] = df
    st.success(f"Applied strategy: {strategy}")

# 预览清洗后数据集的前 30 行，让用户即时确认效果
# Preview the first 30 rows of the cleaned dataset so the user can verify the result immediately
st.dataframe(st.session_state["df"].head(30), use_container_width=True)