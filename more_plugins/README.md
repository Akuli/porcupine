# More plugins!

Porcupine is by default a minimal editor that gets the job done, but
it's by no means *limited* to being a minimal editor. If you want to
play tetris in Porcupine you're in the right place!

Installing these plugins is easy:

1. Figure out where to put the plugins by running this on a terminal or
   command prompt:

        porcupine --print-plugindir

2. Copy/paste a plugin file to your plugin directory.
3. Restart Porcupine.
4. Customize the plugin if you don't like it.

| File                  | Description                                               | Dependencies (1)                  |
| --------------------- | --------------------------------------------------------- | --------------------------------- |
| pythonprompt.py (2)   | Simple `>>>` prompt tab.                                  |                                   |
| tetris.py             | Fun tetris game.                                          |                                   |
| ttkthemes.py (3)      | Nicer colors for everything else than the main text area. | `python -m pip install ttkthemes` |

Notes:
1. The plugin doesn't work if you haven't ran this command yet. Replace
   `python` with `py` on Windows and `python3` on other operating systems.
2. This plugin does not work. It should be fixed soon.
3. [Click here](https://github.com/RedFantom/ttkthemes/wiki/Themes) to get
   an idea of what different themes look like.
