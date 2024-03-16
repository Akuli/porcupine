from tkinter import ttk

from porcupine.plugins.update_check import x_days_ago
from porcupine import settings


def test_x_days_ago():
    assert x_days_ago(0) == "today"
    assert x_days_ago(1) == "yesterday"
    assert x_days_ago(2) == "2 days ago"
    assert x_days_ago(3) == "3 days ago"
    assert x_days_ago(10) == "10 days ago"
    assert x_days_ago(20) == "20 days ago"
    assert x_days_ago(30) == "30 days ago"
    assert x_days_ago(40) == "40 days ago"
    assert x_days_ago(45) == "45 days ago"
    assert x_days_ago(46) == "about 2 months ago"
    assert x_days_ago(47) == "about 2 months ago"
    assert x_days_ago(349) == "about 11 months ago"
    assert x_days_ago(350) == "about 11 months ago"
    assert x_days_ago(351) == "about 1 year ago"
    assert x_days_ago(352) == "about 1 year ago"
    assert x_days_ago(380) == "about 1 year ago"
    assert x_days_ago(381) == "about 1 year and 1 month ago"
    assert x_days_ago(410) == "about 1 year and 1 month ago"
    assert x_days_ago(411) == "about 1 year and 2 months ago"
    assert x_days_ago(715) == "about 1 year and 11 months ago"
    assert x_days_ago(716) == "about 2 years ago"
    assert x_days_ago(745) == "about 2 years ago"
    assert x_days_ago(746) == "about 2 years and 1 month ago"
    assert x_days_ago(776) == "about 2 years and 1 month ago"
    assert x_days_ago(777) == "about 2 years and 2 months ago"


# IMO the update checkbox is easier to see if it is the last thing.
# I want users to disable update checking if they hate it.
def test_update_checkbox_is_last():
    content = settings.get_dialog_content()
    width, height = content.grid_size()
    last_row = content.grid_slaves(row=height-1)

    assert len(last_row) == 1
    assert isinstance(last_row[0], ttk.Checkbutton)
    assert last_row[0]['text'] == 'asd'
