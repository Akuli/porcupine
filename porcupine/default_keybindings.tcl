# This file contains Tcl code that is executed when Porcupine starts.


event add "<<Menubar:File/New File>>" <Control-n>
event add "<<Menubar:File/Open>>" <Control-o>
event add "<<Menubar:File/Save>>" <Control-s>
event add "<<Menubar:File/Save As>>" <Control-S>   ;# uppercase S means you need to hold down shift
event add "<<Menubar:File/Close>>" <Control-w>
event add "<<Menubar:File/Quit>>" <Control-q>
event add "<<Menubar:View/Bigger Font>>" <Control-plus>
event add "<<Menubar:View/Smaller Font>>" <Control-minus>
event add "<<Menubar:View/Reset Font Size>>" <Control-0>

# reload plugin
event add "<<Menubar:File/Reload>>" <Control-r>

# run plugin
event add "<<Menubar:Run/Compile>>" <F4>
event add "<<Menubar:Run/Run>>" <F5>
event add "<<Menubar:Run/Compile and Run>>" <F6>
event add "<<Menubar:Run/Lint>>" <F7>

# gotoline plugin
event add "<<Menubar:Edit/Go to Line>>" <Control-l>

# fullscreen plugin
event add "<<Menubar:View/Full Screen>>" <F11>

# find plugin
event add "<<Menubar:Edit/Find and Replace>>" <Control-f>

# fold plugin
event add "<<Menubar:Edit/Fold>>" <Alt-f>

# more_plugins/terminal.py
# upper-case T means Ctrl+Shift+T
# I use non-shifted ctrl+t for swapping two characters before cursor while editing
event add "<<Menubar:Tools/Terminal>>" <Control-T>

# more_plugins/pythonprompt.py
event add "<<Menubar:Run/Interactive Python prompt>>" <Control-i>


# Text widgets have confusing control-click behaviour by default. Disabling it
# here makes control-click same as just click.
bind Text <Control-Button-1> {}
