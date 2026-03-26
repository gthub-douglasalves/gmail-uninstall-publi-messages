"""Escaneamento de e-mails promocionais e extração de headers de desinscrição."""

import re
import email.utils
from dataclasses import dataclass, field

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn


@dataclass
class SenderInfo:
    """Informações agrupadas de um remetente."""
    email: str
    display_name: str
    count: int = 0
    unsubscribe_links: list[str] = field(default_factory=list)
    unsubscribe_mailto: list[str] = field(default_factory=list)
    has_one_click: bool = False
    message_ids: list[str] = field(default_factory=list)

    @property
    def has_unsubscribe(self) -> bool:
        return bool(self.unsubscribe_links or self.unsubscribe_mailto)

    @property
    def method_label(self) -> str:
        if self.unsubscribe_links:
            return "HTTP" + (" (One-Click)" if self.has_one_click else "")
        if self.unsubscribe_mailto:
            return "E-mail"
        return "Nenhum"


def scan_emails(service, max_results: int = 500,
                query: str = "category:promotions") -> dict[str, SenderInfo]:
    """Busca e-mails e agrupa por remetente."""
    msg_ids = _fetch_message_ids(service, query, max_results)

    if not msg_ids:
        return {}

    senders: dict[str, SenderInfo] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Analisando e-mails..."),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    ) as progress:
        task = progress.add_task("scan", total=len(msg_ids))

        # Process in batches of 50
        for i in range(0, len(msg_ids), 50):
            batch_ids = msg_ids[i:i + 50]
            batch = service.new_batch_http_request()

            results = {}

            def make_callback(mid):
                def callback(request_id, response, exception):
                    if exception is None:
                        results[mid] = response
                return callback

            for mid in batch_ids:
                batch.add(
                    service.users().messages().get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["From", "List-Unsubscribe",
                                         "List-Unsubscribe-Post"],
                    ),
                    callback=make_callback(mid),
                )

            batch.execute()

            for mid, msg in results.items():
                headers = {h["name"].lower(): h["value"]
                           for h in msg.get("payload", {}).get("headers", [])}

                from_header = headers.get("from", "")
                sender_name, sender_email = _parse_from(from_header)

                if not sender_email:
                    progress.advance(task)
                    continue

                key = sender_email.lower()

                if key not in senders:
                    senders[key] = SenderInfo(
                        email=sender_email,
                        display_name=sender_name or sender_email,
                    )

                info = senders[key]
                info.count += 1
                info.message_ids.append(mid)

                unsub_header = headers.get("list-unsubscribe", "")
                if unsub_header:
                    links, mailtos = _parse_unsubscribe_header(unsub_header)
                    for link in links:
                        if link not in info.unsubscribe_links:
                            info.unsubscribe_links.append(link)
                    for mailto in mailtos:
                        if mailto not in info.unsubscribe_mailto:
                            info.unsubscribe_mailto.append(mailto)

                if headers.get("list-unsubscribe-post", ""):
                    info.has_one_click = True

                progress.advance(task)

    return dict(sorted(senders.items(), key=lambda x: x[1].count, reverse=True))


def _fetch_message_ids(service, query: str, max_results: int) -> list[str]:
    """Busca IDs de mensagens paginando pela API."""
    ids = []
    page_token = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Buscando e-mails promocionais..."),
    ) as progress:
        progress.add_task("fetch", total=None)

        while len(ids) < max_results:
            batch_size = min(500, max_results - len(ids))
            result = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=batch_size,
                pageToken=page_token,
            ).execute()

            messages = result.get("messages", [])
            if not messages:
                break

            ids.extend(m["id"] for m in messages)
            page_token = result.get("nextPageToken")
            if not page_token:
                break

    return ids[:max_results]


def _parse_from(from_header: str) -> tuple[str, str]:
    """Extrai nome e e-mail do header From."""
    name, addr = email.utils.parseaddr(from_header)
    return name, addr


def _parse_unsubscribe_header(header: str) -> tuple[list[str], list[str]]:
    """Analisa o header List-Unsubscribe e retorna (links_http, links_mailto)."""
    http_links = []
    mailto_links = []

    # Extract URLs between angle brackets
    urls = re.findall(r"<([^>]+)>", header)

    for url in urls:
        url = url.strip()
        if url.lower().startswith("http://") or url.lower().startswith("https://"):
            http_links.append(url)
        elif url.lower().startswith("mailto:"):
            mailto_links.append(url)

    return http_links, mailto_links
