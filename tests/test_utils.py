from porcupine import get_main_window, utils


def test_create_tcl_list(porcusession):
    def simple_test(stringlist, expected_stringed):
        stringed = utils.create_tcl_list(stringlist)
        assert stringed == expected_stringed
        assert get_main_window().tk.splitlist(stringed) == tuple(stringlist)

    simple_test(['a', 'b', 'c'], 'a b c')
    simple_test(['1', '2', '3'], '1 2 3')
    simple_test(['a', 'b', 'c and d'], 'a b {c and d}')
    simple_test(['{', '}', '{ and }'], r'\{ \} {{ and }}')

    # test iterables of different types
    assert utils.create_tcl_list([1, 2.0, 3.14, 'asd']) == '1 2.0 3.14 asd'
    assert utils.create_tcl_list((1, 2.0, 3.14, 'asd')) == '1 2.0 3.14 asd'
    assert utils.create_tcl_list('abc') == 'a b c'
    assert utils.create_tcl_list(iter('abc')) == 'a b c'
    assert utils.create_tcl_list(range(5)) == '0 1 2 3 4'
    assert utils.create_tcl_list((i for i in (1, 2, 3))) == '1 2 3'


def test_bind_with_data(porcusession):
    ran = 0

    # i don't know why the main window works better with this than a
    # temporary tkinter.Frame()
    def cb(event):
        assert event.widget is get_main_window()
        assert event.data_tuple(int, str, int) == (1, 'asd asd', 3)
        nonlocal ran
        ran += 1

    utils.bind_with_data(get_main_window(), '<<Asd>>', cb, add=True)
    get_main_window().event_generate(
        '<<Asd>>', data=utils.create_tcl_list([1, 'asd asd', 3]))
    assert ran == 1
