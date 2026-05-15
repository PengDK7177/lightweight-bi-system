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


def _detect_column_type(col_name: str, col_series: pd.Series) -> str:
    """
    根据列名和数据特征自动检测列的类型，用于判断最合适的缺失值处理策略。
    Auto-detect column type based on name and data characteristics to choose optimal missing-value strategy.
    
    返回值 / Returns:
        - "countable": 计数类列（销量、订单数等）→ 建议 zero
        - "financial": 财务数据（收入、成本等）→ 建议 drop/mark
        - "date": 日期列 → 建议 ffill/drop
        - "categorical": 分类列 → 建议 ffill/mode
        - "id": ID列 → 建议 drop
        - "other": 其他 → 默认 drop
    """
    col_lower = col_name.lower()
    
    # 规则 1：根据列名关键词识别
    # Rule 1: Detect by column name keywords
    countable_hints = {"quantity", "count", "num", "amount_count", "order_count", "sale_count", "total_items"}
    financial_hints = {"price", "revenue", "cost", "fee", "salary", "income", "payment", "balance", "profit"}
    date_hints = {"date", "time", "datetime", "timestamp", "created", "updated", "start", "end"}
    id_hints = {"id", "identifier", "code"}
    categorical_hints = {"category", "type", "status", "name", "country", "city", "region"}
    
    if any(hint in col_lower for hint in id_hints):
        return "id"
    if any(hint in col_lower for hint in date_hints):
        return "date"
    if any(hint in col_lower for hint in countable_hints):
        return "countable"
    if any(hint in col_lower for hint in financial_hints):
        return "financial"
    if any(hint in col_lower for hint in categorical_hints):
        return "categorical"
    
    # 规则 2：根据数据类型推断
    # Rule 2: Infer from data type
    if pd.api.types.is_integer_dtype(col_series):
        return "countable"  # 整数通常是计数
    if pd.api.types.is_float_dtype(col_series):
        return "financial"  # 浮点数倾向于财务数据
    if pd.api.types.is_datetime64_any_dtype(col_series):
        return "date"
    if pd.api.types.is_object_dtype(col_series) or pd.api.types.is_string_dtype(col_series):
        return "categorical"
    
    return "other"


def fill_missing(
    df: pd.DataFrame,
    strategy: str | dict = "auto",
    return_info: bool = False
) -> pd.DataFrame | tuple[pd.DataFrame, dict]:
    """
    处理缺失值，支持按列指定不同的策略，或使用自动检测。
    Handle missing values with per-column strategies or auto-detection.
    
    参数 / Args:
        df: 输入 DataFrame
        strategy: 处理策略，可以是：
            - "auto": 自动根据列类型检测（推荐）
            - "drop": 删除含缺失值的行（全局）
            - "zero": 填零（全局，仅数值列）
            - "ffill": 前向填充（全局）
            - 字典格式：{"col1": "zero", "col2": "drop", "col3": "ffill"}
              Per-column strategies: {"col1": "zero", "col2": "drop", "col3": "ffill"}
        return_info: 若为 True，返回 (df, 处理信息字典)；否则只返回 df
    
    返回 / Returns:
        - 若 return_info=False：处理后的 DataFrame
        - 若 return_info=True：(处理后的 DataFrame, 处理信息字典)
        
    处理规则 / Rules:
        Auto 模式：
        - ID列: drop（无ID的行无效）
        - 日期列: ffill 然后 bfill
        - 计数类: zero（缺失 = 无该项）
        - 财务数据: drop（不应假设为0）
        - 分类: ffill → bfill（重复前值）
        - 其他: drop（保守方案）
    """
    # 若 DataFrame 为空则直接返回
    if df is None or df.empty:
        if return_info:
            return df, {"status": "empty", "processed_columns": {}}
        return df
    
    out = df.copy()
    process_info = {}
    
    # 统一化 strategy 参数为字典形式 {col: strategy}
    # Normalize strategy parameter to per-column dict format
    if isinstance(strategy, dict):
        col_strategies = strategy
    elif strategy == "auto":
        # 自动检测每列的最佳策略
        col_strategies = {}
        for col in out.columns:
            col_type = _detect_column_type(col, out[col])
            if col_type == "id":
                col_strategies[col] = "drop"
            elif col_type == "date":
                col_strategies[col] = "ffill"
            elif col_type == "countable":
                col_strategies[col] = "zero"
            elif col_type == "financial":
                col_strategies[col] = "drop"
            elif col_type == "categorical":
                col_strategies[col] = "ffill"
            else:
                col_strategies[col] = "drop"
    else:
        # 简单字符串策略应用到全部列
        col_strategies = {col: strategy for col in out.columns}
    
    # 处理每一列
    # Process each column with its assigned strategy
    for col in out.columns:
        col_strategy = col_strategies.get(col, "drop")  # 默认 drop
        missing_count = out[col].isna().sum()
        process_info[col] = {
            "strategy": col_strategy,
            "missing_count": int(missing_count),
            "missing_ratio": float(missing_count / len(out)) if len(out) > 0 else 0.0,
        }
        
        # 无缺失值则跳过
        # Skip if no missing values
        if missing_count == 0:
            continue
        
        if col_strategy == "drop":
            # 删除该列的缺失行（仅限该列）
            # Drop rows where this column is missing
            out = out.dropna(subset=[col]).reset_index(drop=True)
            process_info[col]["action"] = "dropped_rows"
            process_info[col]["rows_dropped"] = int(missing_count)
        
        elif col_strategy == "zero":
            # 仅对数值列填零
            # Fill with zero (only for numeric columns)
            if pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].fillna(0)
                process_info[col]["action"] = "filled_zero"
            else:
                # 非数值列无法填零，改为 drop
                out = out.dropna(subset=[col]).reset_index(drop=True)
                process_info[col]["action"] = "non_numeric_dropped"
                process_info[col]["rows_dropped"] = int(missing_count)
        
        elif col_strategy == "ffill":
            # 前向填充 + 后向填充
            # Forward-fill then back-fill (avoid deprecated fillna(method=...))
            out[col] = out[col].ffill().bfill()
            remaining_na = out[col].isna().sum()
            process_info[col]["action"] = "filled_ffill_bfill"
            process_info[col]["remaining_na"] = int(remaining_na)
    
    if return_info:
        return out, {"processed_columns": process_info}
    return out


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

    def _best_date_parse(series: pd.Series) -> tuple[pd.Series, float]:
        """
        尝试多种日期解析策略，返回成功率最高的解析结果。
        Try multiple date parsing strategies and return the parsed series with the highest success ratio.
        """
        # 候选解析策略：优先显式格式，最后兜底自动推断
        # Candidate parsing strategies: explicit formats first, then generic inference
        candidates = [
            pd.to_datetime(series, errors="coerce", format="%Y-%m-%d"),
            pd.to_datetime(series, errors="coerce", format="%d/%m/%Y"),
            pd.to_datetime(series, errors="coerce", format="%d-%m-%Y"),
            pd.to_datetime(series, errors="coerce", dayfirst=True),
            pd.to_datetime(series, errors="coerce", dayfirst=False),
        ]

        best = candidates[0]
        best_ratio = (best.notna().sum() / len(series)) if len(series) > 0 else 0.0
        for parsed in candidates[1:]:
            ratio = (parsed.notna().sum() / len(series)) if len(series) > 0 else 0.0
            if ratio > best_ratio:
                best = parsed
                best_ratio = ratio
        return best, best_ratio

    for col in out.columns:
        # 情况 1：列已是 datetime 类型，直接格式化为 DD/MM/YYYY 字符串
        # Case 1: column is already a datetime dtype — format directly to DD/MM/YYYY string
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%d/%m/%Y")
            converted.append(col)
            continue

        # 情况 2：文本列（object 或 pandas string）尝试识别日期
        # Case 2: textual column (object or pandas string)  attempt date detection
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue

        # 取前 '50 个非空样本做快速识别，按可解析比例判断是否为日期列
        # Use up to 50 non-null samples and decide by parse ratio instead of requiring 100% success
        sample = out[col].dropna().head(50)
        if len(sample) == 0:
            continue

        # 通过多策略尝试提高识别准确率（兼容 YYYY-MM-DD 与 UK 格式）
        # Use multi-strategy parsing for robust detection across ISO and UK date formats
        parsed_sample, sample_ratio = _best_date_parse(sample)

        # 样本解析率过低则跳过，防止误判普通文本列
        # Skip if sample parse ratio is too low to avoid false positives on text columns
        if sample_ratio < 0.6:
            continue

        # 对全列使用同样的多策略解析并再次校验成功率
        # Parse the full column with the same multi-strategy approach and validate again
        parsed, _ = _best_date_parse(out[col])
        non_null = out[col].notna().sum()
        full_ratio = (parsed.notna().sum() / non_null) if non_null > 0 else 0.0

        # 满足阈值才执行标准化输出
        # Standardize output only when the full-column parse ratio passes the threshold
        if full_ratio >= 0.5:
            out[col] = parsed.dt.strftime("%d/%m/%Y").fillna("")
            converted.append(col)

    return out, converted


# GBP 货币字段标准化
# GBP currency field standardisation


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



# 邮箱与手机号脱敏
# Email and phone number masking (PII)


# 匹配标准邮箱地址的正则表达式
# Regex pattern for standard email addresses
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# 匹配手机号常见字符集合的正则（检测时配合位数规则，兼容括号开头与分机号）
# Regex for allowed phone characters (used with digit-count rules; supports leading brackets and extensions)
_PHONE_ALLOWED_CHARS_RE = re.compile(r"^[\d\s\-().+xextEXT]+$")


def _is_phone_like(value: str) -> bool:
    """
    判断单个值是否像手机号（更宽容，适配括号、空格、连字符与分机号写法）。
    Determine whether a value is phone-like (lenient for brackets, spaces, hyphens, and extensions).

    说明 / Notes:
    - 至少包含 10 位数字（避免把日期等短数字串误判为手机号）。
      Require at least 10 digits to avoid misclassifying short numeric strings like dates.
    - 允许如 x123、ext123、ext.123 等分机号后缀。
      Allow extension suffixes such as x123, ext123, or ext.123.
    - 去掉分机号后，不允许出现其他字母字符。
      After removing extension notation, no other alphabetic characters are allowed.
    """
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False

    # 邮箱不应被当作手机号
    # Emails should never be treated as phone numbers
    if "@" in text:
        return False

    # 字符集初筛：仅允许电话号码常见字符
    # Character whitelist pre-check: allow only common phone characters
    if not _PHONE_ALLOWED_CHARS_RE.match(text):
        return False

    # 去掉分机号表达后再做字母检查，避免把普通文本误识别为手机号
    # Remove extension notation first, then reject residual alphabetic text
    # 兼容三种常见分机写法：
    # Support common extension formats:
    # 1) "x1234" 紧贴号码（如 02012345678x123）
    # 2) " x1234" 带空格
    # 3) "ext1234" / "ext.1234"
    text_wo_ext = re.sub(r"(?i)(?:\s*x\s*\d+|x\d+|\s*ext\.?\s*\d+)\s*$", "", text).strip()
    if re.search(r"[A-Za-z]", text_wo_ext):
        return False

    # 至少 10 位数字，兼容国际和常见本地号码长度
    # Require at least 10 digits to cover common local/international phone lengths
    return len(re.findall(r"\d", text)) >= 10


def _is_masked_phone_like(value: str) -> bool:
    """
    判断值是否看起来像“已部分掩盖”的手机号（用于再次点击掩盖时识别列类型）。
    Detect whether a value looks like an already-partially-masked phone number (for rerun detection).
    """
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False

    # 已掩盖手机号通常含 *，并保留少量数字（如末尾 4 位）
    # Masked phones usually contain * and keep a few digits (e.g., last 4)
    if "*" not in text:
        return False

    # 允许电话号码常见字符再加 *，防止把普通文本当作已掩盖手机号
    # Allow common phone characters plus * to avoid misclassifying generic text
    if not re.fullmatch(r"[\d\s\-().+xextEXT*]+", text):
        return False

    # 至少保留 2 位数字且至少有 2 个 *，提高判定稳定性
    # Require at least 2 digits and 2 asterisks for stable detection
    return len(re.findall(r"\d", text)) >= 2 and text.count("*") >= 2


def _is_likely_date_series(sample: pd.Series, threshold: float = 0.8) -> bool:
    """
    判断一列样本是否更像日期而非手机号。
    Decide whether a sample series looks more like dates than phone numbers.

    规则 / Rule:
    - 使用 dayfirst=True 解析样本；若可解析比例 >= threshold，视为日期列。
      Parse with dayfirst=True; treat as date-like when parse ratio >= threshold.
    """
    if sample is None or len(sample) == 0:
        return False

    parsed = pd.to_datetime(sample.astype(str).str.strip(), errors="coerce", dayfirst=True)
    return (parsed.notna().sum() / len(sample)) >= threshold


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
        # 处理文本列（object 或 pandas string）；其他类型通常不含 PII
        # Process textual columns (object or pandas string); other dtypes typically do not contain PII
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue

        # 取前 100 个非空样本进行检测
        # Sample up to 100 non-null values for detection
        sample = out[col].dropna().head(100).astype(str)
        if len(sample) == 0:
            continue

        # 若该列高度疑似日期列，则跳过手机号检测，避免把 invoice_date 误判成 phone
        # If this column is highly date-like, skip phone detection to avoid misclassifying invoice_date
        is_date_like = _is_likely_date_series(sample, threshold=0.8)

        # 统计样本中匹配邮箱 / 手机号正则的比例
        # Count how many sample values match the email / phone regex
        email_hits = sample.apply(lambda v: bool(_EMAIL_RE.match(v.strip()))).sum()
        ratio = len(sample)
        email_ratio = email_hits / ratio

        # 手机号命中率外，再附加数字位数约束：至少 10 位数字，减少日期字符串误判
        # In addition to regex hit rate, require at least 10 digits to reduce date-string false positives
        phone_like_hits = sample.apply(lambda v: _is_phone_like(v)).sum()
        masked_phone_hits = sample.apply(lambda v: _is_masked_phone_like(v)).sum()
        phone_ratio = (phone_like_hits + masked_phone_hits) / ratio

        # 列名提示：若列名包含 phone/mobile/tel 等关键词，可放宽阈值，便于补掩盖残留号码
        # Name hint: relax threshold for columns named like phone/mobile/tel so rerun can finish masking leftovers
        phone_name_hint = any(k in col.lower() for k in ["phone", "mobile", "tel", "telephone", "contact_number"])

        if email_ratio >= 0.5:
            # 识别为邮箱列：对每个非空值应用邮箱脱敏函数
            # Identified as an email column — apply the email masking function to each non-null value
            out[col] = out[col].apply(
                lambda v: _mask_email(str(v).strip()) if pd.notna(v) and _EMAIL_RE.match(str(v).strip()) else v
            )
            masked_cols.append(f"{col} (email)")

        elif (not is_date_like) and (
            phone_ratio >= 0.5 or (phone_name_hint and (phone_like_hits > 0 or masked_phone_hits > 0))
        ):
            # 识别为手机号列：对每个非空值应用手机号脱敏函数
            # Identified as a phone column — apply the phone masking function to each non-null value
            out[col] = out[col].apply(
                lambda v: _mask_phone(str(v).strip())
                if pd.notna(v) and _is_phone_like(str(v))
                else v
            )
            masked_cols.append(f"{col} (phone)")

    return out, masked_cols