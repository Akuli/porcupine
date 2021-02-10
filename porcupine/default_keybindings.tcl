# This file contains Tcl code that is executed when Porcupine starts.

# Use Command on mac, Control on other systems
if {[tk windowingsystem] == "aqua"} {
    set contmand Command
} else {
    set contmand Control
}

event add "<<Menubar:File/New File>>" <$contmand-n>
event add "<<Menubar:File/Open>>" <$contmand-o>
event add "<<Menubar:File/Save>>" <$contmand-s>
event add "<<Menubar:File/Save As>>" <$contmand-S>   ;# uppercase S means you need to hold down shift
event add "<<Menubar:File/Close>>" <$contmand-w>
event add "<<Menubar:File/Quit>>" <$contmand-q>
event add "<<Menubar:View/Bigger Font>>" <$contmand-plus>
event add "<<Menubar:View/Smaller Font>>" <$contmand-minus>
event add "<<Menubar:View/Reset Font Size>>" <$contmand-0>

# reload plugin
event add "<<AutoReload>>" <Button-1>
event add "<<AutoReload>>" <FocusIn>

# run plugin
event add "<<Menubar:Run/Compile>>" <F4>
event add "<<Menubar:Run/Run>>" <F5>
event add "<<Menubar:Run/Compile and Run>>" <F6>
event add "<<Menubar:Run/Lint>>" <F7>

# gotoline plugin
event add "<<Menubar:Edit/Go to Line>>" <$contmand-l>

# fullscreen plugin
event add "<<Menubar:View/Full Screen>>" <F11>

# find plugin
event add "<<Menubar:Edit/Find and Replace>>" <$contmand-f>

# fold plugin
event add "<<Menubar:Edit/Fold>>" <Alt-f>

# urls plugin
event add "<<Urls:OpenWithMouse>>" <$contmand-Button-1>
event add "<<Urls:OpenWithKeyboard>>" <$contmand-Return>

# tab_order plugin
# Prior = Page Up, Next = Page Down
event add "<<TabOrder:SelectLeft>>" <$contmand-Prior>
event add "<<TabOrder:SelectRight>>" <$contmand-Next>
event add "<<TabOrder:MoveLeft>>" <$contmand-Shift-Prior>
event add "<<TabOrder:MoveRight>>" <$contmand-Shift-Next>
for {set i 1} {$i <= 9} {incr i} {
    # e.g. Alt+2 to select second tab
    event add "<<TabOrder:SelectTab$i>>" <Alt-Key-$i>
}

# xbutton plugin
event add "<<XButton:CloseWhenCloseButtonClicked>>" <Button-1>
if {[tk windowingsystem] != "aqua"} {   # doesn't make sense on mac, see #303
    event add "<<XButton:CloseWhenTabClicked>>" <Button-2>
}

# more_plugins/terminal.py
# upper-case T means Ctrl+Shift+T or Command+Shift+T
# I use non-shifted ctrl+t for swapping two characters before cursor while editing
event add "<<Menubar:Tools/Terminal>>" <$contmand-T>

# more_plugins/pythonprompt.py
event add "<<Menubar:Run/Interactive Python prompt>>" <$contmand-i>
event add "<<PythonPrompt:KeyboardInterrupt>>" <$contmand-c>
event add "<<PythonPrompt:Copy>>" <$contmand-C>
# FIXME: conflicts with gotoline plugin
#event add "<<PythonPrompt:Clear>>" <$contmand-l>
event add "<<PythonPrompt:Clear>>" <$contmand-L>
event add "<<PythonPrompt:SendEOF>>" <$contmand-d> <$contmand-D>


# Text widgets have confusing control-click behaviour by default. Disabling it
# here makes control-click same as just click.
bind Text <$contmand-Button-1> {}

# Also, by default, Control+Slash selects all and Control+A goes to beginning.
event delete "<<LineStart>>" <$contmand-a>
event add "<<SelectAll>>" <$contmand-a>
