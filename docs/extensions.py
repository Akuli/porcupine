from typing import Tuple

import docutils.nodes
import docutils.utils

from sphinx.addnodes import desc_annotation, desc_name
from sphinx.domains.python import PyObject, PyXRefRole
from sphinx.util.nodes import split_explicit_title

SOURCE_URI = 'https://github.com/Akuli/porcupine/tree/master/'


# this is mostly copy/pasted from cpython's Doc/tools/extensions/pyspecific.py
def source_role(typ, rawtext, text, lineno, inliner, options={}, content=[]):
    has_t, title, target = split_explicit_title(text)
    title = docutils.utils.unescape(title)
    target = docutils.utils.unescape(target)
    refnode = docutils.nodes.reference(
        title, title, refuri=SOURCE_URI + target)
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
        return (class_name + '.' + name, '')

    def get_index_text(self, modname: str, name_cls: Tuple[str, str]) -> str:
        class_name, event_name = name_cls[0].rsplit('.', 1)
        return f'<<{event_name}>> ({modname}.{class_name} virtual event)'


class TkVirtualEventXRefRole(PyXRefRole):

    def process_link(self, *args, **kwargs):
        title, target = super().process_link(*args, **kwargs)
        return '<<' + title + '>>', target


def setup(app):
    app.add_role('source', source_role)
    app.add_role_to_domain('py', 'virtevt', TkVirtualEventXRefRole())
    app.add_directive_to_domain('py', 'virtualevent', TkVirtualEvent)
