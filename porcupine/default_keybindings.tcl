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

# tab_closing plugin
event add "<<TabClosing:XButtonClickClose>>" <Button-1>
if {[tk windowingsystem] == "aqua"} {
    # right-click is Button-2, no wheel-click (afaik)
    event add "<<TabClosing:ShowMenu>>" <Button-2>
} else {
    # right-click is Button-3, wheel-click is Button-2
    event add "<<TabClosing:ShowMenu>>" <Button-3>
    event add "<<TabClosing:HeaderClickClose>>" <Button-2>
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

# more_plugins/tetris.py
event add "<<Tetris:NewGame>>" <F2>
event add "<<Tetris:Pause>>" <p> <P>


# Text widgets have confusing control-click behaviour by default. Disabling it
# here makes control-click same as just click.
bind Text <$contmand-Button-1> {}

# Also, by default, Control+Slash selects all and Control+A goes to beginning.
event delete "<<LineStart>>" <$contmand-a>
event add "<<SelectAll>>" <$contmand-a>

bind Text <$contmand-Delete> {
    try {%W delete sel.first sel.last} on error {} {
        set start [%W index insert]
        event generate %W <<NextWord>>
        %W delete $start insert
    }
}

bind Text <BackSpace> {
    set beforecursor [%W get {insert linestart} insert]
    if {
        [string length [bind %W <<Dedent>>]] != 0 &&
        [string length $beforecursor] != 0 &&
        [string is space $beforecursor]
    } {
        event generate %W <<Dedent>>
    } else {
        %W delete {insert - 1 char}
    }
}

bind Text <$contmand-BackSpace> {
    try {%W delete sel.first sel.last} on error {} {
        set end [%W index insert]
        event generate %W <<PrevWord>>
        %W delete insert $end
    }
}

bind Text <Shift-$contmand-Delete> {
    try {%W delete sel.first sel.last} on error {} {
        if {[%W index insert] == [%W index {insert lineend}]} {
            %W delete insert
        } else {
            %W delete insert {insert lineend}
        }
    }
}

bind Text <Shift-$contmand-BackSpace> {
    try {%W delete sel.first sel.last} on error {} {
        if {[%W index insert] == [%W index {insert linestart}]} {
            %W delete {insert - 1 char}
        } else {
            %W delete {insert linestart} insert
        }
    }
}

# When pasting, delete what was selected
# Here + adds to end of existing binding
bind Text <<Paste>> {+
    catch {%W delete sel.first sel.last}
}
