import pandas as pd


def remove_duplicates(df: pd.DataFrame, subset=None) -> pd.DataFrame:
    """
    删除 DataFrame 中的重复行并重置索引。
    Remove duplicate rows from the DataFrame and reset the index.
    """
    # 若 DataFrame 为空则直接返回，避免对空数据执行无意义操作
    # Return early if the DataFrame is None or empty to avoid operating on empty data
    if df is None or df.empty:
        return df

    # 根据指定列（或全部列）去重，并重置行索引以保持连续性
    # Drop duplicate rows based on the given subset of columns (or all columns if None), then reset the index
    return df.drop_duplicates(subset=subset).reset_index(drop=True)


def fill_missing(df: pd.DataFrame, strategy: str = "drop") -> pd.DataFrame:
    """
    使用指定策略处理缺失值，支持 drop（删除）、zero（填零）、ffill（前向填充）三种方式。
    Handle missing values using one of three strategies: drop, zero, or ffill (forward-fill).
    """
    # 若 DataFrame 为空则直接返回，无需处理
    # Return early if the DataFrame is None or empty
    if df is None or df.empty:
        return df

    # Strategy 'drop': remove any row that contains at least one missing value, then reset the index
    if strategy == "drop":
        return df.dropna().reset_index(drop=True)

    # Strategy 'zero': replace all missing values with 0, suitable for numeric data
    if strategy == "zero":
        return df.fillna(0)

    # Strategy 'ffill': forward-fill with the previous row's value, then back-fill to cover leading NaNs
    if strategy == "ffill":
        return df.ffill().bfill()

    
    return df


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    将列名统一规范化为小写 snake_case 格式，去除首尾空白并用下划线替换空格。
    Normalise column names to lowercase snake_case: strip whitespace and replace spaces with underscores.
    """
    # 若 DataFrame 为空则直接返回
    # Return early if the DataFrame is None or empty
    if df is None or df.empty:
        return df

    # 复制 DataFrame 以避免修改原始数据
    # Copy the DataFrame to avoid mutating the caller's data
    out = df.copy()

    # 对每个列名：转为字符串 → 去首尾空格 → 转小写 → 空格替换为下划线
    # For each column name: cast to str → strip whitespace → lowercase → replace spaces with underscores
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def standardize_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    自动检测 DataFrame 中的日期列，并将其格式统一为英国标准格式 DD/MM/YYYY（字符串类型）。
    Auto-detect date columns in the DataFrame and reformat them to the UK standard DD/MM/YYYY (as strings).

    检测规则 / Detection rules:
    - 已为 datetime64 类型的列直接格式化。
      Columns already typed as datetime64 are formatted directly.
    - object/string 类型的列尝试用 pandas 解析；解析失败的列保持不变。
      Object/string columns are parsed with pandas; columns that fail to parse are left unchanged.

    返回 / Returns:
        (transformed_df, list_of_converted_column_names)
        转换后的 DataFrame 副本，以及成功转换的列名列表（用于 UI 反馈）。
        A copy of the transformed DataFrame and a list of column names that were converted (for UI feedback).
    """
    # 若 DataFrame 为空则直接返回，并附带空列表表示无列被转换
    # Return early with an empty list when the DataFrame is None or empty
    if df is None or df.empty:
        return df, []

    # 复制 DataFrame，保持原始数据不变
    # Copy the DataFrame to avoid mutating the caller's data
    out = df.copy()

    # 记录成功转换的列名，供调用方在 UI 中展示反馈信息
    # Track converted column names so the caller can display feedback in the UI
    converted: list[str] = []

    for col in out.columns:
        # 情况 1：列已是 datetime 类型，直接格式化为 DD/MM/YYYY 字符串
        # Case 1: column is already a datetime dtype — format directly to DD/MM/YYYY string
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%d/%m/%Y")
            converted.append(col)
            continue

        # 情况 2：object 或 string 类型列，尝试解析为 datetime，成功则格式化
        # Case 2: object/string column — attempt to parse as datetime; format if successful
        if out[col].dtype == object:
            # 取前 50 个非空样本进行快速嗅探，避免对大列做全量解析尝试
            # Sample up to 50 non-null values for a quick sniff to avoid full-column parse attempts
            sample = out[col].dropna().head(50)
            try:
                # infer_datetime_format 加速解析；errors='raise' 确保解析失败时跳过该列
                # infer_datetime_format speeds up parsing; errors='raise' ensures we skip on failure
                parsed_sample = pd.to_datetime(sample, infer_datetime_format=True, errors="raise")
                # 样本全部解析成功后，对整列进行转换（失败值变为 NaT，再还原为空字符串）
                # If the full sample parses successfully, convert the entire column (NaT becomes empty string)
                parsed = pd.to_datetime(out[col], infer_datetime_format=True, errors="coerce")
                # 仅当至少一半的非空值被成功解析时才视为日期列，防止误判普通文本列
                # Only treat the column as a date column if at least half of non-null values parsed successfully
                non_null = out[col].notna().sum()
                if non_null > 0 and (parsed.notna().sum() / non_null) >= 0.5:
                    out[col] = parsed.dt.strftime("%d/%m/%Y").fillna("")
                    converted.append(col)
            except (ValueError, TypeError):
                # 解析失败，跳过该列，保持原始内容不变
                # Parsing failed — skip this column and leave its content unchanged
                pass

    return out, converted