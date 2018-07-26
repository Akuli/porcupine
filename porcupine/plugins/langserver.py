import difflib

from porcupine import get_tab_manager, tabs, utils


# this thing's line numbers start at 0
def index_to_line_column(index, text):
    lineno = text.count('\n', 0, index)
    column = index - (text.rfind('\n', 0, index) + 1)
    return (lineno, column)


class LangServerHandler:

    def __init__(self, tab):
        self.tab = tab
        self.full_code = tab.textwidget.get('1.0', 'end - 1 char')

    # langserver protocol wants to keep track of text insertions and deletions,
    # and this is the best way to do it in porcupine because tkinter
    def on_content_changed(self, event):
        new_code = self.tab.textwidget.get('1.0', 'end - 1 char')
        matcher = difflib.SequenceMatcher(a=self.full_code, b=new_code)

        for (delete_equal_replace_or_insert,
             old_start, old_end, new_start, new_end) in matcher.get_opcodes():
            if delete_equal_replace_or_insert == 'equal':
                continue

            replacement = new_code[new_start:new_end]

            how_many_deleted = old_end - old_start
            how_many_inserted = new_end - new_start

            # it's important to use new_start for everything because that is
            # the start value that represents the state of the code after
            # applying the previous edits... note that this code runs in a
            # loop, and the changes are applied in order
            #
            # think of this like:
            #    new_code[new_start:new_end] = old_code[old_start:old_end]
            #
            # and after that:
            #    new_code[new_start:end] == old_code[old_start:old_end]
            end = new_start + how_many_deleted

            start_lineno, start_column = index_to_line_column(
                new_start, new_code)
            end_lineno, end_column = index_to_line_column(end, new_code)
            print("replace from %d:%d to %d:%d with %r" % (
                start_lineno, start_column, end_lineno, end_column,
                replacement))

        self.full_code = new_code


def on_new_tab(event):
    tab = event.data_widget
    if isinstance(tab, tabs.FileTab):
        handler = LangServerHandler(tab)
        tab.textwidget.bind('<<ContentChanged>>', handler.on_content_changed,
                            add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
