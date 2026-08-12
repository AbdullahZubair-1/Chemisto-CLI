"""Rich-powered terminal rendering.

All user-facing output goes through this module so formatting stays
consistent, and so the REPL logic in cli.py stays free of presentation
details.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager

from rich.console import Console

# Windows terminals often default to a legacy codepage (e.g. cp1252) that
# cannot encode the box-drawing characters Rich uses for panels and tables.
# Reconfigure the standard streams to UTF-8 up front so output never crashes
# with a UnicodeEncodeError regardless of the host codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from chemisto.context import CommandContext
from chemisto.directory import DirEntry
from chemisto.gateway import HistoryEntry, ModelInfo

console = Console()


def print_banner(model: str, chat_id: str) -> None:
    body = Text()
    body.append("AI Terminal Coding Assistant\n", style="dim")
    body.append("Model: ", style="bold")
    body.append(f"{model}\n")
    body.append("Session: ", style="bold")
    body.append(chat_id)
    console.print(Panel(body, title="Chemisto", border_style="cyan", expand=False))


def print_assistant_reply(text: str) -> None:
    console.print(Panel(Markdown(text), title="Chemisto", border_style="green", expand=True))


def print_success(message: str) -> None:
    console.print(f"[bold green]OK[/bold green] {message}")


def print_error(message: str) -> None:
    console.print(f"[bold red]ERROR[/bold red] {message}")


def print_info(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")


@contextmanager
def thinking_status():
    with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots") as status:
        yield status


def print_help(entries: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    for usage, description in entries:
        table.add_row(usage, description)
    console.print(Panel(table, title="Chemisto Commands", border_style="cyan"))


def print_directory_listing(entries: list[DirEntry], path: str) -> None:
    table = Table(title=f"Contents of {path}", show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Size", justify="right")
    for entry in entries:
        kind = "dir" if entry.is_dir else "file"
        size = "-" if entry.size is None else f"{entry.size:,}"
        table.add_row(entry.name, kind, size)
    console.print(table)


def print_directory_tree(lines: list[str], path: str) -> None:
    console.print(Panel(Text("\n".join(lines)), title=f"Tree: {path}", border_style="cyan"))


def print_command_result(context: CommandContext) -> None:
    status_style = "green" if context.exit_code == 0 and not context.timed_out else "red"
    status = "TIMED OUT" if context.timed_out else str(context.exit_code)
    console.print(
        Panel(
            f"[bold]Command:[/bold] {context.command}\n"
            f"[bold]Exit code:[/bold] [{status_style}]{status}[/{status_style}]",
            title="Command Result",
            border_style=status_style,
        )
    )


def print_history(chat_id: str, entries: list[HistoryEntry]) -> None:
    console.print(f"[bold cyan]Session:[/bold cyan] {chat_id}\n")
    if not entries:
        console.print("[dim](no messages yet)[/dim]")
        return
    for entry in entries:
        role_style = "bold magenta" if entry.role == "user" else "bold green"
        role_label = entry.role.upper()
        console.print(f"[{role_style}][{entry.index}] {role_label}[/{role_style}]")
        console.print(Markdown(entry.content))
        console.print()


def print_stats(model: str, message_count: int, turn_count: int, estimated_tokens: int) -> None:
    table = Table(title="Session Statistics", show_header=False, box=None)
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Model", model)
    table.add_row("Messages", str(message_count))
    table.add_row("Turns", str(turn_count))
    table.add_row("Est. tokens", f"{estimated_tokens:,} (estimate)")
    console.print(Panel(table, border_style="cyan"))


def print_model_list(models: list[ModelInfo], current_model: str) -> None:
    table = Table(title="Available Models", show_header=True, header_style="bold cyan")
    table.add_column("Id")
    table.add_column("Label")
    table.add_column("Active", justify="center")
    for model in models:
        active = "yes" if model.id == current_model else ""
        table.add_row(model.id, model.label, active)
    console.print(table)
