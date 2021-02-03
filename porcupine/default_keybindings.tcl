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
event add "<<AutoReload>>" <Button-1>
event add "<<AutoReload>>" <FocusIn>

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

# tab_order plugin
# Prior = Page Up, Next = Page Down
event add "<<TabOrder:SelectLeft>>" <Control-Prior>
event add "<<TabOrder:SelectRight>>" <Control-Next>
event add "<<TabOrder:MoveLeft>>" <Control-Shift-Prior>
event add "<<TabOrder:MoveRight>>" <Control-Shift-Next>
for {set i 1} {$i <= 9} {incr i} {
    # e.g. Alt+2 to select second tab
    event add "<<TabOrder:SelectTab$i>>" <Alt-Key-$i>
}

# more_plugins/terminal.py
# upper-case T means Ctrl+Shift+T
# I use non-shifted ctrl+t for swapping two characters before cursor while editing
event add "<<Menubar:Tools/Terminal>>" <Control-T>

# more_plugins/pythonprompt.py
event add "<<Menubar:Run/Interactive Python prompt>>" <Control-i>


# Text widgets have confusing control-click behaviour by default. Disabling it
# here makes control-click same as just click.
bind Text <Control-Button-1> {}
