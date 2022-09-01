# This file contains Tcl code that is executed when Porcupine starts. It's
# meant to be used for custom key bindings. See Porcupine's default keybinding
# file for examples of what you can put here:
#
#    https://github.com/Akuli/porcupine/blob/master/porcupine/default_keybindings.tcl

event delete "<<Menubar:File/New File>>" <Control-n>
event add "<<Menubar:File/New File>>" <Control-Alt-n>

event delete "<<Menubar:Edit/Find and Replace>>" <Control-f>
event add "<<Menubar:Edit/Find and Replace>>" <Control-Alt-f>

event delete "<<Menubar:Edit/Sort Lines>>" <Alt-s>
event delete "<<Menubar:Edit/Fold>>" <Alt-f>
event delete "<<Menubar:View/Pop Tab>>" <Control-P>

event add <<PrevWord>> <Alt-b>
event add <<NextWord>> <Alt-f>
event add <<SelectPrevWord>> <Alt-B>
event add <<SelectNextWord>> <Alt-F>

event add <<PrevPara>> <Alt-p>
event add <<NextPara>> <Alt-n>
event add <<SelectPrevPara>> <Alt-P>
event add <<SelectNextPara>> <Alt-N>

bind Text <Control-m> {event generate %W <Return>}

bind Text <Alt-BackSpace> { set end   [%W index insert]; event generate %W <<PrevWord>>; %W delete insert $end; break }
bind Text <Alt-h> { set end   [%W index insert]; event generate %W <<PrevWord>>; %W delete insert $end; break }
bind Text <Alt-d> { set start [%W index insert]; event generate %W <<NextWord>>; %W delete $start insert; break }

event delete "<<Menubar:Help>>" <Alt-h>

event delete <<PrevLine>> <Up>
event delete <<NextLine>> <Down>
event delete <<PrevChar>> <Left>
event delete <<NextChar>> <Right>
event delete <<PrevPara>> <Control-Up>
event delete <<NextPara>> <Control-Down>
event delete <<PrevWord>> <Control-Left>
event delete <<NextWord>> <Control-Right>
event delete <<SelectPrevLine>> <Shift-Up>
event delete <<SelectNextLine>> <Shift-Down>
event delete <<SelectPrevChar>> <Shift-Left>
event delete <<SelectNextChar>> <Shift-Right>
event delete <<SelectPrevPara>> <Shift-Control-Up>
event delete <<SelectNextPara>> <Shift-Control-Down>
event delete <<SelectPrevWord>> <Shift-Control-Left>
event delete <<SelectNextWord>> <Shift-Control-Right>
