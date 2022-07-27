import os
from pathlib import Path


def test_sources_txt_is_up_to_date():
    sources_file_content = Path("porcupine/images/sources.txt").read_text()
    for filename in os.listdir("porcupine/images"):
        if filename not in {"__init__.py", "__pycache__", "sources.txt"}:
            assert filename in sources_file_content
