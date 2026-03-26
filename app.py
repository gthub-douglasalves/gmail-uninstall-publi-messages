"""
Gmail Unsubscriber - Web App para desinscrever de e-mails promocionais.

Uso:
  1. Coloque o arquivo credentials.json nesta pasta (veja README.md)
  2. pip install -r requirements.txt
  3. python app.py
  4. Abra no navegador do iPhone: http://<seu-ip>:5000
"""

import os
import re
import json
import email.utils
import base64
from email.mime.text import MIMEText
from urllib.parse import parse_qs

import requests as http_requests
from flask import Flask, redirect, url_for, session, request, render_template_string
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = os.urandom(24)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

# ── HTML Templates ───────────────────────────────────────────────────────────

PAGE_BASE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Unsubscriber">
<title>Gmail Unsubscriber</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    background: #f5f5f7; color: #1d1d1f;
    max-width: 600px; margin: 0 auto; padding: 16px;
    padding-bottom: 100px;
  }
  h1 { font-size: 24px; text-align: center; margin: 20px 0; }
  h2 { font-size: 18px; margin: 16px 0 8px; }
  .card {
    background: #fff; border-radius: 12px;
    padding: 16px; margin: 8px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  .sender {
    display: flex; align-items: center;
    padding: 12px 0; border-bottom: 1px solid #f0f0f0;
  }
  .sender:last-child { border-bottom: none; }
  .sender input[type=checkbox] {
    width: 22px; height: 22px; margin-right: 12px;
    accent-color: #007aff; flex-shrink: 0;
  }
  .sender-info { flex: 1; min-width: 0; }
  .sender-name {
    font-weight: 600; font-size: 15px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .sender-email {
    font-size: 12px; color: #86868b;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .sender-count {
    background: #e8e8ed; border-radius: 12px;
    padding: 2px 10px; font-size: 13px; font-weight: 600;
    margin-left: 8px; flex-shrink: 0;
  }
  .badge {
    font-size: 10px; padding: 2px 6px; border-radius: 4px;
    font-weight: 600; margin-left: 6px;
  }
  .badge-http { background: #d4edda; color: #155724; }
  .badge-mail { background: #fff3cd; color: #856404; }
  .badge-none { background: #f8d7da; color: #721c24; }
  .btn {
    display: block; width: 100%; padding: 16px;
    background: #007aff; color: #fff;
    border: none; border-radius: 12px;
    font-size: 17px; font-weight: 600;
    cursor: pointer; text-align: center;
    text-decoration: none;
    margin-top: 12px;
  }
  .btn:active { background: #005ecb; }
  .btn-danger { background: #ff3b30; }
  .btn-danger:active { background: #d63028; }
  .btn-outline {
    background: #fff; color: #007aff;
    border: 2px solid #007aff;
  }
  .btn-login {
    background: #fff; color: #1d1d1f; border: 2px solid #e8e8ed;
    display: flex; align-items: center; justify-content: center; gap: 10px;
    margin-top: 40px;
  }
  .toolbar {
    position: fixed; bottom: 0; left: 0; right: 0;
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(10px);
    padding: 12px 16px; padding-bottom: max(12px, env(safe-area-inset-bottom));
    border-top: 1px solid #e8e8ed;
    max-width: 600px; margin: 0 auto;
  }
  .select-bar {
    display: flex; gap: 8px; margin-bottom: 8px;
    font-size: 14px;
  }
  .select-bar a {
    color: #007aff; text-decoration: none;
    padding: 4px 8px;
  }
  .status { text-align: center; padding: 40px 16px; color: #86868b; }
  .status .icon { font-size: 48px; margin-bottom: 12px; }
  .result-ok { color: #34c759; }
  .result-fail { color: #ff3b30; }
  .result-item {
    padding: 10px 0; border-bottom: 1px solid #f0f0f0;
    font-size: 14px;
  }
  .result-item:last-child { border-bottom: none; }
  .spinner {
    border: 3px solid #e8e8ed; border-top-color: #007aff;
    border-radius: 50%; width: 32px; height: 32px;
    animation: spin 0.8s linear infinite;
    margin: 20px auto;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .option-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 0;
  }
  .toggle {
    position: relative; width: 51px; height: 31px;
  }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle .slider {
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: #e8e8ed; border-radius: 31px; cursor: pointer;
    transition: 0.3s;
  }
  .toggle .slider::before {
    content: ''; position: absolute;
    width: 27px; height: 27px; left: 2px; bottom: 2px;
    background: #fff; border-radius: 50%;
    transition: 0.3s;
  }
  .toggle input:checked + .slider { background: #34c759; }
  .toggle input:checked + .slider::before { transform: translateX(20px); }
  .summary { text-align: center; font-size: 15px; margin: 12px 0; }
</style>
</head>
<body>
{{ content }}
</body>
</html>
"""

LOGIN_PAGE = """
<div style="text-align:center; margin-top: 60px;">
  <div style="font-size:64px;">📧</div>
  <h1>Gmail Unsubscriber</h1>
  <p style="color:#86868b; margin:16px;">
    Desinscreva-se de e-mails<br>promocionais automaticamente
  </p>
  <a href="/auth" class="btn btn-login">
    Entrar com Google
  </a>
</div>
"""

LOADING_PAGE = """
<h1>Gmail Unsubscriber</h1>
<div class="card">
  <div class="status">
    <div class="spinner"></div>
    <p>Buscando e-mails promocionais...</p>
    <p style="font-size:13px; margin-top:8px;">Isso pode levar alguns segundos</p>
  </div>
</div>
<script>fetch('/api/scan').then(r=>r.json()).then(d=>{if(d.ok)location.href='/senders';else location.href='/?erro='+d.msg;});</script>
"""

SENDERS_PAGE = """
<h1>Gmail Unsubscriber</h1>
<p class="summary">
  <strong>{{ total_emails }}</strong> e-mails de
  <strong>{{ total_senders }}</strong> remetentes
</p>

<form action="/unsubscribe" method="post" id="form">
<div class="card">
  {% for s in senders %}
  <div class="sender">
    <input type="checkbox" name="sel" value="{{ loop.index0 }}" checked>
    <div class="sender-info">
      <div class="sender-name">{{ s.name }}</div>
      <div class="sender-email">{{ s.email }}</div>
    </div>
    <span class="sender-count">{{ s.count }}</span>
    {% if s.links %}
      <span class="badge badge-http">HTTP</span>
    {% elif s.mailtos %}
      <span class="badge badge-mail">E-mail</span>
    {% else %}
      <span class="badge badge-none">---</span>
    {% endif %}
  </div>
  {% endfor %}
</div>

<div class="card">
  <div class="option-row">
    <span>Apagar e-mails também</span>
    <label class="toggle">
      <input type="checkbox" name="trash">
      <span class="slider"></span>
    </label>
  </div>
</div>

<div class="toolbar">
  <div class="select-bar">
    <a href="#" onclick="toggleAll(true);return false;">Selecionar todos</a>
    <a href="#" onclick="toggleAll(false);return false;">Nenhum</a>
  </div>
  <button type="submit" class="btn btn-danger">
    Desinscrever selecionados
  </button>
</div>
</form>

<script>
function toggleAll(checked) {
  document.querySelectorAll('input[name=sel]').forEach(c => c.checked = checked);
}
</script>
"""

PROCESSING_PAGE = """
<h1>Gmail Unsubscriber</h1>
<div class="card">
  <div class="status">
    <div class="spinner"></div>
    <p>Desinscrevendo...</p>
    <p style="font-size:13px; margin-top:8px;">{{ count }} remetentes</p>
  </div>
</div>
<script>
fetch('/api/unsubscribe', {method:'POST',headers:{'Content-Type':'application/json'},
  body: JSON.stringify({{ data | tojson }})
}).then(r=>r.json()).then(d=>{location.href='/results';});
</script>
"""

RESULTS_PAGE = """
<h1>Concluído!</h1>
<div class="card">
  <div class="status">
    <div class="icon">{{ '✅' if ok > 0 else '⚠️' }}</div>
    <p><strong>{{ ok }}</strong> desinscrições com sucesso</p>
    {% if fail > 0 %}
    <p class="result-fail">{{ fail }} falharam</p>
    {% endif %}
    {% if trashed > 0 %}
    <p style="margin-top:8px;">{{ trashed }} e-mails na lixeira</p>
    {% endif %}
  </div>
</div>

<div class="card">
  {% for r in results %}
  <div class="result-item">
    <span class="{{ 'result-ok' if r.success else 'result-fail' }}">
      {{ '✓' if r.success else '✗' }}
    </span>
    <strong>{{ r.name }}</strong>
    <span style="color:#86868b;">— {{ r.detail }}</span>
  </div>
  {% endfor %}
</div>

<a href="/scan" class="btn" style="margin-top:20px;">Escanear novamente</a>
<a href="/logout" class="btn btn-outline">Sair</a>
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def render(content_template, **kwargs):
    content = render_template_string(content_template, **kwargs)
    return render_template_string(PAGE_BASE, content=content)


def get_service():
    """Reconstroi o serviço Gmail a partir do token salvo na sessão."""
    token_data = session.get("token")
    if not token_data:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(token_data), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session["token"] = creds.to_json()
    if not creds.valid:
        return None
    return build("gmail", "v1", credentials=creds)


def buscar_emails(service, max_results=500):
    """Busca e-mails promocionais e agrupa por remetente."""
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
        return []

    remetentes = {}

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

    lista = sorted(remetentes.values(), key=lambda x: x["count"], reverse=True)
    return lista


def desinscrever_http(url, usar_post, sess):
    try:
        if usar_post:
            resp = sess.post(url, data={"List-Unsubscribe": "One-Click"}, timeout=15)
        else:
            resp = sess.get(url, timeout=15)
        return resp.status_code < 400, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:80]


def desinscrever_mailto(mailto_uri, service):
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
        return True, f"E-mail para {addr}"
    except Exception as e:
        return False, str(e)[:80]


def desinscrever(remetente, sess, service):
    if remetente["links"] and remetente["one_click"]:
        for url in remetente["links"]:
            ok, msg = desinscrever_http(url, True, sess)
            if ok:
                return True, f"POST {msg}"
    if remetente["links"]:
        for url in remetente["links"]:
            ok, msg = desinscrever_http(url, False, sess)
            if ok:
                return True, f"GET {msg}"
    if remetente["mailtos"]:
        for mailto in remetente["mailtos"]:
            ok, msg = desinscrever_mailto(mailto, service)
            if ok:
                return True, msg
    return False, "Sem método disponível"


def lixeira(service, msg_ids):
    for i in range(0, len(msg_ids), 50):
        lote = msg_ids[i:i + 50]
        batch = service.new_batch_http_request()
        for mid in lote:
            batch.add(service.users().messages().trash(userId="me", id=mid))
        batch.execute()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if session.get("token"):
        return redirect(url_for("scan"))
    return render(LOGIN_PAGE)


@app.route("/auth")
def auth():
    flow = Flow.from_client_secrets_file(
        "credentials.json", scopes=SCOPES,
        redirect_uri=request.url_root.rstrip("/") + "/callback",
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent",
    )
    session["state"] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    flow = Flow.from_client_secrets_file(
        "credentials.json", scopes=SCOPES,
        redirect_uri=request.url_root.rstrip("/") + "/callback",
        state=session.get("state"),
    )
    flow.fetch_token(authorization_response=request.url)
    session["token"] = flow.credentials.to_json()
    return redirect(url_for("scan"))


@app.route("/scan")
def scan():
    if not session.get("token"):
        return redirect(url_for("index"))
    return render(LOADING_PAGE)


@app.route("/api/scan")
def api_scan():
    service = get_service()
    if not service:
        return json.dumps({"ok": False, "msg": "Não autenticado"})

    lista = buscar_emails(service)
    session["senders"] = lista
    return json.dumps({"ok": True, "count": len(lista)})


@app.route("/senders")
def senders():
    if not session.get("token"):
        return redirect(url_for("index"))
    lista = session.get("senders", [])
    if not lista:
        return redirect(url_for("scan"))
    total_emails = sum(s["count"] for s in lista)
    return render(SENDERS_PAGE, senders=lista,
                  total_emails=total_emails, total_senders=len(lista))


@app.route("/unsubscribe", methods=["POST"])
def unsubscribe_form():
    if not session.get("token"):
        return redirect(url_for("index"))
    selected = request.form.getlist("sel")
    trash = "trash" in request.form
    data = {"selected": selected, "trash": trash}
    return render(PROCESSING_PAGE, count=len(selected), data=data)


@app.route("/api/unsubscribe", methods=["POST"])
def api_unsubscribe():
    service = get_service()
    if not service:
        return json.dumps({"ok": False})

    data = request.get_json()
    selected = [int(i) for i in data.get("selected", [])]
    do_trash = data.get("trash", False)
    lista = session.get("senders", [])

    sess = http_requests.Session()
    sess.headers["User-Agent"] = "Mozilla/5.0"

    results = []
    trashed = 0
    for idx in selected:
        if 0 <= idx < len(lista):
            s = lista[idx]
            ok, detail = desinscrever(s, sess, service)
            results.append({"name": s["name"], "email": s["email"],
                            "success": ok, "detail": detail})
            if do_trash:
                lixeira(service, s["msg_ids"])
                trashed += s["count"]

    session["results"] = results
    session["trashed"] = trashed
    return json.dumps({"ok": True})


@app.route("/results")
def results():
    if not session.get("token"):
        return redirect(url_for("index"))
    res = session.get("results", [])
    trashed = session.get("trashed", 0)
    ok = sum(1 for r in res if r["success"])
    fail = sum(1 for r in res if not r["success"])
    return render(RESULTS_PAGE, results=res, ok=ok, fail=fail, trashed=trashed)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # permite HTTP local
    print()
    print("=== Gmail Unsubscriber ===")
    print("Abra no iPhone: http://<seu-ip>:5000")
    print()
    app.run(host="0.0.0.0", port=5000, debug=True)
