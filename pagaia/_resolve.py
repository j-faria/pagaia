from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

_NAME_RE = re.compile(r"^(?P<release>DR\d+)_(?P<source_id>\d+)$")


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


def make_getattr(
    module_name: str,
    specs: dict[str, TableSpec],
    fetch: Callable[[str, str, int], Any] = _fetch,
) -> Callable[[str], Target]:
    """Build a module-level ``__getattr__`` for names like ``DR3_123456789``"""

    def __getattr__(name: str) -> Target:
        m = _NAME_RE.match(name)
        if m is None:
            # Must be AttributeError so that `from pagaia import nss`
            # (submodule import), hasattr(), copy/pickle probes, etc. still work.
            raise AttributeError(f"module {module_name!r} has no attribute {name!r}")

        release, source_id = m["release"], int(m["source_id"])
        try:
            spec = specs[release]
        except KeyError:
            raise AttributeError(
                f"module {module_name!r} has no data for release {release!r}; "
                f"available: {', '.join(sorted(specs))}"
            ) from None

        row = fetch(spec.table, spec.id_column, source_id)
        return Target(release, source_id, spec.table, row)

    return __getattr__
