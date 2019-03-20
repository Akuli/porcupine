from porcupine import get_main_window, settings


config = settings.get_section('Window Size and Location')
config.add_option('width', 650, reset=False)
config.add_option('height', 600, reset=False)
config.add_option('x', None, reset=False)
config.add_option('y', None, reset=False)


def save_geometry():
    namedtuple = get_main_window().geometry()
    config['width'], config['height'], config['x'], config['y'] = namedtuple


def setup():
    get_main_window().geometry(
        config['width'], config['height'], config['x'], config['y'])
    get_main_window().bind('<<PorcupineQuit>>', save_geometry)
