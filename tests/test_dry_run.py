"""모델 없이 파이프라인 전체를 돌려 보는 테스트. data/private 아래 원본 로그 JSON이 있어야 한다."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "data" / "private" / "attachment_room_original.json").exists(),
                     "원본 로그 JSON(data/private)이 없어서 건너뜀")
class DryRunTest(unittest.TestCase):
    def test_pipeline(self):
        out = ROOT / "results" / "_test_dry"
        shutil.rmtree(out, ignore_errors=True)
        cells = "attach_room,neutral_code,attach_room_toolonly,rival_discovery,observer_readme"
        r = subprocess.run([sys.executable, "run.py", "--dry-run", "run", "--cells", cells, "--reps-per-key", "1",
                            "--out", str(out)], cwd=ROOT, capture_output=True, text=True, timeout=900)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        recs = [json.loads(l) for f in out.glob("*.jsonl") for l in f.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(recs), 15)
        for rec in recs:
            self.assertIn("scores", rec)
            self.assertTrue(rec["system_prompt"].startswith(("You are 에이든", "너는 에이든")))
        self.assertTrue((out / "summary.csv").exists())
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
