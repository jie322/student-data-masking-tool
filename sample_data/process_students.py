# 批量运行内置表格，生成脱敏结果、中文处理报告和待人工填写的核对清单。
"""处理学生信息表，生成脱敏结果、处理报告和人工核对清单。"""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py"))
from student import mask_value, process_file, read_tables, recommend

SECRET = "student-rules-verification-2026"
LABELS = {"input_rows":"导入行数", "output_rows":"保留行数", "anomaly_rows":"异常行数", "skipped_rows":"隔离行数", "masked_cells":"脱敏单元格", "residual_cells":"敏感残留", "formula_cells":"公式文本转义数"}


# 读取内置正常与异常表，比较处理前后源文件摘要，并保存核对材料。
def main():
    folder = Path(__file__).resolve().parent
    output = folder / "processed_output"
    output.mkdir(exist_ok=True)
    reports = []
    for stem, extension in (("students_100", "csv"), ("students_100", "xlsx"), ("students_edge_cases", "csv")):
        source = folder / f"{stem}.{extension}"
        rules = {c: recommend(c) for t in read_tables(source) for c in t["columns"]}
        # 记录源文件内容摘要；处理后再比较，可确认没有改动原文件。
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        result = process_file(source, output / f"{stem}_masked.{extension}", rules, "mask", SECRET)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, "源文件被修改"
        report = {"编号":len(reports) + 1, "原文件保持不变":True, "汇总":{LABELS[k]:v for k, v in result["summary"].items()}, "阻止导出":result["blocked"],
                  "异常":[{"数据表":i["sheet"], "原始行号":i["row"], "列位置":i["column"] or "整行", "说明":i["reason"]} for i in result["issues"]]}
        reports.append(report)
        print(f"文件{len(reports)}：导入 {result['summary']['input_rows']} 行，保留 {result['summary']['output_rows']} 行，异常 {result['summary']['anomaly_rows']} 行。")
    (output / "处理报告.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")

    # 预期值手工列出；这里仅生成核对清单，不冒称已完成人工复核。
    # 预期结果由此处明确列出，不根据算法临时推算，避免用程序证明自己。
    examples = [
        ("手机号", "+86 13962578301", "+86 139****8301"),
        ("手机号", "+86 15890214672", "+86 158****4672"),
        ("手机号", "+86 18835792046", "+86 188****2046"),
        ("手机号", "+86 12345", "〔异常值已隐藏〕"),
        ("邮箱", "li.mingxuan001@qq.com", "l***@***"),
        ("邮箱", "Wang.Zihan+school@outlook.com", "w***@***"),
        ("邮箱", "a@163.com", "***@***"),
        ("邮箱", "wang.zihan@@163.com", "〔异常值已隐藏〕"),
        ("身份证号", "110108200502020019", "110*************19"),
        ("姓名", "李明轩", "李**"),
        ("姓名", "李", "*"),
        ("家庭住址", "北京市海淀区学院路21号2栋101室", "〔已隐藏〕"),
    ]
    with (folder / "人工核对样本.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["序号", "字段", "原始值", "预期结果", "实际结果", "自动比较", "人工核对结论（待填写）"])
        for i, (column, original, expected) in enumerate(examples, 1):
            # 自动比较只说明这条样本符合预期；人工结论仍留待实际核对后填写。
            actual = mask_value(original, recommend(column), SECRET)[0]
            writer.writerow([i, column, original, expected, actual, "一致" if expected == actual else "不一致", "待人工核对"])
            assert actual == expected, f"核对样本{i}未通过"
    print("已生成 12 项待人工复核样本；运行日志未输出任何敏感原文。")


if __name__ == "__main__":
    main()
