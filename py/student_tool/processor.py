"""表格批处理管道编排模块：负责规则前置校验、多工作表逐行脱敏、多级异常策略分流、残留安全扫描及最终导出写出。"""

from pathlib import Path

from .constants import REASONS
from .exporters import write_tables
from .masking import mask_value, normalized
from .readers import json_value, read_tables
from .rules import validate_rules
from .safety import build_secret_pattern, safe_cell, scan_output


def process_tables(tables, rules, policy="mask", secret="", preview_rows=10, destination=None):
    """编排并执行表格数据的完整脱敏处理流程，实施安全审计与条件写出。

    Args:
        tables: 包含 columns（表头）与 rows（数据行二维列表）的工作表字典列表。
        rules: 列名至脱敏规则的配置映射。
        policy: 异常处理策略，可选 "mask"（异常字段占位隐藏）、"skip"（整行跳过隔离）、"stop"（阻断整批导出）。
        secret: 兼容性密钥参数。
        preview_rows: 前端样本预览保留的最大行数（默认 10）。
        destination: 导出文件输出路径；为 None 时仅在内存中处理并不生成磁盘文件。

    Returns:
        dict: 包含处理统计指标 (summary)、安全告警列表 (issues)、预览工作表 (sheets) 及是否阻断导出标记 (blocked)。
    """
    # 步骤一：前置配置及策略合法性强校验，防止携带非法配置进入数据流水线
    validate_rules(rules)
    if policy not in ("mask", "skip", "stop"):
        raise ValueError("异常处理方式无效。")
    if any(c not in rules for t in tables for c in t["columns"]):
        raise ValueError("有字段未配置规则，请重新检查列配置。")
    if not any(r["mode"] != "keep" for r in rules.values()):
        raise ValueError("请至少配置一个脱敏或删除规则。")

    issues, output = [], []
    summary = {"input_rows": 0, "output_rows": 0, "anomaly_rows": 0, "skipped_rows": 0, "masked_cells": 0, "residual_cells": 0, "formula_cells": 0}

    # 记录结构化异常事件：仅保存表名、物理行列号、问题代码及标准化原因，杜绝敏感原值进入报告
    def issue(sheet, row, column, code):
        issues.append({"sheet": f"数据表{sheet}", "row": row, "column": column, "code": code, "reason": REASONS[code]})

    # 提取批次内标记为敏感字段的原始文本，编译为用于跨列残留检测的正则模式
    secret_pattern = build_secret_pattern(tables, rules)

    # 步骤二：逐个工作表执行行级流式处理；kept 保存非删除 (drop) 列在原表中的索引
    for sheet_index, table in enumerate(tables, 1):
        columns = table["columns"]
        kept = [j for j, c in enumerate(columns) if rules[c]["mode"] != "drop"]
        if not kept:
            raise ValueError("不能删除全部列。")
        rows_out, seen = [], set()

        # 数据行号从 2 起算，与 Excel 表格用户视图对应（第 1 行为表头）
        for row_number, row in enumerate(table["rows"], 2):
            summary["input_rows"] += 1
            before = len(issues)
            if len(row) != len(columns):
                issue(sheet_index, row_number, 0, "width")
            # 规整行宽：补齐缺失单元格或截断超宽列以保障列对齐，列宽异常行后续将被强制隔离
            padded = (row + [None] * len(columns))[:len(columns)]
            # 提取本行唯一性标识字段（如学号），与已处理集合比对以判定行间重复异常
            identifiers = {(j, normalized(padded[j], "identifier")) for j, c in enumerate(columns) if rules[c]["type"] == "identifier" and padded[j] is not None and str(padded[j]).strip()}
            if identifiers & seen:
                issue(sheet_index, row_number, 0, "duplicate")
            seen.update(identifiers)

            # 遍历保留列并调用单元格脱敏引擎，累计单元格脱敏计数
            processed, changed = [], 0
            for j in kept:
                value, code, did_change = mask_value(padded[j], rules[columns[j]], secret)
                if code:
                    issue(sheet_index, row_number, j + 1, code)
                # 对潜在公式注入字符 (=, +, -, @) 进行转义，消除 CSV/Excel 宏执行安全隐患
                value, formula = safe_cell(json_value(value))
                if formula:
                    summary["formula_cells"] += 1
                    issue(sheet_index, row_number, j + 1, "formula")
                changed += did_change
                processed.append(value)

            # 判定当前行是否存在业务异常（公式转义与已脱敏重算仅记录，不标记为结构性异常行）
            anomaly = any(i["code"] not in ("formula", "remasked") for i in issues[before:])
            if anomaly:
                summary["anomaly_rows"] += 1

            # 异常策略分流：列宽异常强制隔离；在 "skip" 策略下出现数据异常的行亦执行整行跳过隔离
            if len(row) != len(columns) or (anomaly and policy == "skip"):
                summary["skipped_rows"] += 1
                continue
            rows_out.append((row_number, processed))
            summary["masked_cells"] += changed

        output.append({"columns": [safe_cell(columns[j])[0] for j in kept], "rows": rows_out, "indices": kept})

    # 步骤三：执行全局敏感残留深度审计，覆盖全量输出行与表头（非仅限于预览子集）
    checked = scan_output(output, secret_pattern, preview_rows)
    issues.extend(checked["issues"])
    summary.update(checked["summary"])

    # 熔断阻断策略：一旦发现敏感残留，或在 "stop" 策略下触发任何数据异常，立即阻断数据导出
    blocked = checked["blocked"] or (policy == "stop" and summary["anomaly_rows"] > 0)

    # 步骤四：仅当安全审计全数通过且已指定合法目标路径时，方可持久化写入磁盘文件
    if not blocked and destination is not None:
        write_tables(destination, output)
    return {"summary": summary, "issues": issues, "sheets": checked["sheets"], "blocked": blocked}


def preview_file(source, rules, policy="mask", secret="", preview_rows=10):
    """读取数据文件前 N 行样本并执行脱敏处理，返回用于前端预览的数据结构，不产生磁盘导出文件。"""
    tables = read_tables(source)
    for table in tables:
        table["rows"] = table["rows"][:preview_rows]
    return process_tables(tables, rules, policy, secret, preview_rows)


def process_file(source, destination, rules, policy="mask", secret="", preview_rows=10):
    """执行完整文件的全量脱敏批处理流程，实施目标路径防覆盖保护并输出统计与报告。"""
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError("导出路径不能覆盖原文件。")
    return process_tables(read_tables(source), rules, policy, secret, preview_rows, destination)
