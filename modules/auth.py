# 引入标准库：hashlib 用于密码哈希，hmac 用于安全比对，json/os/Path 用于文件操作
# Standard library imports: hashlib for password hashing, hmac for secure comparison, json/os/Path for file I/O
import hashlib
import hmac
import json
import os
from pathlib import Path

# 引入 Streamlit 用于构建 Web UI 及维护会话状态
# Import Streamlit for building the Web UI and managing session state
import streamlit as st


# 本地 JSON 文件路径，用于存储演示级别的用户账户数据
# Path to the local JSON file used as a lightweight demo-level account store
USER_STORE_PATH = Path("data/users.json")

# PBKDF2 迭代轮数，轮数越高暴力破解成本越大，推荐最低 100,000
# Number of PBKDF2 iterations; higher values increase brute-force cost (minimum 100,000 recommended)
PBKDF2_ROUNDS = 120_000


def _hide_navigation_before_login() -> None:
    """
    在未登录状态下隐藏侧边栏与展开控件，确保仅显示登录界面。
    Hide the sidebar and expand control before authentication so only the login UI is visible.
    """
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hash_password(password: str, salt_hex: str | None = None) -> str:
    """
    使用 PBKDF2-HMAC-SHA256 对密码进行加盐哈希，返回格式为 salt$hash 的字符串。
    Hash a password with PBKDF2-HMAC-SHA256 and return a 'salt$hash' formatted string.
    """
    # 若未提供 salt，则随机生成 16 字节的盐值；否则从十六进制字符串恢复
    # Generate 16 random bytes as salt if not provided; otherwise decode from the hex string
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)

    # 执行 PBKDF2 派生，生成 SHA-256 摘要
    # Derive a SHA-256 digest using PBKDF2 with the specified iteration count
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)

    # 以 "盐值十六进制$摘要十六进制" 格式返回，便于存储和校验时分割
    # Return as "salt_hex$digest_hex" so salt and hash can be easily split during verification
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """
    将明文密码与存储的 salt$hash 字符串进行比对，返回是否匹配。
    Verify a plain-text password against a stored 'salt$hash' string; returns True if they match.
    """
    # 分离盐值与哈希值；若格式不符则直接返回 False，防止异常泄漏信息
    # Split salt and digest; return False immediately on malformed input to avoid error leaks
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
    except ValueError:
        return False

    # 用同一盐值重新计算哈希，然后使用 hmac.compare_digest 做常数时间比较以防时序攻击
    # Recompute the hash with the same salt, then use constant-time comparison to prevent timing attacks
    calculated = _hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(calculated, f"{salt_hex}${digest_hex}")


def _ensure_user_store() -> dict:
    """
    确保本地用户存储文件存在并具有合法结构；若文件缺失则创建默认管理员账户。
    Ensure the local user store exists with a valid structure; create a default admin on first run.
    """
    # 若父目录不存在则递归创建，保证后续写文件不报错
    # Create parent directories recursively if they do not exist
    USER_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 文件不存在时写入包含默认 admin 账户的初始 JSON
    # Write initial JSON with a default admin account when the file is absent
    if not USER_STORE_PATH.exists():
        default_payload = {
            "users": [
                {
                    "username": "admin",
                    "password_hash": _hash_password("admin123"),
                    "role": "admin",
                }
            ]
        }
        USER_STORE_PATH.write_text(json.dumps(default_payload, indent=2), encoding="utf-8")
        return default_payload

    # 尝试读取并解析现有 JSON；解析失败则返回空用户列表，避免整个应用崩溃
    # Attempt to read and parse the existing JSON; fall back to an empty list on failure
    try:
        payload = json.loads(USER_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {"users": []}

    # 防御性校验：确保顶层是 dict
    # Defensive check: ensure the top-level structure is a dict
    if not isinstance(payload, dict):
        payload = {"users": []}

    # 防御性校验：确保 users 字段是列表
    # Defensive check: ensure the 'users' field is a list
    if not isinstance(payload.get("users"), list):
        payload["users"] = []

    return payload


def authenticate_local_user(username: str, password: str) -> dict | None:
    """
    从本地 JSON 存储中验证用户名和密码，验证通过则返回用户信息字典，否则返回 None。
    Authenticate a username/password pair against the local JSON store; returns the user dict or None.
    """
    # 用户名或密码为空时直接拒绝，避免空字符串绕过后续匹配
    # Reject immediately if either field is empty to prevent empty-string bypass
    if not username or not password:
        return None

    # 加载用户存储，并对用户名去除首尾空白，防止因误输入空格导致匹配失败
    # Load the user store and strip whitespace from the username to tolerate accidental spaces
    payload = _ensure_user_store()
    normalized_username = username.strip()

    # 遍历用户列表，找到匹配用户名后再校验密码
    # Iterate over the user list; once a matching username is found, verify the password
    for user in payload["users"]:
        # 跳过格式错误的条目，保持鲁棒性
        # Skip malformed entries to keep the loop robust
        if not isinstance(user, dict):
            continue
        if user.get("username") != normalized_username:
            continue

        # 取出存储的哈希值并进行安全比对
        # Retrieve the stored hash and perform a secure comparison
        stored_hash = user.get("password_hash", "")
        if _verify_password(password, stored_hash):
            return user

    # 未找到匹配用户或密码错误，统一返回 None（不区分两种失败原因，防止用户名枚举）
    # Return None for both "user not found" and "wrong password" to prevent username enumeration
    return None


def init_auth_state() -> None:
    """
    初始化 Streamlit 会话状态中的认证相关键，防止首次访问时出现 KeyError。
    Initialise authentication keys in Streamlit session state to avoid KeyError on first access.
    """
    # 若 authenticated 键不存在则设为 False（未登录状态）
    # Set 'authenticated' to False if it has not been set yet
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # 若 username 键不存在则设为 None
    # Set 'username' to None if it has not been set yet
    if "username" not in st.session_state:
        st.session_state["username"] = None


def logout() -> None:
    """
    清除会话中的认证状态并重新运行应用，将用户重定向回登录页。
    Clear authentication state from the session and rerun the app to redirect the user to the login page.
    """
    # 将登录标志重置为 False，并清空存储的用户名
    # Reset the login flag and clear the stored username
    st.session_state["authenticated"] = False
    st.session_state["username"] = None

    # 触发 Streamlit 重新渲染，使登录页面立即显示
    # Trigger a Streamlit rerun so the login page is displayed immediately
    st.rerun()


def render_user_sidebar(logout_key: str = "logout") -> None:
    """
    在侧边栏显示当前登录用户名及退出登录按钮。
    Render the current user's name and a logout button in the Streamlit sidebar.
    """
    with st.sidebar:
        # 展示当前登录的用户名；若键不存在则降级显示 'unknown'
        # Display the current username; fall back to 'unknown' if the key is missing
        st.success(f"Logged in as: {st.session_state.get('username', 'unknown')}")

        # 点击退出按钮时调用 logout() 清除会话并重定向
        # Call logout() when the button is clicked to clear the session and redirect
        if st.button("Logout", key=logout_key):
            logout()


def login_form() -> bool:
    """
    渲染登录表单，验证成功后更新会话状态并重新加载应用。
    Render the login form; update session state and rerun the app on successful authentication.
    """
    st.subheader("Account Login")

    # 使用 Streamlit 表单组件收集用户名和密码，避免每次输入都触发页面刷新
    # Use a Streamlit form to collect credentials without triggering a rerun on every keystroke
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    # 仅在用户点击提交按钮后才执行认证逻辑
    # Only run authentication logic when the submit button has been pressed
    if submitted:
        user = authenticate_local_user(username, password)
        if user:
            # 认证成功：写入会话状态并立即重新渲染，跳转到主界面
            # Authentication succeeded: persist state and rerun to navigate to the main UI
            st.session_state["authenticated"] = True
            st.session_state["username"] = user.get("username")
            st.success("Login successful")
            st.rerun()
        else:
            # 认证失败：显示通用错误信息，不透露失败原因
            # Authentication failed: show a generic error message to avoid leaking details
            st.error("Invalid username or password")

    # 提示首次启动时的默认账户，方便演示和测试
    # Hint at the default account for first-run demos and testing
    st.caption("Default account (first run): admin / admin123")
    return bool(st.session_state.get("authenticated"))


def render_login_page() -> None:
    """
    渲染独立登录页：未登录时仅显示登录相关内容。
    Render a dedicated login page: before authentication, show login content only.
    """
    _hide_navigation_before_login()
    st.title("Lightweight BI System")
    st.markdown("### Login")
    login_form()


def require_login(logout_key: str = "logout") -> None:
    """
    页面守卫：若用户未登录则显示警告并阻止页面继续渲染。
    Page guard: display a warning and halt rendering for unauthenticated users.
    """
    # 确保会话状态中存在认证相关键
    # Ensure authentication keys are present in session state
    init_auth_state()

    # 未登录则显示提示信息并调用 st.stop() 终止后续渲染
    # Show a warning and call st.stop() to halt the page for unauthenticated users
    if not st.session_state.get("authenticated"):
        _hide_navigation_before_login()
        st.switch_page("app.py")
        st.stop()

    # 已登录则在侧边栏渲染用户信息和退出按钮
    # Render user info and logout button in the sidebar for authenticated users
    render_user_sidebar(logout_key=logout_key)
