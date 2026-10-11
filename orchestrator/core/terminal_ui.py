"""Minimal professional terminal UI (black/silver/white, subtle gold accent). No heavy colors."""

from __future__ import annotations


GOLD = "\033[33m"
SILVER = "\033[37m"
WHITE = "\033[97m"
DIM = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _line(char: str = "=", n: int = 40) -> str:
    return char * n


def header(title: str = "AI CODING SUPERVISOR") -> str:
    return f"{WHITE}{BOLD}{_line()}\n{title}\n{_line()}{RESET}"


def section(title: str) -> str:
    return f"\n{GOLD}{BOLD}## {title}{RESET}"


def kv(k: str, v: str) -> str:
    return f"{DIM}{k}:{RESET} {SILVER}{v}{RESET}"


def step(ok: bool, label: str) -> str:
    mark = "[x]" if ok else "[ ]"
    color = SILVER if ok else DIM
    return f"{color}{mark} {label}{RESET}"


def result_block(status: str) -> str:
    return f"\n{GOLD}{BOLD}## RESULT{RESET}\n{kv('STATUS', status)}"
