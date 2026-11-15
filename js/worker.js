/**
 * Web Worker 后台计算沙箱主入口模块 (Background Computation Sandbox Entrypoint)。
 * 负责沙箱安全隔离限制注入 (Network Guard)、WebAssembly Python 运行时拉起 (Pyodide)
 * 以及任务路由分发（元数据提取、前瞻样本预览、全量批量处理与旧版兼容接口）。
 */
import { installNetworkGuard } from "./worker/network.js";
import { loadRuntime } from "./worker/runtime.js";
import { handleStudent } from "./worker/student-handler.js";
import { createLegacyHandlers } from "./worker/legacy-handlers.js";

// 注入网络安全守卫策略：严格限制沙箱网络请求仅限本地 vendor/ 与 py/ 静态资源
const fetchedVendorUrls = installNetworkGuard();
const post = (message, transfer) => self.postMessage(message, transfer);
let pyodide;
let legacyHandlers = {};

/**
 * 异步初始化计算沙箱运行时环境：
 * 载入 Pyodide WebAssembly 内核、导入 openpyxl 纯 Python Wheel、挂载业务源码并上报就绪状态。
 */
async function init() {
  try {
    pyodide = await loadRuntime(post, fetchedVendorUrls);
    legacyHandlers = createLegacyHandlers(pyodide, post);
    post({ type: "ready", vendorAssets: Array.from(fetchedVendorUrls) });
  } catch {
    post({
      type: "error",
      message: "处理引擎加载失败。请检查本地服务；若 IDM 拦截了 ZIP 请求，请关闭其浏览器集成后刷新。",
    });
  }
}

/**
 * 监听主线程派发的消息事件并执行任务分发：
 * - init: 初始化运行沙箱
 * - student-inspect / student-preview / student-process: 学生信息表业务脱敏任务
 * - legacy: 兼容性通用脱敏接口
 */
self.onmessage = ({ data: message }) => {
  if (message.type === "init") {
    init();
  } else if (["student-inspect", "student-preview", "student-process"].includes(message.type)) {
    handleStudent(pyodide, message, post);
  } else if (Object.hasOwn(legacyHandlers, message.type)) {
    legacyHandlers[message.type](message);
  } else {
    post({ type: "error", message: "unknown message type: " + message.type });
  }
};
