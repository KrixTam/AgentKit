import sys
import subprocess
from pathlib import Path

def main():
    app_path = Path(__file__).parent / "app.py"
    try:
        sys.exit(subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)] + sys.argv[1:]).returncode)
    except KeyboardInterrupt:
        # 捕获 Ctrl+C，静默退出，不打印啰嗦的 traceback
        sys.exit(130)

if __name__ == "__main__":
    main()