// Service Worker 管理页面资源缓存；它与处理表格的 js/worker.js 是不同后台任务。这里缓存程序资源，不接收学生文件内容。
// 缓存名称含版本；应用资源清单或部署策略变更时可更新版本以替换旧缓存。
const CACHE_NAME = "student-mask-v3-modules";
// 应用外壳清单：页面、脚本、算法和内置表；新增模块应同步登记。
const APP_SHELL = [
  "./",
  "index.html",
  "css/main.css",
  "js/config.js",
  "js/features/import.js",
  "js/features/processing.js",
  "js/main.js",
  "js/services/downloads.js",
  "js/services/engine.js",
  "js/services/report.js",
  "js/state.js",
  "js/theme.js",
  "js/ui/dom.js",
  "js/ui/feedback.js",
  "js/ui/files.js",
  "js/ui/results.js",
  "js/ui/rules.js",
  "js/worker/errors.js",
  "js/worker/legacy-handlers.js",
  "js/worker/network.js",
  "js/worker/runtime.js",
  "js/worker/student-handler.js",
  "js/worker.js",
  "py/config.py",
  "py/engine.py",
  "py/heuristics.py",
  "py/links.py",
  "py/mapping.py",
  "py/masker.py",
  "py/report.py",
  "py/restorer.py",
  "py/student.py",
  "py/student_tool/__init__.py",
  "py/student_tool/constants.py",
  "py/student_tool/exporters.py",
  "py/student_tool/masking.py",
  "py/student_tool/processor.py",
  "py/student_tool/readers.py",
  "py/student_tool/rules.py",
  "py/student_tool/safety.py",
  "vendor/jszip/jszip-3.10.1.min.js",
  "sample_data/students_100.csv",
  "sample_data/students_100.xlsx",
  "sample_data/students_edge_cases.csv",
];

// 安装阶段先准备基本资源；waitUntil 表示安装要等这些异步操作完成。
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// 激活时清理旧版本缓存，再接管页面后续的资源请求。
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// Split by path, not by origin — everything is same-origin now (the
// no-CDN decision, design.md §9.1), but that doesn't mean everything is
// immutable:
// - "vendor/" (Pyodide runtime + wheels): pinned to a specific version by
//   us, never changes for a given deploy — cache-first, cache forever.
//   This is what makes the offline run possible after the first load.
// - everything else (our own HTML/JS/CSS/PY): changes between deploys —
//   network-first with `cache: "no-store"` (bypassing the browser's own
//   HTTP cache, not just Cache Storage), falling back to cache offline.
// 只接管读取请求：vendor 依赖优先用缓存，业务源码优先读本机服务的新版本。
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  const isVendored = url.origin === self.location.origin && url.pathname.includes("/vendor/");

  // 第三方依赖版本固定，命中缓存可直接使用；缺少时读取并补进缓存。
  if (isVendored) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  event.respondWith(
    // 页面与算法可能更新，所以先读取最新文件；无法读取时再使用已有缓存。
    fetch(event.request, { cache: "no-store" })
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
