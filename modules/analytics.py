import pandas as pd


def calculate_vat(df: pd.DataFrame, amount_col: str, vat_rate: float = 0.20) -> pd.DataFrame:
    """
    根据指定的金额列计算增值税（VAT），并将结果追加到 DataFrame 中。
    Calculate VAT based on a specified amount column and append the results to the DataFrame.

    参数 / Parameters:
        df        -- 输入的 DataFrame 数据表 / Input DataFrame
        amount_col -- 用于计算增值税的金额列名 / Column name used for VAT calculation
        vat_rate   -- 增值税税率，默认为 20%（0.20） / VAT rate, defaults to 20% (0.20)

    返回 / Returns:
        包含以下两个新增列的 DataFrame 副本 / A copy of the DataFrame with two new columns:
        - vat_amount      : 增值税金额（= 原始金额 × 税率）/ VAT amount (= net amount × rate)
        - amount_incl_vat : 含税总金额（= 原始金额 + 增值税金额）/ Gross amount (= net + VAT)
    """
    # 若传入的 DataFrame 为空或不含任何数据，则直接返回原对象，避免后续报错
    # If the DataFrame is None or empty, return it as-is to avoid downstream errors
    if df is None or df.empty:
        return df

    # 校验指定的金额列是否存在于 DataFrame 中，不存在则抛出异常提示调用方
    # Validate that the specified amount column exists; raise a clear error if not
    if amount_col not in df.columns:
        raise ValueError(f"Column '{amount_col}' not found.")

    # 复制原始 DataFrame，防止对原始数据造成修改（保持数据不可变原则）
    # Copy the original DataFrame to avoid mutating the caller's data (immutability principle)
    out = df.copy()

    # 将金额列强制转换为数值类型；无法转换的值（如文本）会变为 NaN，再填充为 0.0，确保计算不中断
    # Coerce the amount column to numeric; non-numeric values become NaN, then are filled with 0.0
    out[amount_col] = pd.to_numeric(out[amount_col], errors="coerce").fillna(0.0)

    # 按照税率计算每行的增值税金额，并写入新列 vat_amount
    # Multiply each row's net amount by the VAT rate and store the result in vat_amount
    out["vat_amount"] = out[amount_col] * vat_rate

    # 将原始金额与增值税金额相加，得到含税总金额，写入新列 amount_incl_vat
    # Add the net amount and VAT amount to produce the gross total, stored in amount_incl_vat
    out["amount_incl_vat"] = out[amount_col] + out["vat_amount"]

    return out


def basic_kpis(df: pd.DataFrame, amount_col: str) -> dict:
    """
    对指定数值列计算基本统计指标（KPI）。
    Compute basic summary KPIs for a specified numeric column.

    参数 / Parameters:
        df        -- 输入的 DataFrame 数据表 / Input DataFrame
        amount_col -- 需要统计的数值列名 / Name of the numeric column to analyse

    返回 / Returns:
        包含以下键的字典 / A dictionary with the following keys:
        - rows : 数据行数 / Total number of rows
        - sum  : 总和 / Sum of all values
        - avg  : 平均值 / Mean value
        - min  : 最小值 / Minimum value
        - max  : 最大值 / Maximum value
    """
    # 若 DataFrame 为空，或指定列不存在，则返回全为零的默认结果，保证 UI 层渲染不报错
    # Return a zero-filled default dict when the DataFrame is empty or the column is missing
    if df is None or df.empty or amount_col not in df.columns:
        return {"rows": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}

    # 将目标列转换为数值类型，非数值内容填充为 0.0，确保统计函数可以正常运行
    # Convert the target column to numeric, filling non-numeric entries with 0.0
    s = pd.to_numeric(df[amount_col], errors="coerce").fillna(0.0)

    # 汇总并返回各项统计指标；使用 int/float 显式转型，避免返回 numpy 类型导致序列化问题
    # Aggregate and return all KPIs; explicit int/float casts prevent numpy type serialisation issues
    return {
        "rows": int(len(df)),    # 总行数 / Total row count
        "sum": float(s.sum()),   # 所有值的总和 / Sum of all values
        "avg": float(s.mean()),  # 所有值的平均值 / Mean of all values
        "min": float(s.min()),   # 最小值 / Minimum value
        "max": float(s.max()),   # 最大值 / Maximum value
    }


def _best_date_parse(series: pd.Series) -> pd.Series:
    """
    尝试多种日期解析策略，返回成功率最高的结果。
    Try multiple date parsing strategies and return the best-success parsed series.
    """
    s = series.astype(str).str.strip()
    candidates = [
        pd.to_datetime(s, errors="coerce", format="%Y-%m-%d"),
        pd.to_datetime(s, errors="coerce", format="%d/%m/%Y"),
        pd.to_datetime(s, errors="coerce", format="%d-%m-%Y"),
        pd.to_datetime(s, errors="coerce", dayfirst=True),
        pd.to_datetime(s, errors="coerce", dayfirst=False),
    ]

    best = candidates[0]
    best_ratio = best.notna().mean()
    for parsed in candidates[1:]:
        ratio = parsed.notna().mean()
        if ratio > best_ratio:
            best = parsed
            best_ratio = ratio
    return best


def cash_flow_analysis(
    df: pd.DataFrame,
    date_col: str,
    amount_col: str,
    status_col: str | None = None,
) -> pd.DataFrame:
    """
    生成按月现金流分析结果。
    Build a monthly cash-flow analysis table.

    返回列 / Returned columns:
    - month
    - total_amount
    - paid_amount
    - outstanding_amount
    - cumulative_paid
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["month", "total_amount", "paid_amount", "outstanding_amount", "cumulative_paid"])
    if date_col not in df.columns or amount_col not in df.columns:
        return pd.DataFrame(columns=["month", "total_amount", "paid_amount", "outstanding_amount", "cumulative_paid"])

    out = df.copy()
    out[amount_col] = pd.to_numeric(out[amount_col], errors="coerce").fillna(0.0)
    out["_date"] = _best_date_parse(out[date_col])
    out = out[out["_date"].notna()].copy()
    if out.empty:
        return pd.DataFrame(columns=["month", "total_amount", "paid_amount", "outstanding_amount", "cumulative_paid"])

    out["month"] = out["_date"].dt.to_period("M").dt.to_timestamp()
    out["_paid_amount"] = out[amount_col]

    # 若存在支付状态列，则只把 paid/completed/settled/success 计入实收现金流
    # If payment status exists, only paid/completed/settled/success counts as actual inflow
    if status_col and status_col in out.columns:
        status = out[status_col].astype(str).str.strip().str.lower()
        paid_mask = status.isin(["paid", "completed", "settled", "success"])
        out.loc[~paid_mask, "_paid_amount"] = 0.0

    monthly = (
        out.groupby("month", as_index=False)
        .agg(
            total_amount=(amount_col, "sum"),
            paid_amount=("_paid_amount", "sum"),
        )
        .sort_values("month")
    )
    monthly["outstanding_amount"] = monthly["total_amount"] - monthly["paid_amount"]
    monthly["cumulative_paid"] = monthly["paid_amount"].cumsum()
    return monthly


def _rfm_score(series: pd.Series, high_is_good: bool = True, bins: int = 4) -> pd.Series:
    """按分位数给一列打分（1~bins）。Score a series by quantiles (1..bins)."""
    ranked = series.rank(method="first")
    try:
        score = pd.qcut(ranked, bins, labels=False) + 1
    except ValueError:
        # 值重复过多时回退为等宽分箱
        # Fallback to equal-width bins when too many duplicated values exist
        score = pd.cut(ranked, bins=bins, labels=False, include_lowest=True) + 1

    if not high_is_good:
        score = (bins + 1) - score
    return score.astype(int)


def rfm_analysis(df: pd.DataFrame, customer_col: str, date_col: str, amount_col: str) -> pd.DataFrame:
    """
    计算简化版 RFM 分析结果。
    Compute a simplified RFM analysis result.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["customer_id", "recency", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm_score", "segment"])
    for col in [customer_col, date_col, amount_col]:
        if col not in df.columns:
            return pd.DataFrame(columns=["customer_id", "recency", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm_score", "segment"])

    out = df.copy()
    out[amount_col] = pd.to_numeric(out[amount_col], errors="coerce").fillna(0.0)
    out["_date"] = _best_date_parse(out[date_col])
    out = out[out["_date"].notna()].copy()
    out = out[out[customer_col].notna()].copy()
    if out.empty:
        return pd.DataFrame(columns=["customer_id", "recency", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm_score", "segment"])

    snapshot_date = out["_date"].max() + pd.Timedelta(days=1)
    rfm = (
        out.groupby(customer_col)
        .agg(
            recency=("_date", lambda x: (snapshot_date - x.max()).days),
            frequency=("_date", "count"),
            monetary=(amount_col, "sum"),
        )
        .reset_index()
        .rename(columns={customer_col: "customer_id"})
    )

    rfm["r_score"] = _rfm_score(rfm["recency"], high_is_good=False, bins=4)
    rfm["f_score"] = _rfm_score(rfm["frequency"], high_is_good=True, bins=4)
    rfm["m_score"] = _rfm_score(rfm["monetary"], high_is_good=True, bins=4)
    rfm["rfm_score"] = rfm["r_score"] + rfm["f_score"] + rfm["m_score"]

    def _segment(score: int) -> str:
        if score >= 10:
            return "Champion"
        if score >= 8:
            return "Loyal"
        if score >= 6:
            return "Potential"
        return "At Risk"

    rfm["segment"] = rfm["rfm_score"].apply(_segment)
    return rfm.sort_values("rfm_score", ascending=False).reset_index(drop=True)


def rfm_segment_summary(rfm_df: pd.DataFrame) -> pd.DataFrame:
    """按用户分群汇总数量与平均消费。Summarise customer segment counts and average spend."""
    if rfm_df is None or rfm_df.empty or "segment" not in rfm_df.columns:
        return pd.DataFrame(columns=["segment", "customers", "avg_monetary"])

    summary = (
        rfm_df.groupby("segment", as_index=False)
        .agg(customers=("customer_id", "count"), avg_monetary=("monetary", "mean"))
        .sort_values("customers", ascending=False)
    )
    return summary