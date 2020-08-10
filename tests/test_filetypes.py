from porcupine import get_main_window, filetypes


# porcusession because it may use get_main_window()
def test_get_filedialog_kwargs(porcusession):
    kwargs = filetypes.get_filedialog_kwargs()

    if kwargs:
        assert kwargs.keys() == {'filetypes'}
        if get_main_window().tk.call('tk', 'windowingsystem') == 'aqua':
            # see comments in filetypes.get_filedialog_kwargs()
            assert len(kwargs['filetypes']) > 1

        for pair in kwargs['filetypes']:
            assert isinstance(pair, tuple)
            assert len(pair) == 2
            assert isinstance(pair[0], str)
            if pair[1] != '*':
                # because tkinter likes tuples, and in tcl, "*" is a string
                # that is also a list of length 1
                assert isinstance(pair[1], tuple)
            assert all(isinstance(pattern, str) for pattern in pair[1])

        assert kwargs['filetypes'][0] == ('All Files', '*')
        assert '.py' in dict(kwargs['filetypes'])['Python']

    else:
        # see comments in filetypes.get_filedialog_kwargs()
        assert get_main_window().tk.call('tk', 'windowingsystem') == 'aqua'

    # it must be consistent
    assert filetypes.get_filedialog_kwargs() == kwargs
    assert filetypes.get_filedialog_kwargs() == kwargs
    assert filetypes.get_filedialog_kwargs() == kwargs

    # TODO: test that new filetypes appear in the return value when they
    #       are added
