from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(APP_DIR))
