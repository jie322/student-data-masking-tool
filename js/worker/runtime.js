/**
 * WebAssembly Python 运行时载入与虚拟文件系统挂载服务 (Pyodide Runtime Loader)。
 * 负责离线加载 Pyodide WebAssembly 内核、通过 micropip 本地安装 openpyxl 及其依赖 Wheel、
 * 并在沙箱内存虚拟文件系统 (Emscripten MEMFS /app) 中构建源码目录树与环境初始化。
 */
const PYODIDE_INDEX = new URL("../../vendor/pyodide/", import.meta.url).href;
const WHEELS = [
  new URL("../../vendor/wheels/et_xmlfile-2.0.0-py3-none-any.whl", import.meta.url).href,
  new URL("../../vendor/wheels/openpyxl-3.1.5-py2.py3-none-any.whl", import.meta.url).href,
];

// 需要同步挂载到沙箱内存虚拟文件系统 (/app) 的 Python 业务模块清单
const PY_MODULES = [
  "config.py",
  "heuristics.py",
  "engine.py",
  "mapping.py",
  "masker.py",
  "restorer.py",
  "report.py",
  "student.py",
  "student_tool/__init__.py",
  "student_tool/constants.py",
  "student_tool/exporters.py",
  "student_tool/masking.py",
  "student_tool/processor.py",
  "student_tool/readers.py",
  "student_tool/rules.py",
  "student_tool/safety.py",
];

/**
 * 完整拉起并初始化 Pyodide 沙箱环境。
 * @param {Function} post 状态上报回调函数。
 * @param {Set} fetchedVendorUrls 本地依赖加载跟踪集合。
 * @returns {Promise<any>} 初始化完毕的 Pyodide 实例。
 */
export async function loadRuntime(post, fetchedVendorUrls) {
  const status = (text) => post({ type: "status", text });
  status("正在加载本地处理引擎……");

  // 记录动态 import 载入的 Pyodide 核心脚本
  fetchedVendorUrls.add(PYODIDE_INDEX + "pyodide.mjs");
  const { loadPyodide } = await import(PYODIDE_INDEX + "pyodide.mjs");

  // 初始化 Pyodide 实例，拦截静默 stdout/stderr 避免用户数据在沙箱日志中泄露
  const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX, stdout: () => {}, stderr: () => {} });
  status("本地引擎已加载。");

  status("正在加载 Excel 读写组件……");
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");
  // 严格从本地 vendor/wheels/ 离线安装依赖包，杜绝任何外部公网网络通信
  await micropip.install(WHEELS);
  status("Excel 读写组件已就绪。");

  // 在 Emscripten MEMFS 虚拟内存文件系统中创建 /app 根目录并同步源码
  pyodide.FS.mkdirTree("/app");
  for (const name of PY_MODULES) {
    const response = await fetch(new URL("../../py/" + name, import.meta.url));
    if (!response.ok) throw new Error("Python module unavailable");
    const path = "/app/" + name;
    pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
    pyodide.FS.writeFile(path, await response.text());
  }

  // 配置 Python sys.path 搜索路径并预热导入核心脱敏模块
  pyodide.runPython("import sys\nsys.path.insert(0, '/app')");
  await pyodide.runPythonAsync("import config, engine, mapping, masker, restorer, report, student");
  status("表格处理引擎已就绪。");
  return pyodide;
}
