Files in this directory define how to map a tree-sitter syntax tree into Pygments
token types. We need to know the corresponding Pygments token types to use
Pygments color themes, and we use them with tree-sitter for a couple reasons:
- The pygments highlighter uses them already. We want the user to only select
  one color theme.
- There are many pygments themes to choose from.
- It is relatively easy to make new pygments themes. I am currently using a
  Pygments theme named "zaab" created by a friend of mine, available here:
  https://github.com/8banana/banana-themes

In tree-sitter, each programming language has a name ("python" in this example)
that is used in several places:
- Argument of `scripts/tree-sitter-dump.py` (see below)
- tree_sitter_language_name in default_filetypes.toml and filetypes.toml
- Names of .yml files in this directory
- Inside the binaries from https://github.com/grantjenks/py-tree-sitter-languages/

Porcupine comes with a script for exploring tree-syntax syntax trees:

    $ cat hello.py
    print('hello')

    $ python3 scripts/tree-sitter-dump.py python hello.py
    type=module text="print('hello')"
      type=expression_statement text="print('hello')"
        type=call text="print('hello')"
          field 'function': type=identifier text='print'
          field 'arguments': type=argument_list text="('hello')"
            type=( text='('
            type=string text="'hello'"
              type=" text="'"
              type=" text="'"
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

You can also explore how queries work by passing in --query. For more about
queries, see tree-sitter's documentation:
https://tree-sitter.github.io/tree-sitter/using-parsers#pattern-matching-with-queries

    $ python3 scripts/tree-sitter-dump.py python hello.py --query '(call arguments: (argument_list) @asdasd)'
    type=module text="print('hello')"
      type=expression_statement text="print('hello')"
        type=call text="print('hello')"
          field 'function': type=identifier text='print'
          field 'arguments': type=argument_list text="('hello')"
            type=( text='('
            type=string text="'hello'"
              type=" text="'"
              type=" text="'"
            type=) text=')'

    Running query on the tree: (call arguments: (argument_list) @asdasd)
      @asdasd matched: type=argument_list text="('hello')"

The script only prints the `@` captures. In the .yml files, you can use:
- `@Token.Foo.Bar` to highlight the captured node with `Token.Foo.Bar`.
- `@recurse` to clear already added highlighting for the captured node and then
  recursively visit the captured node.

One caveat with queries is that when tree-sitter runs the query, it looks for
matches recursively. For example, there's a query in python.yml that handles
f-strings. If you put an f-string inside an f-string, the query for the outer
f-string will also find the inner f-string.

This hopefully gives you a good overall idea of the file format, but many
details are undocumented. Just ask me (Akuli) if you need help with something
related to these files.
