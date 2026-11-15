"""多源异构表格数据解析模块：支持 CSV、TSV、Excel (XLSX) 的只读流式解析、编码自适应探测与样本元数据提取。"""

import csv
import datetime as dt
import io
from pathlib import Path

import openpyxl

from .rules import recommend


def read_tables(path):
    """解析指定格式的数据文件，将其规整为包含表头和数据行的标准内存结构。

    支持自动探测 UTF-8-SIG 与 GB18030 字符集编码，保留单元格原始文本，杜绝长整型标识符（如学号、身份证）被错误转为科学计数法或浮点数。

    Args:
        path: 源文件路径字符串或 Path 对象。

    Returns:
        list[dict]: 各工作表解析结果构成的列表，每个元素包含 "columns"（列名列表）与 "rows"（行数据二维列表）。

    Raises:
        ValueError: 遭遇不支持的格式、文件体积超标 (25MB)、行列不合规或总行数超过 10 万行限制。
    """
    ext = Path(path).suffix.lower()
    if ext not in (".csv", ".tsv", ".xlsx"):
        raise ValueError("只支持 CSV、TSV 和 XLSX；旧版 XLS 请先另存为 XLSX。")
    if Path(path).stat().st_size > 25 * 1024 * 1024:
        raise ValueError("单个文件不能超过 25 MB。")

    if ext == ".xlsx":
        # 针对 Excel 启用轻量只读模式 (read_only=True)，读取包括隐藏表在内的全量工作表原始值
        book = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
        try:
            raw = [(sheet.title, [list(row) for row in sheet.values]) for sheet in book.worksheets]
        finally:
            book.close()
    else:
        # 纯文本表格优先尝试 UTF-8 BOM 解码；解码失败时自动回退至常见中文 GB18030 编码
        content = Path(path).read_bytes()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("gb18030")
        raw = [("数据表1", list(csv.reader(io.StringIO(text), delimiter="\t" if ext == ".tsv" else ",", strict=True)))]

    tables = []
    count = 0
    for _, rows in raw:
        if not rows:
            continue
        # 提取首行作为表头列名：拦截包含空白列名或同名重名列的异常表格，防止列映射歧义
        headers = [str(value).strip() if value is not None else "" for value in rows[0]]
        if not all(headers) or len(set(headers)) != len(headers):
            raise ValueError("表头存在空列名或重复列名，请整理表头后重新导入。")
        # 跨工作表累计计算有效数据行数，严控单文件 10 万行性能安全阈值
        count += len(rows) - 1
        if count > 100_000:
            raise ValueError("单个文件最多处理 100000 行，请拆分后导入。")
        # 规整有效数据行（排除首行表头）
        tables.append({"columns": headers, "rows": rows[1:]})

    if not tables:
        raise ValueError("文件中没有可读取的数据表。")
    return tables


def json_value(value):
    """单元格数值类型序列化转换：将日期、时间等富类型转换为 ISO-8601 标准字符串，基础标量类型保持原值。"""
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


def inspect_file(path):
    """读取文件元数据并抽取前 5 行样本数据，生成各列的推荐脱敏规则配置供前端初次展示与核对。"""
    tables = read_tables(path)
    return {"sheets": [
        {"label": f"数据表{i + 1}", "columns": t["columns"], "rows": [[json_value(v) for v in r] for r in t["rows"][:5]], "count": len(t["rows"]),
         "rules": {c: recommend(c) for c in t["columns"]}}
        for i, t in enumerate(tables)
    ], "row_count": sum(len(t["rows"]) for t in tables)}
