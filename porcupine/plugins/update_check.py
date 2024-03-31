"""Check for updates when Porcupine starts.

If a new version of Porcupine has been released, this plugin notifies you about
it by showing a message in the status bar. If you don't like it, uncheck the
"Check for updates when Porcupine starts" checkbox in the settings or disable
this plugin.
"""
from __future__ import annotations

import datetime
import logging

import requests

from porcupine import __version__ as this_porcupine_version
from porcupine import settings, utils
from porcupine.plugins import statusbar
from porcupine.settings import global_settings

log = logging.getLogger(__name__)

# Place the update checkbox towards the end of the settings dialog
setup_after = ["restart"]


def x_days_ago(days: int) -> str:
    days_in_year = 365.25  # good enough
    days_in_month = days_in_year / 12
    months = round(days / days_in_month)

    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 1.5 * days_in_month:
        return f"{days} days ago"

    months = round(days / days_in_month)
    if months < 12:
        return f"about {months} months ago"
    if months == 12:
        return "about a year ago"
    if months == 13:
        return "about a year and a month ago"
    if months < 24:
        return f"about a year and {months - 12} months ago"
    if months % 24 == 0:
        return f"about {months // 12} years ago"
    if months % 24 == 1:
        return f"about {months // 12} years and a month ago"
    return f"about {months // 12} years and {months % 12} months ago"


def get_date(version: str) -> datetime.date:
    year, month, day = map(int, version.lstrip("v").split("."))
    return datetime.date(year, month, day)


def get_latest_release() -> str | None:
    """Returns name of the latest release, or None if Porcupine is up to date.

    This is slow, and runs in a new thread.
    """
    response = requests.get(
        "https://api.github.com/repos/Akuli/porcupine/releases/latest",
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        timeout=3,
    )
    response.raise_for_status()
    version: str = response.json()["tag_name"].lstrip("v")

    assert not version.startswith("v")
    assert not this_porcupine_version.startswith("v")

    if version == this_porcupine_version:
        log.debug("this is the latest version of Porcupine")
        return None

    return version


def done_callback(success: bool, result: str | None) -> None:
    if not success:
        # Handle errors somewhat silently. Update checking is not very important.
        log.warning("checking for updates failed")
        log.info(f"full error message from update checking:\n{result}")
        return

    if result is not None:
        # There is a new release
        some_days_ago = x_days_ago((datetime.date.today() - get_date(result)).days)
        statusbar.set_global_message(f"A new version of Porcupine was released {some_days_ago}.")


def setup() -> None:
    global_settings.add_option("update_check_on_startup", True)
    settings.add_checkbutton(
        "update_check_on_startup", text="Check for updates when Porcupine starts"
    )

    if global_settings.get("update_check_on_startup", bool):
        utils.run_in_thread(get_latest_release, done_callback)
