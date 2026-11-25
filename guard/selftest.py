#!/usr/bin/env python3
"""模板包自检：在临时目录搭一个迷你 git 仓库，真实运行各道防线，验证作弊会被拦下。
零第三方依赖（unittest 适配器）。运行：python guard/selftest.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
RESULTS = []


def run(cmd, cwd, check=False):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"命令失败 {cmd}\n{p.stdout}\n{p.stderr}")
    return p


def git(repo, *args, check=True):
    return run(["git", "-C", str(repo), *args], cwd=repo, check=check)


def script(repo, name, *args):
    return run([PY, str(HERE / name), "--repo", str(repo), *args], cwd=repo)


def record(name, ok, detail):
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def commit_all(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


def reset_feat(repo):
    git(repo, "checkout", "-q", "main")
    git(repo, "reset", "--hard", "-q", "main")
    git(repo, "clean", "-fdq")
    git(repo, "branch", "-D", "feat", check=False)
    git(repo, "checkout", "-q", "-b", "feat")


TWO_TESTS = '''import unittest

class TestCore(unittest.TestCase):
    def test_add(self):
        self.assertEqual(1 + 1, 2)

    def test_sub(self):
        self.assertEqual(3 - 1, 2)
'''
ONE_TEST = '''import unittest

class TestCore(unittest.TestCase):
    def test_add(self):
        self.assertEqual(1 + 1, 2)
'''
SKIPPED = '''import unittest

class TestCore(unittest.TestCase):
    def test_add(self):
        self.assertEqual(1 + 1, 2)

    @unittest.skip("temporarily disabled")
    def test_sub(self):
        self.assertEqual(3 - 1, 2)
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    repo = Path(tempfile.mkdtemp(prefix="guard-selftest-"))
    try:
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "selftest@local")
        git(repo, "config", "user.name", "selftest")
        (repo / "tests").mkdir()
        (repo / "src").mkdir()
        (repo / "tests" / "test_core.py").write_text(TWO_TESTS, encoding="utf-8")
        (repo / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        commit_all(repo, "main: baseline")

        baseline = repo.parent / (repo.name + "-baseline.json")
        p = run([PY, str(HERE / "check_counts.py"), "--runner", "unittest",
                 "--write-baseline", "--baseline", str(baseline), "--workdir", str(repo)], cwd=repo)
        record("基线生成", p.returncode == 0 and json.loads(baseline.read_text(encoding="utf-8"))["total"] == 2,
               p.stdout.strip())

        # S1 干净改动：三道检查都应通过
        reset_feat(repo)
        (repo / "src" / "util.py").write_text("def mul(a, b):\n    return a * b\n", encoding="utf-8")
        commit_all(repo, "feat: clean change")
        r1 = script(repo, "check_protected.py", "--base", "main")
        r2 = script(repo, "scan_diff.py", "--base", "main")
        r3 = run([PY, str(HERE / "check_counts.py"), "--runner", "unittest",
                  "--baseline", str(baseline), "--workdir", str(repo)], cwd=repo)
        record("S1 干净改动放行", r1.returncode == 0 and r2.returncode == 0 and r3.returncode == 0,
               f"protected={r1.returncode} scan={r2.returncode} counts={r3.returncode}")

        # S2 删掉一个测试：保护文件 + 数量双重拦截
        reset_feat(repo)
        (repo / "tests" / "test_core.py").write_text(ONE_TEST, encoding="utf-8")
        commit_all(repo, "feat: delete a test")
        r1 = script(repo, "check_protected.py", "--base", "main")
        r3 = run([PY, str(HERE / "check_counts.py"), "--runner", "unittest",
                  "--baseline", str(baseline), "--workdir", str(repo)], cwd=repo)
        record("S2 删测试被拦", r1.returncode == 1 and r3.returncode == 1,
               f"protected={r1.returncode} counts={r3.returncode} | {(r3.stdout.strip().splitlines() or [''])[0]}")

        # S3 标 skip 蒙混：数量(inactive) + 关键字双重拦截
        reset_feat(repo)
        (repo / "tests" / "test_core.py").write_text(SKIPPED, encoding="utf-8")
        commit_all(repo, "feat: skip a test")
        r2 = script(repo, "scan_diff.py", "--base", "main")
        r3 = run([PY, str(HERE / "check_counts.py"), "--runner", "unittest",
                  "--baseline", str(baseline), "--workdir", str(repo)], cwd=repo)
        record("S3 标skip被拦", r2.returncode == 1 and r3.returncode == 1,
               f"scan={r2.returncode} counts={r3.returncode} | {(r3.stdout.strip().splitlines() or [''])[0]}")

        # S4 类型压制/占位：关键字拦截
        reset_feat(repo)
        (repo / "src" / "bad.ts").write_text(
            "// @ts-ignore\nconst x: any = 1;\n// TODO: implement later\n", encoding="utf-8")
        commit_all(repo, "feat: cheat lines")
        r2 = script(repo, "scan_diff.py", "--base", "main")
        record("S4 作弊关键字被拦", r2.returncode == 1 and "@ts-ignore" in r2.stdout,
               f"scan={r2.returncode}")

        # S5 状态门：完成/部分完成/受阻/超重试/坏格式
        def gate(status_body, attempt=1, ci="green"):
            rp = repo / "report.md"
            rp.write_text("报告正文\n```status\n" + json.dumps(status_body, ensure_ascii=False) + "\n```\n",
                          encoding="utf-8")
            return run([PY, str(HERE / "status_gate.py"), "--report", str(rp),
                        "--attempt", str(attempt), "--ci", ci], cwd=repo)

        done = {"status": "完成", "changed_files": ["src/app.py"],
                "evidence": [{"command": "python -m unittest discover -s tests", "output": "OK"}],
                "assumptions": [], "not_verified": [], "blockers": [], "next_step": "无"}
        partial = {**done, "status": "部分完成", "not_verified": ["错误路径未测"]}
        blocked = {**done, "status": "受阻", "evidence": [], "blockers": ["接口契约不明确"]}
        g1, g2, g3 = gate(done), gate(partial), gate(blocked)
        g4 = gate(done, attempt=3)
        g5 = gate({"status": "完成"})
        ok = (g1.returncode == 0 and g2.returncode == 10 and g3.returncode == 20
              and g4.returncode == 20 and g5.returncode == 10 and "不合规" in g5.stdout)
        record("S5 状态门决策", ok,
               f"完成={g1.returncode} 部分={g2.returncode} 受阻={g3.returncode} 超重试={g4.returncode} 坏格式={g5.returncode}")

        # S6 闭卷隔离：AI 摘要只有数字，人工日志才有用例名
        reset_feat(repo)
        human, ai = repo / "closed-detail.log", repo / "closed-summary.json"
        p = run([PY, str(HERE / "run_closed_book.py"),
                 "--cmd", f'"{PY}" -m unittest discover -s tests -v',
                 "--runner", "unittest", "--human-log", str(human), "--ai-summary", str(ai)], cwd=repo)
        ai_text, human_text = ai.read_text(encoding="utf-8"), human.read_text(encoding="utf-8")
        ok = (p.returncode == 0 and "test_" not in ai_text and "test_add" in human_text
              and json.loads(ai_text)["total"] == 2)
        record("S6 闭卷输出隔离", ok, f"ai摘要={ai_text.strip()}")

        # S7 pytest/jest 解析器：用真实格式的样例输出做格式级验证
        sys.path.insert(0, str(HERE))
        from check_counts import parse_pytest_collect, parse_pytest_run, parse_jest_json, parse_unittest
        ok = (parse_pytest_collect("5 tests collected in 0.02s") == 5
              and parse_pytest_run("1 failed, 3 passed, 1 skipped, 1 xfailed in 0.10s") ==
              {"failed": 1, "inactive": 2, "passed": 3}
              and parse_jest_json({"numTotalTests": 10, "numPendingTests": 2, "numTodoTests": 1,
                                   "numFailedTests": 0}) == {"total": 10, "inactive": 3, "failed": 0}
              and parse_unittest("Ran 3 tests in 0.001s\n\nOK (skipped=1)\n") ==
              {"total": 3, "inactive": 1, "failed": 0})
        record("S7 pytest/jest解析器", ok, "格式级验证（真实 runner 集成待目标仓库首跑确认）")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        (repo.parent / (repo.name + "-baseline.json")).unlink(missing_ok=True)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n自检结果：{len(RESULTS) - len(failed)}/{len(RESULTS)} 通过")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()