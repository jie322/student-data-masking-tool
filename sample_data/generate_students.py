# 维护 100 条学生记录和异常校验表；手动运行会重新生成此目录的数据文件。
"""维护学生信息表和字段校验数据。"""

import csv
from pathlib import Path
from random import Random

from openpyxl import Workbook


# 一份学生表的 16 个字段；同一顺序同时用于 CSV 和 Excel。
HEADERS = [
    "学号", "姓名", "性别", "年级", "班级", "出生日期", "手机号",
    "身份证号", "邮箱", "家庭住址", "语文成绩", "数学成绩", "英语成绩",
    "监护人手机号", "备用邮箱", "校园卡号",
]


# 由地区码、出生日期和顺序号组成前 17 位，再计算第 18 位校验码。
def identity(number, birth_date, region="110108"):
    # 按 18 位号码结构计算校验码。
    base = region + birth_date.replace("-", "") + f"{number:03d}"
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    return base + "10X98765432"[sum(int(n) * w for n, w in zip(base, weights)) % 11]


# 按固定表头保存 CSV，使用带 BOM 的 UTF-8 方便识别中文。
def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(HEADERS)
        writer.writerows(rows)


# 生成正常学生记录和边界记录，并分别保存为 CSV、Excel。
def main():
    # 固定生成顺序，便于重复运行时复现同一组数据和测试结果。
    rng = Random(8)
    rows = []
    surnames = [("李", "li"), ("王", "wang"), ("张", "zhang"), ("刘", "liu"), ("陈", "chen"), ("杨", "yang"), ("赵", "zhao"), ("黄", "huang"), ("周", "zhou"), ("吴", "wu")]
    given_names = [("明轩", "mingxuan"), ("梓涵", "zihan"), ("宇航", "yuhang"), ("欣怡", "xinyi"), ("浩然", "haoran"), ("雨桐", "yutong"), ("俊杰", "junjie"), ("诗涵", "shihan"), ("子墨", "zimo"), ("佳宁", "jianing")]
    locations = [("北京市海淀区", "110108"), ("上海市杨浦区", "310110"), ("江苏省南京市鼓楼区", "320106"), ("浙江省杭州市西湖区", "330106"), ("湖北省武汉市洪山区", "420111")]
    phone_numbers = set()

    # 从预设号段生成 11 位号码，并统一加 +86 前缀。
    def phone_number():
        while True:
            phone = rng.choice(("138", "139", "150", "158", "166", "177", "188")) + f"{rng.randrange(100_000_000):08d}"
            if phone not in phone_numbers:
                phone_numbers.add(phone)
                return "+86 " + phone

    for number in range(1, 101):
        birth_date = f"2005-{number % 12 + 1:02d}-{number % 28 + 1:02d}"
        surname, surname_pinyin = surnames[(number - 1) // 10]
        given_name, given_pinyin = given_names[(number - 1) % 10]
        location, region = locations[(number - 1) % len(locations)]
        local = f"{surname_pinyin}.{given_pinyin}{number:03d}"
        domain = ("qq.com", "163.com", "outlook.com")[(number - 1) % 3]
        rows.append([
            f"2023{number:06d}",
            surname + given_name,
            "男" if number % 2 else "女",
            "2023级",
            f"计算机230{(number - 1) % 5 + 1}班",
            birth_date,
            phone_number(),
            identity(number, birth_date, region),
            f"{local}@{domain}",
            f"{location}{('学院路', '文华路', '长青路', '建设路', '湖滨路')[(number - 1) % 5]}{20 + number}号{number % 6 + 1}栋{100 + number}室",
            rng.randint(60, 100),
            rng.randint(60, 100),
            rng.randint(60, 100),
            phone_number(),
            f"{surname_pinyin}{given_pinyin}{number:03d}@126.com",
            f"CARD2023{number:06d}",
        ])

    output_dir = Path(__file__).resolve().parent
    save_csv(output_dir / "students_100.csv", rows)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "学生信息"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    from openpyxl.styles import Font, PatternFill, Alignment
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="193950")
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 27
    widths = [19, 14, 8, 12, 22, 14, 23, 25, 40, 46, 12, 12, 12, 23, 40, 23]
    from openpyxl.utils import get_column_letter
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for column in ("A", "G", "H", "N", "P"):
        for cell in sheet[column]:
            cell.number_format = "@"
    workbook.save(output_dir / "students_100.xlsx")

    edge = [r.copy() for r in rows[:12]]
    edge[0][6] = "+86 12345"                   # 手机位数错误
    edge[1][8] = "wang.zihan@@163.com"          # 邮箱格式错误
    edge[2][7] = rows[2][7][:-1] + ("1" if rows[2][7][-1] != "1" else "2")
    edge[3][1] = ""                            # 必填姓名为空
    edge[4][0] = ""                            # 必填学号为空
    edge[5][7] = identity(6, "2005-02-30")       # 日期错误，保留 18 位结构
    digits = edge[6][6].removeprefix("+86 ")
    edge[6][6] = "+86 " + digits[:3] + "****" + digits[-4:]
    edge[7][8] = "s***@***"                     # 已处理的邮箱
    edge[8] = edge[7].copy()                     # 重复标识
    edge[9][7] = edge[9][7][:3] + "*" * 13 + edge[9][7][-2:]  # 已处理的 18 位身份证
    edge[10][10] = "=1+1"                       # CSV 公式注入
    edge[11].append("多余列中的原文")             # 列数不一致
    save_csv(output_dir / "students_edge_cases.csv", edge)
    print("已更新 100 行学生信息（CSV、Excel）和 12 行字段校验数据。")


if __name__ == "__main__":
    main()
