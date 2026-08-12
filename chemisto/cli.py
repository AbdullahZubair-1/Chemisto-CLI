"""Chemisto's Read-Eval-Print Loop and process entry point.

    Read input -> command or message? -> execute command / send message
    -> display result -> repeat

Ctrl+C and /exit /quit both terminate cleanly with no traceback.
"""
from __future__ import annotations

from chemisto.commands import AppState, dispatch
from chemisto.config import settings
from chemisto.context import ContextManager
from chemisto.exceptions import ChemistoError
from chemisto.gateway import GatewayClient
from chemisto.parser import parse_input
from chemisto.renderer import (
    console,
    print_assistant_reply,
    print_banner,
    print_error,
    thinking_status,
)
from chemisto.session import resume_or_create_session


def send_message(state: AppState, user_text: str) -> None:
    prompt = state.context.build_prompt(user_text)
    try:
        with thinking_status():
            reply = state.client.send_message(state.session.chat_id, prompt, model=state.session.model)
    except ChemistoError as exc:
        print_error(str(exc))
        return

    state.context.clear()
    state.turn_count += 1
    state.message_count += 2
    print_assistant_reply(reply.reply)


def run_repl(state: AppState) -> None:
    while True:
        try:
            raw = console.input("[bold cyan]>[/bold cyan] ")
        except EOFError:
            console.print("Goodbye!")
            return

        parsed = parse_input(raw)
        if not parsed.raw.strip():
            continue

        if parsed.is_command:
            if parsed.command == "":
                print_error("Unknown command: /. Type /help to see available commands.")
                continue
            should_continue = dispatch(state, parsed.command, parsed.argument)
            if not should_continue:
                return
            continue

        send_message(state, parsed.argument)


def main() -> None:
    client = GatewayClient(settings)

    try:
        session, _resumed = resume_or_create_session(settings, client)
    except ChemistoError as exc:
        print_error(str(exc))
        return

    state = AppState(
        settings=settings,
        client=client,
        session=session,
        context=ContextManager(),
    )

    print_banner(model=state.session.model, chat_id=state.session.chat_id)

    try:
        run_repl(state)
    except KeyboardInterrupt:
        console.print("\nGoodbye!")


if __name__ == "__main__":
    main()
