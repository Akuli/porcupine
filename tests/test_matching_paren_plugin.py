def test_basic(filetab):
    text = filetab.textwidget
    text.insert('1.0', 'print("hello")')
    text.mark_set('insert', '1.6')  # between ( and "
    assert text.get('matching_paren.first', 'matching_paren.last') == '("hello")'
    text.mark_set('insert', '1.0 lineend')
    assert text.get('matching_paren.first', 'matching_paren.last') == '("hello")'
    text.mark_set('insert', '1.2')
    assert not text.tag_ranges('matching_paren')


def test_nested(filetab):
    text = filetab.textwidget
    text.insert('1.0', "{'foo': {'bar': 'baz'}, 'lol': 'wat'}")

    # outer braces
    text.mark_set('insert', '1.0')
    assert not text.tag_ranges('matching_paren')   # cursor must always be after the paren
    text.mark_set('insert', '1.1')
    assert text.index('matching_paren.first') == '1.0'
    assert text.index('matching_paren.last') == text.index('1.0 lineend')
    text.mark_set('insert', '1.0 lineend')
    assert text.index('matching_paren.first') == '1.0'
    assert text.index('matching_paren.last') == text.index('1.0 lineend')

    # inner braces
    text.mark_set('insert', '1.9')
    assert text.get('matching_paren.first', 'matching_paren.last') == "{'bar': 'baz'}"
    text.mark_set('insert', '1.22')
    assert text.get('matching_paren.first', 'matching_paren.last') == "{'bar': 'baz'}"


def test_square_brackets_and_round_parens_and_curly_braces_nested(filetab):
    text = filetab.textwidget
    text.insert('1.0', '''\
stuff = [
    ('a', 'b', {'c', 'd'})
]''')

    # [square brackets]
    text.mark_set('insert', '1.0 lineend')
    assert text.get('matching_paren.first', 'matching_paren.last') == '''[
    ('a', 'b', {'c', 'd'})
]'''
    text.mark_set('insert', '3.1')
    assert text.get('matching_paren.first', 'matching_paren.last') == '''[
    ('a', 'b', {'c', 'd'})
]'''

    # (round parens)
    text.mark_set('insert', '2.5')
    assert text.get('matching_paren.first', 'matching_paren.last') == "('a', 'b', {'c', 'd'})"
    text.mark_set('insert', '2.0 lineend')
    assert text.get('matching_paren.first', 'matching_paren.last') == "('a', 'b', {'c', 'd'})"

    # {curly braces}
    text.mark_set('insert', '2.16')
    assert text.get('matching_paren.first', 'matching_paren.last') == "{'c', 'd'}"
    text.mark_set('insert', '2.0 lineend - 1 char')
    assert text.get('matching_paren.first', 'matching_paren.last') == "{'c', 'd'}"


def test_404(filetab):
    text = filetab.textwidget

    # make sure that searching for matching paren doesn't "wrap around"
    for content in ['print(asdf', 'p)int(asdf', ')rint(asdf', 'prin)(asdf']:
        text.delete('1.0', 'end')
        text.insert('1.0', content)
        text.mark_set('insert', '1.6')
        assert not text.tag_ranges('matching_paren')


def test_wrong_paren_between(filetab):
    text = filetab.textwidget
    text.insert('1.0', 'foo([)')
    text.mark_set('insert', '1.0 lineend')
    assert not text.tag_ranges('matching_paren')
