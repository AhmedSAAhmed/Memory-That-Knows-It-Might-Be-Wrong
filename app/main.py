"""FastAPI app: /health, /api, and the Gradio UI mounted at /."""
from __future__ import annotations

import logging

import gradio as gr
from fastapi import FastAPI

from app.config import VERSION, get_settings
from app.llm.client import providers_from_settings
from app.ui.layout import build_ui
from app.ui.theme import CSS_PATH, FORCE_LIGHT_JS, HEAD, navy_theme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

api = FastAPI(title="Memory That Knows It Might Be Wrong", version=VERSION)


@api.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "version": VERSION,
        "llm_providers": [p.name for p in providers_from_settings(s)],
    }


app = gr.mount_gradio_app(
    api,
    build_ui(),
    path="/",
    theme=navy_theme(),
    css_paths=[CSS_PATH],
    head=HEAD,
    js=FORCE_LIGHT_JS,
    footer_links=[],
    ssr_mode=False,
)
