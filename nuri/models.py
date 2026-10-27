from dataclasses import dataclass


class UserError(Exception):
    """A fixed, safe message suitable for the requesting user."""


@dataclass(frozen=True)
class Expression:
    phrase: str
    meaning: str


@dataclass(frozen=True)
class Result:
    source: str
    mode: str
    translation: str = ""
    expressions: tuple[Expression, ...] = ()
    corrected: str = ""
    feedback: str = ""
