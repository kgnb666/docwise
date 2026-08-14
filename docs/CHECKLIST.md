# 投递前检查清单（最后冲刺用）

> 目标：投递前把每一栏都打勾。已经打勾的是我这边确认过的，
> 剩下的是需要你在自己机器/服务器上操作的。

## ✅ 代码与质量（已完成，可复跑验证）

- [x] 一键全量验证：`powershell -ExecutionPolicy Bypass -File scripts/run_all.ps1`（ruff → 70 测试 → 真实评测 → 基准 → SUMMARY.md）
- [x] 后端启动正常：`cd backend && .\.venv\Scripts\uvicorn app.main:app --reload --port 8000`
- [x] 前端启动正常：`cd frontend && npm run dev` → http://localhost:5173
- [x] 单元测试全绿：`cd backend && python -m pytest -q`（70 个）
- [x] 静态检查零告警：`ruff check app tests scripts`
- [x] 真实评测数据已生成：`docs/eval/offline_report.json`（top-1 四档对比）、`quality_report.json`（32 题）、`benchmark.json`（延迟/成本）、`SUMMARY.md`（汇总页）

## 📚 真实知识库（关键，待你提供内容）

- [ ] 确定知识库领域（如：课程笔记 / 算法面试题 / 技术文档）
- [ ] 收集资料（md/txt/pdf），放到一个文件夹
- [ ] 导入：`cd backend && python scripts/import_kb.py <文件夹>`
- [ ] 扩充测试集：`tests/data/test_set.json` 追加问题（每个问题标注期望来源文档）
- [ ] 重跑评测：`python scripts/run_eval.py --embedding openai --tokenizer jieba --reranker-api --top-k 1`
- [ ] 把真实数据更新到 `docs/EVAL.md` / `docs/RESUME.md`

## 🚀 部署上线

- [ ] 本机安装 Git（https://git-scm.com/download/win）
- [ ] 推送 GitHub：`git init && git add . && git commit -m "feat: DocWise RAG + Agent" && git push`
- [ ] 确认 CI 通过（Actions 页面：ruff + pytest + build）
- [ ] 买轻量服务器（¥30/月档，Ubuntu 22.04），安全组放行 80/443
- [ ] 按 `docs/DEPLOYMENT.md` 部署：docker compose up --build -d
- [ ] 访问 http://服务器IP 验证（上传文档 → 问答 → 引用 → 工具调用）
- [ ] 配置域名 + HTTPS（Caddy 自动证书）

## 🎬 演示与求职包装

- [ ] 按 `docs/DEMO_SCRIPT.md` 录 3 分钟演示视频（Xbox Game Bar / OBS）
- [ ] 视频上传 B 站/YouTube，链接放简历
- [ ] `docs/RESUME.md`：填真实知识库规模 + Demo 链接 + GitHub 链接，套进简历
- [ ] README 加演示截图/动图
- [ ] `docs/INTERVIEW.md`：24 问全部能口头讲一遍（重点 Q15.5/Q16.5 两个 bug 案例）
- [ ] 30 秒电梯演讲背熟（docs/RESUME.md 末尾）

## 🧪 投递前最后自测（模拟面试官）

- [ ] 换台干净机器（或清空浏览器缓存）重新走一遍：上传 → 提问 → 追问 → 工具调用
- [ ] 问自己：「为什么用混合检索」「评测怎么做的」「最大难点」「如果重做会改什么」
- [ ] 确认 .env 没被提交（`git status` 里不应出现 .env）
