from porcupine import get_main_window, settings


config = settings.get_section('General')
config.add_option('default_geometry', '650x500', reset=False)


def save_geometry(event):
    config['default_geometry'] = event.widget.geometry()


def setup():
    get_main_window().geometry(config['default_geometry'])
    get_main_window().bind('<<PorcupineQuit>>', save_geometry, add=True)
