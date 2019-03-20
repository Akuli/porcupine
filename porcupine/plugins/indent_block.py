"""Allow selecting multiple lines and indenting them all at once."""

from teek.extras import cross_platform

from porcupine import get_tab_manager, tabs

# TODO: this plugin seems to be broken without tabs2spaces.py?
setup_before = ['tabs2spaces']      # see tabs2spaces.py


def on_tab_key(shifted, event):
    try:
        [(start_index, end_index)] = event.widget.get_tag('sel').ranges()
    except ValueError as e:
        # nothing selected, allow doing other stuff
        return None

    start = start_index.line
    end = end_index.line
    if end_index.column != 0:
        # something's selected on the end line, let's indent/dedent it too
        end += 1

    for lineno in range(start, end):
        line_start = event.widget.TextIndex(lineno, 0)
        if shifted:
            event.widget.dedent(line_start)
        else:
            # if the line is empty or it contains nothing but
            # whitespace, don't touch it
            content = event.widget.get(line_start, line_start.lineend())
            if not (content.isspace() or not content):
                event.widget.indent(line_start)

    # select only the lines we indented but everything on them
    event.widget.get_tag('sel').remove()
    event.widget.get_tag('sel').add((start, 0), (end, 0))


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        cross_platform.bind_tab_key(tab.textwidget, on_tab_key, event=True)


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
