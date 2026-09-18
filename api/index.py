"""Expose the backend when deploying the repository root to Vercel."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))

from app.main import app

__all__ = ["app"]
