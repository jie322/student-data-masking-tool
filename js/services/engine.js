/**
 * 计算引擎通信服务模块 (Engine Worker Client Service)。
 * 维护主线程与 Web Worker 计算沙箱的双向 RPC 消息通信，
 * 封装基于递增 RequestId 与 Promise 响应映射机制的异步调用协议。
 */
import { state } from "../state.js";
import { $ } from "../ui/dom.js";
import { log, notice, setBusy } from "../ui/feedback.js";

// 实例化计算沙箱 Worker 独立线程，防止复杂数据脱敏阻塞 UI 渲染帧
const worker = new Worker(new URL("../worker.js", import.meta.url), { type: "module" });

// 维护异步待决请求队列 (RequestId -> { resolve, reject })
const pending = new Map();
let nextId = 1;

/**
 * 向计算沙箱投递结构化指令并返回 Promise。
 * @param {string} type 任务类型标识（如 "student-inspect" | "student-preview" | "student-process"）。
 * @param {Object} data 负载数据。
 * @param {Transferable[]} [transfer=[]] 可转移对象（如 ArrayBuffer 零拷贝所有权移交）。
 * @returns {Promise<any>}
 */
export function request(type, data, transfer = []) {
  return new Promise((resolve, reject) => {
    const id = String(nextId++);
    pending.set(id, { resolve, reject });
    worker.postMessage({ type, id, ...data }, transfer);
  });
}

// 监听沙箱返回的消息协议并分发处理
worker.onmessage = ({ data }) => {
  // 1. 运行时加载状态推进
  if (data.type === "status") {
    log(data.text);
    $("status").textContent = data.text;
  }
  // 2. 引擎全量环境初始化完毕
  if (data.type === "ready") {
    state.ready = true;
    $("status").textContent = "引擎已就绪 · 文件在本机处理";
    $("status").className = "status ready";
    $("loadProgress").hidden = true;
    log("可以导入学生信息表。");
    setBusy(false);
  }
  // 3. 引擎启动异常
  if (data.type === "error") {
    $("status").textContent = data.message;
    $("status").className = "status error";
    $("loadProgress").hidden = true;
    notice(data.message, true);
    log("处理引擎未能启动，请检查本地环境。");
  }
  // 4. 业务任务执行完毕：依据 RequestId 唤醒对应 Promise
  if (data.type === "student-result") {
    const task = pending.get(data.id);
    pending.delete(data.id);
    if (task) {
      data.error ? task.reject(new Error(data.error)) : task.resolve(data);
    }
  }
};

// 监听 Worker 未捕获异常并熔断所有处于 Pending 状态的请求
worker.onerror = () => {
  notice("处理进程意外停止，请刷新页面后重新导入。", true);
  log("处理进程意外停止，未导出新文件。");
  for (const task of pending.values()) {
    task.reject(new Error("处理进程已停止。"));
  }
  pending.clear();
  state.ready = false;
  setBusy(false);
};

/**
 * 触发计算沙箱环境初始化流程（加载 Pyodide、openpyxl、脱敏业务脚本）。
 */
export function startEngine() {
  worker.postMessage({ type: "init" });
}
