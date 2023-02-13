from porcupine import get_main_window
from porcupine.menubar import get_menu

import tkinter 

def show_menu(event) -> None:

    ft = tkinter.Menu(tearoff=0)
    
    # Other menu items can be added here
    ft.add_cascade(label="Edit", menu=get_menu("Edit"), underline=0)
    ft.add_separator()
    ft.add_cascade(label="Tools", menu=get_menu("Tools"), underline=0)

    ft.tk_popup(event.x_root, event.y_root)
    ft.bind("<Unmap>", (lambda event: ft.after_idle(ft.update)), add=True)

    

def setup()-> None:

    w = get_main_window()
    w.bind("<<RightClick>>", show_menu)
    
    
    


        