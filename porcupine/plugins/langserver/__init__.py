import typing as t

import porcupine

from .client import Client


def on_new_tab(event) -> None:
    tab = event.data_widget

    if isinstance(tab, porcupine.tabs.FileTab):
        Client(tab)


def setup() -> None:
    tab_manager = porcupine.get_tab_manager()
    porcupine.utils.bind_with_data(
        tab_manager, "<<NewTab>>", on_new_tab, add=True
    )
