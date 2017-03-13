"""Syntax highlighting for Tkinter's text widget."""

# This thing uses tokenize for parsing the syntax. It works very well,
# and I had no trouble at all when testing this with a 10000 line test
# file.
#
# Usually the tokenize module isn't used for highlighting, so you are probably
# thinking of other modules. Here's why I didn't use them:
#   ast
#       The ast module allows no syntax errors at all, but tokenizing
#       doesn't require perfectly valid syntax. Especially things like
#       indentation errors and unclosed quotes are reasons why ast isn't
#       useful here.
#   pygments
#       Two reasons: implementing a formatter for a tkinter Text widget
#       is difficult and pygments is way too slow for highlighting as
#       the user types.
#
# The highlighting is done semi-asynchronously using generators, and
# this is the only sane way to highlight without freezing I could think
# of. The highlighting takes time and using threads with tkinter
# requires a queue with a callback that clears the queue every n
# milliseconds, so it would be laggy. The highlighting also needs to be
# cancelled if the user keeps typing while it's running, and simply
# setting Highlighter's _highlight_job to a new generator works very
# well for that.

import builtins
import keyword
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import tokenize


class Highlighter:

    def __init__(self, textwidget):
        self.textwidget = textwidget

        bold = tkfont.Font(font=textwidget['font'])
        bold['weight'] = 'bold'

        # the order of these matters, the tags added last will be above
        # tags added earlier
        textwidget.tag_config('decorator', foreground='#ff0099')
        textwidget.tag_config('builtin', foreground='#9966cc')
        textwidget.tag_config('keyword', foreground='#cc9900')
        textwidget.tag_config('string', foreground='#00cc00')
        textwidget.tag_config('comment', foreground='#999999')
        textwidget.tag_config('exception', foreground='#ff0000')
        textwidget.tag_config('syntax-error', background='#ff0000')

        self._highlight_job = None

        self._builtins = set()
        self._exceptions = set()
        for name in dir(builtins):
            if name.startswith('_'):
                continue
            value = getattr(builtins, name)
            if isinstance(value, type) and issubclass(value, Exception):
                self._exceptions.add(name)
            else:
                self._builtins.add(name)

        # some things like True and False are both in keyword.kwlist and
        # dir(builtins), so we'll treat them as builtins
        self._keywords = set(keyword.kwlist) - self._builtins

    def _on_idle(self):
        # sometimes this gets added as a Tk idle callback twice but it
        # doesn't matter, see Tcl_DoWhenIdle(3tcl)
        if self._highlight_job is None:
            # not highlighting anything currently
            return

        try:
            next(self._highlight_job)
        except StopIteration:
            # done with highlighting
            self._highlight_job = None
            return

        # let's run this again when we can
        self.textwidget.after_idle(self._on_idle)

    def _clear_tags(self, first_lineno, last_lineno=None):
        """Delete all tags between two lines, except the selection tag."""
        start = '%d.0' % first_lineno
        if last_lineno is None:
            # end of whole file
            end = 'end-1c'
        else:
            # end of last_lineno'th line
            end = '%d.0+1l-1c' % last_lineno

        for tag in self.textwidget.tag_names():
            if tag != 'sel':
                self.textwidget.tag_remove(tag, start, end)

    def _iter_lines(self):
        last_lineno = int(self.textwidget.index('end-1c').split('.')[0])
        for lineno in range(1, last_lineno):
            yield self.textwidget.get('%d.0' % lineno, '%d.0' % (lineno+1))
        last_line = self.textwidget.get('end-1l', 'end-1c')
        if last_line:
            yield last_line

    def _highlight_coro(self):
        bytelines = (line.encode('utf-8', errors='replace')
                     for line in self._iter_lines())

        last_lineno = 0
        try:
            tokens = tokenize.tokenize(bytelines.__next__)
            for tokentype, string, startpos, endpos, line in tokens:
                if tokentype == tokenize.NAME:
                    if string in self._builtins:
                        tag = 'builtin'
                    elif string in self._exceptions:
                        tag = 'exception'
                    elif string in self._keywords:
                        tag = 'keyword'
                    else:
                        continue
                elif tokentype == tokenize.STRING:
                    tag = 'string'
                elif tokentype == tokenize.COMMENT:
                    tag = 'comment'
                elif tokentype == tokenize.OP and string == '@':
                    # it might be a decorator or an "a @ b" expression,
                    # we need to check. this handles this corner case...
                    #
                    #   @stuff(this, decorator, takes,
                    #          arguments, on, multiple, lines)
                    #   def thing():
                    #       ...
                    #
                    # ...but screws up when doing this:
                    #
                    #   stuff = (a
                    #            @ b)
                    #
                    # note that Raymond Hettinger's highlighting script
                    # (distributed with python in Tools/scripts/highlight.py)
                    # doesn't highlight decorators at all, so I think
                    # this is better than that
                    match = re.search(r'^\s*@[^(\n]+', line)
                    if match is None:
                        continue
                    endpos = (endpos[0], match.end())
                    tag = 'decorator'
                else:
                    continue

                if endpos[0] > last_lineno:
                    # we need to delete old highlights between these
                    # line numbers, it's important to NOT yield between
                    # deleting and adding tags because that makes the
                    # text flicker. right before deleting is actually
                    # the only time when we can be sure that
                    # everything's highlighted, so we'll yield here.
                    yield
                    self._clear_tags(last_lineno+1, endpos[0])
                    last_lineno = endpos[0]

                self.textwidget.tag_add(tag, '%d.%d' % startpos,
                                        '%d.%d' % endpos)

        except SyntaxError as e:
            try:
                msg, (file, line, column, code) = e.args
            except ValueError:
                # we don't know what caused the error, so let's not care
                # about it
                pass
            else:
                # we can highlight the bad syntax
                start = '%d.0' % line
                end = '%d.%d' % (line, column)
                self._clear_tags(last_lineno+1)
                self.textwidget.tag_add('syntax-error', start, end)
                return   # don't run the _clear_tags a few lines below this

        # these errors come fron tokenize.tokenize()
        # TODO: handle things like "# coding: ascii" at the top of the
        # file, get rid of UnicodeDecodeError here and errors='replace'
        # in other places
        except (UnicodeDecodeError, tokenize.TokenError) as e:
            pass

        # sometimes there's nothing to highlight at the end of the
        # text widget and we need to delete old highlights
        self._clear_tags(last_lineno+1)

    def highlight(self):
        self._highlight_job = self._highlight_coro()
        self.textwidget.after_idle(self._on_idle)


def main():
    if len(sys.argv) > 2 or sys.argv[1:] == ['--help']:
        sys.exit("usage: %s [FILE]" % sys.argv[0])

    def on_modified(event):
        text.unbind('<<Modified>>')
        text.edit_modified(False)
        text.bind('<<Modified>>', on_modified)
        highlighter.highlight()

    root = tk.Tk()
    text = tk.Text(root, fg='white', bg='black', insertbackground='white')
    text.pack(fill='both', expand=True)

    highlighter = Highlighter(text)
    text.bind('<<Modified>>', on_modified)
    if len(sys.argv) == 2:
        with open(sys.argv[1], 'r') as f:
            text.insert('1.0', f.read())

    root.mainloop()


if __name__ == '__main__':
    main()
