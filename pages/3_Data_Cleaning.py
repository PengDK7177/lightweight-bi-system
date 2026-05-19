import streamlit as st
from modules.cleaning import (
    remove_duplicates,
    fill_missing,
    standardize_columns,
    standardize_dates,
    standardize_currency,
    mask_pii,
)
from modules.auth import require_login
from modules.ui import inject_bi_theme, render_empty_state, render_page_header


# Halt page rendering for unauthenticated users
require_login(logout_key="logout_data_cleaning")

# 显示页面标题
# Display the page title
inject_bi_theme()

# 从会话状态读取数据集；若不存在则提示用户先前往数据导入页
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    render_empty_state("No dataset in session. Go to Data Import first.")
    st.stop()

# 渲染统一页面头部，并展示清洗前数据集规模
# Render the shared page header and show the pre-cleaning dataset scale
render_page_header(
    "Data Cleaning",
    "Standardise columns, handle missing values, format dates and currency, and mask sensitive fields before analysis.",
    stats=[
        (f"{df.shape[0]:,}", "Rows loaded"),
        (f"{df.shape[1]:,}", "Columns loaded"),
        ("PII", "Masking available"),
    ],
)

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

# 缺失值处理选项（面向非技术用户的可读文案）
# Missing-value options with non-technical, user-friendly labels
missing_value_options = {
    "Auto-detect (recommended)": "auto",
    "Remove rows with missing values": "drop",
    "Replace missing values with 0": "zero",
    "Fill using the previous available value": "ffill",
}

st.subheader("How should we handle missing values?")

# 简单模式 vs 高级模式切换
# Toggle between simple and advanced modes
mode_col1, mode_col2 = st.columns(2)
with mode_col1:
    use_simple_mode = st.checkbox("Simple mode (apply to all columns)", value=True, key="simple_mode_toggle")

# 简单模式：全局策略
# Simple mode: global strategy for all columns
if use_simple_mode:
    selected_option_label = st.selectbox(
        "Choose a strategy for all columns:",
        list(missing_value_options.keys()),
    )
    strategy = missing_value_options[selected_option_label]
    
    # 为每个选项提供简短说明，帮助 SME 用户理解对数据的影响
    # Provide short explanations for each option so SME users understand the data impact
    missing_value_explanations = {
        "Auto-detect (recommended)": "Each column's missing values are handled based on its type: IDs→drop, numbers→zero, dates→ffill, etc.",
        "Remove rows with missing values": "Rows that have any empty cells will be deleted from the dataset.",
        "Replace missing values with 0": "Empty cells will be replaced with 0, useful when 0 is a meaningful value.",
        "Fill using the previous available value": "Each empty cell is filled with the value from the previous row in the same column.",
    }
    st.caption(f"Explanation: {missing_value_explanations[selected_option_label]}")
    
    # 按钮：应用所选策略并将结果存回会话状态
    # Button: apply the chosen strategy and persist the result to session state
    if st.button("Apply Missing Value Strategy"):
        df, info = fill_missing(df, strategy=strategy, return_info=True)
        st.session_state["df"] = df
        st.success(f"Applied: {selected_option_label}")
        
        # 显示处理摘要
        # Show processing summary
        with st.expander("View processing details"):
            for col, details in info["processed_columns"].items():
                status = f"**{col}** → {details['strategy']}"
                if details['missing_count'] > 0:
                    status += f" ({details['action']}, {details['missing_count']} missing values)"
                st.write(status)

# 高级模式：按列指定策略
# Advanced mode: specify strategy per column
else:
    st.info("📋 Select a strategy for each column independently. Columns with no missing values will not be affected.")
    
    # 初始化会话状态中的列策略配置（若未存在）
    # Initialize per-column strategy config in session state (if not already present)
    if "col_strategies" not in st.session_state:
        st.session_state["col_strategies"] = {col: "auto" for col in df.columns}
    
    # 创建两列布局：列名 + 策略选择框
    # Layout: column name | strategy selector
    strategy_labels = {
        "auto": "🤖 Auto-detect",
        "drop": "🗑️ Drop rows with missing",
        "zero": "0️⃣ Fill with zero",
        "ffill": "➡️ Fill with previous value",
    }
    
    # 分组展示列（按列类型猜测进行分组，便于用户理解）
    # Group columns by likely type to help users navigate
    st.write("**Configure strategy for each column:**")
    
    col_strategy_container = st.container()
    with col_strategy_container:
        # 为每个数据列创建选择器
        # Create a selector for each data column
        cols_per_row = 2
        cols = st.columns(cols_per_row)
        
        for idx, col in enumerate(df.columns):
            col_widget = cols[idx % cols_per_row]
            with col_widget:
                missing_in_col = df[col].isna().sum()
                missing_label = f" ({missing_in_col} missing)" if missing_in_col > 0 else " (complete)"
                
                selected = st.selectbox(
                    f"{col}{missing_label}",
                    list(strategy_labels.keys()),
                    format_func=lambda x: strategy_labels[x],
                    key=f"col_strategy_{col}",
                )
                st.session_state["col_strategies"][col] = selected
    
    # 按钮：应用按列的自定义策略
    # Button: apply per-column strategy configuration
    if st.button("Apply Custom Per-Column Strategy"):
        # 使用会话状态中的列策略配置
        # Use the per-column strategy configuration from session state
        df, info = fill_missing(df, strategy=st.session_state["col_strategies"], return_info=True)
        st.session_state["df"] = df
        st.success("✅ Custom strategies applied!")
        
        # 显示详细处理结果
        # Show detailed processing results
        with st.expander("View processing details"):
            processed_summary = []
            for col, details in info["processed_columns"].items():
                action = details.get('action', 'skipped')
                rows_affected = details.get('rows_dropped', 0)
                status_line = f"**{col}** → {details['strategy']} | {action}"
                if rows_affected > 0:
                    status_line += f" (dropped {rows_affected} rows)"
                elif details['missing_count'] > 0:
                    status_line += f" (affected {details['missing_count']} cells)"
                processed_summary.append(status_line)
            
            for line in processed_summary:
                st.write(line)

# 按钮：自动检测日期列并将其格式统一为英国标准格式 DD/MM/YYYY
# Button: auto-detect date columns and reformat them to UK standard DD/MM/YYYY
if st.button("Standardize Dates to UK Format (DD/MM/YYYY)"):
    df, converted_cols = standardize_dates(df)
    st.session_state["df"] = df
    if converted_cols:
        # 列出所有已转换的列名，方便用户确认哪些列受到影响
        # List every converted column so the user can confirm which columns were affected
        st.success(f"Date columns reformatted to DD/MM/YYYY: {', '.join(converted_cols)}")
    else:
        # 未发现可识别的日期列时给予提示
        # Inform the user when no recognisable date columns were found
        st.info("No date columns detected.")

# 按钮：自动检测 GBP 货币列并将其标准化为数值类型（去除 £ 符号及逗号）
# Button: auto-detect GBP currency columns and normalise them to float (strip £ and commas)
if st.button("Standardize GBP Currency Fields"):
    df, converted_cols = standardize_currency(df)
    st.session_state["df"] = df
    if converted_cols:
        # 告知用户哪些列被识别为货币列并完成标准化
        # Inform the user which columns were identified as currency and normalised
        st.success(f"Currency columns normalised to float: {', '.join(converted_cols)}")
    else:
        # 未发现货币列时给予提示
        # Inform the user when no currency columns were detected
        st.info("No GBP currency columns detected.")

# 按钮：自动检测邮箱和手机号列并进行脱敏（NFR4 隐私保护）
# Button: auto-detect and mask email / phone columns to protect PII (NFR4 privacy requirement)
if st.button("Mask PII (Email & Phone)"):
    df, masked_cols = mask_pii(df)
    st.session_state["df"] = df
    if masked_cols:
        # 列出已脱敏的列，让用户确认敏感数据已被处理
        # List the masked columns so the user can confirm sensitive data has been handled
        st.success(f"PII masked — affected columns: {', '.join(masked_cols)}")
        # 标记会话状态，供 Dashboard 等页面展示脱敏提醒（NFR4 验证）
        # Set a session flag so Dashboard and export pages can display a masking notice (NFR4 verification)
        st.session_state["pii_masked"] = True
    else:
        # 未发现 PII 列时给予提示
        # Inform the user when no PII columns were found
        st.info("No email or phone columns detected.")

# 预览清洗后数据集的前 30 行，让用户即时确认效果
# Preview the first 30 rows of the cleaned dataset so the user can verify the result immediately
st.dataframe(st.session_state["df"].head(30), use_container_width=True)
