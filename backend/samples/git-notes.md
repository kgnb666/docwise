# 示例文档：Git 与协作开发笔记

## Git 基本概念

Git 是一个分布式版本控制系统，用来跟踪代码的每次修改。仓库（Repository）里每个
文件的变化都被记录成一次提交（Commit），提交信息要写清楚"这次改了什么、为什么"。
`git status` 查看工作区状态，`git add` 把改动加入暂存区，`git commit` 生成一次提交。

## 分支与合并

分支（Branch）是 Git 最强大的特性之一：`git branch feature` 创建分支，
`git checkout feature` 切换分支，`git merge feature` 把功能分支合并回主线。

合并有两种方式：
- merge：保留完整的提交历史，会生成一个"合并提交"，适合记录真实开发过程；
- rebase：把当前分支的提交"重新铺"到目标分支顶端，历史是一条直线，更干净，
  但不要对已推送的公共分支执行 rebase，否则会改写别人的历史。

## 回退与撤销

- `git reset --hard HEAD~1`：回退到上一个提交（丢弃改动，慎用）；
- `git revert <commit>`：生成一个反向提交来撤销指定提交（适合公共分支）；
- `git stash`：把未提交的改动暂存起来，切换分支后再 `git stash pop` 取回。

## GitHub 协作流程与 CI

典型的团队流程是 GitHub Flow：从 main 拉出功能分支 → 提交代码 → 推送 →
发起 Pull Request（PR）→ 代码评审通过后合并。PR 是代码审查和讨论的载体。

GitHub Actions 是内置的 CI/CD：在 .github/workflows/ 下写 YAML 定义工作流，
每次 push 或 PR 自动执行（如跑测试、构建、部署）。工作流由 job、step 组成，
可以按事件（push / pull_request / schedule）触发。

## 提交信息规范

推荐 Conventional Commits：feat（新功能）、fix（修复）、docs（文档）、
refactor（重构）、test（测试）、chore（杂务）。格式如：
`feat: 支持追问改写`。规范的提交信息让历史可读、可自动生成 changelog。
