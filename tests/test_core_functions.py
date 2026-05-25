"""Unit tests for the Lightweight BI prototype core functions.

单元测试文件：验证轻量 BI 原型系统中的核心数据处理和分析函数。
"""

from pathlib import Path
import sys

import pandas as pd

# Ensure tests can import project modules when pytest is run from the repo root.
# 确保从项目根目录运行 pytest 时，测试文件可以导入 modules 目录中的项目模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.analytics import basic_kpis, calculate_vat, cash_flow_analysis, rfm_analysis
from modules.cleaning import (
    fill_missing,
    mask_pii,
    remove_duplicates,
    standardize_categorical_values,
    standardize_currency,
    standardize_dates,
)


def _assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    """Compare floating point values with a small tolerance.

    使用较小误差范围比较浮点数，避免小数计算造成误判。
    """
    assert abs(float(actual) - float(expected)) <= tolerance


def test_calculate_vat_adds_expected_columns_and_values():
    """VAT calculation should add VAT and gross amount columns.

    VAT 计算应新增增值税金额和含税总金额两列。
    """
    df = pd.DataFrame({"net_amount": [100, 250]})

    result = calculate_vat(df, amount_col="net_amount", vat_rate=0.20)

    assert list(result["vat_amount"]) == [20, 50]
    assert list(result["amount_incl_vat"]) == [120, 300]


def test_basic_kpis_returns_numeric_summary():
    """KPI summary should return row count and common numeric aggregates.

    KPI 汇总应返回行数以及常见数值统计结果。
    """
    df = pd.DataFrame({"amount": [10, 20, 30]})

    result = basic_kpis(df, "amount")

    assert result == {"rows": 3, "sum": 60.0, "avg": 20.0, "min": 10.0, "max": 30.0}


def test_cash_flow_analysis_groups_paid_and_outstanding_amounts_by_month():
    """Cash-flow analysis should separate paid and unpaid monthly totals.

    现金流分析应按月份区分已支付金额和未支付金额。
    """
    df = pd.DataFrame(
        {
            "invoice_date": ["2025-01-02", "2025-01-18", "2025-02-03"],
            "total_amount": [100, 200, 300],
            "payment_status": ["Paid", "Pending", "Paid"],
        }
    )

    result = cash_flow_analysis(
        df,
        date_col="invoice_date",
        amount_col="total_amount",
        status_col="payment_status",
    )

    january = result[result["month"] == pd.Timestamp("2025-01-01")].iloc[0]
    february = result[result["month"] == pd.Timestamp("2025-02-01")].iloc[0]

    _assert_close(january["total_amount"], 300)
    _assert_close(january["paid_amount"], 100)
    _assert_close(january["outstanding_amount"], 200)
    _assert_close(february["cumulative_paid"], 400)


def test_rfm_analysis_creates_customer_segments():
    """RFM analysis should produce customer-level scores and value segments.

    RFM 分析应生成客户级评分和价值分层结果。
    """
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C1", "C2", "C3"],
            "invoice_date": ["2025-01-01", "2025-02-01", "2024-12-01", "2025-03-01"],
            "net_amount": [100, 150, 80, 300],
        }
    )

    result = rfm_analysis(
        df,
        customer_col="customer_id",
        date_col="invoice_date",
        amount_col="net_amount",
    )

    assert set(["customer_id", "recency", "frequency", "monetary", "value_segment"]).issubset(
        result.columns
    )
    assert set(result["customer_id"]) == {"C1", "C2", "C3"}
    assert result["value_segment"].isin(["High Value", "Medium Value", "Low Value"]).all()


def test_remove_duplicates_drops_duplicate_rows_and_resets_index():
    """Duplicate removal should keep unique records and reset the index.

    去重功能应保留唯一记录并重置索引。
    """
    df = pd.DataFrame({"id": [1, 1, 2], "amount": [10, 10, 20]})

    result = remove_duplicates(df)

    assert len(result) == 2
    assert list(result.index) == [0, 1]


def test_fill_missing_auto_handles_numeric_and_categorical_columns():
    """Automatic missing-value handling should process columns by detected type.

    自动缺失值处理应根据列类型采用相应策略。
    """
    df = pd.DataFrame(
        {
            "quantity": [1, None, 3],
            "category": ["Retail", None, "Wholesale"],
        }
    )

    result, info = fill_missing(df, strategy="auto", return_info=True)

    assert result["quantity"].isna().sum() == 0
    assert result["category"].isna().sum() == 0
    assert info["processed_columns"]["quantity"]["strategy"] == "zero"
    assert info["processed_columns"]["category"]["strategy"] == "ffill"


def test_standardize_dates_formats_date_columns_to_uk_style():
    """Date standardisation should convert recognised date values to DD/MM/YYYY.

    日期标准化应将可识别日期转换为英国 DD/MM/YYYY 格式。
    """
    df = pd.DataFrame({"invoice_date": ["2025-01-15", "16/02/2025"], "amount": [100, 200]})

    result, converted_cols = standardize_dates(df)

    assert "invoice_date" in converted_cols
    assert list(result["invoice_date"]) == ["15/01/2025", "16/02/2025"]


def test_standardize_dates_handles_datetime_columns_and_invalid_dates():
    """Date standardisation should handle datetime strings and mark impossible dates.

    日期标准化应处理带时间的日期字符串，并把不可能日期标记为 Invalid Date。
    """
    df = pd.DataFrame(
        {
            "last_login": ["2026-05-08 10:30:00", "08/05/2026 22:10", "2026-99-99 99:99:99"],
            "invoice_date": ["2026.04.30", "2026.04.31", "13/13/2026"],
        }
    )

    result, converted_cols = standardize_dates(df)

    assert "last_login" in converted_cols
    assert "invoice_date" in converted_cols
    assert list(result["last_login"]) == ["08/05/2026", "08/05/2026", "Invalid Date"]
    assert list(result["invoice_date"]) == ["30/04/2026", "Invalid Date", "Invalid Date"]


def test_mask_pii_masks_email_and_phone_columns():
    """PII masking should mask email addresses and phone numbers.

    敏感信息脱敏应处理邮箱地址和电话号码。
    """
    df = pd.DataFrame(
        {
            "email": ["alice@example.com", "bob@example.org"],
            "phone": ["07911 123456", "(020) 1234 5678"],
            "name": ["Alice", "Bob"],
        }
    )

    result, masked_cols = mask_pii(df)

    assert "email (email)" in masked_cols
    assert "phone (phone)" in masked_cols
    assert result.loc[0, "email"] == "a***@example.com"
    assert result.loc[0, "phone"].endswith("3456")
    assert "*" in result.loc[0, "phone"]


def test_standardize_categorical_values_normalises_case_and_dirty_markers():
    """Categorical cleaning should group missing/invalid markers and normalise casing.

    分类值清洗应归类缺失/无效标记，并统一同义类别的大小写差异。
    """
    df = pd.DataFrame(
        {
            "region": ["London", "london", " LONDON ", "N/A", "invalid data"],
            "payment_status": ["paid", " Paid ", "FAILED", None, "unknown"],
        }
    )

    result, report = standardize_categorical_values(df)

    assert list(result["region"]) == ["London", "London", "London", "Missing", "Invalid Value"]
    assert list(result["payment_status"]) == ["Paid", "Paid", "Failed", "Missing", "Unknown"]
    assert "region" in report["processed_columns"]
    assert "payment_status" in report["processed_columns"]


def test_standardize_categorical_values_classifies_postal_code_errors():
    """Postal cleaning should separate missing, invalid, and badly formatted postcodes.

    邮编清洗应区分缺失值、明确无效值和格式错误值。
    """
    df = pd.DataFrame(
        {
            "postal_code": ["sw1a1aa", "INVALID", None, "12345", " M1 1AE "],
        }
    )

    result, report = standardize_categorical_values(df)

    assert list(result["postal_code"]) == [
        "SW1A 1AA",
        "Invalid Postal Code",
        "Missing",
        "Incorrect Format",
        "M1 1AE",
    ]
    assert report["processed_columns"]["postal_code"]["action"] == "standardised_postcode_categories"


def test_fill_missing_handles_missing_labels_created_by_categorical_cleaning():
    """Missing-value handling should still work after categorical cleaning.

    即使分类清洗先把空值显示为 Missing，缺失值处理仍应继续把它当作真正缺失值处理。
    """
    df = pd.DataFrame({"region": ["London", None, "Leeds"], "quantity": [1, None, 3]})

    categorised, _ = standardize_categorical_values(df)
    result, info = fill_missing(categorised, strategy="auto", return_info=True)

    assert list(categorised["region"]) == ["London", "Missing", "Leeds"]
    assert list(result["region"]) == ["London", "London", "Leeds"]
    assert result["quantity"].isna().sum() == 0
    assert info["processed_columns"]["region"]["missing_count"] == 1


def test_standardize_currency_cleans_gbp_amounts_and_vat_rates():
    """Numeric standardisation should clean GBP amounts and rate fields.

    数值标准化应清理 GBP 金额和 VAT rate 字段，并把无效字母值转为缺失值。
    """
    df = pd.DataFrame(
        {
            "net_amount": ["£1,200.00", "1.2e3", "abc"],
            "amount_gbp": ["£3,333.33", "2400", "invalid"],
            "vat_rate": ["20%", "0.2", "abc"],
        }
    )

    result, converted_cols = standardize_currency(df)

    assert {"net_amount", "amount_gbp", "vat_rate"}.issubset(set(converted_cols))
    assert list(result["net_amount"].round(2))[:2] == [1200.00, 1200.00]
    assert pd.isna(result.loc[2, "net_amount"])
    assert list(result["amount_gbp"].round(2))[:2] == [3333.33, 2400.00]
    assert pd.isna(result.loc[2, "amount_gbp"])
    assert list(result["vat_rate"].dropna()) == [0.2, 0.2]
    assert pd.isna(result.loc[2, "vat_rate"])
