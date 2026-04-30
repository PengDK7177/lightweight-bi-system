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

# 缺失值处理选项（面向非技术用户的可读文案）
# Missing-value options with non-technical, user-friendly labels
missing_value_options = {
    "Remove rows with missing values": "drop",
    "Replace missing values with 0": "zero",
    "Fill using the previous available value": "ffill",
}

# 下拉框展示易懂文案；内部仍映射到原有策略代码，保证后端逻辑不变
# Show friendly labels in the selectbox while mapping to existing strategy codes internally
selected_option_label = st.selectbox(
    "How should we handle missing values?",
    list(missing_value_options.keys()),
)
strategy = missing_value_options[selected_option_label]

# 为每个选项提供简短说明，帮助 SME 用户理解对数据的影响
# Provide short explanations for each option so SME users understand the data impact
missing_value_explanations = {
    "Remove rows with missing values": "Rows that have any empty cells will be deleted from the dataset. / 包含空白单元格的整行会被删除。",
    "Replace missing values with 0": "Empty cells will be replaced with 0, useful when 0 is a meaningful value. / 空白单元格会替换为 0，适用于 0 有业务含义的场景。",
    "Fill using the previous available value": "Each empty cell is filled with the value from the previous row in the same column. / 每个空白单元格会用同一列上一行的值进行填充。",
}
st.caption(f"Explanation: {missing_value_explanations[selected_option_label]}")

# 按钮：应用所选策略并将结果存回会话状态
# Button: apply the chosen strategy and persist the result to session state
if st.button("Apply Missing Value Strategy"):
    df = fill_missing(df, strategy=strategy)
    st.session_state["df"] = df
    st.success(f"Applied: {selected_option_label}")

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