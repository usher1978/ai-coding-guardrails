# AI 编码约束模板包（ai-coding-guardrails）

不依赖具体项目的防线模板。核心思路：**不指望 AI 自觉，让作弊在机制上走不通**；同时给“做不到”一个固定出口——诚实报告受阻是合格交付，硬凑通过才是违规。

## 威胁 → 控制 对照

| 作弊方式 | 控制 | 文件 |
|---|---|---|
| 删/改/跳过测试 | 保护文件 + 数量与 skip 检查 | guard/check_protected.py、guard/check_counts.py |
| 改检查配置绕过 | 保护文件 + CODEOWNERS + 脚本/基线从 main 读取 | guard/config.json、ci/guard.yml、setup/ |
| 针对用例硬编码 | 闭卷用例（独立私有仓库）+ 隔离输出 | ci/closed-book.yml、guard/run_closed_book.py |
| 占位/类型压制/吞异常 | 新增行关键字扫描（block/warn 两级） | guard/scan_diff.py |
| --no-verify 跳过本地钩子 | 服务端 required CI + 分支保护 | ci/pre-commit、setup/github-checklist.md |
| 批准后再推一次 | 作废过期审批 + 审批最新 push | setup/github-checklist.md |
| 反复提交试探闭卷答案 | 仅人工触发 + 命令经 secret + 输出隔离 | ci/closed-book.yml、guard/run_closed_book.py |
| 虚报完成 | 状态块校验 + evidence 必填 + 编排停止规则 | guard/status_gate.py、templates/ |
| “部分完成”蒙混合并 | 部分完成一律人工审查 | guard/status_gate.py |

## 目录

```
ai-coding-guardrails/
├── README.md                      本文件
├── rules/AGENTS.md                项目规则（15 行，按工具约定改名放置）
├── templates/
│   ├── task-contract.md           每次派活的任务合同模板
│   ├── status-report.example.md   机器可解析状态块格式与示例
│   └── prompts.md                 独立审查提示词 + 完成后追问 + 编排停止规则
├── guard/                         检查脚本（Python 标准库，零第三方依赖）
│   ├── config.json                保护清单 + 扫描规则（本身受保护）
│   ├── check_protected.py         保护文件检查
│   ├── scan_diff.py               作弊关键字扫描
│   ├── check_counts.py            测试数量/skip 检查（unittest/pytest/jest）
│   ├── status_gate.py             状态块校验 + 停止规则
│   ├── run_closed_book.py         闭卷隔离运行器
│   └── selftest.py                自检（真实跑各道防线）
├── ci/
│   ├── guard.yml                  GitHub Actions required CI（trusted-base 模式）
│   ├── closed-book.yml            闭卷验收（仅人工触发）
│   └── pre-commit                 本地预警钩子
└── setup/
    ├── github-checklist.md        分支保护/权限/闭卷配置清单 + 残余风险
    └── CODEOWNERS.template        保护路径审批模板
```

## 安装（等有真实仓库时）

1. 复制 guard/、ci/、rules/、templates/ 进仓库；规则文件按工具约定放置。
2. 按项目替换：ci/guard.yml 的测试步骤与 runner；CODEOWNERS 的人工账号。
3. 人工在 main 上生成基线 guard/baseline.json 并提交（基线受保护，PR 里不许改）。
4. 按 setup/github-checklist.md 配分支保护、AI 账号权限、工具权限层。
5. 闭卷：私有仓库 + 两个 secret + dispatch workflow。
6. 验证：python guard/selftest.py；再开测试 PR 确认平台配置生效。

## 自检（已实际运行，8/8 通过）

```
python guard/selftest.py
```

在临时目录搭迷你 git 仓库真实运行：干净改动放行；删测试、标 skip、作弊关键字被拦；状态门对完成/部分完成/受阻/超重试/坏格式给出正确决策；闭卷输出隔离（AI 摘要只有数字，用例名只在人工日志）。

## 已知边界

- unittest 适配器已端到端验证；pytest/jest 适配器为格式级验证，目标仓库首跑时确认。
- 数量检查是地板：不防“数量不变的断言弱化”；关键字扫描是烟雾信号，不是证明。
- CI 模板为 GitHub Actions；GitLab/自建需等价翻译（保护文件 + required pipeline + 审批规则）。
- property-based 测试（fast-check / Hypothesis）用于核心纯逻辑，按项目另加，不在本包内。
- 编排层重试计数必须放在模型不可写的位置，本包只提供校验与决策脚本。
安装验证记录：本仓库由模板包安装生成，guard 为 required check。
