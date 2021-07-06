from porcupine import utils
from porcupine.plugins.autocomplete import Response


def get_completions(filetab):
    events = []
    utils.bind_with_data(filetab, "<<AutoCompletionResponse>>", events.append, add=False)
    filetab.update()
    filetab.textwidget.event_generate("<Tab>")

    [event] = events
    return [comp.display_text for comp in event.data_class(Response).completions]


def test_pasteId_lastPasteId(filetab):
    filetab.textwidget.insert("1.0", "pasteId lastPasteId lastPasteId lastPasteId past")
    filetab.textwidget.mark_set("insert", "end - 1 char")
    assert get_completions(filetab) == ["pasteId", "lastPasteId"]


latex_code = r"""\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsfonts}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{amsthm}
\usepackage{enumitem}

\theoremstyle{plain}
\newtheorem{theorem}{Theorem}

\begin{document}

\section*{Hello World}

\subsection*{Hello World}

\begin{theorem}
Foo
\end{theorem}

\begin{theorem}
Bar
\end{theorem}

\begin{t

\end{document}
"""


def test_rare_thing_goes_last(filetab):
    filetab.textwidget.insert("end", latex_code)
    lineno = latex_code.split(r"\begin{t" + "\n")[0].count("\n") + 1
    filetab.textwidget.mark_set("insert", f"{lineno}.0 lineend")

    # Theorem first
    assert get_completions(filetab)[0] == "theorem"
    # If we type "the", then we get less matches and it makes sense to check exact
    filetab.textwidget.insert("insert", "he")
    filetab.textwidget.mark_set("insert", "insert lineend")
    assert get_completions(filetab) == ["theorem", "theoremstyle", "newtheorem", "Theorem"]


def test_case_sensitive_match_goes_first(filetab):
    filetab.textwidget.insert("end", "Foo foo f")
    filetab.textwidget.mark_set("insert", "1.0 lineend")
    assert get_completions(filetab) == ["foo", "Foo"]

    filetab.textwidget.delete("1.0", "end")
    filetab.textwidget.insert("end", "Foo foo F")
    filetab.textwidget.mark_set("insert", "1.0 lineend")
    assert get_completions(filetab) == ["Foo", "foo"]
