"""Gradio Blocks UI: chat + evidence, inspector, privacy, failure lab, how it works."""
from __future__ import annotations

import gradio as gr

from app.agent.orchestrator import Agent
from app.ui.render import evidence_html, status_html

HERO = """
<div class="navy-hero">
  <p class="navy-eyebrow">/// Doo Assist · Qamar Home support (demo)</p>
  <h1>Memory that knows it might be <em>wrong</em></h1>
  <p>Every fact this agent remembers carries a source, a confidence, a freshness and a scope.
     When it isn't sure, it says so and asks. When you say forget, it forgets.</p>
  <div class="navy-chips">
    <span class="navy-chip">source</span><span class="navy-chip">confidence</span>
    <span class="navy-chip">freshness</span><span class="navy-chip">scope</span>
    <span class="navy-chip">forgetting policy</span>
  </div>
</div>
"""

SOON = '<div class="navy-panel"><p class="navy-section-title">/// {title}</p><p class="navy-empty">{body}</p></div>'


def build_ui(agent: Agent | None = None) -> gr.Blocks:
    agent = agent or Agent()

    def on_send(message: str, history: list[dict], request: gr.Request):
        history = list(history or [])
        if not (message or "").strip():
            return "", history, gr.skip(), gr.skip()
        session_id = getattr(request, "session_hash", None) or "anon"
        result = agent.respond(session_id, message, history)
        history += [{"role": "user", "content": message},
                    {"role": "assistant", "content": result.reply}]
        return ("", history,
                evidence_html(result.evidence, result.used_ids, result.hedged_ids),
                status_html(result.provider, result.model, result.notes, result.injection_score))

    with gr.Blocks(title="Memory That Knows It Might Be Wrong") as demo:
        gr.HTML(HERO)
        with gr.Tabs():
            with gr.Tab("Chat"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=3):
                        chat = gr.Chatbot(height=460, label="Doo Assist", layout="bubble",
                                          placeholder="Hi, I'm Doo Assist for Qamar Home. How can I help?",
                                          feedback_options=None)
                        with gr.Row():
                            box = gr.Textbox(placeholder="Type a message… e.g. “I moved to Abu Dhabi”",
                                             show_label=False, scale=5, container=False)
                            send = gr.Button("Send", variant="primary", scale=1)
                        status = gr.HTML("")
                    with gr.Column(scale=2):
                        evidence = gr.HTML(evidence_html([]))
                send.click(on_send, [box, chat], [box, chat, evidence, status])
                box.submit(on_send, [box, chat], [box, chat, evidence, status])

            with gr.Tab("What do you remember about me?"):
                gr.HTML(SOON.format(title="Memory inspector",
                                    body="Every memory about you, with its source quote, confidence and status. "
                                         "Confirm, correct or revoke any of them. (Day 3)"))
            with gr.Tab("Privacy"):
                gr.HTML(SOON.format(title="Privacy controls",
                                    body="Incognito, never-remember categories, sensitive-data consent, "
                                         "export and the audit log. (Day 3)"))
            with gr.Tab("Failure Lab"):
                gr.HTML(SOON.format(title="Failure Lab",
                                    body="Move the clock forward, contradict yourself, revoke a fact, try an "
                                         "injection - and watch the memory handle it. (Day 3-4)"))
            with gr.Tab("How it works"):
                gr.HTML(SOON.format(title="Architecture",
                                    body="Write path, retrieval path, forgetting path. (Day 2)"))
    return demo
