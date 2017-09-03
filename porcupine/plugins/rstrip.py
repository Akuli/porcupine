"""Remove trailing whitespace when enter is pressed."""

from porcupine import get_tab_manager, tabs, utils


def after_enter(textwidget):
    """Strip trailing whitespace at the end of a line."""
    lineno = int(textwidget.index('insert').split('.')[0]) - 1
    line = textwidget.get('%d.0' % lineno, '%d.0 lineend' % lineno)
    if len(line) != len(line.rstrip()):
        textwidget.delete('%d.%d' % (lineno, len(line.rstrip())),
                          '%d.0 lineend' % lineno)


def on_new_tab(event):
    if isinstance(event.data_widget, tabs.FileTab):
        textwidget = event.data_widget.textwidget

        def bind_callback(event):
            textwidget.after_idle(after_enter, textwidget)

        textwidget.bind('<Return>', bind_callback, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
