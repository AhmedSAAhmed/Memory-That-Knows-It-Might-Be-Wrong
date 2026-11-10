"""Server-issued, expiring identities shared by HTTP and Gradio callbacks."""
import hashlib
import hmac
import os
import secrets
import time
from uuid import uuid4

from app.config import memory_config


class SessionIdentity:
    def __init__(self, *, secret: bytes | None = None, timer=time.time):
        self.secret = secret or os.getenv("SESSION_SECRET", "").encode() or secrets.token_bytes(32)
        self.timer = timer

    def issue(self) -> str:
        payload = f"{uuid4().hex}.{int(self.timer())}"
        return payload + "." + hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()

    def verify(self, token: str | None) -> str | None:
        if not isinstance(token, str):
            return None
        try:
            customer, timestamp, signature = token.split(".")
            if len(customer) != 32 or any(ch not in "0123456789abcdef" for ch in customer):
                return None
            payload = customer + "." + timestamp
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
            age = self.timer() - int(timestamp)
            if hmac.compare_digest(expected, signature) and 0 <= age < memory_config()["demo"]["session_seconds"]:
                return customer
        except (ValueError, TypeError):
            pass
        return None

    def customer(self, request) -> str:
        customer = self.verify(dict(request.cookies).get("memory_session"))
        if not customer:
            raise ValueError("Refresh the page to start a private demo session.")
        return customer
