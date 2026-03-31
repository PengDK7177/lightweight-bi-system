# 引入 pandas 库，用于数据清洗与转换操作
# Import pandas for data cleaning and transformation operations
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

    # 策略 drop：删除含有任意缺失值的行，然后重置索引
    # Strategy 'drop': remove any row that contains at least one missing value, then reset the index
    if strategy == "drop":
        return df.dropna().reset_index(drop=True)

    # 策略 zero：将所有缺失值填充为 0，适用于数值型数据
    # Strategy 'zero': replace all missing values with 0, suitable for numeric data
    if strategy == "zero":
        return df.fillna(0)

    # 策略 ffill：先用前一行的值向前填充，再用后一行的值向后填充以覆盖开头的缺失
    # Strategy 'ffill': forward-fill with the previous row's value, then back-fill to cover leading NaNs
    if strategy == "ffill":
        return df.ffill().bfill()

    # 未匹配到任何策略时原样返回，调用方负责传入合法值
    # Return the DataFrame unchanged if an unrecognised strategy is provided
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