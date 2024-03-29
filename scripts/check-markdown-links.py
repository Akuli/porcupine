"""Check that links in markdown files point to reasonable places."""

import os
import re
import subprocess
import sys
from functools import cache
from http.client import responses as status_code_names
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).absolute().parent.parent
assert (PROJECT_ROOT / "README.md").is_file()
os.chdir(PROJECT_ROOT)


def find_markdown_files():
    output = subprocess.check_output(["git", "ls-files", "*.md"], text=True)
    return [Path(line) for line in output.splitlines()]


def find_links(markdown_file_path):
    content = markdown_file_path.read_text(encoding="utf-8")

    if markdown_file_path.name == "CHANGELOG.md":
        # Ignore changelogs of old versions. Editing them doesn't make sense.
        header_matches = list(re.finditer("^## ", content, flags=re.MULTILINE))
        end_of_current_version = header_matches[1].start()
        content = content[:end_of_current_version]

    for lineno, line in enumerate(content.splitlines(), start=1):
        link_regexes = [
            r"\[\S*?\]\((\S*?)\)",  # [text](target)
            r"^\[.*\]: (\S*)$",  # [text]: target
        ]
        for regex in link_regexes:
            for link_target in re.findall(regex, line):
                yield (lineno, link_target)


@cache
def check_https_url(url):
    try:
        # Many sites redirect to front page for bad URLs. Let's not treat that as ok.
        response = requests.head(url, timeout=1, allow_redirects=False)
    except requests.exceptions.RequestsException as e:
        return f"HTTP HEAD request failed: {e}"

    if response.status_code != 200:
        return f"site returns {response.status_code} {status_code_names[response.status_code]}"

    return None


def check_link(markdown_file_path, link_target):
    if link_target.startswith("http://"):
        return "this link should probably use https instead of http"

    if link_target.startswith("https://"):
        return check_https_url(link_target)

    if "//" in link_target:
        return "double slashes are allowed only in http:// and https:// links"

    if "\\" in link_target:
        return "use forward slashes instead of backslashes"

    path = markdown_file_path.parent / link_target

    if PROJECT_ROOT not in path.resolve().parents:
        return "link points outside of the Porcupine project folder"

    if not path.exists():
        return "link points to a file or folder that doesn't exist"

    return None


def main():
    paths = find_markdown_files()
    assert paths

    good_links = 0
    bad_links = 0

    for path in paths:
        for lineno, link_target in find_links(path):
            problem = check_link(path, link_target)
            if problem:
                print(f"{path}:{lineno}: {problem}")
                bad_links += 1
            else:
                good_links += 1

    assert good_links + bad_links > 0

    print()
    print(f"Checked {good_links + bad_links} links in {len(paths)} files.")
    print(f"Found {bad_links} bad links.")
    if bad_links > 0:
        sys.exit(1)


main()
