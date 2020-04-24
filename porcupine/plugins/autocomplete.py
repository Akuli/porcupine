# this will be replaced with langserver support soon™
import collections
import itertools
import json
import re

from porcupine import get_tab_manager, tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py


class _AutoCompleter:

    def __init__(self, tab):
        self.tab = tab
        self._startpos = None
        self._suffixes = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id = None   # None means no response matches

        # this is easy to understand but hard to explain
        # see _put_completion_to_text_widget
        self._can_reset_now = True

    def _request_completions(self):
        the_id = next(self._id_counter)
        self._waiting_for_response_id = the_id
        self.tab.event_generate('<<AutoCompletionRequest>>', data=json.dumps({
            'id': the_id,
        }))

    def _put_first_suffix_to_text_widget(self):
        self._can_reset_now = False
        self.tab.textwidget.delete(self._startpos, 'insert')
        self.tab.textwidget.mark_set('insert', self._startpos)
        self.tab.textwidget.insert(self._startpos, self._suffixes[0])
        self._can_reset_now = True

    def receive_completions(self, event):
        print('receiving xd')
        info_dict = event.data_json()
        if info_dict['id'] == self._waiting_for_response_id:
            self._waiting_for_response_id = None
            self._suffixes = collections.deque(info_dict['suffixes'])
            self._suffixes.append('')   # end of completions
            self._put_first_suffix_to_text_widget()

    def _can_complete_here(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        return (
            # don't complete in beginning of line or with space before cursor
            re.search(r'\S$', before_cursor)
            # don't complete  in the beginning or middle of a word
            and not re.search(r'^\w', after_cursor)         # noqa
        )

    def _complete(self, rotation):
        if self._suffixes is None:
            self._startpos = self.tab.textwidget.index('insert')
            if not self._can_complete_here():
                # let tabs2spaces and other plugins handle it
                return None

            self._request_completions()
            return 'break'

        self._suffixes.rotate(rotation)
        self._put_first_suffix_to_text_widget()
        return 'break'

    def on_tab(self, event, shifted):
        if event.widget.tag_ranges('sel'):
            # something's selected, autocompleting is probably not the
            # right thing to do
            return None
        return self._complete(1 if shifted else -1)

    def reset(self, *junk):
        if self._can_reset_now:
            self._suffixes = None
            self._waiting_for_response_id = None


def on_new_tab(event):
    tab = event.data_widget
    if isinstance(tab, tabs.FileTab):
        completer = _AutoCompleter(tab)
        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind('<<CursorMoved>>', completer.reset, add=True)
        utils.bind_with_data(tab, '<<AutoCompletionResponse>>',
                             completer.receive_completions, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
