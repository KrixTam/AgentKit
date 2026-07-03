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

def _read_value_from_local_env_files(key: str) -> tuple[str | None, str | None]:
    candidates = []
    candidates.append(os.path.join(os.getcwd(), ".env"))
    candidates.append(os.path.join(os.getcwd(), ".evn"))
    candidates.append(os.path.join(project_root, ".env"))
    candidates.append(os.path.join(project_root, ".evn"))
    candidates.append(os.path.join(agentkit_root, ".env"))
    candidates.append(os.path.join(agentkit_root, ".evn"))

    here = os.path.abspath(__file__)
    base = os.path.dirname(here)
    while True:
        candidates.append(os.path.join(base, ".env"))
        candidates.append(os.path.join(base, ".evn"))
        parent = os.path.dirname(base)
        if parent == base:
            break
        base = parent

    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() != key:
                        continue
                    value = v.strip().strip("'").strip('"')
                    if value:
                        return value, path
        except Exception:
            continue
    return None, None


def resolve_effective_standard_model() -> tuple[str | None, str]:
    value = (env.get("AGENTKIT_STANDARD_MODEL") or "").strip()
    if value:
        return value, "env"
    value, path = _read_value_from_local_env_files("AGENTKIT_STANDARD_MODEL")
    if value:
        return value, f"file:{path}"
    return None, "none"


print(f"Found {len(scripts)} scripts to run.")

results = []
env = os.environ.copy()
env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

effective_model, effective_model_source = resolve_effective_standard_model()
print("\n=== META ===")
if effective_model:
    print(f"AGENTKIT_STANDARD_MODEL={effective_model} ({effective_model_source})")
else:
    print("AGENTKIT_STANDARD_MODEL=(not set) (none)")

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
