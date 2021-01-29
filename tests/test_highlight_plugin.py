from pygments.lexers import PythonLexer


def test_deleting_bug(filetab):
    def tag_ranges(tag):
        return list(map(str, filetab.textwidget.tag_ranges(tag)))

    filetab.settings.set('pygments_lexer', PythonLexer)
    filetab.textwidget.insert('1.0', 'return None')
    assert tag_ranges('Token.Keyword') == ['1.0', '1.6']
    assert tag_ranges('Token.Keyword.Constant') == ['1.7', '1.11']
    assert tag_ranges('Token.Literal.String.Double') == []

    filetab.textwidget.insert('1.0', '"')
    filetab.update()
    assert tag_ranges('Token.Keyword') == []
    assert tag_ranges('Token.Keyword.Constant') == []
    assert tag_ranges('Token.Literal.String.Double') == ['1.0', '1.12']

    filetab.textwidget.delete('1.0')
    filetab.update()
    assert tag_ranges('Token.Keyword') == ['1.0', '1.6']
    assert tag_ranges('Token.Keyword.Constant') == ['1.7', '1.11']
    assert tag_ranges('Token.Literal.String.Double') == []
