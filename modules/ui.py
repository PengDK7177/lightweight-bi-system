# 引入 Streamlit 用于注入全局样式和渲染页面头部组件
# Import Streamlit for injecting global styles and rendering page header components
import streamlit as st


# 定义统一的 BI 页面视觉样式，供所有已登录页面复用
# Define the shared BI page visual style reused by all authenticated pages
def inject_bi_theme() -> None:
    """
    注入统一的 BI 系统页面样式，包括背景、卡片、表单控件、按钮和表格细节。
    Inject the unified BI system page style, including background, cards, form controls, buttons, and tables.
    """
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 8% 8%, rgba(20, 151, 143, 0.14), transparent 28%),
                radial-gradient(circle at 94% 4%, rgba(241, 171, 67, 0.12), transparent 24%),
                linear-gradient(135deg, #f5f8fa 0%, #eef4f6 42%, #f8fbfc 100%);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0c1822 0%, #102934 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * {
            color: #ecf6f7;
        }

        .block-container {
            max-width: 1220px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }

        .bi-page-hero {
            margin-bottom: 1.25rem;
            padding: 1.6rem 1.8rem;
            border-radius: 20px;
            color: #f8fbfc;
            background:
                linear-gradient(135deg, rgba(8, 23, 33, 0.96), rgba(13, 61, 68, 0.92)),
                radial-gradient(circle at 80% 20%, rgba(241, 171, 67, 0.20), transparent 26%);
            border: 1px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 20px 46px rgba(19, 44, 55, 0.16);
        }

        .bi-page-kicker {
            margin-bottom: 0.5rem;
            color: #7ee6dd;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .bi-page-title {
            margin: 0;
            color: #ffffff;
            font-size: clamp(2rem, 4vw, 3.1rem);
            line-height: 1.08;
            font-weight: 800;
            letter-spacing: 0;
        }

        .bi-page-subtitle {
            max-width: 760px;
            margin: 0.75rem 0 0;
            color: rgba(236, 247, 247, 0.78);
            font-size: 1rem;
            line-height: 1.65;
        }

        .bi-stat-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1.35rem;
        }

        .bi-stat-card {
            padding: 0.9rem 1rem;
            border-radius: 14px;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.13);
        }

        .bi-stat-value {
            color: #ffffff;
            font-size: 1.35rem;
            font-weight: 800;
            line-height: 1;
        }

        .bi-stat-label {
            margin-top: 0.4rem;
            color: rgba(236, 247, 247, 0.72);
            font-size: 0.78rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
            border: 1px solid rgba(22, 54, 68, 0.10);
            box-shadow: 0 16px 34px rgba(19, 44, 55, 0.08);
            background: rgba(255, 255, 255, 0.90);
        }

        .stButton > button,
        .stDownloadButton > button {
            min-height: 2.75rem;
            border-radius: 10px;
            border: 1px solid rgba(15, 127, 119, 0.18);
            background: linear-gradient(135deg, #0b766f 0%, #159b91 70%, #f1ab43 145%);
            color: #ffffff;
            font-weight: 800;
            box-shadow: 0 10px 22px rgba(21, 139, 130, 0.16);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: rgba(15, 127, 119, 0.28);
            background: linear-gradient(135deg, #095f59 0%, #11897f 70%, #dd9634 145%);
            color: #ffffff;
        }

        .stTextInput input,
        .stSelectbox [data-baseweb="select"],
        .stFileUploader section {
            border-radius: 10px;
            border-color: #d8e3e7;
            background: #fbfdfe;
        }

        .stMetric {
            padding: 0.8rem 0.95rem;
            border-radius: 14px;
            background: #ffffff;
            border: 1px solid rgba(22, 54, 68, 0.09);
            box-shadow: 0 10px 24px rgba(19, 44, 55, 0.07);
        }

        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(22, 54, 68, 0.09);
            box-shadow: 0 12px 28px rgba(19, 44, 55, 0.06);
        }

        .streamlit-expanderHeader {
            border-radius: 12px;
            font-weight: 700;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 1.4rem;
            }

            .bi-page-hero {
                padding: 1.25rem;
                border-radius: 16px;
            }

            .bi-stat-strip {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# 渲染统一页面头部，强化模块定位并展示关键上下文
# Render a shared page header to strengthen module identity and key context
def render_page_header(
    title: str,
    subtitle: str,
    *,
    kicker: str = "Lightweight BI System",
    stats: list[tuple[str, str]] | None = None,
) -> None:
    """
    渲染统一的页面头部区域，可选展示三项以内的模块状态指标。
    Render the shared page hero area, optionally showing up to three module status metrics.
    """
    stat_markup = ""
    if stats:
        stat_cards = []
        for value, label in stats[:3]:
            stat_cards.append(
                f'<div class="bi-stat-card"><div class="bi-stat-value">{value}</div>'
                f'<div class="bi-stat-label">{label}</div></div>'
            )
        stat_markup = f'<div class="bi-stat-strip">{"".join(stat_cards)}</div>'

    st.markdown(
        f"""
        <section class="bi-page-hero">
            <div class="bi-page-kicker">{kicker}</div>
            <h1 class="bi-page-title">{title}</h1>
            <p class="bi-page-subtitle">{subtitle}</p>
            {stat_markup}
        </section>
        """,
        unsafe_allow_html=True,
    )


# 渲染统一的空状态提示，避免各页面提示文案和视觉样式分散
# Render a shared empty-state message to keep guidance and visual treatment consistent
def render_empty_state(message: str, detail: str | None = None) -> None:
    """
    渲染一个统一的信息提示，用于尚未导入数据或尚未生成分析结果的场景。
    Render a shared information prompt for states where data or analysis outputs are not ready.
    """
    st.info(message if detail is None else f"{message}\n\n{detail}")
