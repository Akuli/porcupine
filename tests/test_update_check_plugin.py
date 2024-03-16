import datetime
import os
import sys

import pytest

from porcupine.plugins import update_check


def test_x_days_ago():
    assert update_check.x_days_ago(0) == "today"
    assert update_check.x_days_ago(1) == "yesterday"
    assert update_check.x_days_ago(2) == "2 days ago"
    assert update_check.x_days_ago(3) == "3 days ago"
    assert update_check.x_days_ago(10) == "10 days ago"
    assert update_check.x_days_ago(20) == "20 days ago"
    assert update_check.x_days_ago(30) == "30 days ago"
    assert update_check.x_days_ago(40) == "40 days ago"
    assert update_check.x_days_ago(45) == "45 days ago"
    assert update_check.x_days_ago(46) == "about 2 months ago"
    assert update_check.x_days_ago(47) == "about 2 months ago"
    assert update_check.x_days_ago(349) == "about 11 months ago"
    assert update_check.x_days_ago(350) == "about 11 months ago"
    assert update_check.x_days_ago(351) == "about a year ago"
    assert update_check.x_days_ago(352) == "about a year ago"
    assert update_check.x_days_ago(380) == "about a year ago"
    assert update_check.x_days_ago(381) == "about a year and a month ago"
    assert update_check.x_days_ago(410) == "about a year and a month ago"
    assert update_check.x_days_ago(411) == "about a year and 2 months ago"
    assert update_check.x_days_ago(715) == "about a year and 11 months ago"
    assert update_check.x_days_ago(716) == "about 2 years ago"
    assert update_check.x_days_ago(745) == "about 2 years ago"
    assert update_check.x_days_ago(746) == "about 2 years and a month ago"
    assert update_check.x_days_ago(776) == "about 2 years and a month ago"
    assert update_check.x_days_ago(777) == "about 2 years and 2 months ago"


@pytest.mark.skipif(
    sys.platform == "macos" and os.environ.get("GITHUB_ACTIONS") == "true",
    reason="failed MacOS CI in github actions, don't know why",
)
def test_fetching_release_creator():
    # I don't want to know which way it calls this function.
    # Let's just make it work in both cases.
    assert update_check.fetch_release_creator("2024.03.09") == "Akuli"
    assert update_check.fetch_release_creator("v2024.03.09") == "Akuli"


def test_the_message(mocker):
    mock_datetime = mocker.patch("porcupine.plugins.update_check.datetime")
    mock_datetime.date.side_effect = datetime.date
    mock_datetime.date.today.return_value = datetime.date(2024, 3, 16)

    assert (
        update_check.format_new_release_message("v2024.03.09", None)
        == "A new version of Porcupine was released 7 days ago."
    )
    assert (
        update_check.format_new_release_message("v2024.03.09", "Akuli")
        == "Akuli released a new version of Porcupine 7 days ago."
    )
