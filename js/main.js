/**
 * 前端应用交互主入口模块 (Application Entrypoint)。
 * 负责生命周期编排：UI 组件事件监听注册、本地脱敏计算引擎初始化拉起以及 Service Worker 离线缓存声明。
 */
import { files, rules, state } from "./state.js";
import { $ } from "./ui/dom.js";
import { invalidate, log, notice, setBusy } from "./ui/feedback.js";
import { renderFiles } from "./ui/files.js";
import { rebuildRules, renderRules } from "./ui/rules.js";
import { importFiles, loadSample } from "./features/import.js";
import { previewResults, processFiles } from "./features/processing.js";
import { bindDownloadLinks } from "./services/downloads.js";
import { startEngine } from "./services/engine.js";

// 1. 注册文件选择变更事件：捕获文件列表并调度导入解析管道
$("fileInput").addEventListener("change", async () => {
  const selected = [...$("fileInput").files];
  // 重置 Input 的 FileList 状态，允许用户连续选取同名或同一磁盘文件
  $("fileInput").value = "";
  await importFiles(selected);
});

// 2. 绑定演示样本快捷载入：提供标准百人学生表与极限边界异常表的快速导入验证
$("sampleBtn").addEventListener("click", () => loadSample("students_100.csv"));
$("edgeBtn").addEventListener("click", () => loadSample("students_edge_cases.csv"));

// 3. 重置与清空交互：释放前端内存数据结构，重置文件队列、规则映射与结果预览状态
$("clearBtn").addEventListener("click", () => {
  files.length = 0;
  rules.clear();
  state.fileSequence = 1;
  renderFiles();
  renderRules();
  invalidate("导入表格并配置规则后，点击“预览脱敏效果”查看处理后的数据样式。");
  notice();
  $("sourceDetails").open = false;
  log("已清空本次导入和结果，原文件未修改。");
});

// 4. 规则变更防呆联动：当规则重置或异常策略变更时，标记旧脱敏结果失效以防数据状态不一致
$("resetRulesBtn").addEventListener("click", () => { rebuildRules(true); invalidate(); });
$("anomalyPolicy").addEventListener("change", () => invalidate());

// 5. 编排脱敏执行事件：分别绑定轻量级前瞻样本预览与全量批量脱敏流水线
$("previewBtn").addEventListener("click", previewResults);
$("processBtn").addEventListener("click", processFiles);

// 6. 注册跨平台导出下载通道：自动适配浏览器 Blob 虚拟下载与桌面端 Win32 视窗保存对话框
bindDownloadLinks(notice);

// 7. 注册 PWA 离线资源缓存服务 (Service Worker)
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => log("离线缓存未启用；本地服务运行时仍可使用。"));
}

// 8. 初始化就绪态并启动脱敏后台引擎 (Web Worker + Pyodide)
setBusy(false);
startEngine();
