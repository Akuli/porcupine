"""Allow selecting multiple lines and indenting them all at once."""

import functools

from porcupine import tabs, utils


def on_tab(event, shift=False):
    try:
        start_index, end_index = map(str, event.widget.tag_ranges('sel'))
    except ValueError as e:
        # nothing selected, allow doing other stuff
        return None

    start = int(start_index.split('.')[0])
    end = int(end_index.split('.')[0])
    if end_index.split('.')[1] != '0':
        # something's selected on the end line, let's indent/dedent it too
        end += 1

    for lineno in range(start, end):
        if shift:
            event.widget.dedent('%d.0' % lineno)
        else:
            # if the line is empty or it contains nothing but
            # whitespace, don't touch it
            content = event.widget.get(
                '%d.0' % lineno, '%d.0 lineend' % lineno)
            if not (content.isspace() or not content):
                event.widget.indent('%d.0' % lineno)

    # select only the lines we indented but everything on them
    event.widget.tag_remove('sel', '1.0', 'end')
    event.widget.tag_add('sel', '%d.0' % start, '%d.0' % end)

on_shift_tab = functools.partial(on_tab, shift=True)    # noqa


def tab_callback(tab):
    if not isinstance(tab, tabs.FileTab):
        yield
        return

    print("wolo")
    text = tab.textwidget
    with utils.temporary_bind(text, '<Tab>', on_tab):
        with utils.temporary_bind(text, utils.shift_tab(), on_shift_tab):
            yield


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)
