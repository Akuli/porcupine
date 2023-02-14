from porcupine.plugins import rightclick_menu, text_google_search

def setup()->None:
    rightclick_menu.add_filetab_command("Search Google for text", text_google_search.google_search)


