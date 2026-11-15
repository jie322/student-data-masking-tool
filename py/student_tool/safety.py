"""安全防御与敏感残留检测模块：提供 CSV/Excel 公式注入转义防护、敏感原文字典跨列扫描及全表残留安全审计机制。"""

import re

from .constants import HIDDEN, INVALID, LEAK, REASONS, TOKEN


def safe_cell(value):
    """单元格公式注入防护清洗：对以 '=, +, -, @' 起始的字符串添加前导单引号转义，防止执行恶意公式。

    Args:
        value: 待导出的单元格值。

    Returns:
        tuple: (escaped_value, did_escape_bool)，指示转义后的安全值及是否发生公式字符转义。
    """
    # 符合 +86 规范的大陆手机号仅包含数字与星号掩码，无公式注入风险，放行不予转义
    if isinstance(value, str) and re.fullmatch(r"\+86 [0-9*]{11}", value):
        return value, False
    # 针对以 '=, +, -, @' 开头且非纯数字/浮点数的字符串注入单引号前缀，强制表格软件按普通文本解析
    if isinstance(value, str) and re.match(r"^[\s\ufeff]*[=+\-@]", value) and not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return "'" + value, True
    return value, False


def build_secret_pattern(tables, rules):
    """收集批次内已标记敏感字段的原始明文，构建跨列残留检索的正则表达式字典。

    Args:
        tables: 原始数据表列表。
        rules: 列规则映射表。

    Returns:
        re.Pattern or None: 编译后的多模式正则扫描对象（按原文字符串长度降序排序以实现最长匹配）。
    """
    raw_secrets = set()
    for table in tables:
        for row in table["rows"]:
            for j, column in enumerate(table["columns"]):
                # 仅收集已明确标记为敏感类型的列明文；过滤系统占位符、历史代号及含星号字段
                if j < len(row) and row[j] is not None and rules[column]["type"] != "other":
                    text = str(row[j]).strip()
                    if len(text) >= 2 and text not in (HIDDEN, INVALID) and not TOKEN.fullmatch(text) and "*" not in text:
                        raw_secrets.add(text)
    # 按字符串长度降序排序并使用 re.escape 转义元字符，确保正则引擎优先匹配长敏感词并防止正则注入
    return re.compile("|".join(re.escape(s) for s in sorted(raw_secrets, key=len, reverse=True))) if raw_secrets else None


def scan_output(output, secret_pattern, preview_rows):
    """全量扫描待导出表格（包括表头与所有数据行），检测未脱敏残留并生成安全审计报告。

    Args:
        output: 待导出表格的结构化数据列表。
        secret_pattern: 批次敏感原文明文正则扫描模式。
        preview_rows: 前端安全预览截取的最大行数。

    Returns:
        dict: 包含预览表结构 (sheets)、残留告警清单 (issues)、统计摘要 (summary) 及熔断阻断标记 (blocked)。
    """
    previews, issues = [], []
    summary = {"residual_cells": 0, "output_rows": 0}
    blocked = False

    for sheet_index, table in enumerate(output, 1):
        safe_rows = []
        # 将表头作为第 1 行与全量数据行一同纳入审计范围，严防敏感明文通过动态列名隐蔽泄露
        for row_number, row in [(1, table["columns"])] + table["rows"]:
            display_row = []
            for j, value in enumerate(row, 1):
                text = "" if value is None else str(value)
                # 双重检测机制：1) 通用敏感格式扫描（手机/身份证/邮箱）；2) 当前批次敏感原文字典跨列比对
                residual = not TOKEN.fullmatch(text) and (LEAK.search(text) or (secret_pattern and secret_pattern.search(text)))
                if residual:
                    summary["residual_cells"] += 1
                    issues.append({
                        "sheet": f"数据表{sheet_index}", "row": row_number,
                        "column": table["indices"][j - 1] + 1,
                        "code": "residual", "reason": REASONS["residual"],
                    })
                    blocked = True
                display_row.append("〔检测到敏感残留〕" if residual else value)
            if row_number == 1:
                display_columns = display_row
            # 持续进行整表安全审计，仅截取前 preview_rows 行供前端安全预览展示
            elif len(safe_rows) < preview_rows:
                safe_rows.append(display_row)
        previews.append({"label": f"数据表{sheet_index}", "columns": display_columns, "rows": safe_rows, "count": len(table["rows"])})
        summary["output_rows"] += len(table["rows"])
    return {"sheets": previews, "issues": issues, "summary": summary, "blocked": blocked}
