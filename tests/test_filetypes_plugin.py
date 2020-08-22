from porcupine import filedialog_kwargs


def test_get_filedialog_kwargs(porcusession):
    for pair in filedialog_kwargs['filetypes']:
        assert isinstance(pair, tuple)
        assert len(pair) == 2
        assert isinstance(pair[0], str)
        if pair[1] != '*':
            # because tkinter likes tuples, and in tcl, "*" is a string
            # that is also a list of length 1
            assert isinstance(pair[1], tuple)
        assert all(isinstance(pattern, str) for pattern in pair[1])

    assert filedialog_kwargs['filetypes'][0] == ('All Files', '*')
    assert '.py' in dict(filedialog_kwargs['filetypes'])['Python']
