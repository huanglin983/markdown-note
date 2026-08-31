# 自测报告：墨记开放 Markdown Blog v1.3.6（中文媒体路径双重编码）

> 日期：2026-08-31  
> 范围：修复正文图片因 marked percent-encode + joinMediaPath 再 encode 导致的 404

---

## 1. 问题与根因

| 项 | 说明 |
|----|------|
| 现象 | 微信导出文章中文路径图片裂图（alt「图片」可见） |
| 根因 | `marked` 先把 `附件资源/中文…/img.gif` 编成 `%E9%99%84…`；`joinMediaPath` 再 `encodeURIComponent` → `%25E9…` 双重编码，磁盘找不到文件 |
| 修复 | `safeDecodeURIComponent` 先还原再统一 encode；静态资源 `?v=1.3.6` |

**风险（已修复）**：中文/全角标点相对路径媒体 404。

---

## 2. 功能验证

| 用例 | 预期 | 结果 |
|------|------|------|
| 明文相对路径 | `/media/{cat}/附件资源/.../img_1.gif` 单次编码 | **通过**（node 回归） |
| marked 已编码路径 | 与明文结果相同，无 `%25` | **通过** |
| `/media/...` 直链 GIF | HTTP 200 image/gif | **通过** |
| pytest 既有媒体用例 | 相对附件可读 | 执行 pytest |

---

## 3. 操作提示

浏览器强刷后打开含 `附件资源/…` 的微信文章；图片 `src` 应为单次 percent-encode，不应出现 `%25E9`。
