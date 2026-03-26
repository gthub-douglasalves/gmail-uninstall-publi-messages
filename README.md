# Gmail Unsubscriber

Desinscreve automaticamente de e-mails promocionais do Gmail.
Funciona no navegador do iPhone (ou qualquer dispositivo).

## Configuração (uma vez só)

1. Acesse https://console.cloud.google.com/
2. Crie um projeto e ative a **Gmail API**
3. Crie credenciais **OAuth 2.0** (tipo: **Aplicativo da Web**)
4. Em "URIs de redirecionamento autorizados", adicione: `http://localhost:5000/callback`
5. Baixe o JSON e salve como `credentials.json` nesta pasta
6. Em "Tela de consentimento OAuth", adicione seu e-mail como usuário de teste

## Uso

```bash
pip install -r requirements.txt
python app.py
```

Abra no navegador do iPhone: `http://<ip-do-seu-computador>:5000`

**Dica:** No iPhone, abra o site no Safari e toque em "Adicionar à Tela de Início" para usar como um app.

## Versão CLI

Também tem a versão de terminal:

```bash
python unsubscribe.py
```
