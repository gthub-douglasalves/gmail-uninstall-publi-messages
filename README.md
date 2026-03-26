# Gmail Unsubscriber

Ferramenta CLI em Python para desinscrever automaticamente de e-mails promocionais do Gmail.

## Funcionalidades

- Escaneia e-mails promocionais do Gmail via API
- Agrupa por remetente e mostra quantidade de e-mails
- Desinscreve via HTTP (One-Click RFC 8058) ou mailto
- Opção para mover e-mails para lixeira ou arquivar
- Relatório detalhado das ações executadas
- Modo simulação (dry-run)

## Pré-requisitos

- Python 3.10+
- Uma conta Google/Gmail

## Configuração do Google Cloud

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto (ou selecione um existente)
3. Ative a **Gmail API**:
   - Menu → APIs e Serviços → Biblioteca
   - Pesquise "Gmail API" → Ativar
4. Crie credenciais OAuth 2.0:
   - Menu → APIs e Serviços → Credenciais
   - Criar credenciais → ID do cliente OAuth
   - Tipo: **Aplicativo para computador**
   - Baixe o arquivo JSON
5. Renomeie o arquivo para `credentials.json` e coloque na raiz do projeto
6. Em "Tela de consentimento OAuth", adicione seu e-mail como usuário de teste

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Uso básico - escaneia promoções e permite selecionar
python -m gmail_unsubscriber

# Escanear mais e-mails
python -m gmail_unsubscriber --max-results 1000

# Desinscrever e mover para lixeira
python -m gmail_unsubscriber --trash

# Desinscrever e arquivar
python -m gmail_unsubscriber --archive

# Busca personalizada
python -m gmail_unsubscriber --query "from:newsletter"

# Modo simulação (não executa nada)
python -m gmail_unsubscriber --dry-run

# Selecionar todos automaticamente e salvar relatório
python -m gmail_unsubscriber --all --report relatorio.json

# Pular desinscrição via e-mail (mailto)
python -m gmail_unsubscriber --skip-mailto
```

## Opções

| Flag | Descrição |
|------|-----------|
| `--credentials` | Caminho do arquivo de credenciais (padrão: `credentials.json`) |
| `--max-results` | Máximo de e-mails a analisar (padrão: 500) |
| `--query` | Consulta de busca do Gmail (padrão: `category:promotions`) |
| `--trash` | Mover e-mails para a lixeira |
| `--archive` | Arquivar e-mails |
| `--skip-mailto` | Não enviar e-mails de desinscrição |
| `--dry-run` | Simular sem executar |
| `--report` | Salvar relatório em JSON |
| `--all` | Selecionar todos os remetentes |

## Segurança

- `credentials.json` e `token.json` estão no `.gitignore`
- O token é armazenado localmente e pode ser revogado a qualquer momento
- A ferramenta usa o escopo `gmail.modify` (não permite exclusão permanente)
