"""Autenticação OAuth2 com a API do Gmail."""

import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service(credentials_path: str = "credentials.json",
                      token_path: str = "token.json"):
    """Autentica e retorna o serviço da API do Gmail."""
    if not os.path.exists(credentials_path):
        print(f"[ERRO] Arquivo '{credentials_path}' não encontrado.")
        print()
        print("Para usar esta ferramenta, você precisa criar credenciais OAuth2:")
        print("  1. Acesse https://console.cloud.google.com/")
        print("  2. Crie um projeto e ative a API do Gmail")
        print("  3. Crie credenciais OAuth 2.0 (tipo: Aplicativo para computador)")
        print("  4. Baixe o arquivo JSON e salve como 'credentials.json' neste diretório")
        sys.exit(1)

    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                os.remove(token_path)
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
