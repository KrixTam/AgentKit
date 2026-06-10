import glob
import os
import subprocess
import sys
import time

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

agentkit_root = os.path.join(project_root, "agentkit")
examples_dir = os.path.join(agentkit_root, "examples", "standard")
scripts = sorted(glob.glob(os.path.join(examples_dir, "*.py")))
scripts = [s for s in scripts if os.path.basename(s).startswith(("0", "1"))]

print(f"Found {len(scripts)} scripts to run.")

results = []
env = os.environ.copy()
env["PYTHONPATH"] = agentkit_root + os.pathsep + env.get("PYTHONPATH", "")

for idx, script in enumerate(scripts, start=1):
    filename = os.path.basename(script)
    print(f"\n--- Running {filename} ---")
    start = time.time()
    result = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env)
    duration = time.time() - start

    ok = result.returncode == 0
    status = "✅" if ok else "❌"
    print(f"[{status}] {filename} in {duration:.2f}s")
    if not ok:
        print(f"--- STDERR ---\n{result.stderr}\n--- STDOUT ---\n{result.stdout}")

    results.append(
        {
            "#": str(idx),
            "示例": os.path.splitext(filename)[0],
            "文件": filename,
            "耗时": f"{duration:.2f}s",
            "状态": status,
            "说明": "运行通过" if ok else "运行失败",
            "returncode": result.returncode,
            "_duration": duration,
        }
    )

print("\n=== SUMMARY (REPORT FIELDS) ===")
print("| # | 示例 | 文件 | 耗时 | 状态 | 说明 |")
print("|---|------|------|-----:|:----:|------|")
for r in results:
    print(f"| {r['#']} | {r['示例']} | `{r['文件']}` | {r['耗时']} | {r['状态']} | {r['说明']} |")

total_duration = sum(r["_duration"] for r in results)
passed = sum(1 for r in results if r["returncode"] == 0)
print(f"| | **合计** | | **{total_duration:.2f}s** | **{passed}/{len(results)}** | |")

if any(r["returncode"] != 0 for r in results):
    sys.exit(1)
