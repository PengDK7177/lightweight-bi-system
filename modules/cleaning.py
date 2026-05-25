# 引入 pandas 库，用于数据处理与转换操作
# Import pandas for data cleaning and transformation operations
import pandas as pd

# 引入 re 模块，用于正则表达式匹配（邮箱、手机号检测与脱敏）
# Import re for regular expression matching used in PII detection and masking
import re

# Import warnings so noisy pandas date-inference warnings can be suppressed in controlled checks
import warnings


# 常见缺失、未知和无效标记，用于把脏分类值归入稳定类别。
# Common missing, unknown, and invalid markers used to group dirty categorical values into stable labels.
_MISSING_TOKENS = {"", "nan", "none", "null", "n/a", "na", "not set", "missing"}
_UNKNOWN_TOKENS = {"unknown", "unk", "not known"}
_INVALID_TOKENS = {"invalid", "invalid data", "error", "err"}

# UK postcode pattern. It accepts a normal outward code plus inward code, with optional spacing.
# 英国邮编格式校验；允许中间空格缺失，清洗时会重新加上标准空格。
_UK_POSTCODE_RE = re.compile(
    r"^(GIR\s?0AA|[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})$",
    re.IGNORECASE,
)


def _normalise_text_value(value: object) -> str | object:
    """
    清理单个文本值：去除首尾空格、压缩多余空格，并按常见标记归类。
    Clean one text value: trim, collapse repeated spaces, and classify common dirty markers.
    """
    if pd.isna(value):
        return "Missing"

    text = re.sub(r"\s+", " ", str(value).strip())
    lowered = text.lower()

    if lowered in _MISSING_TOKENS:
        return "Missing"
    if lowered in _UNKNOWN_TOKENS:
        return "Unknown"
    if lowered in _INVALID_TOKENS:
        return "Invalid Value"
    return text


def _convert_semantic_missing_to_na(df: pd.DataFrame) -> pd.DataFrame:
    """
    将文本型缺失标记重新转换为 pandas NA，保证后续缺失值策略仍能识别它们。
    Convert text-based missing markers back to pandas NA so later missing-value strategies can still detect them.

    说明 / Note:
    - Standardize Categorical Values 会把空值显示为 "Missing"，便于用户查看分类质量。
      Standardize Categorical Values displays blank values as "Missing" for clearer category review.
    - Apply Missing Value Strategy 需要把这些显示标签重新当作缺失值处理。
      Apply Missing Value Strategy must treat those display labels as missing values again.
    """
    out = df.copy()
    semantic_missing = _MISSING_TOKENS | {"missing"}

    for col in out.columns:
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue

        text_values = out[col].astype("string").str.strip().str.lower()
        missing_mask = text_values.isin(semantic_missing)
        if missing_mask.any():
            out.loc[missing_mask, col] = pd.NA

    return out


def _is_postal_column(column_name: str) -> bool:
    """
    判断列名是否表示邮编字段。
    Decide whether a column name represents a postal-code field.
    """
    name = str(column_name).lower()
    return any(hint in name for hint in ["postal", "postcode", "post_code", "zip"])


def _standardise_postcode(value: object) -> str:
    """
    将英国邮编统一为大写和标准空格；无法识别的值归类为稳定类别。
    Standardise UK postcodes to uppercase with a normal space; group invalid values into stable labels.
    """
    normalised = _normalise_text_value(value)
    if normalised == "Missing":
        return "Missing"
    if normalised in {"Unknown", "Invalid Value"}:
        return "Invalid Postal Code" if normalised == "Invalid Value" else "Unknown"

    compact = re.sub(r"\s+", "", str(normalised).upper())
    if _UK_POSTCODE_RE.match(compact):
        return f"{compact[:-3]} {compact[-3:]}"
    return "Incorrect Format"


def _looks_like_pii_or_free_text(column_name: str, sample: pd.Series) -> bool:
    """
    跳过邮箱、电话、备注等不适合统一大小写的自由文本或敏感字段。
    Skip emails, phones, notes, and other free-text or sensitive fields that should not be title-cased.
    """
    name = str(column_name).lower()
    if any(hint in name for hint in ["email", "phone", "mobile", "tel", "note", "remark", "comment"]):
        return True

    sample_text = sample.dropna().astype(str).str.strip().head(100)
    if sample_text.empty:
        return False

    email_ratio = sample_text.apply(lambda v: bool(_EMAIL_RE.match(v))).mean()
    long_text_ratio = sample_text.str.len().gt(40).mean()
    return email_ratio >= 0.3 or long_text_ratio >= 0.3


def standardize_categorical_values(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    逐列检查分类文本值，并统一异常值、空值、邮编和大小写不一致问题。
    Inspect categorical text values column by column and standardise dirty markers, postcodes, and case inconsistencies.

    返回 / Returns:
        (cleaned_df, report)
        report 包含每列的处理动作和受影响单元格数量。
        report records the action and affected cell count for each processed column.
    """
    if df is None or df.empty:
        return df, {"status": "empty", "processed_columns": {}}

    out = df.copy()
    report: dict[str, dict] = {}

    for col in out.columns:
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue

        before = out[col].copy()

        if _is_postal_column(col):
            out[col] = out[col].apply(_standardise_postcode)
            action = "standardised_postcode_categories"
        else:
            sample = out[col].dropna().head(100)
            if _looks_like_pii_or_free_text(col, sample):
                continue

            cleaned = out[col].apply(_normalise_text_value)

            # 仅对低基数字段统一大小写；ID、代码和高基数字段保持原样以避免破坏业务编码。
            # Title-case only low-cardinality categorical fields; keep IDs, codes, and high-cardinality values intact.
            unique_ratio = cleaned.astype(str).nunique(dropna=True) / max(len(cleaned), 1)
            name = str(col).lower()
            code_like = any(hint in name for hint in ["id", "code", "identifier"])
            category_name_hint = any(
                hint in name
                for hint in ["category", "type", "status", "country", "city", "region"]
            )
            if not code_like and (category_name_hint or unique_ratio <= 0.5):
                cleaned = cleaned.apply(
                    lambda v: v if v in {"Missing", "Unknown", "Invalid Value"} else str(v).title()
                )

            out[col] = cleaned
            action = "standardised_categorical_values"

        changed = (before.astype("string").fillna("<NA>") != out[col].astype("string").fillna("<NA>")).sum()
        if int(changed) > 0:
            report[col] = {
                "action": action,
                "changed_cells": int(changed),
                "categories_after": sorted(out[col].astype(str).dropna().unique().tolist())[:20],
            }

    return out, {"processed_columns": report}

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
    
    # 先把 "Missing"/"N/A"/"NULL" 等文本标记恢复为真正缺失值，避免清洗按钮顺序影响结果。
    # First restore "Missing"/"N/A"/"NULL" text markers to real missing values so button order does not change behaviour.
    out = _convert_semantic_missing_to_na(df)
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


# 修正版日期标准化实现：覆盖上方旧实现，修复混合格式和脏值导致的漏检
# Revised date standardisation implementation: overrides the older version above and fixes missed detection with mixed formats and dirty values
def standardize_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    自动检测日期列，并将可解析日期统一为英国标准格式 DD/MM/YYYY。
    Auto-detect date columns and convert parseable dates to UK DD/MM/YYYY format.

    说明 / Notes:
    - invoice_date、signup_date 等列名命中日期关键词时，即使混有少量脏值也会被识别。
      Columns such as invoice_date and signup_date are detected by name even when they contain dirty values.
    - 无法解析的非空日期值会标记为 Invalid Date，避免无效日期进入后续分析。
      Unparseable non-null date values are marked as Invalid Date so invalid dates do not flow into later analysis.
    """
    # 若 DataFrame 为空则直接返回，并附带空列表表示无列被转换
    # Return early with an empty list when the DataFrame is None or empty
    if df is None or df.empty:
        return df, []

    # 复制 DataFrame，保持原始数据不变
    # Copy the DataFrame to avoid mutating the caller's data
    out = df.copy()
    converted: list[str] = []

    # 日期列名提示词：命中这些词时降低检测阈值
    # Date column name hints: lower the detection threshold when any hint is present
    date_name_hints = {
        "date", "time", "datetime", "timestamp", "created", "updated",
        "start", "end", "signup", "dob", "birth", "paid_on", "due", "login",
    }

    def _has_date_name_hint(column_name: str) -> bool:
        """
        判断列名是否明显暗示日期含义。
        Decide whether the column name clearly suggests date semantics.
        """
        normalized_name = str(column_name).lower()
        return any(hint in normalized_name for hint in date_name_hints)

    def _parse_dates_lenient(series: pd.Series) -> pd.Series:
        """
        使用多种显式格式逐步解析日期，兼容同一列中混合的 /、-、ISO 等格式。
        Parse dates with multiple explicit formats so mixed /, -, and ISO formats in one column are supported.
        """
        # 先把值转为 pandas string，并清理首尾空白，避免空格影响解析
        # Convert values to pandas string and trim whitespace so spaces do not break parsing
        text = series.astype("string").str.strip()

        # 用全 NaT 序列作为结果容器，后续格式只填补尚未解析成功的位置
        # Use an all-NaT result series and let later formats fill only still-missing positions
        parsed_result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

        def _safe_parse_scalar(value: object, date_format: str | None = None):
            """
            安全解析单个日期值；超出 pandas 纳秒时间范围的值会返回 NaT。
            Safely parse one date value; values outside pandas' nanosecond timestamp range return NaT.
            """
            try:
                parsed = pd.to_datetime(value, errors="coerce", format=date_format)
            except (pd.errors.OutOfBoundsDatetime, OverflowError, ValueError):
                return pd.NaT

            if pd.isna(parsed):
                return pd.NaT

            # pandas datetime64[ns] 只能稳定覆盖约 1678-2261 年；超出范围保留原值
            # pandas datetime64[ns] is safe roughly for years 1678-2261; out-of-range values are preserved
            parsed_year = getattr(parsed, "year", None)
            if parsed_year is None or parsed_year < 1678 or parsed_year > 2261:
                return pd.NaT

            try:
                return pd.Timestamp(parsed)
            except (pd.errors.OutOfBoundsDatetime, OverflowError, ValueError):
                return pd.NaT

        def _safe_parse_with_format(values: pd.Series, date_format: str | None = None) -> pd.Series:
            """
            逐值安全解析日期，避免某个异常值拖垮整列转换。
            Parse dates safely value by value so one exceptional value cannot break the whole column.
            """
            parsed_values = [_safe_parse_scalar(value, date_format=date_format) for value in values]
            return pd.Series(parsed_values, index=values.index, dtype="datetime64[ns]")

        def _safe_parse_dayfirst(values: pd.Series) -> pd.Series:
            """
            安全执行 dayfirst=True 兜底解析，避免 2400-01-01 等值导致整列失败。
            Safely run the dayfirst=True fallback so values like 2400-01-01 do not crash the whole column.
            """
            parsed_values = []
            for value in values:
                try:
                    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
                except (pd.errors.OutOfBoundsDatetime, OverflowError, ValueError):
                    parsed_values.append(pd.NaT)
                    continue

                if pd.isna(parsed):
                    parsed_values.append(pd.NaT)
                    continue

                parsed_year = getattr(parsed, "year", None)
                if parsed_year is None or parsed_year < 1678 or parsed_year > 2261:
                    parsed_values.append(pd.NaT)
                    continue

                try:
                    parsed_values.append(pd.Timestamp(parsed))
                except (pd.errors.OutOfBoundsDatetime, OverflowError, ValueError):
                    parsed_values.append(pd.NaT)
            return pd.Series(parsed_values, index=values.index, dtype="datetime64[ns]")

        # 显式格式优先，避免 pandas 对混合格式列只按第一种格式推断导致漏识别
        # Prefer explicit formats so pandas does not infer only the first format in mixed-format columns
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%d %m %Y",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            parsed_attempt = _safe_parse_with_format(text, date_format=fmt)
            parsed_result = parsed_result.fillna(parsed_attempt)

        # 最后使用 dayfirst=True 兜底，并屏蔽 pandas 对脏值列的格式推断提示
        # Finally fall back to dayfirst=True and suppress pandas inference warnings for dirty columns
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed_fallback = _safe_parse_dayfirst(text)
        parsed_result = parsed_result.fillna(parsed_fallback)
        return parsed_result

    def _parse_ratio(parsed: pd.Series, source: pd.Series) -> float:
        """
        计算非空原始值中成功解析为日期的比例。
        Calculate the share of non-null source values that were parsed as dates.
        """
        non_null_count = source.notna().sum()
        if non_null_count == 0:
            return 0.0
        return float(parsed.notna().sum() / non_null_count)

    for col in out.columns:
        # 情况 1：列已经是 datetime 类型，直接格式化为 DD/MM/YYYY 字符串
        # Case 1: column is already a datetime dtype; format directly to DD/MM/YYYY string
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%d/%m/%Y")
            converted.append(col)
            continue

        # 情况 2：文本列（object 或 pandas string）尝试识别日期
        # Case 2: textual column (object or pandas string) attempts date detection
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue

        # 取前 100 个非空样本做快速识别，降低大表解析成本
        # Use up to 100 non-null samples for fast detection on large datasets
        sample = out[col].dropna().head(100)
        if len(sample) == 0:
            continue

        # 使用宽松解析器计算样本解析比例，混合格式和部分脏值都能被处理
        # Use the lenient parser to measure sample parse ratio with mixed formats and dirty values
        parsed_sample = _parse_dates_lenient(sample)
        sample_ratio = _parse_ratio(parsed_sample, sample)
        has_name_hint = _has_date_name_hint(col)

        # 有日期列名提示时只要求至少一个有效日期；无提示时要求较高比例以避免误判
        # With a date name hint, require at least one valid date; without it, require a higher ratio
        if has_name_hint:
            should_convert = parsed_sample.notna().any()
        else:
            should_convert = sample_ratio >= 0.6

        if not should_convert:
            continue

        # 解析完整列；对列名明确的日期字段使用宽松阈值，对普通文本字段保持保守阈值
        # Parse the full column; use a lenient threshold for named date fields and a conservative one otherwise
        parsed = _parse_dates_lenient(out[col])
        full_ratio = _parse_ratio(parsed, out[col])
        if (has_name_hint and parsed.notna().any()) or full_ratio >= 0.5:
            # 成功解析的值转为英国日期格式；未解析的非空日期值归类为 Invalid Date。
            # Parsed values become UK date strings; unparseable non-empty date values are grouped as Invalid Date.
            formatted = parsed.dt.strftime("%d/%m/%Y")
            original_text = out[col].astype("string").str.strip()
            missing_mask = original_text.str.lower().isin(_MISSING_TOKENS) | original_text.isna()
            out[col] = out[col].where(parsed.isna(), formatted)
            invalid_mask = parsed.isna() & ~missing_mask
            out.loc[invalid_mask, col] = "Invalid Date"
            out.loc[missing_mask, col] = "Missing"
            converted.append(col)

    return out, converted


# GBP currency field standardisation


# 列名关键词列表：含这些词的列被视为潜在货币列
# Column name keywords that suggest a column may contain monetary values
_CURRENCY_NAME_HINTS = {
    "price", "amount", "cost", "revenue", "total", "fee",
    "gbp", "value", "sales", "income", "profit", "turnover",
    "balance", "payment", "charge", "salary", "wage",
}

# 税率/比例字段提示词；这些字段会被转换为小数形式，例如 20% -> 0.20。
# Rate/percentage column hints; these fields are converted to decimal fractions such as 20% -> 0.20.
_RATE_NAME_HINTS = {"rate", "percent", "percentage", "vat_rate", "discount_rate"}


def _clean_numeric_text(series: pd.Series) -> pd.Series:
    """
    清理金额类文本：只处理 GBP 样式，不做外币换算。
    Clean amount-like text: handle GBP-style values only, without currency exchange conversion.
    """
    cleaned = (
        series
        .astype("string")
        .str.replace("£", "", regex=False)
        .str.replace("拢", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _clean_rate_text(series: pd.Series) -> pd.Series:
    """
    清理税率/比例字段：支持 20%、0.2 和 20 等常见写法。
    Clean rate/percentage fields: supports common forms such as 20%, 0.2, and 20.
    """
    text = series.astype("string").str.strip()
    has_percent = text.str.contains("%", regex=False, na=False)
    numeric = pd.to_numeric(text.str.replace("%", "", regex=False), errors="coerce")
    numeric = numeric.where(~has_percent, numeric / 100)
    numeric = numeric.where(~((~has_percent) & (numeric > 1) & (numeric <= 100)), numeric / 100)
    return numeric.where((numeric >= 0) & (numeric <= 1), pd.NA)


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
        # ---- 判断是否为金额列或比例列 ----
        # ---- Decide whether this column holds amount or rate values ----

        col_lower = col.lower()

        # 规则 1：列名含货币或比例关键词
        # Rule 1: column name contains a currency or rate keyword
        name_match = any(hint in col_lower for hint in _CURRENCY_NAME_HINTS)
        rate_match = any(hint in col_lower for hint in _RATE_NAME_HINTS)

        # 规则 2：列值中超过 50% 含 £ 符号（仅对 object 类型列检查）
        # Rule 2: more than 50% of non-null values contain £ (only checked for object columns)
        value_match = False
        if out[col].dtype == object:
            non_null = out[col].dropna()
            if len(non_null) > 0:
                gbp_text = non_null.astype(str)
                gbp_count = (
                    gbp_text.str.contains('£', regex=False)
                    | gbp_text.str.contains('拢', regex=False)
                ).sum()
                value_match = (gbp_count / len(non_null)) > 0.5

        if not (name_match or value_match or rate_match):
            # 不符合任何规则，跳过
            # Skip columns that match no rule
            continue

        if rate_match:
            # 税率字段标准化：20% -> 0.20；abc/invalid/负数 -> NA。
            # Rate standardisation: 20% -> 0.20; abc/invalid/negative values -> NA.
            numeric = _clean_rate_text(out[col])
            non_null_count = out[col].notna().sum()
            if non_null_count > 0 and (numeric.notna().sum() / non_null_count) >= 0.3:
                out[col] = numeric
                converted.append(col)
            continue

        # ---- 已是数值类型则直接记录，无需再清洗 ----
        # ---- Already numeric — just record it, no cleaning needed ----
        if pd.api.types.is_numeric_dtype(out[col]):
            converted.append(col)
            continue

        # ---- 清洗：去除 £、逗号和空格，再转为 float ----
        # ---- Clean: strip £, commas, and spaces, then cast to float ----
        numeric = _clean_numeric_text(out[col])

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

    # 在此处只需要判断“像不像日期列”，无需向用户暴露 pandas 的格式推断提示。
    # This is only a date-likeness check, so pandas format-inference warnings are intentionally hidden.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
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
