from porcupine import tabs


def test_rstrip(tabmanager):
    tab = tabs.FileTab(tabmanager)
    tabmanager.add_tab(tab)

    tab.textwidget.insert('end', 'print("hello")  ')
    tab.update()
    tab.event_generate('<Return>')
    tab.update()
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'print("hello")\n'

    tabmanager.close_tab(tab)
