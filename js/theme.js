/**
 * UI 主题偏好管理与防闪烁加载模块 (Theme Manager & FOUC Prevention)。
 * 页面首屏渲染前读取持久化偏好，防止深色/浅色模式切换时的样式闪烁 (FOUC)，
 * 支持 Web 端 localStorage 与桌面端 pywebview 偏好文件的双向同步。
 */
(() => {
  const key = "student-mask-theme";
  // 手动切换状态脏标记：防止桌面端异步加载的旧偏好覆盖用户刚触发的手动切换
  let changed = false;

  /**
   * 应用主题至 DOM 根节点并更新无障碍可访问性属性 (ARIA)。
   * @param {string} theme 主题名称 ("dark" | "light")。
   */
  function apply(theme) {
    const dark = theme !== "light";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    const button = document.getElementById("themeToggle");
    if (button) {
      button.textContent = dark ? "切换亮色" : "切换暗色";
      button.setAttribute("aria-label", dark ? "切换到亮色模式" : "切换到暗色模式");
      button.setAttribute("aria-pressed", String(dark));
    }
  }

  // 立即执行初始化，优先读取本地缓存，异常时平滑回退至 dark 暗色主题
  try {
    apply(localStorage.getItem(key) || "dark");
  } catch {
    apply("dark");
  }

  // DOM 就绪后绑定切换按钮事件并持久化存储
  document.addEventListener("DOMContentLoaded", () => {
    apply(document.documentElement.dataset.theme);
    document.getElementById("themeToggle").addEventListener("click", () => {
      changed = true;
      const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      apply(theme);
      try {
        localStorage.setItem(key, theme);
      } catch {
        /* 隔离存储异常，保证当前视窗交互不中断 */
      }
      if (window.pywebview?.api?.set_theme) {
        window.pywebview.api.set_theme(theme).catch(() => {});
      }
    });
  });

  // 监听桌面原生桥接事件 (pywebviewready)，拉取操作系统本地持久化主题配置
  window.addEventListener("pywebviewready", async () => {
    if (!window.pywebview?.api?.get_theme) return;
    try {
      const theme = await window.pywebview.api.get_theme();
      if (!changed && ["dark", "light"].includes(theme)) {
        apply(theme);
      }
    } catch {
      /* 回退使用当前视图主题 */
    }
  });
})();
