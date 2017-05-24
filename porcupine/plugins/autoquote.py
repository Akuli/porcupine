"""Add matching quotes and parentheses automatically."""

parens = {'(': ')', '[': ']', '{': '}'}


def _key_press_callback(event):
    if event.char in {'"', "'"}:
        # if there's already another quote in front of this, don't add
        # anything
        next_char = event.widget.get('insert', 'insert + 1 char')
        if next_char == event.char:
            event.widget.mark_set('insert', 'insert + 1 char')
            return 'break'

        # check for ''' and """ strings
        third_last = event.widget.get('insert - 3 chars', 'insert - 2 chars')
        last_two = event.widget.get('insert - 2 chars', 'insert')
        if third_last != event.char and last_two == event.char*2:
            # the user has already typed exactly two quotes
            old_cursor_pos = event.widget.index('insert')
            event.widget.insert('insert', event.char * 3)
            event.widget.mark_set('insert', old_cursor_pos)
            return None

        # double it up and adjust cursor position
        event.widget.insert('insert', event.char)
        event.widget.mark_set('insert', 'insert - 1 char')
        return None

    if event.char in parens.values():
        # closing parenthese
        next_char = event.widget.get('insert', 'insert + 1 char')
        if next_char == event.char:
            # just move the cursor past it
            event.widget.mark_set('insert', 'insert + 1 char')
            return 'break'
        return None

    if event.char in parens.keys():
        # it's an opening parenthese
        closing = parens[event.char]
        next_char = event.widget.get('insert', 'insert + 1 char')
        if next_char != closing:
            # autocomplete the closing brace
            event.widget.insert('insert', closing)
            event.widget.mark_set('insert', 'insert - 1 char')
            return None

    assert False, "unexpected event character %r" % event.char


all_keys = [
    'apostrophe', 'quotedbl',       # ' "
    'parenleft', 'parenright',      # ( )
    'bracketleft', 'bracketright',  # [ ]
    'braceleft', 'braceright',      # { }
]


def tab_callback(tab):
    if hasattr(tab, 'textwidget'):
        # TODO: figure out why binding to '<Key>' doesn't work
        for key in all_keys:
            tab.textwidget.bind('<' + key + '>', _key_press_callback, add=True)
    yield
    # the textwidget will be destroyed, no need to unbind anything


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)
