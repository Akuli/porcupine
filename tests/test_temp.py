import os
import subprocess
import sys


def test_dirs_temporary_ci_thing():
    print("\n" * 5)
    subprocess.call(
        [
            sys.executable,
            "-c",
            r'import porcupine; print("cache", porcupine.dirs.user_cache_dir); print("config", porcupine.dirs.user_config_dir); print("log", porcupine.dirs.user_log_dir)',
        ]
    )
    print()
    for k, v in os.environ.items():
        print(k, "=", v)
    print("\n" * 5)
