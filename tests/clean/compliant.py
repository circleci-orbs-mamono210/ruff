"""Fixture that Ruff accepts with the default rule set and the formatter."""


def build_greeting(name, punctuation="!"):
    """Return a greeting built from the name and the punctuation."""
    return f"Hello, {name}{punctuation}"


GREETINGS = [build_greeting("world"), build_greeting("ruff", "?")]
