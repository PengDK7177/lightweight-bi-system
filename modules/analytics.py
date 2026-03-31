# 引入 pandas 库，用于数据处理与分析
# Import the pandas library for data processing and analysis
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