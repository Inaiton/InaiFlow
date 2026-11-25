"""Vercel Python entrypoint (all paths are rewritten here by vercel.json)."""

from app.main import app

__all__ = ["app"]
