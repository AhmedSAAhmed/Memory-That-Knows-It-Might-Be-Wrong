"""FastAPI app: /health, /api, and the Gradio UI mounted at /."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.config import VERSION, get_settings
from app.agent.orchestrator import Agent
from app.llm.client import providers_from_settings
from app.ui.layout import build_ui
from app.ui.theme import CSS_PATH, FORCE_LIGHT_JS, HEAD, navy_theme
from app.service import MemoryService
from app.sessions import SessionIdentity
from app.config import memory_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

agent = Agent()
service = MemoryService(agent)
identities = SessionIdentity()


@asynccontextmanager
async def lifespan(application):
    agent.start()
    try:
        yield
    finally:
        service.close()
        agent.close()


api = FastAPI(title="Memory That Knows It Might Be Wrong", version=VERSION, lifespan=lifespan)


@api.middleware("http")
async def private_session(request: Request, call_next):
    token = request.cookies.get("memory_session")
    customer = identities.verify(token)
    fresh = customer is None
    if fresh:
        token = identities.issue()
        customer = identities.verify(token)
    request.state.customer_id = customer
    response = await call_next(request)
    if fresh and request.url.path != "/health":
        response.set_cookie("memory_session", token, httponly=True, secure=request.url.scheme == "https",
                            samesite="lax", max_age=memory_config()["demo"]["session_seconds"])
    return response


@api.get("/api/memories")
def memories(request: Request):
    return service.snapshot(request.state.customer_id)


@api.get("/api/memories/export")
def export_memories(request: Request):
    return JSONResponse(service.export(request.state.customer_id), headers={"Content-Disposition": 'attachment; filename="my-memories.json"'})


@api.get("/api/memories/{memory_id}/history")
def memory_history(memory_id: str, request: Request):
    try:
        return service.history(request.state.customer_id, memory_id)
    except KeyError:
        raise HTTPException(404, "Memory not found") from None


@api.post("/api/memories/{memory_id}/{action}")
def update_memory(memory_id: str, action: str, request: Request, body: dict | None = None):
    customer = request.state.customer_id
    try:
        if action == "confirm":
            service.confirm(customer, memory_id)
        elif action == "correct":
            service.correct(customer, memory_id, (body or {}).get("value"))
        elif action == "revoke":
            service.revoke(customer, memory_id)
        else:
            raise HTTPException(404, "Unknown memory action")
    except KeyError:
        raise HTTPException(404, "Memory not found") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"status": "ok"}


@api.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "version": VERSION,
        "revision": os.getenv("RENDER_GIT_COMMIT", ""),
        "llm_providers": [p.name for p in providers_from_settings(s)],
    }


app = gr.mount_gradio_app(
    api,
    build_ui(agent, service=service, identities=identities),
    path="/",
    theme=navy_theme(),
    css_paths=[CSS_PATH],
    head=HEAD,
    js=FORCE_LIGHT_JS,
    footer_links=[],
    ssr_mode=False,
)
