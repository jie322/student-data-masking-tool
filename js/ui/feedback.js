/**
 * 界面反馈与交互状态同步模块 (Feedback & State Synchronization UI Controller)。
 * 统一管理系统运行日志追踪、全局提示信息、表单组件忙碌态锁定与历史处理结果失效回收。
 */
import { files, state } from "../state.js";
import { $ } from "./dom.js";
import { clearDownloads } from "../services/downloads.js";

/**
 * 追加一条操作审计日志至终端展示窗口。
 * 遵循隐私安全准则：仅接收系统状态与统计数字，禁止传入单元格敏感明文或私有路径。
 * @param {string} message 日志文本。
 */
export function log(message) {
  $("log").textContent += message + "\n";
  $("log").scrollTop = $("log").scrollHeight;
}

/**
 * 渲染或清除界面顶部全局通告消息。
 * @param {string} [message=""] 提示信息文本。
 * @param {boolean} [error=false] 是否标识为错误级别高亮展示。
 */
export function notice(message = "", error = false) {
  $("message").textContent = message;
  $("message").hidden = !message;
  $("message").className = "message" + (error ? " error" : "");
}

/**
 * 全局表单组件忙碌态锁定控制器：依据引擎就绪状态、异步批处理锁及导入有效性联动组件可交互性。
 * @param {boolean} value 是否处于忙碌阻塞状态。
 */
export function setBusy(value) {
  state.busy = value;
  for (const id of ["fileInput", "sampleBtn", "edgeBtn"]) {
    $(id).disabled = state.busy || !state.ready;
  }
  document.querySelector(".file-picker").classList.toggle("disabled", state.busy || !state.ready);
  for (const id of ["clearBtn", "resetRulesBtn"]) {
    $(id).disabled = state.busy || !files.length;
  }
  // 存在格式解析异常的文件时禁用处理按钮，强制用户前置修正或移除损坏文件
  for (const id of ["processBtn", "previewBtn"]) {
    $(id).disabled = state.busy || !state.ready || !files.length || files.some((f) => !f.meta);
  }
  $("anomalyPolicy").disabled = state.busy;
  // 恢复规则输入框状态时，尊重列模式特定的非激活数据属性 (data-inactive)
  document.querySelectorAll("#rulesBody select, #rulesBody input, #fileList button").forEach((el) => {
    el.disabled = state.busy || el.dataset.inactive === "true";
  });
}

/**
 * 标记当前处理结果失效并清理视觉暂存：
 * 回收内存中的下载 URL，隐藏导出入口，重置预览区与告警面板。
 * @param {string} [message="配置已变更，请重新预览或开始批量脱敏。"] 失效占位引导文案。
 */
export function invalidate(message = "配置已变更，请重新预览或开始批量脱敏。") {
  clearDownloads();
  $("downloads").hidden = true;
  $("exportLink").removeAttribute("href");
  $("reportLink").removeAttribute("href");
  $("resultPreview").replaceChildren();
  $("issues").replaceChildren();
  $("resultSummary").className = "empty";
  $("resultSummary").textContent = message;
}
