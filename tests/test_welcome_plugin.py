import re


def test_welcome_text(tabmanager):
    assert not tabmanager.tabs()
    message_label = tabmanager.nametowidget("welcome_frame").nametowidget("message")
    assert re.search(r"new file by pressing [\S]+N", message_label["text"])
    assert re.search(r"open an existing file by pressing [\S]+O", message_label["text"])
    assert re.search(r"save the file with [\S]+S", message_label["text"])
    assert "run it by pressing F5" in message_label["text"]
