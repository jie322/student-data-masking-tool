/**
 * 跨平台产物导出与下载通道服务 (Downloads & Storage Bridge Service)。
 * 管理客户端内存 Blob 及 ObjectURL 生命周期，
 * 封装浏览器原生 a[download] 下载与桌面端 Win32 pywebview 保存对话框的双模路由。
 */
import { $ } from "../ui/dom.js";

const exportBlobs = new Map();
let objectUrls = [];
// 保存锁：控制单实例保存事务，防止高频重复触发系统对话框
let savingExport = false;

/**
 * 释放旧批次生成的 ObjectURL 与 Blob 内存引用，杜绝内存泄漏及脏数据下载风险。
 */
export function clearDownloads() {
  for (const url of objectUrls) URL.revokeObjectURL(url);
  objectUrls = [];
  exportBlobs.clear();
}

/**
 * 为给定的二进制 Blob 注册虚拟 ObjectURL 并纳入内存生命周期管理。
 * @param {Blob} blob 待下载的二进制对象。
 * @returns {string} 可挂载至 DOM 链接的 blob: 协议 URL。
 */
export function downloadUrl(blob) {
  const url = URL.createObjectURL(blob);
  objectUrls.push(url);
  exportBlobs.set(url, blob);
  return url;
}

/**
 * 绑定界面导出与报告下载链接的点击行为（自动适配 Web 浏览器与桌面客户端）。
 * @param {Function} notify 消息提示通知回调。
 */
export function bindDownloadLinks(notify) {
  for (const id of ["exportLink", "reportLink"]) {
    $(id).addEventListener("click", async (event) => {
      // 若处于通用 Web 浏览器环境（未注入 pywebview 宿主 API），保持默认的 a[download] 虚拟下载行为
      if (!window.pywebview?.api?.save_export) return;

      // 处于桌面客户端环境时拦截默认下载，转为调用原生操作系统文件保存选择器
      event.preventDefault();
      if (savingExport) return;
      const link = event.currentTarget;
      const blob = exportBlobs.get(link.href);
      if (!blob) return;

      savingExport = true;
      try {
        // 将客户端 Blob 转换为 Base64 文本载荷，通过 IPC 桥传递至 Python 桌面宿主
        const encoded = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result.split(",")[1]);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });

        // 校验保存上下文有效性：若在转码期间配置发生变更，放弃落盘以防产出脏数据
        if (exportBlobs.get(link.href) !== blob) return;

        const result = await window.pywebview.api.save_export(link.download, encoded);
        if (result.status === "saved") notify("文件已保存。");
        if (result.status === "error") notify(result.message, true);
      } catch {
        notify("保存失败，请重新选择保存位置。", true);
      } finally {
        savingExport = false;
      }
    });
  }
}
