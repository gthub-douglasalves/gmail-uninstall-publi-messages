"""Exibição e geração de relatórios."""

import json
from dataclasses import asdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .scanner import SenderInfo
from .unsubscriber import UnsubscribeResult


def display_sender_table(senders: dict[str, SenderInfo], console: Console) -> None:
    """Exibe tabela de remetentes encontrados."""
    table = Table(
        title="Remetentes de E-mails Promocionais",
        show_lines=True,
    )
    table.add_column("#", style="bold", width=4, justify="right")
    table.add_column("Remetente", style="cyan", max_width=40)
    table.add_column("E-mail", style="dim")
    table.add_column("Qtd", justify="right", style="bold")
    table.add_column("Método", justify="center")

    for idx, (key, info) in enumerate(senders.items(), 1):
        method = info.method_label
        if "HTTP" in method:
            method_style = f"[green]{method}[/green]"
        elif "E-mail" in method:
            method_style = f"[yellow]{method}[/yellow]"
        else:
            method_style = f"[red]{method}[/red]"

        table.add_row(
            str(idx),
            info.display_name,
            info.email,
            str(info.count),
            method_style,
        )

    console.print()
    console.print(table)
    console.print()


def display_results(results: list[UnsubscribeResult], console: Console) -> None:
    """Exibe resultados das desinscrições."""
    table = Table(title="Resultado das Desinscrições", show_lines=True)
    table.add_column("Remetente", style="cyan")
    table.add_column("Método", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Detalhe", style="dim", max_width=50)

    success_count = 0
    fail_count = 0

    for r in results:
        if r.success:
            status = "[green]✓ Sucesso[/green]"
            if r.needs_confirmation:
                status = "[yellow]⚠ Confirmação necessária[/yellow]"
            success_count += 1
        else:
            status = "[red]✗ Falhou[/red]"
            fail_count += 1

        extra = r.detail
        if r.emails_trashed:
            extra += f" | {r.emails_trashed} e-mails na lixeira"
        if r.emails_archived:
            extra += f" | {r.emails_archived} e-mails arquivados"

        table.add_row(
            r.sender_name,
            r.method_used,
            status,
            extra,
        )

    console.print()
    console.print(table)
    console.print()
    console.print(Panel(
        f"[green]Sucesso: {success_count}[/green]  |  [red]Falhou: {fail_count}[/red]",
        title="Resumo",
    ))


def save_report(results: list[UnsubscribeResult], path: str) -> None:
    """Salva relatório em JSON."""
    data = [asdict(r) for r in results]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
