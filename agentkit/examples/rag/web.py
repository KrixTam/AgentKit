import sys
import subprocess
from pathlib import Path

def main():
    app_path = Path(__file__).parent / "app.py"
    sys.exit(subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)] + sys.argv[1:]).returncode)

if __name__ == "__main__":
    main()