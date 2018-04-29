import re

import tkinter.font as tkfont
from porcupine import settings, textwidget
from . import backend

# (he)xchat supports these
_BOLD = '\x02'
_UNDERLINE = '\x1f'
_COLOR = '\x03'   # followed by N or N,M where N and M are 1 or 2 digit numbers
_BACK_TO_NORMAL = '\x0f'


# https://www.mirc.com/colors.html
_MIRC_COLORS = {
    0: '#ffffff',
    1: '#000000',
    2: '#00007f',
    3: '#009300',
    4: '#ff0000',
    5: '#7f0000',
    6: '#9c009c',
    7: '#fc7f00',
    8: '#ffff00',
    9: '#00fc00',
    10: '#009393',
    11: '#00ffff',
    12: '#0000fc',
    13: '#ff00ff',
    14: '#7f7f7f',
    15: '#d2d2d2',
}

# no yellow, white, black or grays
# yellow doesn't look very good on a light background
_NICK_COLORS = sorted(_MIRC_COLORS.keys() - {8, 0, 1, 14, 15})


# yields (text_substring, fg, bg, bold, underline) tuples
# fg and bg are mirc color numbers or None for default color
# bold and underline are booleans
def _parse_styles(text):
    # ^ and $ are included to make the next step easier
    style_regex = r'\x02|\x1f|\x03\d{1,2}(?:,\d{1,2})?|\x0f'

    # parts contains matched parts of the regex followed by texts
    # between those matched parts
    parts = [''] + re.split('(' + style_regex + ')', text)
    assert len(parts) % 2 == 0

    fg = None
    bg = None
    bold = False
    underline = False

    for style_spec, substring in zip(parts[0::2], parts[1::2]):
        if not style_spec:
            # beginning of text
            pass
        elif style_spec == _BOLD:
            bold = True
        elif style_spec == _UNDERLINE:
            underline = True
        elif style_spec.startswith(_COLOR):
            # _COLOR == '\x03'
            fg_spec, bg_spec = re.fullmatch(r'\x03(\d{1,2})(,\d{1,2})?',
                                            style_spec).groups()

            # https://www.mirc.com/colors.html talks about big color numbers:
            # "The way these colors are interpreted varies from client to
            # client. Some map the numbers back to 0 to 15, others interpret
            # numbers larger than 15 as the default text color."
            #
            # i'm not sure how exactly the colors should be mapped to the
            # supported range, so i'll just use the default color thing
            fg = int(fg_spec)
            if fg not in _MIRC_COLORS:
                fg = None

            if bg_spec is not None:
                bg = int(bg_spec.lstrip(','))
                if bg not in _MIRC_COLORS:
                    bg = None
        elif style_spec == _BACK_TO_NORMAL:
            fg = bg = None
            bold = underline = False
        else:
            raise ValueError("unexpected regex match: " + repr(style_spec))

        if substring:
            yield (substring, fg, bg, bold, underline)


# python's string hashes use a randomization by default, so hash('a')
# returns a different value after restarting python
def _nick_hash(nick):
    # http://www.cse.yorku.ca/~oz/hash.html
    hash_ = 5381
    for c in nick:
        hash_ = hash_*33 + ord(c)
    return hash_


def color_nick(nick):
    color = _NICK_COLORS[_nick_hash(nick) % len(_NICK_COLORS)]
    return _BOLD + _COLOR + str(color) + nick + _BACK_TO_NORMAL


class ColoredText(textwidget.ThemedText):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # tags support underlining, but no bolding (lol)
        self._bold_font = tkfont.Font(weight='bold')
        settings.get_section('General').connect(
            'font_family', self._on_font_changed, run_now=False)
        settings.get_section('General').connect(
            'font_size', self._on_font_changed, run_now=False)
        self._on_font_changed()

        def on_destroy(event):
            settings.get_section('General').disconnect(
                'font_family', self._on_font_changed)
            settings.get_section('General').disconnect(
                'font_size', self._on_font_changed)

        self.bind('<Destroy>', on_destroy, add=True)

        # these never change
        self.tag_configure('underline', underline=True)
        self.tag_configure('bold', font=self._bold_font)
        for number, hexcolor in _MIRC_COLORS.items():
            self.tag_configure('foreground-%d' % number, foreground=hexcolor)
            self.tag_configure('background-%d' % number, background=hexcolor)

    def _on_font_changed(self, junk=None):
        # when the font family or size changes, self['font'] also changes
        # see porcupine.textwiddet.ThemedText
        font_updates = tkfont.Font(name=self['font'], exists=True).actual()
        del font_updates['weight']     # ignore boldness

        # fonts don't have a dict-style update() method :(
        for key, value in font_updates.items():
            self._bold_font[key] = value

    def colored_insert(self, index, text):
        """Like insert(), but interprets special color sequences correctly."""
        print("colored_insert is runninggg", repr(text))
        for substring, fg, bg, bold, underline in _parse_styles(text):
            print('  ', [substring, fg, bg, bold, underline])
            tags = []
            if fg is not None:
                tags.append('foreground-%d' % fg)
            if bg is not None:
                tags.append('background-%d' % fg)
            if bold:
                tags.append('bold')
            if underline:
                tags.append('underline')
            self.insert(index, substring, tags)

    def nicky_insert(self, index, text, known_nicks):
        """Like colored_insert(), but colors nicks in known_nicks."""
        result_chars = list(text)
        matches = [match for match in re.finditer(backend.NICK_REGEX, text)
                   if match.group(0) in known_nicks]

        # do this backwards to prevent messing up indexes... you know
        for match in reversed(matches):
            nick = match.group(0)
            if nick in known_nicks:
                result_chars[match.start():match.end()] = color_nick(nick)

        self.colored_insert(index, ''.join(result_chars))
