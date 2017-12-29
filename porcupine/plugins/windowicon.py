import porcupine


def setup():
    window = porcupine.get_main_window()
    window.tk.call('wm', 'iconphoto', window, 'img_logo')
