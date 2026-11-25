"""仓库自测：把 guard/selftest.py 作为测试运行，保证模板防线本身始终可用。"""
import subprocess
import sys
import unittest
from pathlib import Path

SELFTEST = Path(__file__).resolve().parent.parent / "guard" / "selftest.py"


class TestGuardSelftest(unittest.TestCase):
    def test_selftest_all_pass(self):
        p = subprocess.run([sys.executable, str(SELFTEST)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
        self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()