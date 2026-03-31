# 引入 Faker 库，用于生成逼真的虚假测试数据（如姓名、日期等）
# Import Faker for generating realistic synthetic test data (names, dates, etc.)
from faker import Faker

# 引入 pandas 用于构建和导出 DataFrame
# Import pandas for building and exporting the DataFrame
import pandas as pd

# 引入 random 用于生成随机数值和随机选择
# Import random for generating random numbers and making random selections
import random

# 引入 os 用于拼接跨平台文件路径
# Import os for constructing cross-platform file paths
import os

# 初始化 Faker 实例，后续调用其方法生成各类随机数据
# Initialise a Faker instance; its methods will be called to produce various random values
fake = Faker()

# 创建空列表，用于逐行收集生成的发票数据
# Create an empty list to accumulate generated invoice rows one by one
invoices = []

# 循环生成 5000 条演示发票记录，用于本地测试和分析
# Loop to generate 5,000 demo invoice records for local testing and analysis
for i in range(5000):
    # 随机生成不含税金额，保留两位小数
    # Generate a random net amount (excluding VAT), rounded to 2 decimal places
    net_amount = round(random.uniform(20, 800), 2)

    # 固定增值税税率为 20%（英国标准税率）
    # Set a fixed VAT rate of 20% (UK standard rate)
    vat_rate = 0.2

    # 将本条记录以字典形式追加到列表中
    # Append this record as a dictionary to the invoice list
    invoices.append({
        "invoice_id": f"INV{i+1}",                                          # 发票编号 / Invoice number
        "customer_id": f"C{random.randint(1, 2000)}",                        # 随机客户 ID / Random customer ID
        "invoice_date": fake.date_between(start_date='-2y', end_date='today'),  # 近两年内的随机日期 / Random date within the last 2 years
        "net_amount": net_amount,                                            # 不含税金额 / Net amount excluding VAT
        "vat_amount": round(net_amount * vat_rate, 2),                       # 增值税金额 / VAT amount
        "total_amount": round(net_amount * (1 + vat_rate), 2),               # 含税总金额 / Total amount including VAT
        "payment_status": random.choice(["Paid", "Pending", "Overdue"])      # 随机支付状态 / Random payment status
    })

# 将发票列表转换为 pandas DataFrame，便于后续分析和导出
# Convert the invoice list into a pandas DataFrame for analysis and export
df_invoices = pd.DataFrame(invoices)

# 拼接输出文件路径，指向 data 目录下的 invoices.csv
# Build the output file path pointing to invoices.csv inside the data directory
output_path = os.path.join("data", "invoices.csv")

# 将 DataFrame 导出为 CSV 文件，不写入行索引列
# Export the DataFrame to CSV without writing the row index
df_invoices.to_csv(output_path, index=False)

# 打印提示信息，确认文件已成功生成
# Print a confirmation message to indicate the file has been generated successfully
print("Invoices dataset generated:", output_path)