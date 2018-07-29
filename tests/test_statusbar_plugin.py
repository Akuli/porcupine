from porcupine import tabs


# it must work with all kinds of tabs, not just FileTabs
class AsdTab(tabs.Tab):
    pass


def test_that_it_doesnt_crash_with_different_numbers_of_tab_separated_parts(
        tabmanager):
    asd = AsdTab(tabmanager)
    tabmanager.add_tab(asd)

    events = []
    asd.bind('<<StatusChanged>>', events.append, add=True)

    asd.status = "a"
    asd.update()
    events.pop()

    asd.status = "a\tb\tc"
    asd.update()
    events.pop()

    asd.status = "a"
    asd.update()
    events.pop()

    tabmanager.close_tab(asd)
    assert not events
