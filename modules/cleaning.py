# 引入 pandas 库，用于数据处理与转换操作
# Import pandas for data cleaning and transformation operations
import pandas as pd

# 引入 re 模块，用于正则表达式匹配（邮箱、手机号检测与脱敏）
# Import re for regular expression matching used in PII detection and masking
import re

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


# ---------------------------------------------------------------------------
# GBP 货币字段标准化
# GBP currency field standardisation
# ---------------------------------------------------------------------------

# 列名关键词列表：含这些词的列被视为潜在货币列
# Column name keywords that suggest a column may contain monetary values
_CURRENCY_NAME_HINTS = {
    "price", "amount", "cost", "revenue", "total", "fee",
    "gbp", "value", "sales", "income", "profit", "turnover",
    "balance", "payment", "charge", "salary", "wage",
}


def standardize_currency(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    自动检测 GBP 货币列并将其标准化为 Python float 类型。
    Auto-detect GBP currency columns and normalise them to Python float.

    检测规则 / Detection rules:
    - 列名包含货币相关关键词（price、amount、cost 等），或
      Column name contains a currency-related keyword (price, amount, cost …), OR
    - 列中超过 50% 的非空字符串值包含 £ 符号。
      More than 50% of non-null string values in the column contain the £ symbol.

    处理方式 / Processing:
    - 去除 £、逗号、空格等符号，转换为 float；无法转换的值变为 NaN。
      Strip £, commas, and spaces then cast to float; values that cannot be converted become NaN.

    返回 / Returns:
        (transformed_df, list_of_converted_column_names)
    """
    # 若 DataFrame 为空则直接返回
    # Return early when the DataFrame is None or empty
    if df is None or df.empty:
        return df, []

    # 复制，保持原始数据不变
    # Copy to avoid mutating the caller's data
    out = df.copy()
    converted: list[str] = []

    for col in out.columns:
        # ---- 判断是否为货币列 ----
        # ---- Decide whether this column holds currency values ----

        # 规则 1：列名含货币关键词
        # Rule 1: column name contains a currency keyword
        name_match = any(hint in col.lower() for hint in _CURRENCY_NAME_HINTS)

        # 规则 2：列值中超过 50% 含 £ 符号（仅对 object 类型列检查）
        # Rule 2: more than 50% of non-null values contain £ (only checked for object columns)
        value_match = False
        if out[col].dtype == object:
            non_null = out[col].dropna()
            if len(non_null) > 0:
                gbp_count = non_null.astype(str).str.contains("£", regex=False).sum()
                value_match = (gbp_count / len(non_null)) > 0.5

        if not (name_match or value_match):
            # 不符合任何规则，跳过
            # Skip columns that match neither rule
            continue

        # ---- 已是数值类型则直接记录，无需再清洗 ----
        # ---- Already numeric — just record it, no cleaning needed ----
        if pd.api.types.is_numeric_dtype(out[col]):
            converted.append(col)
            continue

        # ---- 清洗：去除 £、逗号、空格，再转为 float ----
        # ---- Clean: strip £, commas, and spaces, then cast to float ----
        cleaned = (
            out[col]
            .astype(str)
            .str.replace("£", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")

        # 仅当至少一半非空值成功转换时才接受，防止误处理普通文本列
        # Only accept the conversion if at least half of non-null values parsed successfully
        non_null_count = out[col].notna().sum()
        if non_null_count > 0 and (numeric.notna().sum() / non_null_count) >= 0.5:
            out[col] = numeric
            converted.append(col)

    return out, converted


# ---------------------------------------------------------------------------
# 邮箱与手机号脱敏
# Email and phone number masking (PII)
# ---------------------------------------------------------------------------

# 匹配标准邮箱地址的正则表达式
# Regex pattern for standard email addresses
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# 匹配英国及常见国际手机号的正则表达式（允许空格、连字符、括号、+44 前缀等）
# Regex for UK and common international phone numbers (spaces, hyphens, brackets, +44 prefix allowed)
_PHONE_RE = re.compile(
    r"^(\+?\d[\d\s\-().]{6,}\d)$"
)


def _mask_email(value: str) -> str:
    """
    对单个邮箱地址进行脱敏：保留首字母，其余本地部分替换为 ***。
    Mask a single email address: keep the first character, replace the rest of the local part with ***.
    例 / e.g.: john.doe@example.com → j***@example.com
    """
    # 分离本地部分与域名部分
    # Split into local part and domain
    local, domain = value.split("@", 1)
    # 保留首字符，其余替换为 ***
    # Keep the first character only; replace the rest with ***
    masked_local = local[0] + "***" if local else "***"
    return f"{masked_local}@{domain}"


def _mask_phone(value: str) -> str:
    """
    对单个手机号进行脱敏：保留末尾 4 位数字，其余数字替换为 *。
    Mask a single phone number: keep the last 4 digits, replace all other digits with *.
    例 / e.g.: 07911 123456 → ***** **3456
    """
    digits = re.findall(r"\d", value)
    if len(digits) < 4:
        # 数字不足 4 位时全部掩盖
        # Mask entirely if fewer than 4 digits are present
        return re.sub(r"\d", "*", value)

    # 计算需要保留的末尾 4 位在原字符串中的起始位置
    # Locate where the last-4-digits section begins in the original string
    keep_from = len(digits) - 4
    digit_idx = 0
    result = []
    for ch in value:
        if ch.isdigit():
            # 前 (n-4) 个数字替换为 *，最后 4 个保留
            # Replace the first (n-4) digits with *, keep the last 4
            result.append("*" if digit_idx < keep_from else ch)
            digit_idx += 1
        else:
            # 非数字字符（空格、连字符等）原样保留
            # Non-digit characters (spaces, hyphens, etc.) are kept as-is
            result.append(ch)
    return "".join(result)


def mask_pii(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    自动检测 DataFrame 中的邮箱和手机号列，并对其进行脱敏处理。
    Auto-detect email and phone number columns in the DataFrame and mask them in-place.

    检测规则 / Detection rules:
    - 对 object 类型列取前 100 个非空样本，若 ≥ 50% 匹配邮箱或手机号正则，则视为 PII 列。
      Sample up to 100 non-null values from each object column; treat it as PII if ≥ 50% match.

    脱敏方式 / Masking:
    - 邮箱：j***@example.com
      Email: j***@example.com
    - 手机号：末尾 4 位保留，其余数字替换为 *
      Phone: last 4 digits retained, all other digits replaced with *

    返回 / Returns:
        (masked_df, list_of_masked_column_names)
    """
    # 若 DataFrame 为空则直接返回
    # Return early when the DataFrame is None or empty
    if df is None or df.empty:
        return df, []

    # 复制，保持原始数据不变
    # Copy to avoid mutating the caller's data
    out = df.copy()
    masked_cols: list[str] = []

    for col in out.columns:
        # 仅处理 object 类型列，数值列不含 PII
        # Only process object columns; numeric columns cannot contain PII
        if out[col].dtype != object:
            continue

        # 取前 100 个非空样本进行检测
        # Sample up to 100 non-null values for detection
        sample = out[col].dropna().head(100).astype(str)
        if len(sample) == 0:
            continue

        # 统计样本中匹配邮箱 / 手机号正则的比例
        # Count how many sample values match the email / phone regex
        email_hits = sample.apply(lambda v: bool(_EMAIL_RE.match(v.strip()))).sum()
        phone_hits = sample.apply(lambda v: bool(_PHONE_RE.match(v.strip()))).sum()
        ratio = len(sample)

        if email_hits / ratio >= 0.5:
            # 识别为邮箱列：对每个非空值应用邮箱脱敏函数
            # Identified as an email column — apply the email masking function to each non-null value
            out[col] = out[col].apply(
                lambda v: _mask_email(str(v).strip()) if pd.notna(v) and _EMAIL_RE.match(str(v).strip()) else v
            )
            masked_cols.append(f"{col} (email)")

        elif phone_hits / ratio >= 0.5:
            # 识别为手机号列：对每个非空值应用手机号脱敏函数
            # Identified as a phone column — apply the phone masking function to each non-null value
            out[col] = out[col].apply(
                lambda v: _mask_phone(str(v).strip()) if pd.notna(v) and _PHONE_RE.match(str(v).strip()) else v
            )
            masked_cols.append(f"{col} (phone)")

    return out, masked_cols