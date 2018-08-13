import porcupine
from .client import Client


def on_new_tab(event):
    tab = event.data_widget

    if isinstance(tab, porcupine.tabs.FileTab):
        Client(tab)


def setup():
    tab_manager = porcupine.get_tab_manager()
    porcupine.utils.bind_with_data(
        tab_manager, "<<NewTab>>", on_new_tab, add=True
    )
