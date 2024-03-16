import datetime
import requests
import tkinter
import threading
import logging
from tkinter import ttk

from porcupine import __version__ as this_porcupine_version
from porcupine import get_tab_manager, images, tabs, utils, settings
from porcupine.settings import global_settings
#from porcupine.plugins.welcome import WelcomeMessageDisplayer
from porcupine.plugins import statusbar
from porcupine import utils


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
        return "about 1 year ago"
    if months == 13:
        return "about 1 year and 1 month ago"
    if months < 24:
        return f"about 1 year and {months - 12} months ago"
    if months % 24 == 0:
        return f"about {months // 12} years ago"
    if months % 24 == 1:
        return f"about {months // 12} years and 1 month ago"
    return f"about {months // 12} years and {months % 12} months ago"


def _grid_to_end(widget: tkinter.Widget) -> None:
    width, height = widget.master.grid_size()
    widget.grid(row=height, column=0, columnspan=width)


def show_update_available(when_released: datetime.date, who_released: str | None) -> None:
    new_version_age = (when_released - datetime.date.today()).days

    if who_released is None:
        text = f"A new version of Porcupine was released {x_days_ago(new_version_age)}."
    else:
        text = f"{who_released} released a new version of Porcupine {x_days_ago(new_version_age)}."

    statusbar.set_global_message(text)
#
#    # See welcome plugin
#    welcome_frame: ttk.Frame = get_tab_manager().nametowidget("welcome_frame")
#    width, height = welcome_frame.grid_size()
#    _grid_to_end(ttk.Label(welcome_frame, text=text))
#    _grid_to_end(ttk.Button(welcome_frame, text="Show update instructions"))
#

# Returns (when_released, who_released)
def fetch_release_info() -> tuple[datetime.date, str | None] | None:
    response = requests.get(
        "https://api.github.com/repos/Akuli/porcupine/releases/latest",
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        timeout=3,
    )
    response.raise_for_status()
    version = response.json()["tag_name"].lstrip("v")

    assert not version.startswith("v")
    assert not this_porcupine_version.startswith("v")

    if version == this_porcupine_version:
        log.debug("this is the latest version of Porcupine")
        return None

    year, month, day = map(int, version.split("."))
    when_released = datetime.date(year, month, day)

    # Who released this? Unfortunately the releases appear as being created by
    # the GitHub Actions bot account, so we look for a commit created by a
    # script that Porcupine maintainers run locally. Because of timezones, the
    # commit date may be off by a day.
    start_time = (when_released - datetime.timedelta(days=1)).isoformat() + ":00:00:00Z"
    end_time = (when_released + datetime.timedelta(days=1)).isoformat() + ":23:59:59Z"

    try:
        response = requests.get(
            "https://api.github.com/repos/Akuli/porcupine/commits",
            params={"since": start_time, "until": end_time},
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            timeout=3,
        )
        response.raise_for_status()
    except requests.RequestException:
        log.info(f"error fetching commits around {when_released.isoformat()}", exc_info=True)
        who_released = None
    else:
        who_released = None
        for commit in response.json():
            if commit["commit"]["message"] == f"Version v{version}":
                who_released = commit["author"]["login"]
                break

    if who_released is None:
        log.warning(f"could not find who released latest Porcupine {version!r}")

    return (when_released, who_released)


def check_for_updates_in_background() -> None:
    def done_callback(success: bool, result: str | tuple[datetime.date, str | None] | None) -> None:
        if not success:
            # Handle errors somewhat silently. Update checking is not very important.
            log.warning("checking for updates failed")
            log.info(f"full error message from update checking:\n{result}")
            return

        assert not isinstance(result, str)

        if result is not None:
            # There is a new release
            when_released, who_released = result
            show_update_available(when_released, who_released)

    utils.run_in_thread(fetch_release_info, done_callback)


def setup() -> None:
    global_settings.add_option("update_check_on_startup", True)
    settings.add_checkbutton(
        "update_check_on_startup", text="Check for updates when Porcupine starts"
    )
    if global_settings.get("update_check_on_startup", bool):
        check_for_updates_in_background()
