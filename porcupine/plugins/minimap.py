"""Display the contents of the file being edited with small font on the side."""
from __future__ import annotations

import sys
import tkinter

from porcupine import get_tab_manager, settings, tabs, textutils, utils

LINE_THICKNESS = 1


# We want self to have the same text content and colors as the main
# text. We do this efficiently with a peer widget.
#
# The only way to bold text is to specify a tag with a bold font, and that's
# what the main text widget does. The peer text widget then gets the same tag
# with the same font, including the same font size. There's is a way to specify
# a font so that you only tell it to bold and nothing more, but then it just
# chooses a default size that is not widget-specific. This means that we need
# a way to override the font of a tag (it doesn't matter if we don't get bolded
# text in the minimap). The only way to override a font is to use another tag
# that has a higher priority.
#
# There is only one tag that is not common to both widgets, sel. It represents
# the text being selected, and we abuse it for setting the smaller font size.
# This means that all of the text has to be selected all the time.
class MiniMap(tkinter.Text):
    def __init__(self, master: tkinter.Misc, tab: tabs.FileTab) -> None:
        super().__init__(master)
        textutils.create_peer_widget(tab.textwidget, self)
        self.config(
            exportselection=False,
            takefocus=False,
            yscrollcommand=self._update_lines,
            wrap="none",
            cursor="arrow",
        )

        self._tab = tab
        self._tab.textwidget.config(highlightthickness=LINE_THICKNESS)

        self.tag_config("sel", foreground="", background="")

        # To indicate the area visible in tab.textwidget, we can't use a tag,
        # because tag configuration is the same for both widgets (except for
        # one tag that we are already abusing). Instead, we put a bunch of
        # frames on top of the text widget to make up a border.
        self._lines = {
            "top": tkinter.Frame(self),
            "left": tkinter.Frame(self),
            "bottom": tkinter.Frame(self),
            "right": tkinter.Frame(self),
        }

        utils.add_scroll_command(tab.textwidget, "yscrollcommand", self._scroll_callback)
        self.bind("<Button-1>", self._on_click_and_drag, add=True)
        self.bind("<Button1-Motion>", self._on_click_and_drag, add=True)

        # We want to prevent the user from selecting anything in self, because
        # of abusing the 'sel' tag. Binding <Button-1> and <Button1-Motion>
        # isn't quite enough.
        self.bind("<Button1-Enter>", self._on_click_and_drag, add=True)
        self.bind("<Button1-Leave>", self._on_click_and_drag, add=True)

        textutils.bind_font_changed(tab, self.set_font)
        self.set_font()

        # Make sure that 'sel' tag stays added even when text widget becomes empty
        tab.textwidget.bind("<<ContentChanged>>", self._update_sel_tag, add=True)

        # don't know why after_idle doesn't work. Adding a timeout causes
        # issues with tests.
        if "pytest" not in sys.modules:
            self.after(50, self._scroll_callback)

    def set_colors(self, foreground: str, background: str) -> None:
        self.config(
            # Seems like inactiveselectbackground must be non-empty
            fg=foreground,
            bg=background,
            inactiveselectbackground=background,
        )

        self._tab.textwidget.config(highlightcolor=foreground)
        for frame in self._lines.values():
            frame.config(bg=foreground)

    def set_font(self) -> None:
        self.tag_config(
            "sel",
            font=(settings.get("font_family", str), round(settings.get("font_size", int) / 3), ()),
        )
        textutils.config_tab_displaying(self, self._tab.settings.get("indent_size", int), tag="sel")
        self._update_lines()

    def _scroll_callback(self) -> None:
        first_visible_index = self._tab.textwidget.index("@0,0 linestart")
        last_visible_index = self._tab.textwidget.index("@0,10000000 linestart")
        self.see(first_visible_index)
        self.see(last_visible_index)
        self._update_lines()

    def _update_sel_tag(self, junk: object = None) -> None:
        self.tag_add("sel", "1.0", "end")

    def _update_lines(self, *junk: object) -> None:
        if not self.tag_cget("sel", "font"):
            # view was created just a moment ago, set_font() hasn't ran yet
            return

        start_bbox = self.bbox(self._tab.textwidget.index("@0,0 linestart"))
        end_bbox = self.bbox(self._tab.textwidget.index("@0,10000000 linestart"))

        hide = set()
        if start_bbox is None and end_bbox is None:
            # no part of text file being edited is visible
            hide = set(self._lines.keys())

        minimap_width, minimap_height = textutils.textwidget_size(self)
        minimap_x_padding, minimap_y_padding = textutils.get_padding(self)

        if self._tab.textwidget.yview() == (0.0, 1.0):  # type: ignore[no-untyped-call]
            # whole file content on screen at once, show screen size instead of file content size
            # this does not take in account wrap plugin
            how_tall_are_lines_on_editor: int = self._tab.tk.call(
                "font", "metrics", self._tab.textwidget["font"], "-linespace"
            )
            how_tall_are_lines_on_minimap: int = self._tab.tk.call(
                "font", "metrics", self.tag_cget("sel", "font"), "-linespace"
            )
            editor_height = textutils.textwidget_size(self._tab.textwidget)[1]
            how_many_lines_fit_on_editor = editor_height / how_tall_are_lines_on_editor

            rect_top = 0
            rect_bottom = int(how_many_lines_fit_on_editor * how_tall_are_lines_on_minimap)

        else:
            if start_bbox is None:
                rect_top = 0
                hide.add("top")
            else:
                x, y, w, h = start_bbox
                rect_top = y - minimap_y_padding

            if end_bbox is None:
                rect_bottom = minimap_height
                hide.add("bottom")
            else:
                x, y, w, h = end_bbox
                rect_bottom = (y - minimap_y_padding) + h

        rect_height = rect_bottom - rect_top

        coords = {
            "top": (0, rect_top, minimap_width, LINE_THICKNESS),
            "left": (0, rect_top, LINE_THICKNESS, rect_height),
            "bottom": (0, rect_bottom - LINE_THICKNESS, minimap_width, LINE_THICKNESS),
            "right": (minimap_width - LINE_THICKNESS, rect_top, LINE_THICKNESS, rect_height),
        }

        for name, widget in self._lines.items():
            if name in hide:
                widget.place_forget()
            else:
                x, y, w, h = coords[name]
                self._lines[name].place(x=x, y=y, width=w, height=h)

        # TODO: figure out when exactly this is needed, remove unnecessary calls?
        self._update_sel_tag()

    def _on_click_and_drag(self, event: tkinter.Event[tkinter.Misc]) -> str:
        self._tab.textwidget.see(self.index(f"@0,{event.y}"))
        return "break"

    def set_width_from_settings(self, junk=None):
        self._tab.panedwindow.paneconfigure(self, width=settings.get("minimap_width", int))

    def save_width_to_settings(self, junk=None):
        settings.set_("minimap_width", self.winfo_width())


def on_new_filetab(tab: tabs.FileTab) -> None:
    minimap = MiniMap(tab.panedwindow, tab)

    minimap.bind('<Map>', minimap.set_width_from_settings, add=True)
    tab.panedwindow.bind('<ButtonRelease-1>', (lambda e: minimap.after_idle(minimap.save_width_to_settings)), add=True)

    textutils.use_pygments_theme(minimap, minimap.set_colors)
    tab.panedwindow.add(minimap, stretch='never')


def setup() -> None:
    settings.add_option("minimap_width", 100)
    get_tab_manager().add_filetab_callback(on_new_filetab)
