"""Transactional email behind ``EmailProvider``. ``ConsoleEmail`` logs + keeps an in-memory ``outbox``
(tests read it); ``ResendEmail`` posts to the Resend API."""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import get_settings

log = logging.getLogger("inaiflow.email")


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None
    tag: str | None = None  # e.g. EMAIL_VERIFY, PASSWORD_RESET, INVITATION


class EmailProvider(abc.ABC):
    name = "abstract"

    @abc.abstractmethod
    async def send(self, message: EmailMessage) -> None: ...

    async def health(self) -> str:
        return "ok"


class ConsoleEmail(EmailProvider):
    name = "console"

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.outbox = [*self.outbox[-99:], message]  # dev/test only (production refuses console email); keep it bounded
        log.info("email to=%s subject=%r tag=%s\n%s", message.to, message.subject, message.tag, message.text)

    def last_to(self, to: str, tag: str | None = None) -> EmailMessage | None:
        for m in reversed(self.outbox):
            if m.to.lower() == to.lower() and (tag is None or m.tag == tag):
                return m
        return None


class ResendEmail(EmailProvider):
    name = "resend"

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key, self.sender = api_key, sender

    async def send(self, message: EmailMessage) -> None:
        payload = {"from": self.sender, "to": [message.to], "subject": message.subject, "text": message.text}
        if message.html:
            payload["html"] = message.html
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            if resp.status_code >= 400:
                log.error("resend failed status=%s body=%s", resp.status_code, resp.text[:300])
        except httpx.HTTPError:
            # Email is best effort: never fail the business transaction because the provider is down.
            log.exception("resend unreachable")


@lru_cache
def get_email() -> EmailProvider:
    s = get_settings()
    if s.EMAIL_PROVIDER == "resend" and s.RESEND_API_KEY:
        return ResendEmail(s.RESEND_API_KEY, s.EMAIL_FROM)
    return ConsoleEmail()
