/**
 * 界面词汇表与元数据枚举配置模块 (UI Schema & Label Mappings)。
 * 维护系统底层数据模型代码至前端标准化中文交互文案的双向语义映射。
 */

// 敏感字段语义类别映射字典 (内部类型标识符 -> 标准中文类型名称)
export const types = {
  phone: "手机号",
  email: "邮箱",
  identity: "身份证号",
  name: "姓名",
  identifier: "学号 / 身份标识",
  address: "地址",
  text: "敏感文本",
  other: "普通字段",
};

// 脱敏操作模式映射字典 (内部模式标识符 -> 标准中文操作名称)
export const modes = {
  keep: "保留原值",
  mask: "部分遮盖",
  full: "全部隐藏",
  drop: "删除此列",
};

// 批处理审计统计指标映射字典 (引擎计数器标识符 -> 审计报告中文统计标签)
export const statLabels = {
  input_rows: "导入行数",
  output_rows: "保留行数",
  masked_cells: "脱敏单元格",
  anomaly_rows: "异常行数",
  skipped_rows: "隔离行数",
  residual_cells: "敏感残留",
  formula_cells: "公式文本转义数",
};
