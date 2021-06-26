"""Add "Use this" buttons into files that contain Git merge conflicts."""
from __future__ import annotations

import itertools
import tkinter
from typing import Any, cast

from porcupine import get_tab_manager, tabs, utils
from porcupine.plugins.linenumbers import LineNumbers

setup_after = ["linenumbers"]


def find_merge_conflicts(textwidget: tkinter.Text) -> list[list[int]]:
    result = []
    current_state = "outside"

    for lineno, line in enumerate(textwidget.get("1.0", "end - 1 char").split("\n")):
        # Line can have basically anything after '<<<<<<< ', even whitespace characters
        if line.startswith("<<<<<<< "):
            expected_current_state = "outside"
            new_state = "first"
        elif line == "=======":
            expected_current_state = "first"
            new_state = "second"
        elif line.startswith(">>>>>>> "):
            expected_current_state = "second"
            new_state = "outside"
        else:
            int("123")  # needed for coverage to notice that the continue runs
            continue

        if current_state != expected_current_state:
            # Something is funny. Maybe the file contains some things that make
            # it look like git merge conflict, but it really isn't that.
            return []

        current_state = new_state
        if new_state == "first":
            result.append([])
        result[-1].append(lineno)

    if current_state == "outside":
        return result
    return []


tag_counter = itertools.count()


class ConflictDisplayer:

    # line numbers not stored to self because they may change as text is edited
    def __init__(
        self, textwidget: tkinter.Text, start_lineno: int, middle_lineno: int, end_lineno: int
    ) -> None:
        self.textwidget = textwidget

        n = next(tag_counter)
        self.part1_tag = f"merge_conflict_{n}_part1"
        self.middle_tag = f"merge_conflict_{n}_middle"
        self.part2_tag = f"merge_conflict_{n}_part2"

        part1_color = utils.mix_colors(self.textwidget["bg"], "magenta", 0.8)
        manual_color = utils.mix_colors(self.textwidget["bg"], "tomato", 0.8)
        part2_color = utils.mix_colors(self.textwidget["bg"], "cyan", 0.8)

        # TODO: also specify fg color
        self.part1_button = self.make_button(
            start_lineno, part1_color, text="Use this", command=self.use_part1
        )
        self.manual_button = self.make_button(
            middle_lineno, manual_color, text="Edit manually", command=self.stop_displaying
        )
        self.part2_button = self.make_button(
            end_lineno, part2_color, text="Use this", command=self.use_part2
        )

        textwidget.tag_config(self.part1_tag, background=part1_color)
        textwidget.tag_config(self.middle_tag, background=manual_color)
        textwidget.tag_config(self.part2_tag, background=part2_color)
        textwidget.tag_lower(self.part1_tag, "sel")
        textwidget.tag_lower(self.middle_tag, "sel")
        textwidget.tag_lower(self.part2_tag, "sel")
        textwidget.tag_add(self.part1_tag, f"{start_lineno}.0", f"{middle_lineno}.0")
        textwidget.tag_add(self.middle_tag, f"{middle_lineno}.0", f"{middle_lineno + 1}.0")
        textwidget.tag_add(self.part2_tag, f"{middle_lineno + 1}.0", f"{end_lineno + 1}.0")

        self._stopped = False

    def make_button(self, lineno: int, bg_color: str, **options: Any) -> tkinter.Button:
        # tkinter.Button to use custom color, that's more difficult with ttk
        button = tkinter.Button(
            self.textwidget, bg=bg_color, fg=utils.invert_color(bg_color), cursor="arrow", **options
        )

        def on_destroy(event: tkinter.Event[tkinter.Misc]) -> None:
            # after_idle needed to prevent segfault
            # https://core.tcl-lang.org/tk/tktview/54fe7a5e718423d16f4a11f9d672cd7bae7da39f
            self.textwidget.after_idle(self.stop_displaying)

        button.bind("<Destroy>", on_destroy, add=True)

        self.textwidget.window_create(f"{lineno}.0 lineend", window=button)  # type: ignore[no-untyped-call]
        return button

    # may get called multiple times
    def stop_displaying(self) -> None:
        if self._stopped:
            return
        self._stopped = True

        self.part1_button.destroy()
        self.manual_button.destroy()
        self.part2_button.destroy()

        self.textwidget.tag_delete(self.part1_tag)
        self.textwidget.tag_delete(self.middle_tag)
        self.textwidget.tag_delete(self.part2_tag)

    def use_part1(self) -> None:
        self.textwidget.delete(f"{self.middle_tag}.first", f"{self.part2_tag}.last")
        self.textwidget.delete(
            f"{self.part1_button} linestart", f"{self.part1_button} linestart + 1 line"
        )
        self.stop_displaying()

    def use_part2(self) -> None:
        self.textwidget.delete(
            f"{self.part2_button} linestart", f"{self.part2_button} linestart + 1 line"
        )
        self.textwidget.delete(f"{self.part1_tag}.first", f"{self.middle_tag}.last")
        self.stop_displaying()


def update_displayers(tab: tabs.FileTab, displayers: list[ConflictDisplayer]) -> None:
    for displayer in displayers:
        displayer.stop_displaying()
    displayers.clear()

    for line_numbers in find_merge_conflicts(tab.textwidget):
        displayers.append(ConflictDisplayer(tab.textwidget, *line_numbers))


def on_new_filetab(tab: tabs.FileTab) -> None:
    displayers: list[ConflictDisplayer] = []
    update_displayers(tab, displayers)
    tab.bind("<<Reloaded>>", (lambda event: update_displayers(tab, displayers)), add=True)

    for child in tab.left_frame.winfo_children():
        if isinstance(child, LineNumbers):
            tab.textwidget.bind(
                "<Enter>",
                (
                    # This runs after clicking "Use this" button, mouse <Enter>s text widget
                    # Don't know why this needs a small timeout instead of after_idle
                    # https://github.com/python/mypy/issues/9658
                    lambda event: tab.after(50, cast(Any, child).do_update)
                ),
                add=True,
            )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
