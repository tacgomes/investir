import csv
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

import pytest

from investir.config import config
from investir.exceptions import (
    FieldUnknownError,
)
from investir.parser.parser import Field, ParserBase, ParsingResult, Row


class FakeParser(ParserBase):
    SCHEMA: Final = (
        Field("A", required=True),
        Field("B"),
    )

    def __init__(self, csv_file: Path) -> None:
        super().__init__(csv_file, self.SCHEMA)

    def parse(self) -> ParsingResult:
        self.validate_fields()
        return ParsingResult([], [], [], [])


@pytest.fixture
def make_parser_with_custom_fields(tmp_path) -> Callable:
    def _wrapper(field_names: Sequence[str]):
        csv_file = tmp_path / "transactions.csv"
        with csv_file.open("w", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=field_names)
            writer.writeheader()
        return FakeParser(csv_file)

    return _wrapper


def test_row_get_with_alias():
    f = Field("A", "B")
    field_mapping = {"A": f, "B": f}
    row = Row({"A": "value"}, field_mapping)
    assert row["A"] == row["B"] == "value"


def test_row_get_with_missing_field():
    row = Row({"A": "value"}, {})
    with pytest.raises(KeyError):
        row["B"]


def test_parser_with_missing_required_field(make_parser_with_custom_fields):
    parser = make_parser_with_custom_fields(["B"])
    assert parser.can_parse() is False


def test_parser_with_unknown_field(make_parser_with_custom_fields):
    parser = make_parser_with_custom_fields(["A", "B", "C"])
    assert parser.can_parse() is True
    with pytest.raises(FieldUnknownError):
        parser.parse()

    config.strict = False
    parser.parse()
