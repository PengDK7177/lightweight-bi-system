import streamlit as st
from modules.cleaning import (
    remove_duplicates,
    fill_missing,
    standardize_columns,
    standardize_categorical_values,
    standardize_dates,
    standardize_currency,
    mask_pii,
)
from modules.auth import require_login
from modules.ui import inject_bi_theme, render_empty_state, render_page_header


# Halt page rendering for unauthenticated users
require_login(logout_key="logout_data_cleaning")

# 鏄剧ず椤甸潰鏍囬
# Display the page title
inject_bi_theme()

# 浠庝細璇濈姸鎬佽鍙栨暟鎹泦锛涜嫢涓嶅瓨鍦ㄥ垯鎻愮ず鐢ㄦ埛鍏堝墠寰€鏁版嵁瀵煎叆椤?
# Read the dataset from session state; prompt the user to import data first if absent
df = st.session_state.get("df")
if df is None:
    render_empty_state("No dataset in session. Go to Data Import first.")
    st.stop()

# 娓叉煋缁熶竴椤甸潰澶撮儴锛屽苟灞曠ず娓呮礂鍓嶆暟鎹泦瑙勬ā
# Render the shared page header and show the pre-cleaning dataset scale
render_page_header(
    "Data Cleaning",
    "Standardise columns, clean categorical values, handle missing values, format dates and currency, and mask sensitive fields before analysis.",
    stats=[
        (f"{df.shape[0]:,}", "Rows loaded"),
        (f"{df.shape[1]:,}", "Columns loaded"),
        ("PII", "Masking available"),
    ],
)

# 鏄剧ず褰撳墠鏁版嵁闆嗙殑琛屽垪鏁帮紝渚夸簬瀵规瘮娓呮礂鍓嶅悗鐨勫彉鍖?
# Show the current shape so users can compare before and after cleaning
st.write("Current shape:", df.shape)

# 鎸夐挳锛氬皢鍒楀悕鏍囧噯鍖栦负灏忓啓 snake_case锛岃鑼冨寲鍚庢湁鍔╀簬鍚庣画鍖归厤鍜岃浆鎹㈡搷浣?
# Button: normalise column names to lowercase snake_case to improve downstream matching
if st.button("Standardize Column Names"):
    df = standardize_columns(df)
    # 灏嗘爣鍑嗗寲鍚庣殑 DataFrame 鍐欏洖浼氳瘽鐘舵€侊紝浣垮叾瀵规墍鏈夐〉闈㈠彲瑙?
    # Write the standardised DataFrame back to session state so all pages see the update
    st.session_state["df"] = df
    st.success("Column names standardized.")

# 鎸夐挳锛氭鏌ュ垎绫诲瓧娈靛苟缁熶竴寮傚父绫诲埆銆佸ぇ灏忓啓鍜岄偖缂栨牸寮忋€?# Button: inspect categorical fields and standardise dirty categories, casing, and postcode formats.
if st.button("Standardize Categorical Values"):
    df, category_report = standardize_categorical_values(df)
    st.session_state["df"] = df
    processed = category_report.get("processed_columns", {})
    if processed:
        st.success(f"Categorical values standardized in {len(processed)} column(s).")
        with st.expander("View categorical cleaning details"):
            for col, details in processed.items():
                st.write(f"**{col}** -> {details['action']} ({details['changed_cells']} changed cells)")
                st.caption(f"Categories after cleaning: {', '.join(details['categories_after'])}")
    else:
        st.info("No categorical inconsistencies or invalid postal values were detected.")

# 鎸夐挳锛氬垹闄ら噸澶嶈锛屽苟灞曠ず鍒犻櫎浜嗗灏戣
# Button: remove duplicate rows and report how many were dropped
if st.button("Remove Duplicates"):
    before = len(df)
    df = remove_duplicates(df)
    st.session_state["df"] = df
    st.success(f"Removed {before - len(df)} duplicate rows.")

# 缂哄け鍊煎鐞嗛€夐」锛堥潰鍚戦潪鎶€鏈敤鎴风殑鍙鏂囨锛?
# Missing-value options with non-technical, user-friendly labels
missing_value_options = {
    "Auto-detect (recommended)": "auto",
    "Remove rows with missing values": "drop",
    "Replace missing values with 0": "zero",
    "Fill using the previous available value": "ffill",
}

st.subheader("How should we handle missing values?")

# 绠€鍗曟ā寮?vs 楂樼骇妯″紡鍒囨崲
# Toggle between simple and advanced modes
mode_col1, mode_col2 = st.columns(2)
with mode_col1:
    use_simple_mode = st.checkbox("Simple mode (apply to all columns)", value=True, key="simple_mode_toggle")

# 绠€鍗曟ā寮忥細鍏ㄥ眬绛栫暐
# Simple mode: global strategy for all columns
if use_simple_mode:
    selected_option_label = st.selectbox(
        "Choose a strategy for all columns:",
        list(missing_value_options.keys()),
    )
    strategy = missing_value_options[selected_option_label]
    
    # 涓烘瘡涓€夐」鎻愪緵绠€鐭鏄庯紝甯姪 SME 鐢ㄦ埛鐞嗚В瀵规暟鎹殑褰卞搷
    # Provide short explanations for each option so SME users understand the data impact
    missing_value_explanations = {
        "Auto-detect (recommended)": "Each column's missing values are handled based on its type: IDs -> drop, numbers -> zero, dates -> fill previous value, etc.",
        "Remove rows with missing values": "Rows that have any empty cells will be deleted from the dataset.",
        "Replace missing values with 0": "Empty cells will be replaced with 0, useful when 0 is a meaningful value.",
        "Fill using the previous available value": "Each empty cell is filled with the value from the previous row in the same column.",
    }
    st.caption(f"Explanation: {missing_value_explanations[selected_option_label]}")
    # 鎻愰啋鐢ㄦ埛锛氬垎绫绘竻娲椾骇鐢熺殑 Missing 鏍囩涔熶細鍦ㄨ繖閲岀户缁綔涓虹己澶卞€煎鐞嗐€?    # Tell users that Missing labels created by categorical cleaning are still handled as missing values here.
    st.caption("Cells labelled as Missing by categorical cleaning are treated as missing values here.")
    
    # 鎸夐挳锛氬簲鐢ㄦ墍閫夌瓥鐣ュ苟灏嗙粨鏋滃瓨鍥炰細璇濈姸鎬?
    # Button: apply the chosen strategy and persist the result to session state
    if st.button("Apply Missing Value Strategy"):
        df, info = fill_missing(df, strategy=strategy, return_info=True)
        st.session_state["df"] = df
        st.success(f"Applied: {selected_option_label}")
        
        # 鏄剧ず澶勭悊鎽樿
        # Show processing summary
        with st.expander("View processing details"):
            for col, details in info["processed_columns"].items():
                status = f"**{col}** -> {details['strategy']}"
                if details['missing_count'] > 0:
                    status += f" ({details['action']}, {details['missing_count']} missing values)"
                st.write(status)

# 楂樼骇妯″紡锛氭寜鍒楁寚瀹氱瓥鐣?
# Advanced mode: specify strategy per column
else:
    st.info("Select a strategy for each column independently. Columns with no missing values will not be affected.")
    
    # 鍒濆鍖栦細璇濈姸鎬佷腑鐨勫垪绛栫暐閰嶇疆锛堣嫢鏈瓨鍦級
    # Initialize per-column strategy config in session state (if not already present)
    if "col_strategies" not in st.session_state:
        st.session_state["col_strategies"] = {col: "auto" for col in df.columns}
    
    # 鍒涘缓涓ゅ垪甯冨眬锛氬垪鍚?+ 绛栫暐閫夋嫨妗?
    # Layout: column name | strategy selector
    strategy_labels = {
        "auto": "Auto-detect",
        "drop": "Drop rows with missing",
        "zero": "Fill with zero",
        "ffill": "Fill with previous value",
    }
    
    # 鍒嗙粍灞曠ず鍒楋紙鎸夊垪绫诲瀷鐚滄祴杩涜鍒嗙粍锛屼究浜庣敤鎴风悊瑙ｏ級
    # Group columns by likely type to help users navigate
    st.write("**Configure strategy for each column:**")
    
    col_strategy_container = st.container()
    with col_strategy_container:
        # 涓烘瘡涓暟鎹垪鍒涘缓閫夋嫨鍣?
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
    
    # 鎸夐挳锛氬簲鐢ㄦ寜鍒楃殑鑷畾涔夌瓥鐣?
    # Button: apply per-column strategy configuration
    if st.button("Apply Custom Per-Column Strategy"):
        # 浣跨敤浼氳瘽鐘舵€佷腑鐨勫垪绛栫暐閰嶇疆
        # Use the per-column strategy configuration from session state
        df, info = fill_missing(df, strategy=st.session_state["col_strategies"], return_info=True)
        st.session_state["df"] = df
        st.success("Custom strategies applied.")
        
        # 鏄剧ず璇︾粏澶勭悊缁撴灉
        # Show detailed processing results
        with st.expander("View processing details"):
            processed_summary = []
            for col, details in info["processed_columns"].items():
                action = details.get('action', 'skipped')
                rows_affected = details.get('rows_dropped', 0)
                status_line = f"**{col}** -> {details['strategy']} | {action}"
                if rows_affected > 0:
                    status_line += f" (dropped {rows_affected} rows)"
                elif details['missing_count'] > 0:
                    status_line += f" (affected {details['missing_count']} cells)"
                processed_summary.append(status_line)
            
            for line in processed_summary:
                st.write(line)

# 鎸夐挳锛氳嚜鍔ㄦ娴嬫棩鏈熷垪骞跺皢鍏舵牸寮忕粺涓€涓鸿嫳鍥芥爣鍑嗘牸寮?DD/MM/YYYY
# Button: auto-detect date columns and reformat them to UK standard DD/MM/YYYY
if st.button("Standardize Dates to UK Format (DD/MM/YYYY)"):
    df, converted_cols = standardize_dates(df)
    st.session_state["df"] = df
    if converted_cols:
        # 鍒楀嚭鎵€鏈夊凡杞崲鐨勫垪鍚嶏紝鏂逛究鐢ㄦ埛纭鍝簺鍒楀彈鍒板奖鍝?
        # List every converted column so the user can confirm which columns were affected
        st.success(f"Date columns reformatted to DD/MM/YYYY: {', '.join(converted_cols)}")
    else:
        # 鏈彂鐜板彲璇嗗埆鐨勬棩鏈熷垪鏃剁粰浜堟彁绀?
        # Inform the user when no recognisable date columns were found
        st.info("No date columns detected.")

# 鎸夐挳锛氳嚜鍔ㄦ娴?GBP 璐у竵鍒楀苟灏嗗叾鏍囧噯鍖栦负鏁板€肩被鍨嬶紙鍘婚櫎 拢 绗﹀彿鍙婇€楀彿锛?
# Button: auto-detect GBP currency columns and normalise them to float (strip 拢 and commas)
if st.button("Standardize GBP Currency & Rate Fields"):
    df, converted_cols = standardize_currency(df)
    st.session_state["df"] = df
    if converted_cols:
        # 鍛婄煡鐢ㄦ埛鍝簺鍒楄璇嗗埆涓鸿揣甯佸垪骞跺畬鎴愭爣鍑嗗寲
        # Inform the user which columns were identified as amount/rate fields and normalised
        st.success(f"Amount/rate columns normalised to numeric values: {', '.join(converted_cols)}")
    else:
        # 鏈彂鐜拌揣甯佸垪鏃剁粰浜堟彁绀?
        # Inform the user when no amount or rate columns were detected
        st.info("No GBP amount or rate columns detected.")

# 鎸夐挳锛氳嚜鍔ㄦ娴嬮偖绠卞拰鎵嬫満鍙峰垪骞惰繘琛岃劚鏁忥紙NFR4 闅愮淇濇姢锛?
# Button: auto-detect and mask email / phone columns to protect PII (NFR4 privacy requirement)
if st.button("Mask PII (Email & Phone)"):
    df, masked_cols = mask_pii(df)
    st.session_state["df"] = df
    if masked_cols:
        # 鍒楀嚭宸茶劚鏁忕殑鍒楋紝璁╃敤鎴风‘璁ゆ晱鎰熸暟鎹凡琚鐞?
        # List the masked columns so the user can confirm sensitive data has been handled
        st.success(f"PII masked 鈥?affected columns: {', '.join(masked_cols)}")
        # 鏍囪浼氳瘽鐘舵€侊紝渚?Dashboard 绛夐〉闈㈠睍绀鸿劚鏁忔彁閱掞紙NFR4 楠岃瘉锛?
        # Set a session flag so Dashboard and export pages can display a masking notice (NFR4 verification)
        st.session_state["pii_masked"] = True
    else:
        # 鏈彂鐜?PII 鍒楁椂缁欎簣鎻愮ず
        # Inform the user when no PII columns were found
        st.info("No email or phone columns detected.")

# 棰勮娓呮礂鍚庢暟鎹泦鐨勫墠 30 琛岋紝璁╃敤鎴峰嵆鏃剁‘璁ゆ晥鏋?
# Preview the first 30 rows of the cleaned dataset so the user can verify the result immediately
st.dataframe(st.session_state["df"].head(30), use_container_width=True)
