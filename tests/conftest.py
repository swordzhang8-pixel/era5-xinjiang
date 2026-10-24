"""让 pytest 能找到 src/ 里的 era5x 包（仓库没用可安装的 pyproject）。"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC / "src"))
