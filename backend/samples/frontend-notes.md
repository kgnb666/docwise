# 前端基础笔记

## 浏览器渲染流程

HTML 解析成 DOM 树 → CSS 解析成 CSSOM → 合并成渲染树 → 布局（Layout）→ 绘制（Paint）→ 合成。
优化：减少重排重绘（批量操作 DOM、用 transform 代替 top/left）、
CSS 放头部 JS 放底部（或 defer/async）、图片懒加载。

## 事件循环

JS 单线程：同步任务先执行，微任务（Promise.then、MutationObserver）
在宏任务（setTimeout、事件回调）之前清空。
经典题目：async/await、setTimeout、Promise 的输出顺序——先微任务队列再下一个宏任务。

## HTTP 缓存

- 强缓存：Cache-Control（max-age）命中直接走本地，不发请求；
- 协商缓存：Last-Modified/ETag 带条件请求，304 不返回体；
- 缓存位置：memory cache、disk cache、Service Worker。
原则：不常变的资源长缓存 + 文件名带内容哈希（发版即换 URL）。

## 跨域与安全

同源策略：协议+域名+端口一致。跨域方案：CORS（后端加响应头）、
JSONP（GET 回调）、反向代理（同源化）、postMessage。
安全：XSS（转义输出/ CSP）、CSRF（SameSite Cookie / Token 校验）、
点击劫持（X-Frame-Options）。
