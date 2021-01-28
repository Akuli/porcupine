"""Syntax highlighting."""

import itertools
import logging
import time
import tkinter
import tkinter.font as tkfont
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, cast

from pygments import styles, token  # type: ignore[import]
from pygments.lexer import Lexer, LexerMeta, RegexLexer  # type: ignore[import]

from porcupine import get_tab_manager, settings, tabs, utils


def _list_all_token_types(tokentype: Any) -> Iterator[Any]:
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub


all_token_tags = set(map(str, _list_all_token_types(token.Token)))
log = logging.getLogger(__name__)
ROOT_STATE_MARK_PREFIX = 'highlight_root_'
root_mark_names = (ROOT_STATE_MARK_PREFIX + str(n) for n in itertools.count())


class Highlighter:

    def __init__(
            self,
            textwidget: tkinter.Text,
            lexer_getter: Callable[[], Lexer]) -> None:
        self.textwidget = textwidget
        self._get_lexer = lexer_getter

        # the tags use fonts from here
        self._fonts: Dict[Tuple[bool, bool], tkfont.Font] = {}
        for bold in (True, False):
            for italic in (True, False):
                # the fonts will be updated later, see _config_changed()
                self._fonts[(bold, italic)] = tkfont.Font(
                    weight=('bold' if bold else 'normal'),
                    slant=('italic' if italic else 'roman'))

        self.textwidget.bind('<<SettingChanged:font_family>>', self._font_changed, add=True)
        self.textwidget.bind('<<SettingChanged:font_size>>', self._font_changed, add=True)
        self.textwidget.bind('<<SettingChanged:pygments_style>>', self._style_changed, add=True)
        self._font_changed()
        self._style_changed()

    def _font_changed(self, junk: object = None) -> None:
        font_updates = cast(Dict[str, Any], tkfont.Font(name='TkFixedFont', exists=True).actual())
        del font_updates['weight']     # ignore boldness
        del font_updates['slant']      # ignore italicness

        for (bold, italic), font in self._fonts.items():
            # fonts don't have an update() method
            for key, value in font_updates.items():
                font[key] = value

    def _style_changed(self, junk: object = None) -> None:
        # http://pygments.org/docs/formatterdevelopment/#styles
        # all styles seem to yield all token types when iterated over,
        # so we should always end up with the same tags configured
        style = styles.get_style_by_name(settings.get('pygments_style', str))
        for tokentype, infodict in style:
            # this doesn't use underline and border
            # i don't like random underlines in my code and i don't know
            # how to implement the border with tkinter
            self.textwidget.tag_config(
                str(tokentype),
                font=self._fonts[(infodict['bold'], infodict['italic'])],
                # empty string resets foreground
                foreground=('' if infodict['color'] is None else '#' + infodict['color']),
                background=('' if infodict['bgcolor'] is None else '#' + infodict['bgcolor']),
            )

            # make sure that the selection tag takes precedence over our
            # token tag
            self.textwidget.tag_lower(str(tokentype), 'sel')

    def _find_previous_root_mark(self, index: str) -> Optional[str]:
        assert not index.startswith(ROOT_STATE_MARK_PREFIX)
        mark = index
        while True:
            mark = self.textwidget.mark_previous(mark)
            if mark is None:
                return None
            if mark.startswith(ROOT_STATE_MARK_PREFIX):
                return mark

    def highlight(self, junk: object = None) -> None:
        start_time = time.perf_counter()

        # Find visible part of code
        last_possible_start = self.textwidget.index('@0,0')
        first_possible_end = self.textwidget.index('@0,10000')

        start = self.textwidget.index(self._find_previous_root_mark(last_possible_start) or '1.0')
        lexer = self._get_lexer()
        use_root_marks = isinstance(lexer, RegexLexer)

        code = self.textwidget.get(start, 'end - 1 char')
        generator = lexer.get_tokens_unprocessed(code)

        tags2add: Dict[str, List[str]] = {}
        new_marks = [self.textwidget.index(start)]  # always 'lineno.column'
        lineno, column = map(int, self.textwidget.index(start).split('.'))

        for position, tokentype, text in generator:
            tag_list = tags2add.setdefault(str(tokentype), [])
            tag_list.append(f'{lineno}.{column}')

            newline_count = text.count('\n')
            if newline_count != 0:
                lineno += newline_count
                column = len(text.rsplit('\n', 1)[-1])
            else:
                column += len(text)
            tag_list.append(f'{lineno}.{column}')

            # We place marks where highlighting may begin.
            # You can't start highlighting anywhere, such as inside a multiline string or comment.
            # The tokenizer is at root state when tokenizing starts.
            # So it has to be in root state for placing a mark.
            # The only way to check for it with pygments is to use local variables inside the generator.
            # It's an ugly hack.
            if use_root_marks and generator.gi_frame.f_locals['statestack'] == ['root']:
                if lineno >= int(new_marks[-1].split('.')[0]) + 10:
                    new_marks.append(f'{lineno}.{column}')
                if self.textwidget.compare(f'{lineno}.{column}', '>=', first_possible_end):
                    break

        end = f'{lineno}.{column}'
        for tag in all_token_tags:
            self.textwidget.tag_remove(tag, start, end)
        for tag, places in tags2add.items():
            self.textwidget.tag_add(tag, *places)

        # Don't know if unsetting marks in loop is guaranteed to work.
        # Possibly similar to changing a Python list while looping over it?
        marks_to_unset = []
        mark: Optional[str] = start
        while True:
            assert mark is not None
            mark = self.textwidget.mark_next(mark)
            if mark is None or self.textwidget.compare(mark, '>', end):
                break
            if mark.startswith(ROOT_STATE_MARK_PREFIX):
                try:
                    new_marks.remove(self.textwidget.index(mark))
                except ValueError:
                    marks_to_unset.append(mark)
        self.textwidget.mark_unset(*marks_to_unset)

        for mark_index in new_marks:
            self.textwidget.mark_set(next(root_mark_names), mark_index)

        mark_count = sum(
            1 if mark.startswith(ROOT_STATE_MARK_PREFIX) else 0
            for mark in self.textwidget.mark_names()
        )
        log.debug(
            f"Highlighted between {start} and {end} in {round((time.perf_counter() - start_time)*1000)}ms. "
            f"Root state marks: {len(marks_to_unset)} deleted, {len(new_marks)} added, {mark_count} total")


# When scrolling, don't highlight too often. Makes scrolling smoother.
def debounce(any_widget: tkinter.Misc, function: Callable[[], None], ms_between_calls_min: int) -> Callable[[], None]:
    timeout_scheduled = False
    running_requested = False

    def timeout_callback() -> None:
        nonlocal timeout_scheduled, running_requested
        assert timeout_scheduled
        if running_requested:
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            running_requested = False
        else:
            timeout_scheduled = False

    def request_running() -> None:
        nonlocal timeout_scheduled, running_requested
        if timeout_scheduled:
            running_requested = True
        else:
            assert not running_requested
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            timeout_scheduled = True

    return request_running


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        # needed because pygments_lexer might change
        def get_lexer() -> Lexer:
            assert isinstance(tab, tabs.FileTab)  # f u mypy
            return tab.settings.get('pygments_lexer', LexerMeta)()

        highlighter = Highlighter(tab.textwidget, get_lexer)
        tab.bind('<<TabSettingChanged:pygments_lexer>>', highlighter.highlight, add=True)
        # TODO: handle changes outside view (currently they are quite rare)
        utils.bind_with_data(tab.textwidget, '<<ContentChanged>>', highlighter.highlight, add=True)
        utils.add_scroll_command(tab.textwidget, 'yscrollcommand', debounce(tab, highlighter.highlight, 50))
        highlighter.highlight()


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
