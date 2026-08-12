from chemisto.parser import is_known_command, parse_input


def test_plain_message_is_not_a_command():
    result = parse_input("Explain Python decorators.")
    assert result.is_command is False
    assert result.command is None
    assert result.argument == "Explain Python decorators."


def test_file_command_with_argument():
    result = parse_input("/file src/auth.py")
    assert result.is_command is True
    assert result.command == "file"
    assert result.argument == "src/auth.py"


def test_run_command_preserves_full_argument():
    result = parse_input("/run pytest tests/")
    assert result.command == "run"
    assert result.argument == "pytest tests/"


def test_model_command_with_argument():
    result = parse_input("/model qwen-model")
    assert result.command == "model"
    assert result.argument == "qwen-model"


def test_model_command_without_argument():
    result = parse_input("/model")
    assert result.command == "model"
    assert result.argument == ""


def test_history_stats_new_clear_have_no_argument():
    for cmd in ("history", "stats", "new", "clear"):
        result = parse_input(f"/{cmd}")
        assert result.command == cmd
        assert result.argument == ""


def test_unknown_command_is_still_parsed_but_not_known():
    result = parse_input("/bogus")
    assert result.is_command is True
    assert result.command == "bogus"
    assert is_known_command(result.command) is False


def test_bare_slash_is_a_command_with_empty_name():
    result = parse_input("/")
    assert result.is_command is True
    assert result.command == ""


def test_whitespace_is_stripped():
    result = parse_input("   /ls   ")
    assert result.command == "ls"
    assert result.argument == ""


def test_known_commands_are_recognized():
    for cmd in ("help", "file", "ls", "tree", "run", "model", "history", "stats", "new", "clear", "exit", "quit"):
        assert is_known_command(cmd) is True
