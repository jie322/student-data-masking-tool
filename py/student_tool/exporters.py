"""脱敏数据持久化导出模块：负责创建全新的 CSV、TSV 或 Excel (XLSX) 文件，隔绝原始工作簿的批注、外部链接及隐藏元数据。"""

import csv
from pathlib import Path

import openpyxl


def write_tables(destination, output):
    """将脱敏处理并通过安全审计的数据写入目标文件。

    在生成 Excel 工作簿时采用流式写入模式 (write_only=True) 全新构建，彻底阻断原文件中潜在的恶意宏、隐藏工作表元数据及历史批注泄露；
    在生成文本表格时写入 UTF-8 BOM 签名，确保在各类 Windows 办公套件中无乱码呈现。

    Args:
        destination: 导出目标文件的存储路径。
        output: 待写出的结构化数据列表，包含工作表表头及行记录。
    """
    target = Path(destination)
    if target.suffix.lower() == ".xlsx":
        # 全新构建 Excel 工作簿，杜绝原始文件的格式残留、批注、隐藏属性或外部链接带出
        book = openpyxl.Workbook(write_only=True)
        for i, table in enumerate(output, 1):
            sheet = book.create_sheet(f"数据表{i}")
            sheet.append(table["columns"])
            # 物理行号仅用于审计定位，不作为业务数据写出，仅输出脱敏后的单元格向量
            for _, row in table["rows"]:
                sheet.append(["" if v is None else v for v in row])
        book.save(target)
    else:
        # 写入 UTF-8-SIG 编码头部，适配 Windows Excel 对中文 CSV/TSV 的识别
        with target.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream, delimiter="\t" if target.suffix.lower() == ".tsv" else ",")
            writer.writerow(output[0]["columns"])
            writer.writerows(r for _, r in output[0]["rows"])
