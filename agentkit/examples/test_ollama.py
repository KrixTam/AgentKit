import os
import time
import subprocess
import glob
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
examples_dir = os.path.join(project_root, "examples", "ollama")
scripts = sorted(glob.glob(os.path.join(examples_dir, "*.py")))
# exclude __init__.py and other non-test scripts
scripts = [s for s in scripts if os.path.basename(s).startswith(("0", "1"))]

print(f"Found {len(scripts)} scripts to run.")

results = []

env = os.environ.copy()
env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

for script in scripts:
    name = os.path.basename(script)
    print(f"\n--- Running {name} ---")
    start = time.time()
    result = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env)
    duration = time.time() - start
    
    status = "✅" if result.returncode == 0 else "❌"
    print(f"[{status}] {name} in {duration:.2f}s")
    if result.returncode != 0:
        print(f"--- STDERR ---\n{result.stderr}\n--- STDOUT ---\n{result.stdout}")
        
    results.append({
        "name": name,
        "duration": duration,
        "status": status,
        "returncode": result.returncode
    })

print("\n=== SUMMARY ===")
for r in results:
    print(f"{r['name']} | {r['duration']:.2f}s | {r['status']}")

# Return a non-zero exit code if any failed
if any(r['returncode'] != 0 for r in results):
    sys.exit(1)
