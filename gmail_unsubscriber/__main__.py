"""CLI principal do Gmail Unsubscriber."""

import argparse
import sys

import requests
from rich.console import Console
from rich.prompt import Prompt

from .auth import get_gmail_service
from .scanner import scan_emails
from .unsubscriber import unsubscribe, trash_emails, archive_emails
from .report import display_sender_table, display_results, save_report


def parse_selection(selection: str, max_val: int) -> list[int]:
    """Converte seleção do usuário em lista de índices.

    Aceita: "1,3,5-10", "all", "todos"
    """
    selection = selection.strip().lower()
    if selection in ("all", "todos", "*"):
        return list(range(1, max_val + 1))

    indices = set()
    for part in selection.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= max_val:
                        indices.add(i)
            except ValueError:
                continue
        else:
            try:
                val = int(part)
                if 1 <= val <= max_val:
                    indices.add(val)
            except ValueError:
                continue

    return sorted(indices)


def main():
    parser = argparse.ArgumentParser(
        description="Desinscreva-se de e-mails promocionais do Gmail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exemplos:
  python -m gmail_unsubscriber
  python -m gmail_unsubscriber --max-results 1000 --trash
  python -m gmail_unsubscriber --query "from:newsletter" --dry-run
  python -m gmail_unsubscriber --all --archive --report relatorio.json
        """,
    )
    parser.add_argument(
        "--credentials", default="credentials.json",
        help="Caminho para o arquivo de credenciais OAuth2 (padrão: credentials.json)",
    )
    parser.add_argument(
        "--max-results", type=int, default=500,
        help="Número máximo de e-mails a analisar (padrão: 500)",
    )
    parser.add_argument(
        "--query", default="category:promotions",
        help="Consulta de busca do Gmail (padrão: category:promotions)",
    )
    parser.add_argument(
        "--trash", action="store_true",
        help="Mover e-mails dos remetentes selecionados para a lixeira",
    )
    parser.add_argument(
        "--archive", action="store_true",
        help="Arquivar e-mails dos remetentes selecionados",
    )
    parser.add_argument(
        "--skip-mailto", action="store_true",
        help="Não tentar desinscrição via mailto (envio de e-mail)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simular sem executar ações reais",
    )
    parser.add_argument(
        "--report",
        help="Caminho para salvar relatório JSON",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Selecionar todos os remetentes automaticamente",
    )

    args = parser.parse_args()
    console = Console()

    console.print("\n[bold]Gmail Unsubscriber[/bold] - Desinscrição de e-mails promocionais\n")

    if args.dry_run:
        console.print("[yellow]Modo simulação ativado - nenhuma ação será executada[/yellow]\n")

    # 1. Autenticar
    console.print("[bold]1.[/bold] Autenticando com o Gmail...")
    service = get_gmail_service(args.credentials)
    console.print("[green]   Autenticado com sucesso![/green]\n")

    # 2. Escanear
    console.print(f"[bold]2.[/bold] Buscando e-mails ({args.query})...\n")
    senders = scan_emails(service, max_results=args.max_results, query=args.query)

    if not senders:
        console.print("[yellow]Nenhum e-mail promocional encontrado.[/yellow]")
        return

    console.print(f"   Encontrados [bold]{sum(s.count for s in senders.values())}[/bold] "
                  f"e-mails de [bold]{len(senders)}[/bold] remetentes.\n")

    # 3. Exibir tabela
    display_sender_table(senders, console)

    # 4. Selecionar remetentes
    if args.all:
        selected_indices = list(range(1, len(senders) + 1))
        console.print("[dim]Todos os remetentes selecionados (--all)[/dim]\n")
    else:
        selection = Prompt.ask(
            "Selecione os remetentes (ex: 1,3,5-10 ou 'todos')",
            default="todos",
        )
        selected_indices = parse_selection(selection, len(senders))

    if not selected_indices:
        console.print("[yellow]Nenhum remetente selecionado.[/yellow]")
        return

    sender_list = list(senders.values())
    selected_senders = [sender_list[i - 1] for i in selected_indices]

    console.print(f"\n[bold]3.[/bold] Processando {len(selected_senders)} remetentes...\n")

    # 5. Desinscrever
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Gmail-Unsubscriber)",
    })

    results = []
    for sender in selected_senders:
        console.print(f"   → {sender.display_name} ({sender.email})...", end=" ")

        result = unsubscribe(
            sender, session,
            gmail_service=service,
            skip_mailto=args.skip_mailto,
            dry_run=args.dry_run,
        )

        # Trash/archive
        if not args.dry_run:
            if args.trash:
                result.emails_trashed = trash_emails(service, sender.message_ids)
            elif args.archive:
                result.emails_archived = archive_emails(service, sender.message_ids)

        if result.success:
            if result.needs_confirmation:
                console.print("[yellow]⚠ pode precisar de confirmação manual[/yellow]")
            else:
                console.print("[green]✓[/green]")
        else:
            console.print("[red]✗[/red]")

        results.append(result)

    # 6. Relatório
    console.print(f"\n[bold]4.[/bold] Relatório final:\n")
    display_results(results, console)

    if args.report:
        save_report(results, args.report)
        console.print(f"\n[dim]Relatório salvo em: {args.report}[/dim]")


if __name__ == "__main__":
    main()
