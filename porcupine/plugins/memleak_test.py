import gc
import os

import psutil

from porcupine import get_tab_manager, tabs
from porcupine.menubar import get_menu

last_value = None


def format_amount(amount, show_plus=False):
    k = 1000
    M = 1000000
    G = 1000000000
    if amount == 0:
        return "+0B" if show_plus else "0B"

    if amount < 0:
        prefix = "-"
        amount = abs(amount)
    elif amount > 0:
        prefix = "+" if show_plus else ""
    else:
        return "0B"

    if amount < k:
        return f"{prefix}{amount}B"
    if amount < M:
        return f"{prefix}{amount / k:.2f}kB"
    if amount < G:
        return f"{prefix}{amount / M:.2f}MB"
    return f"{prefix}{amount / G:.2f}GB"


running = False


def test_mem_leaks_1(n):
    global last_value

    gc.collect()

    new_value = psutil.Process(os.getpid()).memory_info().rss
    if last_value is not None:
        diff = new_value - last_value
        print(f"{format_amount(new_value)} ({format_amount(diff, show_plus=True)})".ljust(23) + "*"*round(diff // 100_000))

    last_value = new_value

    if n > 0 and running:
        for lel in range(10):
            get_tab_manager().add_tab(tabs.FileTab(get_tab_manager()))
        get_tab_manager().after(1000, test_mem_leaks_2, n-1)


def test_mem_leaks_2(n):
    for tab in get_tab_manager().tabs():
        get_tab_manager().close_tab(tab)
    get_tab_manager().after_idle(test_mem_leaks_1, n)


def test_mem_leaks():
    global running
    if not running:
        running = True
        test_mem_leaks_1(100)


def stop_test_mem_leaks():
    global running
    running = False


def setup():
    get_menu("TEMP").add_command(label="START Test Memory Leaks", command=test_mem_leaks)
    get_menu("TEMP").add_command(label="STOP Test Memory Leaks", command=stop_test_mem_leaks)
