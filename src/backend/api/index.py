"""Entrypoint compatível com o runtime Python da Vercel."""

from app.main import app

__all__ = ["app"]
