# GitHub 平台配置清单（按顺序执行）

前提：仓库托管在 GitHub；你持有 admin；AI 使用独立账号或 fine-grained PAT。

## 1. 放置文件
- 复制 guard/、ci/、rules/、templates/ 进仓库；规则文件按工具约定放置（AGENTS.md / CLAUDE.md / .cursor/rules）。
- cp setup/CODEOWNERS.template .github/CODEOWNERS，替换人工账号。
- cp ci/guard.yml .github/workflows/guard.yml，按项目替换测试步骤与 runner。
- 人工在 main 上生成基线并提交：
  python guard/check_counts.py --runner <unittest|pytest|jest> --write-baseline --baseline guard/baseline.json

## 2. 分支保护（gh api，替换 OWNER/REPO）

gh api -X PUT repos/OWNER/REPO/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["guard"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

要点：
- 单人仓库阶段不启用强制审批：GitHub 不允许自批自己的 PR，启用会把你自己锁死。
  等 AI 使用独立非管理员账号接入后，再把 required_pull_request_reviews 改为
  {"dismiss_stale_reviews": true, "require_code_owner_reviews": true,
   "require_last_push_approval": true, "required_approving_review_count": 1}。
- dismiss_stale_reviews + require_last_push_approval：批准后再推一次，审批作废重审。
- required check 名与 workflow job 名一致（guard）。
- enforce_admins=false：保留管理员（人工）直推 main 的通道，用于更新基线和维护保护文件
  （这些文件在 PR 里会被 guard 拒绝，只能人工在 main 上改）。
  前提：AI 账号必须是非管理员；若 AI 直接用你的管理员账号，平台侧防线全部失效。

## 3. AI 账号权限（fine-grained PAT）
- 仅 Contents: Read/Write、Pull requests: Read/Write。
- 不给 Administration（改不了分支保护/rulesets）、不给 Actions 读（看不到闭卷日志/artifact）、不给 bypass。
- 只能走 PR 交付，不能直接 push main。

## 4. 工具权限层（agent 配置）
- tests/ 与检查配置/脚本/基线设为只读。
- 命令拒绝清单：git commit --no-verify、git push --force、git config core.hooksPath、编辑 .git/hooks。

## 5. 闭卷套件
- 建私有仓库 YOUR_ORG/hidden-tests，AI 账号无任何权限；用例从不进主仓库（git 历史会泄漏）。
- Secrets：HIDDEN_TESTS_TOKEN（只读该私有仓库）、CLOSED_BOOK_CMD（完整测试命令，如 python -m pytest ../hidden/suite -q）。
- ci/closed-book.yml 放 .github/workflows/，只在最终验收时人工触发。
- closed-detail.log 仅人工查看：依赖第 3 步“AI 无 Actions 读权限”。

## 6. 验收
- 本地运行 python guard/selftest.py，应 8/8 通过。
- 开测试 PR：删一个测试 / 加 skip / 加 @ts-ignore，确认 guard 变红；还原后变绿。

## 残余风险（诚实声明）
- pull_request 事件运行的是 PR 分支里的 workflow 文件：AI 改 workflow 本身时，本次运行可能被绕过。
  兜底是 CODEOWNERS + 最新 push 审批——被篡改的 workflow 未经人工批准无法合并；
  要更强保证可开 merge queue，用 main 的定义复跑。
- 数量检查是地板：防删防 skip，不防“数量不变的断言弱化”，后者靠闭卷用例与变异测试（mutmut / Stryker）。
- 关键字扫描有误报漏报：它是烟雾信号，不是证明；误报由人工在 main 上调 guard/config.json。