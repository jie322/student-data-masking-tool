# 旧版通用匿名化的配置模型。学生页面的规则应阅读 student_tool/rules.py；这里保留旧接口兼容。
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Optional


# 专门表示配置有误的异常，上层可以据此显示配置提示。
class ConfigError(ValueError):
    pass


# 描述要处理哪份文件、哪张表、哪一列，以及是否只提取单元格中的部分文字。
@dataclass
class ColumnSelector:
    file_pattern: str
    column_name: str
    sheet_name: Optional[str] = None
    extract_regex: Optional[str] = None

    # 创建配置对象后立即检查参数，防止无效配置流入后续处理。
    def __post_init__(self):
        if not self.file_pattern:
            raise ConfigError("file_pattern must not be empty")
        if not self.column_name:
            raise ConfigError("column_name must not be empty")
        if self.extract_regex is not None:
            try:
                compiled = re.compile(self.extract_regex)
            except re.error as e:
                raise ConfigError(f"extract_regex is invalid: {e}")
            if compiled.groups != 1:
                raise ConfigError(
                    "extract_regex must contain exactly one capturing "
                    f"group, found {compiled.groups}"
                )


# 给一类待替换信息配置代号前缀、数字宽度和所在列。
@dataclass
class EntityConfig:
    prefix: str
    width: int = 6
    columns: list = field(default_factory=list)

    # 创建配置对象后立即检查参数，防止无效配置流入后续处理。
    def __post_init__(self):
        if not (2 <= len(self.prefix) <= 10):
            raise ConfigError(f"prefix '{self.prefix}' must be 2-10 characters long")
        if not (4 <= self.width <= 12):
            raise ConfigError(f"width must be 4-12, got {self.width}")
        self.columns = [
            c if isinstance(c, ColumnSelector) else ColumnSelector(**c)
            for c in self.columns
        ]


# 整次通用匿名化任务的配置，汇集多类信息并检查前缀是否冲突。
@dataclass
class AnonConfig:
    entities: dict
    version: int = 1

    # 创建配置对象后立即检查参数，防止无效配置流入后续处理。
    def __post_init__(self):
        self.entities = {
            name: (e if isinstance(e, EntityConfig) else EntityConfig(**e))
            for name, e in self.entities.items()
        }
        prefixes = [e.prefix for e in self.entities.values()]
        if len(prefixes) != len(set(prefixes)):
            dupes = {p for p in prefixes if prefixes.count(p) > 1}
            raise ConfigError(f"entity prefixes are not unique: {sorted(dupes)}")

    # 把配置对象变成按名称取值的字典，便于保存与传递。
    def to_dict(self):
        return {
            "version": self.version,
            "entities": {name: asdict(e) for name, e in self.entities.items()},
        }

    # 从字典重建配置对象，并触发相同的参数校验。
    @classmethod
    def from_dict(cls, data):
        if "entities" not in data:
            raise ConfigError("config has no 'entities' key")
        return cls(version=data.get("version", 1), entities=data["entities"])


# 读取 JSON 配置文字并校验，返回配置对象。
def config_from_json(text: str) -> AnonConfig:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"invalid JSON: {e}")
    return AnonConfig.from_dict(data)


# 将配置对象转换为可保存成文件的 JSON 文字。
def config_to_json(config: AnonConfig) -> str:
    return json.dumps(config.to_dict(), ensure_ascii=False, indent=2)


# 从整个配置中挑出当前文件需要处理的列，按工作表与列名分组。
def columns_for_file(config: dict, file_pattern: str) -> dict:
    """config is a plain dict (not necessarily validated through
    AnonConfig -- it may be a "raw" JSON dict of the same shape).
    Returns {sheet_name: {column_name: {"entity": ..., "extract_regex": ...}}}
    for the columns whose `file_pattern` matches `file_pattern`. Shared by
    the streaming projection (`engine.py`) and by masking (`masker.py`) so
    the grouping logic is not duplicated."""
    result: dict = {}
    for entity_name, entity in config["entities"].items():
        for col in entity["columns"]:
            if col["file_pattern"] != file_pattern:
                continue
            sheet = col.get("sheet_name")
            per_sheet = result.setdefault(sheet, {})
            per_sheet[col["column_name"]] = {
                "entity": entity_name,
                "extract_regex": col.get("extract_regex"),
            }
    return result
