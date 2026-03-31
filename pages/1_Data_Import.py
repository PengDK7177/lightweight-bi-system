# 引入 Streamlit 用于构建页面 UI
# Import Streamlit for building the page UI
import streamlit as st

# 引入 pandas（此页面通过 load_csv 间接使用）
# Import pandas (used indirectly via load_csv on this page)
import pandas as pd

# 引入 Path，用于跨平台文件路径操作
# Import Path for cross-platform file path operations
from pathlib import Path

# 从数据导入模块引入加载工具函数
# Import the data loading utility from the data_import module
from modules.data_import import load_csv

# 引入登录守卫，确保只有已登录用户才能访问此页面
# Import the login guard to ensure only authenticated users can access this page
from modules.auth import require_login

# 若用户未登录则阻止页面继续渲染，并在侧边栏显示用户信息
# Halt page rendering for unauthenticated users and show user info in the sidebar
require_login(logout_key="logout_data_import")

# 显示页面标题
# Display the page title
st.title("Data Import")

# 提供文件上传控件，支持 CSV 和 Excel 格式
# Provide a file upload widget that accepts CSV and Excel formats
uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"])

# 扫描 data/raw 目录，列出可供直接加载的本地文件
# Scan the data/raw directory to list local files available for direct loading
raw_dir = Path("data/raw")
local_files = []
if raw_dir.exists():
    local_files = [p.name for p in raw_dir.iterdir() if p.suffix.lower() in [".csv", ".xlsx", ".xls"]]

# 提供下拉框让用户从本地 raw 目录中选择文件
# Provide a selectbox for the user to pick a file from the local raw directory
selected_local = st.selectbox("Or load from data/raw", ["(none)"] + local_files)

# 初始化 df 为 None，后续根据用户选择赋值
# Initialise df as None; it will be assigned based on the user's selection
df = None

# 优先使用上传的文件；若无上传则尝试加载本地选择的文件
# Prefer the uploaded file; fall back to the locally selected file if nothing was uploaded
if uploaded is not None:
    df = load_csv(uploaded)
elif selected_local != "(none)":
    df = load_csv(raw_dir / selected_local)

# 若成功加载数据，则存入会话状态并预览前 20 行
# If data was loaded successfully, store it in session state and preview the first 20 rows
if df is not None:
    st.session_state["df"] = df
    st.success(f"Loaded successfully: {df.shape[0]} rows × {df.shape[1]} columns")
    st.dataframe(df.head(20), use_container_width=True)

    # 提供保存按钮，将数据持久化到 processed 目录，供后续步骤使用
    # Provide a save button to persist the data to the processed directory for later steps
    if st.button("Save to data/processed/imported_data.csv"):
        Path("data/processed").mkdir(parents=True, exist_ok=True)
        df.to_csv("data/processed/imported_data.csv", index=False)
        st.success("Saved.")
else:
    # 未加载任何数据时显示引导提示
    # Show a guide message when no data has been loaded yet
    st.info("Please upload or select a local file.")