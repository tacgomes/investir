def pytest_addoption(parser):
    parser.addoption(
        "--regen-outputs",
        action="store_true",
        default=False,
        help="Regenerate expected outputs for the CLI tests",
    )
