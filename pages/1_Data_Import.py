
import streamlit as st
import pandas as pd
from pathlib import Path
from modules.data_import import load_csv
from modules.auth import require_login, clear_dataset_state
from modules.ui import inject_bi_theme, render_page_header

# 若用户未登录则阻止页面继续渲染，并在侧边栏显示用户信息
# Halt page rendering for unauthenticated users and show user info in the sidebar
require_login(logout_key="logout_data_import")

# 显示页面标题
# Inject the shared BI visual theme so authenticated pages feel consistent
inject_bi_theme()

# 提供文件上传控件，支持 CSV 和 Excel 格式
# 扫描 data/raw 目录，列出可供直接加载的本地文件
# Scan the data/raw directory to list local files available for direct loading
raw_dir = Path("data/raw")
local_files = []
if raw_dir.exists():
    local_files = [p.name for p in raw_dir.iterdir() if p.suffix.lower() in [".csv", ".xlsx", ".xls"]]

# 渲染统一页面头部，展示当前可用本地数据源数量
# Render the shared page header and show the number of available local data sources
render_page_header(
    "Data Import",
    "Bring CSV or Excel files into the BI workspace, then persist a clean working copy for preview, cleaning, and analytics.",
    stats=[
        (str(len(local_files)), "Local files available"),
        ("CSV/XLSX", "Supported formats"),
        ("Session", "Current workspace scope"),
    ],
)

# 提供文件上传控件，支持 CSV 和 Excel 格式
# Provide a file upload widget that accepts CSV and Excel formats
uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"])

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
    st.info("Please upload or select a local file.")

# ── Dataset Deletion ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Delete Current Dataset")
st.caption(
    "Removes the loaded dataset and all derived outputs (cleaning, analytics, "
    "dashboard, export) from the current session. This action cannot be undone."
)

# Two-step confirmation: first click reveals the real delete button so users
# cannot trigger deletion by accidentally clicking once.
if st.session_state.get("df") is None:
    st.info("No dataset is currently loaded.")
else:
    if "_confirm_delete" not in st.session_state:
        st.session_state["_confirm_delete"] = False

    if not st.session_state["_confirm_delete"]:
        if st.button("🗑️ Delete Dataset", type="secondary"):
            st.session_state["_confirm_delete"] = True
            st.rerun()
    else:
        st.warning(
            "Are you sure? This will clear the dataset and **all** analytics results "
            "(VAT, cash flow, RFM, dashboard). This cannot be undone."
        )
        col_confirm, col_cancel, _ = st.columns([1, 1, 3])
        with col_confirm:
            if st.button("✅ Yes, delete", type="primary"):
                st.session_state.pop("_confirm_delete", None)
                clear_dataset_state()
                st.success("Dataset and all derived outputs have been removed from the session.")
                st.rerun()
        with col_cancel:
            if st.button("Cancel"):
                st.session_state["_confirm_delete"] = False
                st.rerun()
