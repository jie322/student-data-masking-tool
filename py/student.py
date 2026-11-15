"""学生信息脱敏引擎顶级聚合入口 (Facade)。

统一对外暴露 student_tool 内部的常量规范、格式校验、单元格掩码算法、表格管道编排及安全审计接口，
保障前端 Web Worker、自动化集成测试与本地批处理脚本的高兼容性调用。
"""

from student_tool.constants import ALIASES, EMAIL, HIDDEN, INVALID, LEAK, MODES, REASONS, TOKEN, TYPES
from student_tool.masking import already_masked, mask_value, normalize_phone, normalized, valid_identity
from student_tool.processor import preview_file, process_file, process_tables as _process_tables
from student_tool.readers import inspect_file, json_value, read_tables
from student_tool.rules import recommend, validate_rules
from student_tool.safety import safe_cell

__all__ = [
    "ALIASES", "EMAIL", "HIDDEN", "INVALID", "LEAK", "MODES", "REASONS", "TOKEN", "TYPES",
    "already_masked", "mask_value", "normalize_phone", "normalized", "valid_identity",
    "preview_file", "process_file", "inspect_file", "json_value", "read_tables",
    "recommend", "validate_rules", "safe_cell",
]
