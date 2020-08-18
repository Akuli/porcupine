"""If multiple lines are selected and tab is pressed, then indent all of the lines."""
import tkinter

from porcupine import get_tab_manager, textwidget, tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py


def on_tab_key(event: 'tkinter.Event[textwidget.MainText]', shifted: bool) -> None:
    try:
        start_index, end_index = map(str, event.widget.tag_ranges('sel'))
    except ValueError:
        # nothing selected
        return

    start = int(start_index.split('.')[0])
    end = int(end_index.split('.')[0])
    if end_index.split('.')[1] != '0':
        # something's selected on the end line, let's indent/dedent it too
        end += 1

    for lineno in range(start, end):
        if shifted:
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


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        utils.bind_tab_key(tab.textwidget, on_tab_key, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
