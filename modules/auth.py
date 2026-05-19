# 引入标准库：hashlib 用于密码哈希，hmac 用于安全比对，json/os/Path 用于文件操作
# Standard library imports: hashlib for password hashing, hmac for secure comparison, json/os/Path for file I/O
import base64
import hashlib
import hmac
import json
import os
import re
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


def _save_user_store(payload: dict) -> bool:
    """
    将用户数据写回本地 JSON 文件，成功返回 True，失败返回 False。
    Persist user payload back to local JSON storage; returns True on success.
    """
    try:
        USER_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def _validate_username(username: str) -> tuple[bool, str]:
    """
    校验用户名基础规则：长度与字符集。
    Validate basic username rules: length and allowed character set.
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 32:
        return False, "Username cannot exceed 32 characters"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return False, "Username can only use letters, numbers, _, ., -"
    return True, ""


def _validate_password_complexity(password: str) -> tuple[bool, str]:
    """
    校验密码复杂性：长度、大小写、数字、特殊字符、空白字符。
    Validate password complexity: length, case mix, digits, special chars, no spaces.
    """
    issues: list[str] = []

    if len(password) < 8:
        issues.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        issues.append("at least 1 uppercase letter")
    if not re.search(r"[a-z]", password):
        issues.append("at least 1 lowercase letter")
    if not re.search(r"\d", password):
        issues.append("at least 1 number")
    if not re.search(r"[^A-Za-z0-9]", password):
        issues.append("at least 1 special character")
    if re.search(r"\s", password):
        issues.append("no spaces")

    if issues:
        return False, "Password must contain: " + ", ".join(issues)

    return True, ""


def register_local_user(username: str, password: str, confirm_password: str) -> tuple[bool, str]:
    """
    创建本地账户：执行用户名/密码校验、重复用户检查并保存哈希密码。
    Create a local account with validations, duplicate-check, and hashed password storage.
    """
    normalized_username = username.strip()

    if not normalized_username:
        return False, "Username is required"
    if not password:
        return False, "Password is required"
    if password != confirm_password:
        return False, "Passwords do not match"

    username_ok, username_message = _validate_username(normalized_username)
    if not username_ok:
        return False, username_message

    password_ok, password_message = _validate_password_complexity(password)
    if not password_ok:
        return False, password_message

    payload = _ensure_user_store()
    existing_usernames = {
        str(user.get("username", "")).strip().lower()
        for user in payload.get("users", [])
        if isinstance(user, dict)
    }
    if normalized_username.lower() in existing_usernames:
        return False, "Username already exists"

    payload["users"].append(
        {
            "username": normalized_username,
            "password_hash": _hash_password(password),
            "role": "user",
        }
    )

    if not _save_user_store(payload):
        return False, "Failed to save user account"

    return True, "Registration successful"


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
    """Render a polished BI-focused login screen; update session state and rerun on success."""
    hero_image_path = Path("assets/login-data-hero.png")
    hero_image_css = (
        f"url(data:image/png;base64,{base64.b64encode(hero_image_path.read_bytes()).decode('ascii')})"
        if hero_image_path.exists()
        else "linear-gradient(135deg, #10202f 0%, #133d42 48%, #1b2a36 100%)"
    )

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background:
                radial-gradient(circle at 12% 12%, rgba(35, 181, 169, 0.20), transparent 28%),
                radial-gradient(circle at 88% 18%, rgba(246, 177, 74, 0.14), transparent 24%),
                linear-gradient(135deg, #071017 0%, #0f1b24 44%, #f3f6f8 44%, #f7fafc 100%);
        }}
        [data-testid="stHeader"] {{ background: transparent; }}
        .block-container {{
            max-width: 1180px;
            padding-top: 4.2rem;
            padding-bottom: 3rem;
        }}
        .login-hero {{
            position: relative;
            min-height: 610px;
            overflow: hidden;
            border-radius: 24px;
            padding: 2.2rem;
            color: #f8fbfc;
            background:
                linear-gradient(90deg, rgba(5, 14, 22, 0.34), rgba(5, 14, 22, 0.74)),
                {hero_image_css};
            background-size: cover;
            background-position: center;
            box-shadow: 0 28px 70px rgba(3, 10, 18, 0.34);
            border: 1px solid rgba(255, 255, 255, 0.16);
        }}
        .login-hero::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, transparent 0%, rgba(6, 14, 20, 0.82) 100%);
            pointer-events: none;
        }}
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {{
            min-height: 610px;
            padding: 2.1rem 2rem;
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(18, 31, 42, 0.08);
            box-shadow: 0 24px 62px rgba(16, 31, 43, 0.14);
        }}
        .hero-content {{
            position: relative;
            z-index: 1;
            display: flex;
            min-height: 530px;
            flex-direction: column;
            justify-content: space-between;
        }}
        .brand-mark {{
            display: inline-flex;
            align-items: center;
            gap: 0.65rem;
            color: #d8f7f3;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .brand-mark span {{
            width: 34px;
            height: 34px;
            border-radius: 10px;
            display: inline-grid;
            place-items: center;
            background: rgba(36, 199, 184, 0.18);
            border: 1px solid rgba(95, 230, 217, 0.42);
            color: #67f1e3;
            font-size: 1.05rem;
        }}
        .hero-title {{
            max-width: 620px;
            margin: 0;
            color: #ffffff;
            font-size: clamp(2.4rem, 5vw, 4.7rem);
            line-height: 1.02;
            font-weight: 800;
            letter-spacing: 0;
        }}
        .hero-subtitle {{
            max-width: 560px;
            margin-top: 1rem;
            color: rgba(232, 244, 245, 0.82);
            font-size: 1.02rem;
            line-height: 1.7;
        }}
        .metric-row {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1.75rem;
        }}
        .metric-card {{
            padding: 1rem;
            border-radius: 14px;
            background: rgba(8, 18, 26, 0.54);
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(12px);
        }}
        .metric-value {{
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1;
        }}
        .metric-label {{
            margin-top: 0.45rem;
            color: rgba(229, 242, 242, 0.72);
            font-size: 0.78rem;
            line-height: 1.35;
        }}
        .panel-kicker {{
            color: #0c7f78;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}
        .panel-title {{
            margin: 0.45rem 0 0.55rem;
            color: #101820;
            font-size: 2rem;
            line-height: 1.12;
            font-weight: 800;
            letter-spacing: 0;
        }}
        .panel-copy {{
            margin: 0 0 1.2rem;
            color: #5c6b75;
            font-size: 0.94rem;
            line-height: 1.65;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
            padding: 0.28rem;
            border-radius: 12px;
            background: #edf3f5;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 2.65rem;
            border-radius: 10px;
            color: #52616c;
            font-weight: 700;
        }}
        .stTabs [aria-selected="true"] {{
            color: #0d1b24;
            background: #ffffff;
            box-shadow: 0 5px 18px rgba(18, 31, 42, 0.10);
        }}
        .stTextInput label {{
            color: #22313b !important;
            font-weight: 700 !important;
        }}
        .stTextInput input {{
            min-height: 2.9rem;
            border-radius: 10px;
            border: 1px solid #d8e1e6;
            background: #fbfdfe;
            color: #121b22;
            font-size: 0.95rem;
        }}
        .stTextInput input:focus {{
            border-color: #15a89c;
            box-shadow: 0 0 0 3px rgba(21, 168, 156, 0.16);
        }}
        .stFormSubmitButton button {{
            min-height: 3rem;
            border-radius: 10px;
            border: none;
            background: linear-gradient(135deg, #0b766f 0%, #159b91 54%, #f2ad48 140%);
            color: #ffffff;
            font-weight: 800;
            box-shadow: 0 14px 28px rgba(21, 139, 130, 0.24);
        }}
        .stFormSubmitButton button:hover {{
            border: none;
            background: linear-gradient(135deg, #09635d 0%, #118a81 58%, #e69d35 140%);
            color: #ffffff;
        }}
        .login-footnote {{
            margin-top: 1rem;
            padding: 0.9rem 1rem;
            border-radius: 12px;
            background: #f4f8f9;
            color: #667681;
            font-size: 0.84rem;
            line-height: 1.55;
            border: 1px solid #e3ecef;
        }}
        @media (max-width: 900px) {{
            [data-testid="stAppViewContainer"] {{ background: #f6fafb; }}
            .block-container {{ padding-top: 2rem; }}
            .login-hero,
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {{
                min-height: auto;
                border-radius: 18px;
            }}
            .hero-content {{ min-height: 450px; }}
            .metric-row {{ grid-template-columns: 1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.22, 0.78], gap="large")
    submitted_login = False
    submitted_register = False
    username = ""
    password = ""
    register_username = ""
    register_password = ""
    confirm_password = ""

    with left:
        st.markdown(
            '<section class="login-hero">'
            '<div class="hero-content">'
            '<div class="brand-mark"><span>BI</span> Lightweight BI System</div>'
            '<div>'
            '<h1 class="hero-title">Turn messy business data into clear decisions.</h1>'
            '<p class="hero-subtitle">A focused workspace for SME data import, cleaning, VAT analytics, '
            'cash-flow views, and executive dashboards.</p>'
            '<div class="metric-row">'
            '<div class="metric-card"><div class="metric-value">5</div><div class="metric-label">Core BI modules</div></div>'
            '<div class="metric-card"><div class="metric-value">VAT</div><div class="metric-label">Automated tax analysis</div></div>'
            '<div class="metric-card"><div class="metric-value">CSV</div><div class="metric-label">Fast dataset onboarding</div></div>'
            '</div>'
            '</div>'
            '</div>'
            '</section>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            '<div class="panel-kicker">Secure workspace</div>'
            '<h2 class="panel-title">Sign in to your BI cockpit</h2>'
            '<p class="panel-copy">Access imported datasets, cleaning workflows, analytics reports, and dashboards from one place.</p>',
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(["Login", "Register"])

        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Username", key="login_username")
                password = st.text_input(
                    "Password", type="password", placeholder="Password", key="login_password"
                )
                submitted_login = st.form_submit_button("Login", use_container_width=True)

        with register_tab:
            st.caption(
                "Password rules: at least 8 chars, uppercase, lowercase, number, special character, and no spaces."
            )
            with st.form("register_form"):
                register_username = st.text_input(
                    "Username", placeholder="Create a username", key="register_username"
                )
                register_password = st.text_input(
                    "Password", type="password", placeholder="Create a password", key="register_password"
                )
                confirm_password = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Enter password again",
                    key="register_confirm_password",
                )
                submitted_register = st.form_submit_button("Register", use_container_width=True)

        st.markdown(
            '<div class="login-footnote">Default account on first run: <strong>admin</strong> / '
            '<strong>admin123</strong></div>',
            unsafe_allow_html=True,
        )

    if submitted_login:
        user = authenticate_local_user(username, password)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["username"] = user.get("username")
            st.rerun()
        else:
            with right:
                st.error("Invalid username or password")

    if submitted_register:
        success, message = register_local_user(register_username, register_password, confirm_password)
        if success:
            st.session_state["authenticated"] = True
            st.session_state["username"] = register_username.strip()
            st.rerun()
        else:
            with right:
                st.error(message)

    return bool(st.session_state.get("authenticated"))

# All keys that any page writes when loading, cleaning, analysing, or exporting
# data.  Keeping them in one place ensures the delete operation is always in
# sync with the rest of the application.
_DATASET_STATE_KEYS: list[str] = [
    # Core dataset
    "df",
    # PII flag
    "pii_masked",
    # VAT analysis
    "vat_result_df",
    "vat_summary_df",
    "vat_amount_col",
    "vat_rate",
    # Cash-flow analysis
    "cash_flow_df",
    # Customer-frequency analysis
    "customer_payment_frequency_df",
    "customer_payment_frequency_col",
    # Payment-status distribution
    "payment_status_distribution_df",
    "payment_status_col",
    # RFM segmentation
    "rfm_df",
    "rfm_result_df",
    "rfm_summary_df",
    "rfm_config",
]


def clear_dataset_state() -> None:
    """
    从 Streamlit 会话状态中移除所有与当前数据集相关的键，
    使系统恢复到"未加载任何数据集"的初始状态。
    Remove all dataset-related keys from Streamlit session state so that
    preview, analytics, dashboard, and export modules all see a clean
    'no dataset loaded' state.  Authentication keys are left untouched.
    """
    for key in _DATASET_STATE_KEYS:
        st.session_state.pop(key, None)


def render_login_page() -> None:
    """
    渲染独立登录页：未登录时仅显示居中卡片登录界面。
    Render the dedicated login page: show only the centred card login UI.
    """
    _hide_navigation_before_login()
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
