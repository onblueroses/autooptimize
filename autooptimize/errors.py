"""Errors that stop a run."""


class Refusal(Exception):
    """The run must stop. The message says why and what to do."""
