from __future__ import annotations

from porcupine.plugins import toolbar


def _gen_button_group(priority: int, name: str | None = None) -> toolbar.ButtonGroup:
    return toolbar.ButtonGroup(
        name=f"priority = {priority}" if not name else name, priority=priority, buttons=[]
    )


def test_manual_sorted_button_group_list_with_append_and_extend():
    # reverse order
    sorted_button_group_list = toolbar.SortedButtonGroupList(
        [_gen_button_group(i) for i in [100, 0, 50, 25, 2, 1, 99]]
    )

    sorted_button_group_list.append(_gen_button_group(33))
    sorted_button_group_list.append(_gen_button_group(5))

    sorted_button_group_list.extend(
        [_gen_button_group(9), _gen_button_group(8), _gen_button_group(7)]
    )

    for i, button_group in zip(
        [0, 1, 2, 5, 7, 8, 9, 25, 33, 50, 99, 100], sorted_button_group_list
    ):
        assert i == button_group.priority


def test_big_reversed_sorted_button_group_list():
    qty = 100
    # reverse order
    sorted_button_group_list = toolbar.SortedButtonGroupList(
        [_gen_button_group(i) for i in reversed(range(qty))]
    )

    for i, button_group in zip(range(qty), sorted_button_group_list):
        assert i == button_group.priority
