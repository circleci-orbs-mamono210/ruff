"""Fixture whose only violation is a reference to an undefined name."""


def call_missing():
    """Call a name that was never defined."""
    return missing_helper()
