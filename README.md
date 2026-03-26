# Gmail Unsubscriber

Desinscreve automaticamente de e-mails promocionais do Gmail.

## Configuração (uma vez só)

1. Acesse https://console.cloud.google.com/
2. Crie um projeto e ative a **Gmail API**
3. Crie credenciais **OAuth 2.0** (tipo: Aplicativo para computador)
4. Baixe o JSON e salve como `credentials.json` nesta pasta
5. Em "Tela de consentimento OAuth", adicione seu e-mail como usuário de teste

## Uso

```bash
pip install -r requirements.txt
python unsubscribe.py
```

O programa vai:
1. Abrir o navegador para você autorizar (só na primeira vez)
2. Listar todos os remetentes de e-mails promocionais
3. Perguntar de quais você quer desinscrever
4. Perguntar se quer mover os e-mails para a lixeira
5. Executar a desinscrição automaticamente
