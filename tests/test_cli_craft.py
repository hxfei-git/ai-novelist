from ai_novelist.cli import build_parser


def test_cli_has_author_craft_commands():
    parser = build_parser()

    args = parser.parse_args(["index-corpus", "--corpus-dir", "tests/fixtures/corpus"])

    assert args.command == "index-corpus"


def test_chat_help_has_craft_flags(capsys):
    parser = build_parser()
    try:
        parser.parse_args(["chat", "--help"])
    except SystemExit:
        pass
    output = capsys.readouterr().out

    assert "--author-corpus-dir" in output
    assert "--craft-mode" in output
    assert "--local-corpus-dir" in output
