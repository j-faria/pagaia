from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

from ._aliases import get_ids

_RELEASE_PREFIX_RE = re.compile(r"^(?P<release>DR\d+)_(?P<rest>.+)$")
_DIGITS_RE = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class TableSpec:
    """Where to look for a given release in a given module."""
    table: str                  # e.g. "gaiadr3.gaia_source"
    id_column: str = "source_id"


@dataclass
class Target:
    """Information about a single Gaia source in one table."""
    release: str
    source_id: int
    table: str
    data: Any # astropy.table.Row
    meta: dict = field(default_factory=dict)

    @property
    def columns(self):
        return self.data.colnames

    def __getitem__(self, key: str):
        return self.data[key]

    def __repr__(self) -> str:
        return f"<Target {self.release}_{self.source_id} ({self.table})>"
    
    def __get_name__(self):
        import inspect
        frame = inspect.currentframe().f_back.f_back   # the caller of summary()
        ns = {**frame.f_globals, **frame.f_locals}
        try:
            return [
                k for k, v in ns.items() 
                if v is self if not k.startswith("_")
            ][0]
        except IndexError:
            return None

    def summary(self, columns=None, var=None):
        DEFAULT_COLUMNS = ["source_id", "radial_velocity"]
        var = var or self.__get_name__() or "self"
        length = max(
            len(col) for col in (columns or DEFAULT_COLUMNS) 
            if col in self.data.colnames
        )
        length += len(var)
        for col in columns or DEFAULT_COLUMNS:
            if col in self.data.colnames:
                item = f"{var}[{col!r}]"
                print(f"{item:<{length+4}} = {self.data[col]}")

@lru_cache(maxsize=256)
def _fetch(table: str, id_column: str, source_id: int):
    # Imported lazily so `import pagaia` stays fast and offline-safe.
    from astroquery.gaia import Gaia

    # source_id is an int (validated by the regex), so no injection risk.
    query = f"SELECT * FROM {table} WHERE {id_column} = {source_id}"
    result = Gaia.launch_job_async(query).get_results()
    if len(result) == 0:
        raise LookupError(f"source_id {source_id} not found in {table}") from None
    return result[0]


def _release_number(release: str) -> int:
    return int(release[2:])


def make_getattr(
    module_name: str,
    specs: dict[str, TableSpec],
    fetch: Callable[[str, str, int], Any] = _fetch,
) -> Callable[[str], Target]:
    """Build a module-level ``__getattr__``.

    Supported names:
      * ``DR3_4472832130942575872``  explicit release + Gaia id
      * ``DR3_Barnards_Star``        explicit release + alias
      * ``Barnards_Star``            alias; uses the newest release (among the
                                     ones this module supports) that has an id
    """

    def __getattr__(name: str) -> Target:
        # Dunder probes (__path__, __wrapped__, ...) must never hit the alias
        # registry, because normalization would strip the underscores.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")

        m = _RELEASE_PREFIX_RE.match(name)
        release, rest = (m["release"], m["rest"]) if m else (None, name)

        if release is not None and release not in specs:
            raise AttributeError(
                f"module {module_name!r} has no data for release {release!r}; "
                f"available: {', '.join(sorted(specs))}"
            )

        if release is not None and _DIGITS_RE.match(rest):
            source_id = int(rest)
        else:
            ids = get_ids(rest)
            if not ids:
                raise AttributeError(f"module {module_name!r} has no attribute {name!r}")
            if release is None:
                # Newest supported release for which the alias has an id.
                candidates = sorted(specs, key=_release_number, reverse=True)
                release = next((r for r in candidates if r in ids), None)
                if release is None:
                    raise AttributeError(
                        f"alias {rest!r} has ids for {', '.join(sorted(ids))} but "
                        f"module {module_name!r} only supports {', '.join(sorted(specs))}"
                    )
            elif release not in ids:
                raise AttributeError(
                    f"alias {rest!r} has no {release} source_id "
                    f"(registered: {', '.join(sorted(ids))})"
                )
            source_id = ids[release]

        spec = specs[release]
        row = fetch(spec.table, spec.id_column, source_id)
        return Target(release, source_id, spec.table, row)

    return __getattr__
