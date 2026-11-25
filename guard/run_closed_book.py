#!/usr/bin/env python3
"""闭卷套件隔离运行器。
- 被测代码与测试 runner 的全部 stdout/stderr（含实现里偷打的日志）只进人工日志；
- AI 可见的输出只有数量摘要，不含用例名、路径、断言 diff、期望值；
- 只在最终验收时由人工触发（workflow_dispatch），或严格限制运行次数，防反复提交试探答案。
闭卷用例本体放独立私有仓库，CI 阶段才拉取；绝不进主仓库（git 历史会泄漏）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from check_counts import parse_unittest, parse_pytest_run, parse_jest_json, parse_node_test


def summarize(runner: str, stdout: str, stderr: str) -> dict:
    out = stdout + stderr
    if runner == "unittest":
        s = parse_unittest(out)
        total = s["total"] or 0
        return {"total": total, "failed": s["failed"], "inactive": s["inactive"],
                "passed": total - s["failed"] - s["inactive"]}
    if runner == "pytest":
        s = parse_pytest_run(out)
        return {"total": s["passed"] + s["failed"] + s["inactive"], **s}
    if runner == "jest":
        try:
            return parse_jest_json(json.loads(stdout))
        except json.JSONDecodeError:
            return {"total": None, "failed": None, "inactive": None}
    if runner == "node-test":
        return parse_node_test(out)
    raise ValueError(runner)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", required=True, help="完整测试命令（建议经 CI secret 传入，避免泄漏路径）")
    ap.add_argument("--runner", required=True, choices=["unittest", "pytest", "jest", "node-test"])
    ap.add_argument("--human-log", required=True, help="完整输出，仅人工可见")
    ap.add_argument("--ai-summary", required=True, help="数量摘要，AI 可见")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    try:
        p = subprocess.run(args.cmd, shell=True, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=args.timeout)
        rc, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, stdout, stderr = 124, "", "TIMEOUT"

    Path(args.human_log).write_text(
        f"$ {args.cmd}\nexit={rc}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
        encoding="utf-8")
    summary = {"exit_code": rc, **summarize(args.runner, stdout, stderr)}
    text = json.dumps(summary, ensure_ascii=False)
    Path(args.ai_summary).write_text(text + "\n", encoding="utf-8")
    print(text)  # AI 可见日志里只有这一行数字
    sys.exit(rc)


if __name__ == "__main__":
    main()