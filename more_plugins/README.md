# More plugins!

Installing these plugins is easy:

1. Figure out where to put the plugins by opening *About Porcupine* from the *Help* menu.
   You should see your plugin directory at the end of the text.
2. Copy/paste a plugin file to your plugin directory.
3. Restart Porcupine.
4. Customize the plugin if you don't like it.

| File              | Description                                               | Notes |
| ----------------- | --------------------------------------------------------- | ----- |
| pythonprompt.py   | Simple `>>>` prompt tab.                                  |       |
| terminal.py       | Run a terminal inside Porcupine as a tab.                 | 1.    |

Notes:

1.  This plugin is shit. Don't waste your time with it.

    You need to install xterm if you want to use this plugin. That's easy if
    you are using Linux. For example, if you're using a Debian-based
    distribution (e.g. Mint or Ubuntu), run this command:

        sudo apt install xterm

    As far as I know, xterm can be somehow installed on Mac OSX but not on
    Windows. Even if you manage to install xterm on these operating systems
    the plugin will refuse to work, and if you remove the warning it probably
    won't work anyway.

    However, if you manage to get xterm or some other terminal to work inside a
    tkinter program on Windows or OSX I'd be happy to update this plugin!
