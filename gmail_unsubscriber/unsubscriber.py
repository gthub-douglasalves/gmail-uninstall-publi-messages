"""Execução de desinscrição via HTTP e mailto."""

import base64
import re
from dataclasses import dataclass
from email.mime.text import MIMEText
from urllib.parse import urlparse, parse_qs

import requests

from .scanner import SenderInfo


@dataclass
class UnsubscribeResult:
    """Resultado de uma tentativa de desinscrição."""
    sender_email: str
    sender_name: str
    method_used: str  # "http-post", "http-get", "mailto", "none"
    success: bool
    detail: str
    needs_confirmation: bool = False
    emails_trashed: int = 0
    emails_archived: int = 0


def unsubscribe(sender: SenderInfo, session: requests.Session,
                gmail_service=None, skip_mailto: bool = False,
                dry_run: bool = False) -> UnsubscribeResult:
    """Tenta desinscrever de um remetente, priorizando os métodos mais confiáveis."""

    if dry_run:
        method = "nenhum"
        if sender.unsubscribe_links:
            method = "http-post" if sender.has_one_click else "http-get"
        elif sender.unsubscribe_mailto:
            method = "mailto"
        return UnsubscribeResult(
            sender_email=sender.email,
            sender_name=sender.display_name,
            method_used=method,
            success=True,
            detail="[dry-run] Nenhuma ação executada",
        )

    # 1. Try HTTP with POST (One-Click, RFC 8058)
    if sender.unsubscribe_links and sender.has_one_click:
        for url in sender.unsubscribe_links:
            success, detail, needs_confirm = _try_http_unsubscribe(
                url, use_post=True, session=session
            )
            if success:
                return UnsubscribeResult(
                    sender_email=sender.email,
                    sender_name=sender.display_name,
                    method_used="http-post",
                    success=True,
                    detail=detail,
                    needs_confirmation=needs_confirm,
                )

    # 2. Try HTTP with GET
    if sender.unsubscribe_links:
        for url in sender.unsubscribe_links:
            success, detail, needs_confirm = _try_http_unsubscribe(
                url, use_post=False, session=session
            )
            if success:
                return UnsubscribeResult(
                    sender_email=sender.email,
                    sender_name=sender.display_name,
                    method_used="http-get",
                    success=True,
                    detail=detail,
                    needs_confirmation=needs_confirm,
                )

    # 3. Try mailto
    if sender.unsubscribe_mailto and not skip_mailto and gmail_service:
        for mailto in sender.unsubscribe_mailto:
            success, detail = _try_mailto_unsubscribe(mailto, gmail_service)
            if success:
                return UnsubscribeResult(
                    sender_email=sender.email,
                    sender_name=sender.display_name,
                    method_used="mailto",
                    success=True,
                    detail=detail,
                )

    # No method available or all failed
    if not sender.has_unsubscribe:
        return UnsubscribeResult(
            sender_email=sender.email,
            sender_name=sender.display_name,
            method_used="nenhum",
            success=False,
            detail="Nenhum método de desinscrição disponível",
        )

    return UnsubscribeResult(
        sender_email=sender.email,
        sender_name=sender.display_name,
        method_used="falhou",
        success=False,
        detail="Todas as tentativas falharam",
    )


def _try_http_unsubscribe(url: str, use_post: bool,
                          session: requests.Session) -> tuple[bool, str, bool]:
    """Tenta desinscrição via HTTP. Retorna (sucesso, detalhe, precisa_confirmação)."""
    try:
        if use_post:
            resp = session.post(
                url,
                data={"List-Unsubscribe": "One-Click"},
                timeout=15,
                allow_redirects=True,
            )
        else:
            resp = session.get(url, timeout=15, allow_redirects=True)

        needs_confirm = False
        if resp.status_code < 400:
            body = resp.text.lower() if resp.text else ""
            if "<form" in body or "captcha" in body or "confirmar" in body or "confirm" in body:
                needs_confirm = True

            method = "POST" if use_post else "GET"
            return True, f"{method} {url} -> {resp.status_code}", needs_confirm

        return False, f"HTTP {resp.status_code}", False

    except requests.Timeout:
        return False, "Timeout", False
    except requests.RequestException as e:
        return False, str(e)[:100], False


def _try_mailto_unsubscribe(mailto_uri: str, gmail_service) -> tuple[bool, str]:
    """Envia e-mail de desinscrição via API do Gmail."""
    try:
        to_addr, subject, body_text = _parse_mailto(mailto_uri)
        if not to_addr:
            return False, "Endereço mailto inválido"

        message = MIMEText(body_text or "unsubscribe")
        message["to"] = to_addr
        message["subject"] = subject or "unsubscribe"

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail_service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        return True, f"E-mail enviado para {to_addr}"

    except Exception as e:
        return False, str(e)[:100]


def _parse_mailto(mailto_uri: str) -> tuple[str, str, str]:
    """Extrai endereço, assunto e corpo de um URI mailto."""
    # Remove 'mailto:' prefix
    uri = mailto_uri
    if uri.lower().startswith("mailto:"):
        uri = uri[7:]

    # Split address and query
    if "?" in uri:
        addr, query_str = uri.split("?", 1)
        params = parse_qs(query_str)
        subject = params.get("subject", [""])[0]
        body = params.get("body", [""])[0]
    else:
        addr = uri
        subject = ""
        body = ""

    return addr, subject, body


def trash_emails(service, message_ids: list[str]) -> int:
    """Move e-mails para a lixeira em lotes."""
    if not message_ids:
        return 0

    count = 0
    for i in range(0, len(message_ids), 50):
        batch_ids = message_ids[i:i + 50]
        batch = service.new_batch_http_request()

        def make_callback():
            def callback(request_id, response, exception):
                nonlocal count
                if exception is None:
                    count += 1
            return callback

        for mid in batch_ids:
            batch.add(
                service.users().messages().trash(userId="me", id=mid),
                callback=make_callback(),
            )

        batch.execute()

    return count


def archive_emails(service, message_ids: list[str]) -> int:
    """Remove o label INBOX dos e-mails (arquiva)."""
    if not message_ids:
        return 0

    count = 0
    for i in range(0, len(message_ids), 50):
        batch_ids = message_ids[i:i + 50]
        batch = service.new_batch_http_request()

        def make_callback():
            def callback(request_id, response, exception):
                nonlocal count
                if exception is None:
                    count += 1
            return callback

        for mid in batch_ids:
            batch.add(
                service.users().messages().modify(
                    userId="me", id=mid,
                    body={"removeLabelIds": ["INBOX"]},
                ),
                callback=make_callback(),
            )

        batch.execute()

    return count
