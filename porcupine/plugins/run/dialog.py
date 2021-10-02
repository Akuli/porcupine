from __future__ import annotations
import sys
import tkinter
from typing import Callable
from porcupine import utils
from tkinter import ttk

from pathlib import Path


class FormattingEntryAndLabels:
    def __init__(
        self,
        entry_area: ttk.Frame,
        text: str,
        default_format: str,
        substitutions: dict[str, str],
        value_validator: Callable[[str], bool],
        validated_callback: Callable[[], None],
    ):
        grid_y = entry_area.grid_size()[1]
        ttk.Label(entry_area, text=text).grid(row=grid_y, column=0, sticky="w")

        self.format_var = tkinter.StringVar(value=default_format)
        self.entry = ttk.Entry(entry_area, font="TkFixedFont", textvariable=self.format_var)
        self.entry.grid(row=grid_y, column=1, sticky="we")
        self.entry.selection_range(0, "end")

        grid_y += 1
        self.label = ttk.Label(entry_area)
        self.label.grid(row=grid_y, column=1, sticky="we")

        # spacer
        grid_y += 1
        ttk.Label(entry_area).grid(row=grid_y)

        self._substitutions = substitutions
        self._value_validator = value_validator
        self._validated_callback = validated_callback
        self.format_var.trace_add("write", self._validate)
        self._validate()

    def _validate(self, *junk_from_var_trace: object) -> None:
        try:
            value = self.format_var.get().format(**self._substitutions)
        except (ValueError, KeyError, IndexError):
            self.is_valid = False
            self.label.config(text="Substitution error", font="")
        else:
            self.is_valid = self._value_validator(value)
            self.label.config(text=value, font="TkFixedFont")

        # _validated_callback might not work if called from __init__
        if junk_from_var_trace:
            self._validated_callback()

    def get_formatted_value(self) -> str:
        assert self.is_valid
        return self.label["text"]


def _validate_folder(string_path: str) -> str | None:
    if Path(string_path).is_dir():
        return None
    if Path(string_path).exists():
        return "not a folder"
    return "doesn't exist"


class CommandAsker:
    def __init__(self, path: Path):
        self.window = tkinter.Toplevel()

        if sys.platform == "win32":
            terminal_name = "command prompt"
        else:
            terminal_name = "terminal"

        content_frame = ttk.Frame(self.window, borderwidth=10)
        content_frame.pack(fill="both", expand=True)

        project_path = utils.find_project_root(path)
        unquoted_substitutions = {
            "file_stem": path.stem,
            "file_name": path.name,
            "file_path": str(path),
            "folder_name": path.parent.name,
            "folder_path": str(path.parent),
            "project_name": project_path.name,
            "project_path": str(project_path),
        }
        quoted_substitutions = {name: utils.quote(value) for name, value in unquoted_substitutions.items()}

        entry_area = ttk.Frame(content_frame)
        entry_area.pack(fill="x")
        entry_area.grid_columnconfigure(1, weight=1)

        self.command = FormattingEntryAndLabels(
            entry_area,
            text="Run this command:",
            default_format="python3 {file_name}",
            substitutions=quoted_substitutions,
            value_validator=(lambda command: bool(command.strip())),
            validated_callback=self.update_run_button,
        )
        self.cwd = FormattingEntryAndLabels(
            entry_area,
            text="In this directory:",
            default_format="{folder_path}",
            substitutions=unquoted_substitutions,
            value_validator=(lambda d: Path(d).is_dir()),
            validated_callback=self.update_run_button,
        )

        sub_text = "\n".join("{%s} = %s" % pair for pair in unquoted_substitutions.items())
        ttk.Label(content_frame, text=f"Substitutions:\n{sub_text}\n").pack(fill="x")

        # TODO: remember value with settings
        self.terminal_var = tkinter.BooleanVar()

        porcupine_text = (
            "Display the output inside the Porcupine window (does not support keyboard input)"
        )
        external_text = f"Use an external {terminal_name} window"

        ttk.Radiobutton(
            content_frame,
            variable=self.terminal_var,
            value=False,
            text=porcupine_text,
            underline=porcupine_text.index("Porcupine"),
        ).pack(fill="x")
        ttk.Radiobutton(
            content_frame,
            variable=self.terminal_var,
            value=True,
            text=external_text,
            underline=external_text.index("external"),
        ).pack(fill="x")
        self.window.bind("<Alt-p>", (lambda e: self.terminal_var.set(False)), add=True)
        self.window.bind("<Alt-e>", (lambda e: self.terminal_var.set(True)), add=True)

        ttk.Label(content_frame).pack()  # spacer

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill="x")
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.window.destroy)
        cancel_button.pack(side="left", fill="x", expand=True)
        self.run_button = ttk.Button(button_frame, text="Run", command=self.on_run_clicked)
        self.run_button.pack(side="left", fill="x", expand=True)
        self.run_clicked = False

        entries = [e for e in entry_area.winfo_children() if isinstance(e, ttk.Entry)]
        assert entries
        for entry in entries:
            entry.bind("<Return>", (lambda e: self.run_button.invoke()), add=True)
            entry.bind("<Escape>", (lambda e: self.window.destroy()), add=True)

        self.command.entry.selection_range(0, "end")
        self.command.entry.focus_set()

    def update_run_button(self) -> None:
        if self.command.is_valid and self.cwd.is_valid:
            self.run_button.config(state="normal")
        else:
            self.run_button.config(state="disabled")

    def on_run_clicked(self):
        self.run_clicked = True
        self.window.destroy()


asker = CommandAsker(Path(__file__))
asker.window.title("Run command")
# asker.window.transient(get_main_window())
tkinter._default_root.withdraw()
asker.window.wait_window()
if asker.run_clicked:
    print(asker.command.get_formatted_value())
    print(asker.cwd.get_formatted_value())
else:
    print("cancel")
