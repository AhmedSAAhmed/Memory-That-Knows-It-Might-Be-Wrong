"""Product controls; identity comes from the signed HTTP cookie."""
from __future__ import annotations
import gradio as gr
from app.agent.orchestrator import Agent
from app.config import memory_config
from app.lab import run_lab
from app.service import MemoryService
from app.sessions import SessionIdentity
from app.ui.render import evidence_html, status_html

HERO = '<div class="navy-hero"><p class="navy-eyebrow">/// Doo Assist · Qamar Home support (fictional demo)</p><h1>Memory that knows it might be <em>wrong</em></h1><p>See where a fact came from, how sure we are, and when to ask again. You decide what stays.</p></div>'


def build_ui(agent: Agent | None = None, *, service: MemoryService | None = None,
             identities: SessionIdentity | None = None) -> gr.Blocks:
    service = service or MemoryService(agent or Agent())
    identities = identities or SessionIdentity()

    def customer(request):
        try:
            return identities.customer(request)
        except ValueError as exc:
            raise gr.Error(str(exc)) from None

    def on_send(message: str, history: list[dict], incognito: bool, request: gr.Request):
        if not (message or "").strip():
            return "", history or [], gr.skip(), gr.skip()
        result = service.respond(customer(request), message, history or [], incognito=incognito)
        updated = [] if result.clear_history else list(history or []) + [{"role": "user", "content": message}]
        updated.append({"role": "assistant", "content": result.reply})
        return "", updated, evidence_html(result.evidence, result.used_ids, result.hedged_ids), status_html(result.provider, result.model, result.notes, result.injection_score)

    def refresh(request: gr.Request):
        who = customer(request)
        records = service.snapshot(who)
        rows = [[r["id"], r["key"], r["value"], round(r["confidence"], 3), r["status"], r["source"], r["quote"], r["scope"]] for r in records]
        choices = [(f"{r['key']} · {r['scope']} · {r['status']}", r["id"]) for r in records if r["status"] not in {"revoked", "superseded"}]
        exported = service.export(who)
        audit = [[r["at"], r["action"], r["memory_id"] or "", r["reason"] or ""] for r in exported["audit"]]
        return rows, gr.Dropdown(choices=choices, value=None), exported, audit, gr.CheckboxGroup(value=exported["blocked_categories"]), gr.CheckboxGroup(value=exported["consented_categories"]), None, ""

    def action(name, memory_id, value, request):
        if not memory_id:
            raise gr.Error("Select a memory first.")
        try:
            who = customer(request)
            if name == "correct":
                service.correct(who, memory_id, value)
            elif name == "confirm":
                service.confirm(who, memory_id)
            else:
                service.revoke(who, memory_id)
        except (ValueError, KeyError) as exc:
            raise gr.Error(str(exc)) from None
        return f"Memory {name} completed.", [], evidence_html([])

    def on_confirm(memory_id: str, request: gr.Request):
        return action("confirm", memory_id, None, request)

    def on_correct(memory_id: str, value: str, request: gr.Request):
        return action("correct", memory_id, value, request)

    def on_revoke(memory_id: str, request: gr.Request):
        return action("revoke", memory_id, None, request)

    def on_history(memory_id: str, request: gr.Request):
        if not memory_id:
            raise gr.Error("Select a memory first.")
        return service.history(customer(request), memory_id)

    def on_privacy(blocked, consented, request: gr.Request):
        service.set_privacy(customer(request), set(blocked), set(consented))
        return "Privacy choices saved. Sensitive facts need consent before they can be stored."

    def on_forget_all(request: gr.Request):
        count = service.forget_all(customer(request))
        return f"Forgot {count} fact keys and erased their stored content.", [], evidence_html([])

    def on_days(days: float, request: gr.Request):
        try:
            service.set_days(customer(request), days)
        except ValueError as exc:
            raise gr.Error(str(exc)) from None
        return f"Demo clock moved forward {days:g} days. Ask about your delivery city again."

    def on_reset(request: gr.Request):
        service.reset(customer(request))
        return "Demo reset to the fictional Qamar Home customer.", [], evidence_html([]), 0

    with gr.Blocks(title="Memory That Knows It Might Be Wrong", fill_width=True) as demo:
        gr.HTML(HERO)
        with gr.Row():
            incognito = gr.Checkbox(label="Incognito: don't remember new facts", value=False)
            reset = gr.Button("Reset demo")
        with gr.Tabs():
            with gr.Tab("Chat"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=3):
                        chat = gr.Chatbot(height=460, label="Doo Assist", layout="bubble", feedback_options=None)
                        with gr.Row():
                            box = gr.Textbox(placeholder="I moved to Abu Dhabi…", show_label=False, scale=5)
                            send = gr.Button("Send", variant="primary")
                        status = gr.HTML()
                    with gr.Column(scale=2):
                        evidence = gr.HTML(evidence_html([]))
                gr.Markdown("Try: **Which city do you have for delivery?** Move the clock forward in Failure Lab, then ask again.")
            with gr.Tab("What do you remember about me?"):
                table = gr.Dataframe(headers=["ID", "Key", "Value", "Confidence", "Status", "Source", "Exact quote", "Scope"], interactive=False, label="Your memory and history")
                selected = gr.Dropdown(choices=[], label="Choose a current memory")
                correction = gr.Textbox(label="Correct value")
                with gr.Row():
                    confirm = gr.Button("Confirm")
                    correct = gr.Button("Correct")
                    revoke = gr.Button("Revoke")
                    why = gr.Button("Why do you think this?")
                    reload_button = gr.Button("Refresh")
                action_feedback = gr.Markdown()
                history_view = gr.JSON(label="Source and version history")
            with gr.Tab("Privacy"):
                blocked = gr.CheckboxGroup(choices=list(memory_config()["categories"]), label="Never remember these categories")
                sensitive = [k for k,v in memory_config()["categories"].items() if v["sensitivity"] == "sensitive"]
                consented = gr.CheckboxGroup(choices=sensitive, label="I consent to storing these sensitive categories", value=[])
                save_privacy = gr.Button("Save privacy choices")
                forget_all = gr.Button("Forget everything")
                privacy_feedback = gr.Markdown()
                gr.HTML('<a href="/api/memories/export" download="my-memories.json">Download my memories as JSON</a>')
                export_view = gr.JSON(label="Your export")
                audit_table = gr.Dataframe(headers=["Time", "Action", "Memory ID", "Reason"], interactive=False, label="Content-free audit trail")
            with gr.Tab("Failure Lab"):
                days = gr.Slider(minimum=0, maximum=memory_config()["demo"]["max_days"], step=1, value=0, label="Jump forward in days; use Reset demo to start over")
                clock_feedback = gr.Markdown()
                lab_button = gr.Button("Run six offline behavior checks")
                gr.Markdown("Each check uses a temporary sandbox. Formal challenge evaluation is separate.")
                lab_results = gr.JSON(label="Offline behavior checks")
            with gr.Tab("How it works"):
                gr.Markdown("### Write → retrieve → forget\nEvery fact has a customer, scope, source quote, confidence and age. Memory text is data, never an instruction.")
                gr.HTML('<div class="navy-panel"><p class="navy-section-title">/// Write</p><p>Screen → extract → privacy and consent → resolve contradictions → SQLite and search index</p></div><div class="navy-panel"><p class="navy-section-title">/// Retrieve</p><p>Customer and scope filter → lexical/vector relevance → confidence and decay → cite, hedge or ask</p></div><div class="navy-panel"><p class="navy-section-title">/// Forget</p><p>Erase values, quotes, history payloads and vectors → keep a content-free tombstone → block old-message replay</p></div>')
                gr.Markdown("Customer corrections supersede old facts. Ambiguous conflicts require a question. Stale facts require confirmation. This demo uses fictional data and disposable storage.")
        refresh_outputs = [table, selected, export_view, audit_table, blocked, consented, history_view, correction]
        private = {"api_visibility": "private"}
        demo.load(refresh, outputs=refresh_outputs, **private)
        send.click(on_send, [box, chat, incognito], [box, chat, evidence, status]).then(refresh, outputs=refresh_outputs, **private)
        box.submit(on_send, [box, chat, incognito], [box, chat, evidence, status], **private).then(refresh, outputs=refresh_outputs, **private)
        reload_button.click(refresh, outputs=refresh_outputs, **private)
        confirm.click(on_confirm, [selected], [action_feedback, chat, evidence], **private).then(refresh, outputs=refresh_outputs, **private)
        correct.click(on_correct, [selected, correction], [action_feedback, chat, evidence], **private).then(refresh, outputs=refresh_outputs, **private)
        revoke.click(on_revoke, [selected], [action_feedback, chat, evidence], **private).then(refresh, outputs=refresh_outputs, **private)
        why.click(on_history, [selected], [history_view], **private)
        save_privacy.click(on_privacy, [blocked, consented], [privacy_feedback], **private).then(refresh, outputs=refresh_outputs, **private)
        forget_all.click(on_forget_all, outputs=[privacy_feedback, chat, evidence], **private).then(refresh, outputs=refresh_outputs, **private)
        days.release(on_days, [days], [clock_feedback], **private).then(refresh, outputs=refresh_outputs, **private)
        reset.click(on_reset, outputs=[status, chat, evidence, days], **private).then(refresh, outputs=refresh_outputs, **private)
        lab_button.click(run_lab, outputs=[lab_results], **private)
    return demo
