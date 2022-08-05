import os


def test_sources_txt_is_up_to_date():
    with open("porcupine/images/sources.txt") as file:
        filenames_mentioned = [line.split()[0] for line in file]
    non_image_files = {"__init__.py", "__pycache__", "sources.txt"}
    assert set(filenames_mentioned) == set(os.listdir("porcupine/images")) - non_image_files
