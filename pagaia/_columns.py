"""Attribute-style access to the columns of a Target's data row."""
from __future__ import annotations

import difflib


class ColumnAccessor:
    """``target.val.parallax`` -> ``target.data["parallax"]``.

    With ``suffix="_error"`` the same attribute gives the uncertainty column,
    so ``target.err.parallax`` -> ``target.data["parallax_error"]``.
    Values are returned exactly as stored in the table (masked entries stay masked).
    """

    __slots__ = ("_target", "_suffix")

    def __init__(self, target, suffix: str = ""):
        self._target = target
        self._suffix = suffix

    def _available(self) -> list[str]:
        """Attribute names that currently work, e.g. for tab completion."""
        names = list(self._target.data.colnames)
        n = len(self._suffix)
        if not n:
            return names
        return [c[:-n] for c in names if c.endswith(self._suffix) and len(c) > n]

    def __getattr__(self, name: str):
        # Private/dunder probes (__wrapped__, _ipython_*, ...) are never columns.
        if name.startswith("_"):
            raise AttributeError(name)
        data = self._target.data
        column = name + self._suffix
        if column not in data.colnames:
            raise AttributeError(self._message(name, column))
        return data[column]

    def _message(self, name: str, column: str) -> str:
        if self._suffix and name in self._target.data.colnames:
            return f"{self._target!r} has column {name!r} but no uncertainty column {column!r}"
        kind = "uncertainty" if self._suffix else "value"
        msg = f"{self._target!r} has no {kind} column {column!r}"
        close = difflib.get_close_matches(name, self._available(), n=3)
        if close:
            msg += f"; did you mean {', '.join(close)}?"
        return msg

    def __contains__(self, name: str) -> bool:
        return name in self._available()

    def __dir__(self) -> list[str]:
        return sorted(self._available())

    def __repr__(self) -> str:
        label = "err" if self._suffix else "val"
        return f"<{label} of {self._target!r}: {len(self._available())} columns>"
