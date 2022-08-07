Files in this directory define how to map a tree-sitter AST tree into Pygments
token types. We need to know the corresponding Pygments token types to use
Pygments color themes, and we use them with tree-sitter for a couple reasons:
- The pygments highlighter uses them already. We want the user to only select
  one color theme.
- There are many pygments themes to choose from.
- It is relatively easy to make new pygments themes. I am currently using a
  Pygments theme named "zaab" created by a friend of mine, available here:
  https://github.com/8banana/banana-themes

Porcupine comes with a script for exploring tree-syntax syntax trees:

    $ cat hello.py
    print("hello")

    $ python3 scripts/tree-sitter-dump.py python hello.py
    type=module text='print("hello")\n'
      type=expression_statement text='print("hello")'
        type=call text='print("hello")'
          type=identifier text='print'
          type=argument_list text='("hello")'
            type=( text='('
            type=string text='"hello"'
              type=" text='"'
              type=" text='"'
            type=) text=')'

For example, look at the type=identifier part above. That's apparently how
tree-sitter represents print in its syntax tree. In pygments, we want print to
be a Token.Name.Builtin token (i.e. use color of built-in functions), so we
specify that for type=identifier tokens with text "print" in python.yml:

    token_mapping:
      ...
      identifier:
        ...
        print: Token.Name.Builtin
        ...

This gives you a good overall idea of the file format, but the details are
undocumented. Just ask me (Akuli) if you need help with something related to
these files.

In tree-sitter, each language has a language ID ("python" in this example) that
is used in several places:
- Argument of `scripts/tree-sitter-dump.py`
- tree_sitter_language_id in default_filetypes.toml and filetypes.toml
- Names of .yml files in this directory
- Inside the language binaries (see .github/workflows/tree-sitter-binaries.yml)
