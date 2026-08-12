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
- Read local files and add them as explicit, labeled context (`/file`).
- Inspect directory structure (`/ls`, `/tree`).
- Run explicitly requested shell commands and add their output as context (`/run`).
- Switch between three configured OpenRouter free-tier models mid-conversation, without
  losing the conversation (`/model`).
- View conversation history (`/history`) and session statistics (`/stats`).
- Start a fresh session (`/new`) or clear the current one (`/clear`).
- Polished [Rich](https://github.com/Textualize/rich)-powered terminal UI: panels, tables,
  markdown rendering, syntax highlighting, spinners.
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
  poolside/laguna-xs-2.1:free   Poolside Laguna XS 2.1 (free)   [active]
  openai/gpt-oss-20b:free       OpenAI GPT-OSS 20B (free)
  google/gemma-4-31b-it:free    Google Gemma 4 31B (free)

> /model openai/gpt-oss-20b:free
✓ Model switched to openai/gpt-oss-20b:free
```

Switching models only changes which model the *next* turn is sent to. The `chat_id`, and
therefore the full conversation history stored by the gateway, is untouched - switching
models never starts a new conversation.

## Session management

On startup, Chemisto reads `~/.ats-ai/session.json`:

```json
{
  "chat_id": "271052893c13",
  "model": "poolside/laguna-xs-2.1:free"
}
```

- If the file exists and the gateway still recognizes `chat_id`, the CLI resumes that session.
- If the file is missing, malformed, or the gateway no longer recognizes the `chat_id` (for
  example after a gateway restart, since the MVP gateway keeps chat history in memory only),
  Chemisto transparently creates a new session and rewrites the file.
- The file never contains an API key or any other secret.

`/new` explicitly creates a new gateway session, clears local file/command context, and
resets local counters - but keeps the currently selected model unless you also pass one, e.g.
`/model <id>` beforehand.

`/clear` calls the gateway's message-clearing endpoint (`DELETE /sessions/{chat_id}/messages`)
so old turns cannot leak into future requests, and also clears local file/command context.

## File context

`/file <path>` never calls the LLM by itself. It:

1. Reads the file from disk.
2. Validates it (see [File safety](#file-safety)).
3. Detects its language from the file extension.
4. Formats it with explicit delimiters.
5. Stores it in memory as pending context for the *next* message.

```
> /file examples/auth.py
✓ Added file context: examples/auth.py
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
✓ Command completed with exit code 1
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

45 tests across five files, all using mocks/tmp directories - none require a live gateway or
network access:

- `tests/test_parser.py` - command parsing (plain messages, every command form, unknown
  commands, whitespace handling).
- `tests/test_session.py` - saving/loading `~/.ats-ai/session.json`, missing/malformed file
  handling, resuming vs. creating a session.
- `tests/test_context.py` - valid/missing/directory/binary/oversized files, multi-file
  prompts, language detection, command context delimiters, clearing.
- `tests/test_commands.py` - `/run` success/failure/timeout/output-truncation, `/ls` and
  `/tree` directory handling.
- `tests/test_gateway.py` - the HTTP client against a mocked gateway (via `respx`): success
  responses, connection failures, timeouts, HTTP error statuses, and malformed JSON.

## Troubleshooting

| Symptom                                         | Likely cause / fix                                                             |
|--------------------------------------------------|----------------------------------------------------------------------------------|
| `✗ Unable to connect to the Chemisto gateway.`   | The gateway isn't running. Start it with `uvicorn gateway.main:app ...`.        |
| `✗ ... status 401 ...` after sending a message   | `OPENROUTER_API_KEY` is missing/invalid in the gateway's `.env`.                |
| `✗ ... status 400 ... Unknown model id`          | The model ID in `.env` no longer exists on OpenRouter - check `/models` output. |
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
✓ Added file context: examples/auth.py
> Explain the authentication flow and flag any security issues.
[AI response]
> /run pytest examples/demo_tests/
✓ Command completed with exit code 1
> Explain the test failure and suggest a fix.
[AI response]
> /model openai/gpt-oss-20b:free
✓ Model switched to openai/gpt-oss-20b:free
> What did we learn from the previous test?
[AI response using preserved conversation context]
> /history
[conversation history]
> /stats
[statistics]
> /new
✓ New session created
> /quit
Goodbye!
```

## Future improvements

- Persist gateway session history to disk/a database so conversations survive a gateway
  restart (currently in-memory only, by design, for MVP simplicity).
- Streaming responses (token-by-token) instead of waiting for the full reply.
- A `/model` alias that accepts short names (`laguna`, `gpt-oss`, `gemma`) in addition to full
  OpenRouter IDs.
- Rate-limit and retry-with-backoff handling for OpenRouter 429s in the gateway.
- Optional authentication between the CLI and gateway if the gateway is ever exposed beyond
  localhost.
