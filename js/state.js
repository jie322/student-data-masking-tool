/**
 * 全局状态管理模块 (Application State Store)。
 * 维护内存级响应式状态对象，纯前端内存无状态管理，
 * 页面刷新或重置后彻底释放，不持久化任何表格数据。
 */

// 当前会话加载的文件对象记录列表（包含文件索引、格式、内容哈希指纹及工作表元数据）
export const files = [];

// 全局列级脱敏规则映射表 (Column Name -> Rule Configuration Object)；同名列批次共享配置
export const rules = new Map();

// 应用程序全局响应式状态上下文
export const state = {
  ready: false,        // 计算引擎 (Pyodide Worker) 是否就绪
  busy: false,         // 当前是否存在执行中的异步批处理任务
  fileSequence: 1,     // 新增导入文件的自增编号序列
};
