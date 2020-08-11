import os
import pathlib
from typing import Tuple

import docutils.nodes
import docutils.utils

from sphinx.addnodes import desc_annotation, desc_name
from sphinx.domains.python import PyObject, PyXRefRole
from sphinx.util.nodes import split_explicit_title

GITHUB_URL = 'https://github.com/Akuli/porcupine/tree/master/'
PROJECT_ROOT = pathlib.Path(__file__).absolute().parent.parent


# this is mostly copy/pasted from cpython's Doc/tools/extensions/pyspecific.py
def source_role(typ, rawtext, text, lineno, inliner, options={}, content=[]):
    has_t, title, target = split_explicit_title(text)
    title = docutils.utils.unescape(title)
    target = docutils.utils.unescape(target)
    assert (PROJECT_ROOT / target.replace('/', os.sep)).exists(), target
    refnode = docutils.nodes.reference(
        title, title, refuri=(GITHUB_URL + target))
    return [refnode], []


# this is based on the source code of sphinx.domains.python.PyObject, with some
# trial and error
#
# sphinx is a badly documented documentation tool, i hate it
class TkVirtualEvent(PyObject):

    def handle_signature(self, name, signode):
        signode += desc_annotation('virtual event ', 'virtual event ')
        signode += desc_name(f'<<{name}>>', f'<<{name}>>')

        class_name = self.env.ref_context.get('py:class')
        if class_name is None:
            return (name, '')
        return (class_name + '.' + name, '')

    def get_index_text(self, modname: str, name_cls: Tuple[str, str]) -> str:
        event_name = name_cls[0]
        if '.' in event_name:
            class_name, event_name = event_name.rsplit('.', 1)
            text = f'{modname}.{class_name} virtual event'
        else:
            text = 'virtual event'
        return f'<<{event_name}>> ({text})'


class TkVirtualEventXRefRole(PyXRefRole):

    def process_link(self, *args, **kwargs):
        title, target = super().process_link(*args, **kwargs)
        return '<<' + title + '>>', target


def setup(app):
    app.add_role('source', source_role)
    app.add_role_to_domain('py', 'virtevt', TkVirtualEventXRefRole())
    app.add_directive_to_domain('py', 'virtualevent', TkVirtualEvent)
