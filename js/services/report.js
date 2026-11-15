/**
 * 结构化安全合规审计报告生成服务 (Compliance Audit Report Service)。
 * 将脱敏统计数据、物理行列位置及异常诊断事件聚合成标准 JSON 审计报告，
 * 遵循零敏感泄露原则：仅输出统计指标、坐标位置与枚举化异常说明，杜绝任何原始字段明文带出。
 */
import { types, modes, statLabels } from "../config.js";

// 将内部统计键名映射为面向用户的规范化中文名称
const chineseSummary = (summary) =>
  Object.fromEntries(Object.entries(summary).map(([key, value]) => [statLabels[key], value]));

// 输出去名化的字段脱敏规则元数据描述（使用 1-based 列物理位置索引）
const ruleDescription = (r, i) => ({
  列位置: i + 1,
  字段类型: types[r.type],
  处理方式: modes[r.mode],
  保留前位: r.prefix,
  保留后位: r.suffix,
  必填: r.required,
  保留邮箱域名: r.keep_domain,
});

/**
 * 组装结构化合规审计报告。
 * @param {Array} results 各文件处理结果集。
 * @param {Object} summary 批次汇总统计。
 * @param {boolean} blocked 是否处于熔断阻断状态。
 * @param {Map} rules 全局列脱敏规则映射。
 * @param {string} policyLabel 异常策略的中文语义标签。
 * @returns {Object} 符合合规归档规范的结构化报告对象。
 */
export function buildReport(results, summary, blocked, rules, policyLabel) {
  return {
    工具: "学生信息表批量脱敏与安全导出",
    导出状态: blocked ? "已阻止" : "检查通过",
    生成时间: new Date().toISOString(),
    汇总: chineseSummary(summary),
    异常处理: policyLabel,
    文件: results.map(({ file, result }) => ({
      编号: file.index,
      汇总: chineseSummary(result.summary),
      异常: result.issues.map((i) => ({
        数据表: i.sheet,
        原始行号: i.row,
        列位置: i.column || "整行",
        说明: i.reason,
      })),
      规则: file.meta.sheets.map((s) => ({
        数据表: s.label,
        字段配置: s.columns.map((c, i) => ruleDescription(rules.get(c), i)),
      })),
    })),
  };
}
