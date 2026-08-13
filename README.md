# Chemisto

A Claude Code-style AI coding assistant that runs directly in your terminal, backed by a
FastAPI gateway that talks to [OpenRouter](https://openrouter.ai).

```
$ chemisto
╭────────────────── Chemisto ───────────────────╮
│ AI Terminal Coding Assistant                  │
│ Model: poolside/laguna-xs-2.1:free            │
│ Session: 271052893c13                         │
╰────────────────────────────────────────────────╯
> Explain Python decorators.
```

## Features

- Natural-language questions and multi-turn conversations in a REPL.
- Streamed, token-by-token replies rendered live as they arrive, instead of waiting for the
  full response.
- Read local files and add them as explicit, labeled context (`/file`).
- Inspect directory structure (`/ls`, `/tree`).
- Run explicitly requested shell commands and add their output as context (`/run`).
- Switch between three configured OpenRouter free-tier models mid-conversation, without
  losing the conversation (`/model`).
- View conversation history (`/history`) and session statistics (`/stats`).
- Start a fresh session (`/new`) or clear the current one (`/clear`).
- A built-in pacing throttle on the gateway so a burst of quick messages can't blow through
  free-tier rate limits (see [Rate limiting](#rate-limiting)).
- Polished [Rich](https://github.com/Textualize/rich)-powered terminal UI: panels, tables,
  markdown rendering, syntax highlighting, live-updating streamed replies.
- Clean, non-crashing handling of network and execution errors.

## Technology stack

| Component            | Choice                                   |
|-----------------------|-------------------------------------------|
| Language              | Python 3.11+                             |
| CLI HTTP client       | `httpx`                                  |
| Gateway framework     | `FastAPI` + `uvicorn`                    |
| Schemas               | `pydantic` v2                            |
| LLM provider          | `OpenRouter`                             |
| Terminal UI           | `rich`                                   |
| Config                | `python-dotenv` + environment variables  |
| Local session storage | plain JSON file                          |
| Token estimation      | `tiktoken`                               |

No web framework, database, or ORM is used on the CLI side - it is a stateless HTTP client.
The gateway keeps chat history in memory for the MVP (see [Session management](#session-management)).

## Architecture

```
 User
   │
   ▼
 Chemisto CLI  (chemisto/)         <- terminal client, no OpenRouter credentials
   │  HTTP (httpx)
   ▼
 FastAPI LLM Gateway  (gateway/)   <- owns the OpenRouter API key
   │  HTTP (httpx)
   ▼
 OpenRouter
   │
   ▼
 Selected LLM (Poolside / OpenAI / Gemma)
   │
   ▼
 FastAPI LLM Gateway
   │
   ▼
 Chemisto CLI
   │
   ▼
 User
```

The CLI and gateway are two separate processes on purpose:

- **Credential isolation.** Only the gateway process ever holds `OPENROUTER_API_KEY`. The
  CLI cannot leak a key it never has, even if a user's terminal history or session file is
  shared.
- **A stable contract.** `gateway/models.py` defines the exact request/response shapes; both
  sides of the HTTP boundary are written against that one file, so they cannot silently
  drift apart.
- **Swappable provider layer.** If OpenRouter is replaced or a second provider is added
  later, only `gateway/openrouter.py` changes - the CLI is unaffected.

### `/file` flow

```
/file src/auth.py -> read file -> validate -> detect language -> format
                   -> stored as FileContext -> included in the next LLM request
```

### `/run` flow

```
/run pytest tests/ -> subprocess (timeout, output cap) -> stdout/stderr/exit code
                    -> stored as CommandContext -> included in the next LLM request
```

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/AbdullahZubair-1/Chemisto-CLI.git
cd Chemisto-CLI
python -m venv .venv
# Windows (git bash):
source .venv/Scripts/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -e ".[gateway,dev]"
```

This installs:
- the `chemisto` CLI package and its runtime dependencies (`httpx`, `rich`, `python-dotenv`,
  `tiktoken`, `pydantic`),
- the `[gateway]` extra (`fastapi`, `uvicorn`) needed to run the gateway service,
- the `[dev]` extra (`pytest`, `pytest-asyncio`, `respx`) needed to run the test suite.

## Configuration

Copy the example environment file and fill in your OpenRouter key:

```bash
cp .env.example .env
```

```dotenv
# Gateway only - never read by the CLI
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8000
GATEWAY_SESSIONS_DIR=~/.ats-ai/chats

# Three centrally configured models (see Model configuration below)
CHEMISTO_MODEL_1=poolside/laguna-xs-2.1:free
CHEMISTO_MODEL_2=openai/gpt-oss-20b:free
CHEMISTO_MODEL_3=google/gemma-4-31b-it:free

# CLI only - no credentials
CHEMISTO_GATEWAY_URL=http://127.0.0.1:8000
```

`.env` is listed in `.gitignore` and must never be committed. `.env.example` contains only
placeholder values.

## Gateway setup

Start the gateway (from the repo root, with the venv active):

```bash
uvicorn gateway.main:app --host 127.0.0.1 --port 8000
```

Confirm it's up:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

## CLI setup

In a second terminal (same venv):

```bash
chemisto
```

`chemisto` is registered as a console script in `pyproject.toml` (`chemisto = "chemisto.cli:main"`),
so once the package is installed with `pip install -e .` the command is on your `PATH`.

## Commands

| Command            | Description                                    |
|---------------------|-------------------------------------------------|
| `/file <path>`      | Add a file as context                          |
| `/ls`               | List directory contents                        |
| `/tree`             | Show directory tree                            |
| `/run <command>`    | Execute a command and add output as context    |
| `/model`            | List available models                          |
| `/model <name>`     | Switch model                                   |
| `/history`          | Show conversation history                      |
| `/stats`            | Show session statistics                        |
| `/new`              | Start a new session                            |
| `/clear`            | Clear conversation/context                     |
| `/help`             | Show available commands                        |
| `/exit`             | Exit Chemisto                                  |
| `/quit`             | Exit Chemisto                                  |

Anything not starting with `/` is sent to the LLM as a normal message. Unknown `/commands`
print a clean error instead of crashing.

The REPL exits cleanly on `/exit`, `/quit`, or Ctrl+C - no Python traceback is ever shown for
a normal exit.

## Model configuration

Exactly three OpenRouter **free-tier** models are configured, one central place
(`gateway/config.py`, driven by environment variables) - no model ID is hard-coded anywhere
else in the codebase:

| Env var                  | Provider | Default model ID                    |
|---------------------------|----------|---------------------------------------|
| `CHEMISTO_MODEL_1`        | Poolside | `poolside/laguna-xs-2.1:free`         |
| `CHEMISTO_MODEL_2`        | OpenAI   | `openai/gpt-oss-20b:free`             |
| `CHEMISTO_MODEL_3`        | Google   | `google/gemma-4-31b-it:free`          |

> **Verify before relying on these.** OpenRouter's free-tier catalogue changes over time.
> Check https://openrouter.ai/models (filter by "Free") for the currently available IDs and
> update the corresponding `CHEMISTO_MODEL_*` variable in `.env` if one of the defaults above
> has been retired - no code changes are needed, only configuration.

`/model` lists these three models and shows which is active; `/model <id-or-label>` switches
the active model for the *current* session:

```
> /model
Available models:
  poolside/laguna-xs-2.1:free   Laguna XS 2.1   [active]
  openai/gpt-oss-20b:free       GPT-OSS 20B
  google/gemma-4-31b-it:free    Gemma 4 31B

> /model openai/gpt-oss-20b:free
OK Model switched to openai/gpt-oss-20b:free
```

Switching models only changes which model the *next* turn is sent to. The `chat_id`, and
therefore the full conversation history stored by the gateway, is untouched - switching
models never starts a new conversation.

## Streaming

Every reply is streamed token-by-token rather than returned all at once. The flow:

```
CLI sends POST /sessions/{chat_id}/messages/stream
  -> gateway opens a streaming request to OpenRouter (stream: true)
  -> gateway re-emits each token as {"type": "content", "text": "..."} (newline-delimited JSON)
  -> CLI appends each chunk to a live-updating Rich panel as it arrives
  -> gateway emits {"type": "done", "usage": {...}} once OpenRouter's stream ends
  -> CLI re-renders the finished reply as formatted Markdown
```

If OpenRouter returns an error, the gateway signals it in-band as `{"type": "error", ...}`
rather than an HTTP error status, since the HTTP response has already started streaming with
a 200 by that point - the CLI checks the *last* event's type, not just the status code. The
exact contract is documented in `gateway/main.py`'s module docstring.

## Rate limiting

Free-tier OpenRouter models enforce their own rate limits, and those limits are tied to your
account's credit balance - a $0 balance gets the strictest limits and can be exhausted in a
handful of quick messages, surfacing as repeated `429 Too Many Requests` errors.

To avoid that, the gateway enforces a minimum spacing between every call it makes to
OpenRouter, regardless of which session or model triggered it (`OPENROUTER_MIN_INTERVAL_SECONDS`
in `.env`, default `3.0` seconds - see `gateway/ratelimit.py`). If you send a second message
less than 3 seconds after the first, the gateway simply holds the request for the remaining
time before forwarding it - you'll notice a slightly longer pause before the first token
appears, but you won't see a 429. Lower this value if you've added credit to your OpenRouter
account and want faster back-to-back turns; raise it if you're still seeing 429s even with the
default.

## Session management

On startup, Chemisto reads `~/.ats-ai/session.json`:

```json
{
  "chat_id": "271052893c13",
  "model": "poolside/laguna-xs-2.1:free"
}
```

- If the file exists and the gateway still recognizes `chat_id`, the CLI resumes that session -
  and since the gateway now persists every chat to disk (see below), this succeeds across a
  gateway restart too, not just within one run.
- If the file is missing, malformed, or the gateway genuinely doesn't recognize the `chat_id`
  (e.g. its persisted file was deleted), Chemisto transparently creates a new session and
  rewrites the file.
- The file never contains an API key or any other secret.

`/new` explicitly creates a new gateway session, clears local file/command context, and
resets local counters - but keeps the currently selected model unless you also pass one, e.g.
`/model <id>` beforehand.

`/clear` calls the gateway's message-clearing endpoint (`DELETE /sessions/{chat_id}/messages`)
so old turns cannot leak into future requests, and also clears local file/command context.

## Chat history persistence

Every chat is saved by the gateway as its own JSON file under `GATEWAY_SESSIONS_DIR` (default
`~/.ats-ai/chats`), so conversations survive a gateway restart - the gateway reloads every file
in that folder back into memory on startup.

Each file is named after a short topic, generated by asking the model to summarize your first
message in a few words, plus the chat_id for uniqueness:

```
~/.ats-ai/chats/
├── explain-python-decorators-271052893c13.json
├── refactor-auth-flow-99eb39c8b66d.json
└── untitled-020bd148f16d.json          <- title generation hasn't finished yet, or failed
```

The title request is a separate, one-off call to the model (not shown to you, and it doesn't
delay your reply - it runs in the background right after your first message is sent) and is
only ever made once per chat. If it fails or hasn't completed yet, the file is simply named
`untitled-{chat_id}.json` until it succeeds - nothing else about the chat is affected.

Each file contains the full conversation:

```json
{
  "chat_id": "271052893c13",
  "model": "poolside/laguna-xs-2.1:free",
  "created_at": "2026-08-12T09:57:41.923581+00:00",
  "title": "explain python decorators",
  "messages": [
    {"role": "user", "content": "Explain Python decorators."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## File context

`/file <path>` never calls the LLM by itself. It:

1. Reads the file from disk.
2. Validates it (see [File safety](#file-safety)).
3. Detects its language from the file extension.
4. Formats it with explicit delimiters.
5. Stores it in memory as pending context for the *next* message.

```
> /file examples/auth.py
OK Added file context: examples/auth.py
> Find security problems in this file.
```

What actually gets sent to the LLM:

```
[FILE CONTEXT]
Path: examples/auth.py
Language: python

```python
<file contents>
```
[END FILE CONTEXT]

USER REQUEST:
Find security problems in this file.
```

Multiple `/file` calls accumulate - `/file src/auth.py` then `/file src/database.py` then a
question sends both files, each in its own clearly labeled `[FILE CONTEXT]` block. Context is
cleared after it is sent once (and is always cleared by `/new` and `/clear`) so it is never
silently reused across unrelated questions.

### File safety

`/file` handles, with a clean error message rather than a crash:

- File not found.
- Permission denied.
- A directory passed instead of a file.
- Binary files (detected via a null-byte check and refused).
- Files that are not valid UTF-8 text.
- Files larger than `CHEMISTO_MAX_FILE_SIZE_BYTES` (default 200,000 bytes).

Chemisto never reads or sends a whole repository automatically - only files the user
explicitly names with `/file` become context.

## Command context

`/run <command>` executes a shell command **only when the user explicitly types it**:

```
> /run pytest examples/demo_tests/
OK Command completed with exit code 1
> Explain why this test failed.
```

What gets captured and sent:

```
[COMMAND CONTEXT]
Command: pytest examples/demo_tests/
Exit code: 1

STDOUT:
...

STDERR:
...
[END COMMAND CONTEXT]

USER REQUEST:
Explain why this test failed.
```

A configurable timeout (`CHEMISTO_COMMAND_TIMEOUT_SECONDS`, default 30s) and output cap
(`CHEMISTO_MAX_COMMAND_OUTPUT_CHARS`, default 8,000 characters) apply to every `/run`.

## Security

- **The LLM can never execute a command.** There is no code path from an LLM response back
  into `subprocess`. The *only* way a shell command runs is a user typing `/run <command>` at
  the prompt.
- `/run` always runs under a timeout and with output capped, so a runaway or noisy command
  cannot hang the REPL or flood the terminal.
- `/file` always enforces a maximum file size and refuses binary files, so a single command
  cannot blow up memory or send unreadable bytes to the LLM.
- Chemisto never sends more than what the user explicitly added via `/file` or `/run` - it
  does not scan or upload the working directory on its own.
- `OPENROUTER_API_KEY` lives only in the gateway process's environment. It is never returned
  in any gateway response, never logged, and never stored in `~/.ats-ai/session.json`.
- `.env` is git-ignored; `.env.example` contains only placeholder values.

## Testing

```bash
python -m pytest -q
```

56 tests across seven files, all using mocks/tmp directories - none require a live gateway or
network access:

- `tests/test_parser.py` - command parsing (plain messages, every command form, unknown
  commands, whitespace handling).
- `tests/test_session.py` - saving/loading `~/.ats-ai/session.json`, missing/malformed file
  handling, resuming vs. creating a session.
- `tests/test_context.py` - valid/missing/directory/binary/oversized files, multi-file
  prompts, language detection, command context delimiters, clearing.
- `tests/test_commands.py` - `/run` success/failure/timeout/output-truncation, `/ls` and
  `/tree` directory handling.
- `tests/test_gateway.py` - the CLI's HTTP client against a mocked gateway (via `respx`):
  success responses, streaming events (content/done/error), connection failures, timeouts,
  HTTP error statuses, and malformed JSON.
- `tests/test_openrouter_stream.py` - the gateway's SSE parsing of OpenRouter's streaming
  responses (via `respx`): content deltas, trailing usage, and HTTP error statuses.
- `tests/test_ratelimit.py` - the minimum-interval throttle: first call passes through
  immediately, a second call within the interval waits out the remainder, concurrent calls
  serialize with spacing, and a `0` interval never waits.

## Troubleshooting

| Symptom                                         | Likely cause / fix                                                             |
|--------------------------------------------------|----------------------------------------------------------------------------------|
| `ERROR Unable to connect to the Chemisto gateway.`   | The gateway isn't running. Start it with `uvicorn gateway.main:app ...`.        |
| `ERROR ... status 401 ...` after sending a message   | `OPENROUTER_API_KEY` is missing/invalid in the gateway's `.env`.                |
| `ERROR ... status 400 ... Unknown model id`          | The model ID in `.env` no longer exists on OpenRouter - check `/models` output. |
| Garbled box-drawing characters in the terminal    | Use a UTF-8 capable terminal (Windows Terminal); Chemisto forces UTF-8 output on stdout/stderr, but very old `cmd.exe` fonts may still render some glyphs oddly. |
| `/file` says "too large"                        | Raise `CHEMISTO_MAX_FILE_SIZE_BYTES` in `.env` if you really need a bigger file. |

## Example session

```
$ chemisto
╭────────────────── Chemisto ───────────────────╮
│ AI Terminal Coding Assistant                  │
│ Model: poolside/laguna-xs-2.1:free            │
│ Session: 271052893c13                         │
╰────────────────────────────────────────────────╯
> Explain FastAPI dependency injection.
[AI response]
> /file examples/auth.py
OK Added file context: examples/auth.py
> Explain the authentication flow and flag any security issues.
[AI response]
> /run pytest examples/demo_tests/
OK Command completed with exit code 1
> Explain the test failure and suggest a fix.
[AI response]
> /model openai/gpt-oss-20b:free
OK Model switched to openai/gpt-oss-20b:free
> What did we learn from the previous test?
[AI response using preserved conversation context]
> /history
[conversation history]
> /stats
[statistics]
> /new
OK New session created
> /quit
Goodbye!
```

## Future improvements

- A `/model` alias that accepts short names (`laguna`, `gpt-oss`, `gemma`) in addition to full
  OpenRouter IDs.
- Retry-with-backoff handling for the rare OpenRouter 429 that still gets through the
  gateway's throttle (see [Rate limiting](#rate-limiting)).
- Optional authentication between the CLI and gateway if the gateway is ever exposed beyond
  localhost.
