from porcupine import get_main_window


def test_no_previous_command_error(filetab, tmp_path, mocker):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    mock.assert_called_once()
    assert "press F4 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)
