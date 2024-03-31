from tkinter import messagebox
from porcupine import menubar

def hello():
    messagebox.showinfo("Hello", "Hello World!")

def setup():
    menubar.get_menu("Run/Greetings").add_command(label="Hello World", command=hello)
