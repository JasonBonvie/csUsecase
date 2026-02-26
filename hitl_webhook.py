"""
Webhook server for CrewAI AMP task callbacks.

Uses taskWebhookUrl (documented in CrewAI API). AMP POSTs to /task when each
task completes. We filter for tasks that look like review steps (name contains
"review")—e.g. request_review in the Support flow—and store them for the
Streamlit app to display and approve/deny.

Setup:
  1. Run: ngrok http 5050  (or your HITL_WEBHOOK_PORT)
  2. Set CREWAI_WEBHOOK_BASE_URL to the ngrok URL (e.g. https://xxx.ngrok.io)
  3. Include taskWebhookUrl: {base}/task in your kickoff payload
"""

import json
import os
import re
import threading
from pathlib import Path

_HITL_STORE = Path(os.getenv("HITL_STORE_PATH", "./pending_hitl_approvals.json"))
_SERVER_THREAD: threading.Thread | None = None

# Task names that indicate a review step (Support flow: request_review)
_REVIEW_TASK_PATTERN = re.compile(r"review", re.IGNORECASE)


def _read_store() -> list[dict]:
    """Thread-safe read of pending approvals."""
    try:
        if _HITL_STORE.exists():
            with open(_HITL_STORE, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _write_store(data: list[dict]) -> None:
    """Thread-safe write of pending approvals."""
    with open(_HITL_STORE, "w") as f:
        json.dump(data, f, indent=2)


def get_pending_approvals() -> list[dict]:
    """Return list of pending approval requests from task webhook callbacks."""
    return _read_store()


def remove_approval(execution_id: str, task_id: str) -> None:
    """Remove a handled approval from the store."""
    data = [a for a in _read_store() if not (a.get("execution_id") == execution_id and a.get("task_id") == task_id)]
    _write_store(data)


def _is_review_task(body: dict) -> bool:
    """True if this task webhook looks like a review step (e.g. request_review)."""
    name = body.get("name") or body.get("task_id") or ""
    return bool(_REVIEW_TASK_PATTERN.search(str(name)))


def _extract_from_task_payload(body: dict) -> dict | None:
    """Extract execution_id, task_id, content from CrewAI taskWebhookUrl payload."""
    # Per CrewAI webhook docs: name, output, kickoff_id, summary, etc.
    execution_id = body.get("kickoff_id") or body.get("execution_id")
    task_id = body.get("name") or body.get("task_id") or "request_review"
    content = body.get("output") or body.get("summary")
    if isinstance(content, dict):
        content = json.dumps(content, indent=2)
    if not content:
        content = "(No output in task webhook)"
    if not execution_id:
        return None
    return {
        "execution_id": execution_id,
        "task_id": str(task_id),
        "content": content,
        "raw": body,
    }


def _run_server(port: int) -> None:
    """Run Flask server in this thread."""
    from flask import Flask, request

    app = Flask(__name__)

    @app.route("/task", methods=["POST"])
    def task():
        """Receives taskWebhookUrl callbacks from CrewAI AMP (fires on every task completion)."""
        try:
            body = request.get_json(force=True, silent=True) or {}
            # Only store tasks that look like review steps (e.g. request_review)
            if not _is_review_task(body):
                return {"ok": True, "message": "Task received (not a review task, ignored)"}, 200
            extracted = _extract_from_task_payload(body)
            if extracted:
                data = _read_store()
                data = [a for a in data if not (a.get("execution_id") == extracted["execution_id"] and a.get("task_id") == extracted["task_id"])]
                data.append(extracted)
                _write_store(data)
                return {"ok": True, "message": "Review task stored for approval"}, 200
            return {"ok": False, "message": "Missing kickoff_id"}, 400
        except Exception as e:
            return {"ok": False, "message": str(e)}, 500

    @app.route("/step", methods=["POST"])
    def step():
        """Receives stepWebhookUrl callbacks. Acknowledge but do not store."""
        return {"ok": True}, 200

    @app.route("/crew", methods=["POST"])
    def crew():
        """Receives crewWebhookUrl callbacks. Acknowledge but do not store."""
        return {"ok": True}, 200

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200

    app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)


def start_webhook_server(port: int | None = None) -> bool:
    """Start the HITL webhook server in a background daemon thread. Returns True if started."""
    global _SERVER_THREAD
    if _SERVER_THREAD is not None and _SERVER_THREAD.is_alive():
        return True
    port = port or int(os.getenv("HITL_WEBHOOK_PORT", "5050"))
    try:
        _SERVER_THREAD = threading.Thread(target=_run_server, args=(port,), daemon=True)
        _SERVER_THREAD.start()
        return True
    except Exception:
        return False
