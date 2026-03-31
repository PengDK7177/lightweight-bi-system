# 引入 Streamlit，作为整个 BI 系统的 Web 框架
# Import Streamlit as the Web framework for the entire BI system
import streamlit as st

# 从各模块引入核心功能函数
# Import core functions from the project modules
from modules.data_import import load_csv
from modules.cleaning import remove_duplicates
from modules.analytics import calculate_vat
from modules.auth import init_auth_state, login_form, render_user_sidebar

# 配置页面标题和布局（宽屏模式），必须是 Streamlit 脚本中的第一个调用
# Configure the page title and layout (wide mode); must be the first Streamlit call in the script
st.set_page_config(page_title="Lightweight BI System", layout="wide")

# 确保认证相关的会话状态键在任何页面逻辑执行前已初始化
# Ensure auth-related session state keys are initialised before any page logic runs
init_auth_state()

# 首页同时充当登录入口：若用户未登录则渲染登录表单并停止后续渲染
# The home page doubles as the login entry point: show the login form and halt if not authenticated
if not st.session_state.get("authenticated"):
    st.title("Lightweight BI System")
    st.markdown("### Login")
    # 渲染登录表单；成功登录后会自动 rerun，跳过此分支
    # Render the login form; on success it reruns the app and skips this branch
    login_form()
    st.stop()

# ---- 以下内容仅对已登录用户可见 ----
# ---- Content below is only visible to authenticated users ----

# 显示主页标题
# Display the main page title
st.title("Lightweight BI Prototype for UK SMEs")

# 在侧边栏渲染当前用户信息和退出按钮
# Render the current user's info and logout button in the sidebar
render_user_sidebar(logout_key="logout_home")

# 显示欢迎信息和导航提示
# Display a welcome message and navigation hint
st.markdown("### Welcome")
st.write(
    "Use the left sidebar to navigate modules:\n"
    "- Data Import\n"
    "- Data Preview\n"
    "- Data Cleaning\n"
    "- Analytics\n"
    "- Dashboard"
)

# 提示用户通过左侧导航栏切换页面，避免误操作
# Remind users to use only the left sidebar for navigation to prevent confusion
st.info("Tip: This app uses Streamlit Pages. Keep navigation only in the left sidebar.")

