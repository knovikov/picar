"""Печатает значения геймпада, чтобы настроить 8BitDo.

Запуск на Raspberry Pi:

    python3 -m tests.test_controller_print
"""

from kidbot.core.controller import print_controller_events


if __name__ == "__main__":
    print_controller_events()
