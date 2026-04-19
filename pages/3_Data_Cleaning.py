import streamlit as st
import pandas as pd
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

# 读取已识别的货币列（用于预览时显示 £ 格式，不影响底层数值）
# Read recognised currency columns (used to show £ in preview only, without changing raw numeric values)
currency_cols = st.session_state.get("currency_cols", [])

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
        # 记录货币列供表格预览使用，显示为 £x,xxx.xx
        # Store currency columns for preview formatting as £x,xxx.xx
        st.session_state["currency_cols"] = converted_cols
        currency_cols = converted_cols
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

# 预览清洗后数据：若识别到货币列，则仅在显示层添加 £ 格式（不修改底层 DataFrame）
# Preview cleaned data: if currency columns exist, apply £ formatting at display layer only
preview_df = st.session_state["df"].head(30)
if currency_cols:
    # 仅对当前仍存在且为数值类型的列应用 GBP 样式
    # Apply GBP style only to existing columns that are numeric
    fmt = {
        c: (lambda v: f"£{v:,.2f}" if pd.notna(v) else "")
        for c in currency_cols
        if c in preview_df.columns and pd.api.types.is_numeric_dtype(preview_df[c])
    }
    if fmt:
        st.dataframe(preview_df.style.format(fmt), use_container_width=True)
    else:
        st.dataframe(preview_df, use_container_width=True)
else:
    st.dataframe(preview_df, use_container_width=True)