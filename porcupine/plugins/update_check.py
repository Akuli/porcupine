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


def get_date(version: str) -> datetime.date:
    year, month, day = map(int, version.lstrip("v").split("."))
    return datetime.date(year, month, day)


def fetch_release_creator(version: str) -> str | None:
    """Find out who created a release.

    Unfortunately the releases appear as being created by the GitHub Actions
    bot account, so we look for a commit created by a script that Porcupine
    maintainers run locally.
    """

    # Commit date may be off by a day because time zones
    start_time = (get_date(version) - datetime.timedelta(days=1)).isoformat() + ":00:00:00Z"
    end_time = (get_date(version) + datetime.timedelta(days=1)).isoformat() + ":23:59:59Z"

    try:
        response = requests.get(
            "https://api.github.com/repos/Akuli/porcupine/commits",
            params={"since": start_time, "until": end_time},
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            timeout=3,
        )
        response.raise_for_status()
    except requests.RequestException:
        log.info(f"error fetching commits around release date {version}", exc_info=True)
        return None

    for commit in response.json():
        if commit["commit"]["message"] == f"Version v{version}":
            return commit["author"]["login"]

    # script no longer used in a future version of Porcupine?
    return None


def fetch_release_info() -> tuple[str, str | None] | None:
    """Returns (when_released, who_released) for the latest release.

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

    return (version, fetch_release_creator(version))


def format_new_release_message(version: str, who_released: str | None) -> str:
    some_days_ago = x_days_ago((datetime.date.today() - get_date(version)).days)
    if who_released is None:
        return f"A new version of Porcupine was released {some_days_ago}."
    else:
        return f"{who_released} released a new version of Porcupine {some_days_ago}."


def check_for_updates_in_background() -> None:
    def done_callback(success: bool, result: str | tuple[str, str | None] | None) -> None:
        if not success:
            # Handle errors somewhat silently. Update checking is not very important.
            log.warning("checking for updates failed")
            log.info(f"full error message from update checking:\n{result}")
            return

        assert not isinstance(result, str)
        if result is not None:
            # There is a new release
            statusbar.set_global_message(format_new_release_message(*result))

    utils.run_in_thread(fetch_release_info, done_callback)


def setup() -> None:
    global_settings.add_option("update_check_on_startup", True)
    settings.add_checkbutton(
        "update_check_on_startup", text="Check for updates when Porcupine starts"
    )
    if global_settings.get("update_check_on_startup", bool):
        check_for_updates_in_background()
