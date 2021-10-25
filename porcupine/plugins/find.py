"""Find and replace text."""
from __future__ import annotations

import re
import sys
import tkinter
import weakref
from functools import partial
from tkinter import ttk
from typing import Any, Callable, Iterator, TypeVar, cast

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from porcupine import get_tab_manager, images, menubar, tabs, textutils

CallableT = TypeVar("CallableT", bound=Callable[..., Any])


# In Porcupine, I try to avoid leaking memory if you open and close
# a tab. This code creates a memory leak:
#
#    self.var = tkinter.StringVar()
#    self.var.trace_add("write", self.some_method)
#
# Now the variable refers to a method object, which refers to self,
# which refers to the variable. So we have a reference cycle.
#
# Actually the variable doesn't hold a reference to the method
# directly. It registers a command in the Tcl interpreter, making
# the Tcl interpreter refer to the method object until the variable
# is garbage-collected. This is usually fine, but because the garbage
# collection only sees the Tcl interpreter holding a reference to the
# variable, it doesn't see the reference cycle.
#
# GC not working is especially bad if the class defines a widget
# (i.e. inherits from a Tkinter widget), because then it holds a
# reference to the parent widget (self.parent), which holds a
# reference to its parent, and so on. This means that the instance
# of the class will prevent many more widgets from getting garbage
# collected.
#
# To fix this, we break the cycle by basically making the method
# reference self through a weakref.ref().
def method_weakref(method: CallableT) -> CallableT:
    method_ref = weakref.WeakMethod(method)  # type: ignore
    del method
    return lambda *args, **kwargs: method_ref()(*args, **kwargs)  # type: ignore


class Finder(ttk.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent: tkinter.Misc, textwidget: tkinter.Text, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self._textwidget = textwidget

        # grid layout:
        #           column 0         column 1           column 2       column 3
        #       ,------------------------------------------------------------.
        # row 0 | Find:         |   text entry   | [x] Full words only |  X  |
        #       |---------------|----------------|---------------------------|
        # row 1 | Replace with: |   text entry   | [x] Ignore case           |
        #       |------------------------------------------------------------|
        # row 2 | button frame, this thing contains a bunch of buttons       |
        #       |------------------------------------------------------------|
        # row 3 | status label with useful-ish text                          |
        #       |------------------------------------------------------------|
        # row  4| separator                                                  |
        #       `------------------------------------------------------------'
        #
        # the separator helps distinguish this from e.g. status bar below this
        self.grid_columnconfigure(1, weight=1)

        self.full_words_var = tkinter.BooleanVar()
        self.ignore_case_var = tkinter.BooleanVar()
        find_var = tkinter.StringVar()

        self.find_entry = self._add_entry(0, "Find:")
        self.find_entry.config(textvariable=find_var)
        find_var.trace_add("write", method_weakref(self.highlight_all_matches))

        # because cpython gc
        cast(Any, self.find_entry).lol = find_var

        self.replace_entry = self._add_entry(1, "Replace with:")

        self.find_entry.bind("<Shift-Return>", self._go_to_previous_match, add=True)
        self.find_entry.bind("<Return>", self._go_to_next_match, add=True)

        buttonframe = ttk.Frame(self)
        buttonframe.grid(row=2, column=0, columnspan=4, sticky="we")

        self.previous_button = ttk.Button(
            buttonframe, text="Previous match", command=self._go_to_previous_match
        )
        self.next_button = ttk.Button(
            buttonframe, text="Next match", command=self._go_to_next_match
        )
        self.replace_this_button = ttk.Button(
            buttonframe,
            text="Replace this match",
            underline=len("Replace "),
            command=self._replace_this,
        )
        self.replace_all_button = ttk.Button(
            buttonframe, text="Replace all", underline=len("Replace "), command=self._replace_all
        )

        self.previous_button.pack(side="left", padx=(0, 5))
        self.next_button.pack(side="left", padx=(0, 5))
        self.replace_this_button.pack(side="left", padx=(0, 5))
        self.replace_all_button.pack(side="left", padx=(0, 5))
        self._update_buttons()

        self.full_words_var.trace_add("write", method_weakref(self.highlight_all_matches))
        self.ignore_case_var.trace_add("write", method_weakref(self.highlight_all_matches))

        ttk.Checkbutton(
            self, text="Full words only", underline=0, variable=self.full_words_var
        ).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(self, text="Ignore case", underline=0, variable=self.ignore_case_var).grid(
            row=1, column=2, sticky="w"
        )

        self.statuslabel = ttk.Label(self)
        self.statuslabel.grid(row=3, column=0, columnspan=4, sticky="we")

        ttk.Separator(self, orient="horizontal").grid(row=4, column=0, columnspan=4, sticky="we")

        closebutton = ttk.Label(self, cursor="hand2")
        closebutton.grid(row=0, column=3, sticky="ne")
        closebutton.bind("<Button-1>", self.hide, add=True)

        closebutton.config(image=images.get("closebutton"))

        # _update_buttons() uses current selection, update when changes
        textwidget.bind("<<Selection>>", self._update_buttons, add=True)

        textwidget.bind("<<SettingChanged:pygments_style>>", self._config_tags, add=True)
        self._config_tags()

        # catch highlight issue after undo
        textwidget.bind("<<Undo>>", self._handle_undo, add=True)

    def _config_tags(self, junk: object = None) -> None:
        # TODO: use more pygments theme instead of hard-coded colors?
        self._textwidget.tag_config("find_highlight", foreground="black", background="yellow")
        self._textwidget.tag_config(
            "find_highlight_selected", foreground="black", background="orange"
        )
        self._textwidget.tag_raise("find_highlight", "sel")
        self._textwidget.tag_raise("find_highlight_selected", "find_highlight")

    def _add_entry(self, row: int, text: str) -> ttk.Entry:
        ttk.Label(self, text=text).grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(self, width=35, font="TkFixedFont")
        entry.bind("<Escape>", self.hide, add=True)
        entry.bind("<Alt-t>", self._replace_this, add=True)
        entry.bind("<Alt-a>", self._replace_all, add=True)
        entry.bind("<Alt-f>", partial(self._toggle_var, self.full_words_var), add=True)
        entry.bind("<Alt-i>", partial(self._toggle_var, self.ignore_case_var), add=True)
        entry.grid(row=row, column=1, sticky="we", padx=(5, 10))
        return entry

    def _toggle_var(self, var: tkinter.BooleanVar, junk: object) -> str:
        var.set(not var.get())
        return "break"

    def show(self, junk: object = None) -> None:
        try:
            selected_text: str | None = self._textwidget.get("sel.first", "sel.last")
        except tkinter.TclError:
            selected_text = None

        self.pack(fill="x")

        if selected_text is not None and "\n" not in selected_text:
            # Selected text is usable, search for that
            self.find_entry.delete(0, "end")
            self.find_entry.insert(0, selected_text)

        self.find_entry.select_range(0, "end")
        self.find_entry.focus_set()

        self.highlight_all_matches()

        # weird hack to prevent rendering issue on mac
        # https://stackoverflow.com/questions/55366795/does-anyone-know-why-my-tkinter-buttons-arent-rendering
        self.update_idletasks()

    def get_match_tags(self, index: str | None = None) -> list[str]:
        return [tag for tag in self._textwidget.tag_names(index) if tag.startswith("find_match_")]

    # Deleting and removing a tag are different concepts.
    # Deleting means that the whole tag is gone.
    # Removing means that there are no characters using the tag.
    def _delete_match_tags(self) -> None:
        self._textwidget.tag_remove("find_highlight", "1.0", "end")
        for tag in self.get_match_tags():
            self._textwidget.tag_delete(tag)

    def hide(self, junk: object = None) -> None:
        self._delete_match_tags()
        self._textwidget.tag_remove("find_highlight_selected", "1.0", "end")
        self.pack_forget()
        self._textwidget.focus_set()

    # tag_ranges() sucks, i want my text indexes as strings and not stupid _tkinter.Tcl_Obj
    def _tag_ranges(self, tag: str) -> list[str]:
        return [str(index) for index in self._textwidget.tag_ranges(tag)]

    # must be called when going to another match or replacing becomes possible
    # or impossible, i.e. when find_highlight areas or the selection changes
    def _update_buttons(self, junk: object = None) -> None:
        matches_something_state = "normal" if self.get_match_tags() else "disabled"
        self.previous_button.config(state=matches_something_state)
        self.next_button.config(state=matches_something_state)
        self.replace_all_button.config(state=matches_something_state)

        # To consider a match currently selected, it must have 3 tags, all
        # with the same start and end:
        #   - "sel" (text is selected)
        #   - "find_highlight_selected" (text is orange)
        #   - "find_match_123" (it is actually a match)

        locations = self._tag_ranges("sel")
        locations2 = self._tag_ranges("find_highlight_selected")
        if (
            len(locations) == 2
            and locations == locations2
            and any(self._tag_ranges(t) == locations for t in self.get_match_tags("sel.first"))
        ):
            self.replace_this_button.config(state="normal")
        else:
            self.replace_this_button.config(state="disabled")

    def _get_matches_to_highlight(self, looking4: str) -> Iterator[str]:
        # Tkinter's .search() is slow when there are lots of tags from highlight plugin.
        # See "PERFORMANCE ISSUES" in text widget manual page
        text = self._textwidget.get("1.0", "end - 1 char")

        if self.full_words_var.get():
            regex = r"\b" + re.escape(looking4) + r"\b|\n"
        else:
            regex = re.escape(looking4) + "|\n"
        flags = re.IGNORECASE if self.ignore_case_var.get() else 0

        lineno = 1
        for match in re.finditer(regex, text, flags):
            if match.group(0) == "\n":
                lineno += 1
            else:
                if lineno == 1:
                    column = match.start()
                else:
                    column = match.start() - text.rindex("\n", 0, match.start()) - 1
                yield f"{lineno}.{column}"

    def highlight_all_matches(self, *junk: object) -> None:
        self._delete_match_tags()

        looking4 = self.find_entry.get()
        if not looking4:  # don't search for empty string
            self._update_buttons()
            self.statuslabel.config(text="Type something to find.")
            return
        if self.full_words_var.get() and not re.fullmatch(r"\w|\w.*\w", looking4):
            self._update_buttons()
            self.statuslabel.config(
                text=f'"{looking4}" is not a valid word. Maybe uncheck "Full words only"?'
            )
            return

        count = 0
        for start_index in self._get_matches_to_highlight(looking4):
            # Both tags needed:
            #   - "find_highlight" to display with yellow color in gui
            #   - "find_match_123" to distinguish matches, even when repeated
            self._textwidget.tag_add(
                "find_highlight", start_index, f"{start_index} + {len(looking4)} chars"
            )
            self._textwidget.tag_add(
                f"find_match_{count}", start_index, f"{start_index} + {len(looking4)} chars"
            )
            count += 1

        self._update_buttons()
        if count == 0:
            self.statuslabel.config(text="Found no matches :(")
        elif count == 1:
            self.statuslabel.config(text="Found 1 match.")
        else:
            self.statuslabel.config(text=f"Found {count} matches.")

    def _select_match(self, match_tags: list[str], index: int) -> None:
        tag = match_tags[index]
        self._textwidget.tag_remove("sel", "1.0", "end")
        self._textwidget.tag_remove("find_highlight_selected", "1.0", "end")
        self._textwidget.tag_add("sel", f"{tag}.first", f"{tag}.last")
        self._textwidget.tag_add("find_highlight_selected", f"{tag}.first", f"{tag}.last")
        self._textwidget.mark_set("insert", f"{tag}.first")
        self._textwidget.see("insert")

        self.statuslabel.config(text=f"Match {index + 1}/{len(match_tags)}")
        self._update_buttons()

    def _go_to_next_match(self, junk: object = None) -> None:
        # If we have no matches, then "Next match" button is disabled and
        # this was invoked through key binding
        tags = self.get_match_tags()
        if tags:
            # If no matches highlighted yet, can highlight match exactly at cursor
            # Applies only to next match, previous always search before cursor
            some_match_already_highlighted = str(self.replace_this_button["state"]) == "normal"
            operator: Literal[">=", ">"] = ">" if some_match_already_highlighted else ">="

            # find first pair that starts after the cursor, or cycle back to first
            possible_indexes = (
                i
                for i, tag in enumerate(tags)
                if self._textwidget.compare(f"{tag}.first", operator, "insert")
            )
            index = next(possible_indexes, 0)
            self._select_match(tags, index)

    def _go_to_previous_match(self, junk: object = None) -> None:
        tags = self.get_match_tags()
        if tags:
            possible_indexes = (
                i
                for i, tag in reversed(list(enumerate(tags)))
                if self._textwidget.compare(f"{tag}.first", "<", "insert")
            )
            index = next(possible_indexes, len(tags) - 1)
            self._select_match(tags, index)

    def _replace_this(self, junk: object = None) -> str:
        if str(self.replace_this_button["state"]) == "disabled":
            self.statuslabel.config(text='Click "Previous match" or "Next match" first.')
            return "break"

        [tag] = self.get_match_tags("sel.first")
        self._textwidget.tag_remove("find_highlight", f"{tag}.first", f"{tag}.last")
        self._textwidget.mark_set("insert", f"{tag}.first")
        self._update_buttons()

        with textutils.change_batch(self._textwidget):
            self._textwidget.replace(f"{tag}.first", f"{tag}.last", self.replace_entry.get())
        self._textwidget.tag_delete(tag)

        self._go_to_next_match()

        left = len(self.get_match_tags())
        if left == 0:
            self.statuslabel.config(text="Replaced the last match.")
        elif left == 1:
            self.statuslabel.config(text="Replaced a match. There is 1 more match.")
        else:
            self.statuslabel.config(text=f"Replaced a match. There are {left} more matches.")
        return "break"

    def _replace_all(self, junk: object = None) -> str:
        match_tags = self.get_match_tags()

        with textutils.change_batch(self._textwidget):
            for tag in match_tags:
                self._textwidget.replace(f"{tag}.first", f"{tag}.last", self.replace_entry.get())

        self._delete_match_tags()
        self._update_buttons()

        if len(match_tags) == 1:
            self.statuslabel.config(text="Replaced 1 match.")
        else:
            self.statuslabel.config(text=f"Replaced {len(match_tags)} matches.")
        return "break"

    def _handle_undo(self, event: object) -> None:
        if self.winfo_viewable():
            self.after_idle(self.highlight_all_matches)


def on_new_filetab(tab: tabs.FileTab) -> None:
    finder = Finder(tab.bottom_frame, tab.textwidget)
    tab.bind("<<FiletabCommand:Edit/Find and Replace>>", finder.show, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    menubar.add_filetab_command("Edit/Find and Replace")
