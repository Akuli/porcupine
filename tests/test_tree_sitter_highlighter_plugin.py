import subprocess
import sys

# I currently don't think the new highlight plugin needs lots of tests.
# If highlight plugin doesn't work, it's usually quite obvious after using it a while.
#
# That said, it does a few fragile things:
#    - Unzipping and loading the binary file (could go wrong in platform-specific ways)
#    - The dumping command-line interface, used only when configuring the plugin in filetypes.ini
#
# These need testing, and this test conveniently tests them both.
def test_dumping_hello_world_program(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello')")
    output = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "porcupine.plugins.tree_sitter_highlight",
            "python",
            str(tmp_path / "hello.py"),
        ],
        text=True,
    )

    expected_output = """
type=module text="print('hello')"
  type=expression_statement text="print('hello')"
    type=call text="print('hello')"
      type=identifier text='print'
      type=argument_list text="('hello')"
        type=( text='('
        type=string text="'hello'"
          type=" text="'"
          type=" text="'"
        type=) text=')'
    """
    assert output.strip() == expected_output.strip()
