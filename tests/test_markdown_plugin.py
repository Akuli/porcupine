from __future__ import annotations

import itertools
from contextlib import nullcontext as does_not_raise
from typing import NamedTuple

import pytest

from porcupine.plugins import markdown


class ListItemCase(NamedTuple):
    id: str
    line: str
    expected: bool
    marks: list[pytest.MarkDecorator] = []
    raises: Exception | None = None


IS_LIST_ITEM_CASES = [
    ListItemCase(id="# with no separator", line="# item 1", expected=False),
    ListItemCase(id="# bad separator |", line="#| item 1", expected=False),
    ListItemCase(id="# bad separator /", line="#/ item 1", expected=False),
    ListItemCase(id="# bad separator \\", line="#\\ item 1", expected=False),
    ListItemCase(id="ol bad separator |", line="8| item 1", expected=False),
    ListItemCase(id="ol bad separator /", line="8/ item 1", expected=False),
    ListItemCase(id="ol bad separator \\", line="8\\ item 1", expected=False),
    ListItemCase(id="not a list 1", line="item 1", expected=False),
    ListItemCase(id="not a list 2", line="   item 1", expected=False),
    ListItemCase(id="not a list 3", line="          item 1", expected=False),
    ListItemCase(id="not a list 4", line="& item 1", expected=False),
    ListItemCase(id="not a list 5", line="^ item 1", expected=False),
    ListItemCase(id="duplicate token 1", line="-- item 1", expected=False),
    ListItemCase(id="duplicate token 2", line="--- item 1", expected=False),
    ListItemCase(id="duplicate token 3", line="- - - item 1", expected=True),
    ListItemCase(id="duplicate token 4", line="  - item -- 1 -", expected=True),
    ListItemCase(id="duplicate token 5", line="  -#) item -- 1 -", expected=False),
    ListItemCase(id="duplicate token 6", line="  *-#)1. item -- 1 -", expected=False),
]

# test `#` and 0 to 99 numbered lists
# tests ol with `.` and `)`
IS_LIST_ITEM_CASES.extend(
    [
        ListItemCase(id=f"numbered {i}", line=f"{i}{sep} item 1", expected=True)
        for i, sep in itertools.product(itertools.chain(range(100), "#"), (".", ")"))
    ]
)

# test raw li prefixes with and without space
IS_LIST_ITEM_CASES.extend(
    [
        ListItemCase(
            id=f"raw prexix {prefix} no space",
            line=f"{prefix}{' ' if space else ''}",
            expected=space,
        )
        for prefix, space in itertools.product(
            ["1.", "1)", "#.", "#)", "-", "*", "+"], [True, False]
        )
    ]
)

# test numbered list with whitespace following and preceding
IS_LIST_ITEM_CASES.extend(
    [
        ListItemCase(
            id=f"numbered {preceding=} {following=} space",
            line=f"{' ' * preceding}{i}{sep}{' ' * following} item 1",
            expected=True,
        )
        for i, sep, preceding, following in itertools.product(
            ("7", "#"), (".", ")"), range(11), range(11)
        )
    ]
)

# test with whitespace following and preceding
IS_LIST_ITEM_CASES.extend(
    [
        ListItemCase(
            id=f"bullet {preceding=} {following=} space",
            line=f"{' ' * preceding}{bullet} {' ' * following} item 1",
            expected=True,
        )
        for bullet, preceding, following in itertools.product(("-", "*", "+"), range(11), range(11))
    ]
)


@pytest.mark.parametrize(
    "line, expected, raises",
    [
        pytest.param(
            case.line,
            case.expected,
            pytest.raises(case.raises) if case.raises else does_not_raise(),
            marks=case.marks,
            id=case.id,
        )
        for case in IS_LIST_ITEM_CASES
    ],
)
def test_is_list(line: str, expected: bool, raises):
    with raises:
        result = markdown._list_item(line)
        if expected:
            assert result
        if not expected:
            assert not result


@pytest.mark.parametrize(
    "li",
    [
        "-",
        "1.",
        "1. item 1",
        "1) item 1",
        "#) item 1",
        "- item 1",
        "* item 1",
        "+ item 1",
        "+ +++++ weird",
        "1) ))))) still weird",
        "- [ ] unchecked task",
        "- [X] checked task",
    ],
)
def test_filetype_switching(li: str, filetab, tmp_path):
    assert filetab.settings.get("filetype_name", object) == "Python"

    filetab.textwidget.insert("1.0", li)
    filetab.update()
    filetab.textwidget.event_generate("<Tab>")

    assert (
        filetab.textwidget.get("1.0", "insert") == li
    ), "should not effect list items unless using markdown filetype"
    filetab.update()
    filetab.textwidget.event_generate("<Escape>")  # close the autocomplete

    # switch to Markdown filetype format
    filetab.save_as(tmp_path / "asdf.md")
    assert filetab.settings.get("filetype_name", object) == "Markdown"

    filetab.update()
    filetab.textwidget.event_generate("<Tab>")
    # no change to text, should open autocomplete menu
    assert filetab.textwidget.get("1.0", "insert") == li
    filetab.update()
    filetab.textwidget.event_generate("<Escape>")  # close the autocomplete

    # add a space
    filetab.textwidget.insert("insert", " ")
    filetab.update()
    filetab.textwidget.event_generate("<Tab>")
    assert filetab.textwidget.get("1.0", "insert") == f"    {li} ", "should be indented"
    filetab.update()
    filetab.textwidget.event_generate("<Shift-Tab>")
    filetab.update()
    assert filetab.textwidget.get("1.0", "insert") == f"{li} ", "should be back to normal"


@pytest.mark.parametrize(
    "line",
    [
        "# H1 Heading",
        "## H2 Heading",
        "   ### H3 Heading with whitespace preceding",
        "| Markdown    | Table     |",
        "| :---------------- | :------: | ----: |",
        "```python",
        '<h3 id="custom-id">My Great Heading</h3>',
        ": This is the definition",
        "~~The world is flat.~~",
        "==very important words==",
        "X^2^",
        "http://www.example.com",
        "`http://www.example.com`",
    ],
)
def test_non_list(line: str, filetab, tmp_path):
    # switch to Markdown filetype format
    filetab.save_as(tmp_path / "asdf.md")
    assert filetab.settings.get("filetype_name", object) == "Markdown"

    filetab.textwidget.insert("1.0", line)
    filetab.update()
    filetab.textwidget.event_generate("<Tab>")
    filetab.update()
    filetab.textwidget.event_generate("<Escape>")  # close the autocomplete
    assert (
        filetab.textwidget.get("1.0", "end - 1 char") == f"{line}\n"
    ), "should not change, just open autocomplete"


@pytest.mark.parametrize(
    "li",
    [
        "- ",  # note the space
        "1. ",  # note the space
        "1. item 1",
        "1) item 1",
        "#) item 1",
        "- item 1",
        "* item 1",
        "+ item 1",
        "+ +++++ weird",
        "1) ))))) still weird",
        "- [ ] unchecked task",
        "- [X] checked task",
    ],
)
def test_list_continuation(li: str, filetab, tmp_path):
    filetab.textwidget.insert("1.0", li)
    filetab.update()

    # switch to Markdown filetype format
    filetab.save_as(tmp_path / "asdf.md")
    assert filetab.settings.get("filetype_name", object) == "Markdown"

    # new line
    filetab.update()
    filetab.textwidget.event_generate("<Return>")
    current_line = filetab.textwidget.get("insert linestart", "insert")
    assert markdown._list_item(current_line)
