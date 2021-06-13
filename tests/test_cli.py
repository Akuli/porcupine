import porcupine


def test_version(run_porcupine):
    assert run_porcupine(["--version"], 0) == f"Porcupine {porcupine.__version__}\n"


def test_bad_without_plugins_argument(run_porcupine):
    output = run_porcupine(["--without-plugins=asdf"], 2)
    assert "usage:" in output
    assert "--without-plugins: no plugin named 'asdf'" in output
