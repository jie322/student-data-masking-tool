"""面向学生信息表的批量脱敏核心工具包 (student_tool)。

提供表格只读解析、智能别名推断、单元格规范化清洗与脱敏掩码、批处理管道编排及全量安全审计等核心功能。
"""

from .masking import mask_value
from .processor import preview_file, process_file
from .readers import inspect_file, read_tables
from .rules import recommend, validate_rules

__all__ = [
    "inspect_file",
    "mask_value",
    "preview_file",
    "process_file",
    "read_tables",
    "recommend",
    "validate_rules",
]
