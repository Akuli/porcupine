import docutils.nodes
import docutils.utils

from sphinx.addnodes import desc_annotation, desc_name
from sphinx.domains.python import PyClassmember
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
# TODO: implement :virtualevent:`SomeClass.<<Lel>>` ???
class TkVirtualEvent(PyClassmember):

    def get_signatures(self):
        # e.g. ['<<Thing>>'], the return value is a list of sig arguments
        # that are passed to handle_signature() one by one
        return self.arguments

    def handle_signature(self, sig, signode):
        # determine module and class name (if applicable), as well as full name
        modname = self.options.get(
            'module', self.env.ref_context.get('py:module'))
        classname = self.env.ref_context.get('py:class')
        assert modname and classname

        # mod.Class.<<Event>> is kinda weird, but not too bad imo
        fullname = modname + '.' + classname + '.' + sig
        signode['module'] = modname
        signode['class'] = classname
        signode['fullname'] = fullname

        signode += desc_annotation('virtual event ', 'virtual event ')
        signode += desc_name(sig, sig)

        return fullname, classname


def setup(app):
    app.add_role('source', source_role)
    app.add_directive_to_domain('py', 'virtualevent', TkVirtualEvent)
