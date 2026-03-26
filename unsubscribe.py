"""
Gmail Unsubscriber - Desinscreve de e-mails promocionais do Gmail.

Uso:
  1. Coloque o arquivo credentials.json na mesma pasta (veja README.md)
  2. pip install -r requirements.txt
  3. python unsubscribe.py
"""

import os
import sys
import re
import email.utils
import base64
from email.mime.text import MIMEText
from urllib.parse import parse_qs

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


# ── Autenticação ─────────────────────────────────────────────────────────────

def login():
    """Autentica com o Gmail e retorna o serviço da API."""
    if not os.path.exists("credentials.json"):
        print("ERRO: arquivo 'credentials.json' não encontrado.")
        print()
        print("Como obter:")
        print("  1. Acesse https://console.cloud.google.com/")
        print("  2. Crie um projeto e ative a Gmail API")
        print("  3. Crie credenciais OAuth 2.0 (tipo: App para computador)")
        print("  4. Baixe o JSON e salve como 'credentials.json' aqui")
        sys.exit(1)

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                os.remove("token.json")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Busca de e-mails ─────────────────────────────────────────────────────────

def buscar_emails(service, max_results=500):
    """Busca e-mails promocionais e agrupa por remetente."""
    print("Buscando e-mails promocionais...")

    # Buscar IDs
    ids = []
    page_token = None
    while len(ids) < max_results:
        resp = service.users().messages().list(
            userId="me", q="category:promotions",
            maxResults=min(500, max_results - len(ids)),
            pageToken=page_token,
        ).execute()
        msgs = resp.get("messages", [])
        if not msgs:
            break
        ids.extend(m["id"] for m in msgs)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not ids:
        print("Nenhum e-mail promocional encontrado.")
        return {}

    print(f"Encontrados {len(ids)} e-mails. Analisando...")

    # Buscar headers em lotes
    remetentes = {}  # email -> {name, count, links, mailtos, one_click, msg_ids}

    for i in range(0, len(ids), 50):
        lote = ids[i:i + 50]
        batch = service.new_batch_http_request()
        resultados = {}

        def make_cb(mid):
            def cb(req_id, resp, exc):
                if not exc:
                    resultados[mid] = resp
            return cb

        for mid in lote:
            batch.add(
                service.users().messages().get(
                    userId="me", id=mid, format="metadata",
                    metadataHeaders=["From", "List-Unsubscribe", "List-Unsubscribe-Post"],
                ),
                callback=make_cb(mid),
            )
        batch.execute()

        for mid, msg in resultados.items():
            headers = {h["name"].lower(): h["value"]
                       for h in msg.get("payload", {}).get("headers", [])}

            nome, addr = email.utils.parseaddr(headers.get("from", ""))
            if not addr:
                continue

            key = addr.lower()
            if key not in remetentes:
                remetentes[key] = {
                    "name": nome or addr, "email": addr, "count": 0,
                    "links": [], "mailtos": [], "one_click": False, "msg_ids": [],
                }

            r = remetentes[key]
            r["count"] += 1
            r["msg_ids"].append(mid)

            unsub = headers.get("list-unsubscribe", "")
            if unsub:
                for url in re.findall(r"<([^>]+)>", unsub):
                    url = url.strip()
                    if url.startswith("http") and url not in r["links"]:
                        r["links"].append(url)
                    elif url.startswith("mailto:") and url not in r["mailtos"]:
                        r["mailtos"].append(url)

            if headers.get("list-unsubscribe-post"):
                r["one_click"] = True

        print(f"  {min(i + 50, len(ids))}/{len(ids)}")

    # Ordenar por quantidade
    return dict(sorted(remetentes.items(), key=lambda x: x[1]["count"], reverse=True))


# ── Desinscrição ─────────────────────────────────────────────────────────────

def desinscrever_http(url, usar_post, session):
    """Tenta desinscrever via HTTP. Retorna (sucesso, detalhe)."""
    try:
        if usar_post:
            resp = session.post(url, data={"List-Unsubscribe": "One-Click"}, timeout=15)
        else:
            resp = session.get(url, timeout=15)
        return resp.status_code < 400, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:80]


def desinscrever_mailto(mailto_uri, service):
    """Envia e-mail de desinscrição via Gmail API."""
    try:
        uri = mailto_uri[7:] if mailto_uri.lower().startswith("mailto:") else mailto_uri
        if "?" in uri:
            addr, qs = uri.split("?", 1)
            params = parse_qs(qs)
            subject = params.get("subject", ["unsubscribe"])[0]
        else:
            addr, subject = uri, "unsubscribe"

        msg = MIMEText("unsubscribe")
        msg["to"] = addr
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, f"E-mail enviado para {addr}"
    except Exception as e:
        return False, str(e)[:80]


def desinscrever(remetente, session, service):
    """Tenta desinscrever de um remetente."""
    # 1. HTTP POST (One-Click)
    if remetente["links"] and remetente["one_click"]:
        for url in remetente["links"]:
            ok, msg = desinscrever_http(url, True, session)
            if ok:
                return True, f"POST {msg}"

    # 2. HTTP GET
    if remetente["links"]:
        for url in remetente["links"]:
            ok, msg = desinscrever_http(url, False, session)
            if ok:
                return True, f"GET {msg}"

    # 3. Mailto
    if remetente["mailtos"]:
        for mailto in remetente["mailtos"]:
            ok, msg = desinscrever_mailto(mailto, service)
            if ok:
                return True, msg

    return False, "Sem método disponível"


def lixeira(service, msg_ids):
    """Move e-mails para a lixeira."""
    for i in range(0, len(msg_ids), 50):
        lote = msg_ids[i:i + 50]
        batch = service.new_batch_http_request()
        for mid in lote:
            batch.add(service.users().messages().trash(userId="me", id=mid))
        batch.execute()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=== Gmail Unsubscriber ===")
    print()

    service = login()
    print("Autenticado!\n")

    remetentes = buscar_emails(service)
    if not remetentes:
        return

    # Mostrar lista
    lista = list(remetentes.values())
    print(f"\n{'#':>4}  {'Remetente':<40} {'Qtd':>5}  Método")
    print("-" * 70)
    for i, r in enumerate(lista, 1):
        metodo = "HTTP" if r["links"] else ("E-mail" if r["mailtos"] else "---")
        nome = r["name"][:38]
        print(f"{i:>4}  {nome:<40} {r['count']:>5}  {metodo}")

    # Seleção
    print()
    sel = input("Quais desinscrever? (ex: 1,3,5-10 ou 'todos') [todos]: ").strip()
    if not sel:
        sel = "todos"

    if sel.lower() in ("todos", "all", "*"):
        indices = list(range(len(lista)))
    else:
        indices = []
        for parte in sel.split(","):
            parte = parte.strip()
            if "-" in parte:
                a, b = parte.split("-", 1)
                try:
                    indices.extend(range(int(a) - 1, int(b)))
                except ValueError:
                    pass
            else:
                try:
                    indices.append(int(parte) - 1)
                except ValueError:
                    pass
        indices = [i for i in indices if 0 <= i < len(lista)]

    if not indices:
        print("Nenhum selecionado.")
        return

    # Perguntar se quer apagar
    apagar = input("Mover e-mails para a lixeira também? (s/N): ").strip().lower() == "s"

    # Desinscrever
    print()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    ok_count = 0
    for i in indices:
        r = lista[i]
        print(f"  {r['name']} ({r['email']})... ", end="", flush=True)

        sucesso, detalhe = desinscrever(r, session, service)

        if sucesso:
            print(f"OK ({detalhe})")
            ok_count += 1
        else:
            print(f"FALHOU ({detalhe})")

        if apagar:
            lixeira(service, r["msg_ids"])

    # Resumo
    print()
    print(f"Concluído: {ok_count}/{len(indices)} desinscrições com sucesso.")
    if apagar:
        total = sum(lista[i]["count"] for i in indices)
        print(f"{total} e-mails movidos para a lixeira.")
    print()


if __name__ == "__main__":
    main()
