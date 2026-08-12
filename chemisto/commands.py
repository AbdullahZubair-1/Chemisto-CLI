"""Command handlers and dispatch.

Each handler receives the shared AppState and the parsed argument, and
returns True to keep the REPL running or False to exit. Handlers only
touch local resources (filesystem, subprocess, gateway session calls) -
none of them send a message to the LLM except indirectly via /run's or
/file's *next* plain-text turn, which the REPL drives separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from chemisto.config import ChemistoSettings
from chemisto.context import ContextManager
from chemisto.directory import build_tree_lines, list_directory
from chemisto.exceptions import (
    ChemistoError,
    CommandExecutionError,
    FileContextError,
)
from chemisto.executor import run_command
from chemisto.gateway import GatewayClient
from chemisto.renderer import (
    console,
    print_command_result,
    print_directory_listing,
    print_directory_tree,
    print_error,
    print_help,
    print_history,
    print_model_list,
    print_stats,
    print_success,
)
from chemisto.session import LocalSession, save_local_session, start_new_session
from chemisto.tokens import estimate_tokens

HELP_ENTRIES = [
    ("/file <path>", "Add a file as context"),
    ("/ls", "List directory contents"),
    ("/tree", "Show directory tree"),
    ("/run <command>", "Execute a command and add output as context"),
    ("/model", "List available models"),
    ("/model <name>", "Switch model"),
    ("/history", "Show conversation history"),
    ("/stats", "Show session statistics"),
    ("/new", "Start a new session"),
    ("/clear", "Clear conversation/context"),
    ("/help", "Show available commands"),
    ("/exit", "Exit Chemisto"),
    ("/quit", "Exit Chemisto"),
]


@dataclass
class AppState:
    settings: ChemistoSettings
    client: GatewayClient
    session: LocalSession
    context: ContextManager = field(default_factory=ContextManager)
    turn_count: int = 0
    message_count: int = 0
    available_models: list = field(default_factory=list)


def handle_help(state: AppState, argument: str) -> bool:
    print_help(HELP_ENTRIES)
    return True


def handle_file(state: AppState, argument: str) -> bool:
    if not argument:
        print_error("Usage: /file <path>")
        return True
    try:
        state.context.add_file(argument, state.settings)
    except FileContextError as exc:
        print_error(str(exc))
        return True
    print_success(f"Added file context: {argument}")
    return True


def handle_ls(state: AppState, argument: str) -> bool:
    path = argument or "."
    try:
        entries = list_directory(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print_error(str(exc))
        return True
    print_directory_listing(entries, path)
    return True


def handle_tree(state: AppState, argument: str) -> bool:
    path = argument or "."
    try:
        lines = build_tree_lines(path, max_depth=state.settings.tree_max_depth)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print_error(str(exc))
        return True
    print_directory_tree(lines, path)
    return True


def handle_run(state: AppState, argument: str) -> bool:
    if not argument:
        print_error("Usage: /run <command>")
        return True
    try:
        result = run_command(
            argument,
            timeout_seconds=state.settings.command_timeout_seconds,
            max_output_chars=state.settings.max_command_output_chars,
        )
    except CommandExecutionError as exc:
        print_error(str(exc))
        return True

    context = state.context.add_command_result(
        command=result.command,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
    )
    print_command_result(context)
    if result.timed_out:
        print_error(f"Command timed out after {state.settings.command_timeout_seconds}s")
    else:
        print_success(f"Command completed with exit code {result.exit_code}")
    return True


def handle_model(state: AppState, argument: str) -> bool:
    try:
        models, _default = state.client.list_models()
    except ChemistoError as exc:
        print_error(str(exc))
        return True
    state.available_models = models

    if not argument:
        print_model_list(models, state.session.model)
        return True

    match = next((m for m in models if m.id == argument or m.label == argument), None)
    if match is None:
        print_error(f"Unknown model: {argument}. Run /model to see available models.")
        return True

    state.session.model = match.id
    save_local_session(state.settings, state.session)
    print_success(f"Model switched to {match.id}")
    return True


def handle_history(state: AppState, argument: str) -> bool:
    try:
        _model, entries = state.client.get_history(state.session.chat_id)
    except ChemistoError as exc:
        print_error(str(exc))
        return True
    print_history(state.session.chat_id, entries)
    return True


def handle_stats(state: AppState, argument: str) -> bool:
    try:
        _model, entries = state.client.get_history(state.session.chat_id)
    except ChemistoError as exc:
        print_error(str(exc))
        return True
    estimated = sum(estimate_tokens(e.content) for e in entries)
    print_stats(
        model=state.session.model,
        message_count=len(entries),
        turn_count=state.turn_count,
        estimated_tokens=estimated,
    )
    return True


def handle_new(state: AppState, argument: str) -> bool:
    try:
        new_session = start_new_session(state.settings, state.client, model=state.session.model)
    except ChemistoError as exc:
        print_error(str(exc))
        return True
    state.session = new_session
    state.context.clear()
    state.turn_count = 0
    state.message_count = 0
    print_success("New session created")
    return True


def handle_clear(state: AppState, argument: str) -> bool:
    try:
        state.client.clear_session(state.session.chat_id)
    except ChemistoError as exc:
        print_error(str(exc))
        return True
    state.context.clear()
    print_success("Conversation and context cleared")
    return True


def handle_exit(state: AppState, argument: str) -> bool:
    console.print("Goodbye!")
    return False


COMMAND_HANDLERS = {
    "help": handle_help,
    "file": handle_file,
    "ls": handle_ls,
    "tree": handle_tree,
    "run": handle_run,
    "model": handle_model,
    "history": handle_history,
    "stats": handle_stats,
    "new": handle_new,
    "clear": handle_clear,
    "exit": handle_exit,
    "quit": handle_exit,
}


def dispatch(state: AppState, command: str, argument: str) -> bool:
    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        print_error(f"Unknown command: /{command}. Type /help to see available commands.")
        return True
    return handler(state, argument)
