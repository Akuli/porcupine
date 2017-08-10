import docutils.nodes
import docutils.utils

from sphinx.addnodes import desc_annotation, desc_name
from sphinx.domains.python import PyClassmember, PyXRefRole
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


# this is based on the source code of sphinx.directives.ObjectDescription
# and PyClassmember
class TkVirtualEvent(PyClassmember):

    def get_signatures(self):
        # e.g. ['Thing'], the return value is a list of sig arguments
        # that are passed to handle_signature() one by one
        return self.arguments

    def handle_signature(self, sig, signode):
        assert (not sig.startswith('<<')) and (not sig.endswith('>>'))
        modname = self.options.get(
            'module', self.env.ref_context.get('py:module'))
        classname = self.env.ref_context.get('py:class')
        fullname = classname + '.' + sig

        signode['module'] = modname
        signode['class'] = classname
        signode['fullname'] = fullname

        signode += desc_annotation('virtual event ', 'virtual event ')
        signode += desc_name('<<' + sig + '>>', '<<' + sig + '>>')

        return fullname, ''


class TkVirtualEventXRefRole(PyXRefRole):

    def process_link(self, *args, **kwargs):
        title, target = super().process_link(*args, **kwargs)
        return '<<' + title + '>>', target


def setup(app):
    app.add_role('source', source_role)
    app.add_role_to_domain('py', 'virtevt', TkVirtualEventXRefRole())
    app.add_directive_to_domain('py', 'virtualevent', TkVirtualEvent)
