"""Resolve arbitrary object names to Gaia source_ids via SIMBAD."""
from __future__ import annotations

import os
import re
import time
import warnings

from ._aliases import normalize

_GAIA_ID_RE = re.compile(r"^Gaia\s+(DR\d+)\s+(\d+)$")
_RETRY_AFTER = 300.0  # seconds to leave a failing server alone
# Used only if astroquery does not tell us which mirrors it knows about:
# the main server at CDS (Strasbourg) first, then the CfA (Harvard) mirror.
_DEFAULT_SERVERS = ("simbad.cds.unistra.fr", "simbad.harvard.edu")

_cache: dict[str, dict[str, int]] = {}  # every answer SIMBAD gave this session
_down_until: dict[str, float] = {}      # server -> time before which we skip it


class SimbadUnavailable(RuntimeError):
    """SIMBAD could not be reached or returned an error."""


def _servers() -> list[str]:
    """SIMBAD servers to try, main one first (as listed by astroquery)."""
    try:
        from astroquery.simbad import conf

        servers = list(conf.servers_list)
    except Exception:
        servers = []
    return servers or list(_DEFAULT_SERVERS)


def lookup_gaia_ids(
    name: str, server: str | None = None, timeout: float = 20.0
) -> dict[str, int]:
    """Query one SIMBAD server and return ``{release: source_id}``; ``{}`` if unknown.

    Raises :class:`SimbadUnavailable` if the server cannot be used.
    """
    try:
        from astroquery.simbad import Simbad

        client = type(Simbad)()  # private instance: don't touch the user's settings
        if server is not None:
            client.server = server  # needs astroquery >= 0.4.8
        client.TIMEOUT = timeout
        table = client.query_objectids(name)
    except Exception as exc:  # network errors, timeouts, TAP errors, ...
        if type(exc).__name__ == "EmptyResponseError":  # some versions: unknown name
            return {}
        raise SimbadUnavailable(f"{type(exc).__name__}: {exc}") from exc

    if table is None or len(table) == 0:
        return {}

    column = next((c for c in table.colnames if c.lower() == "id"), table.colnames[0])
    found: dict[str, int] = {}
    for value in table[column]:
        text = value.decode() if isinstance(value, bytes) else str(value)
        m = _GAIA_ID_RE.match(" ".join(text.split()))
        if m:
            found[m[1]] = int(m[2])
    return found


def resolve(name: str) -> dict[str, int]:
    """Cached, failure-tolerant wrapper around :func:`lookup_gaia_ids`. Never raises.

    Tries the main SIMBAD server first and falls back to the mirror(s) if it
    fails (e.g. during maintenance). A server that failed is skipped for a few
    minutes so that every lookup does not wait for a timeout.

    ``name`` may use underscores for spaces (``HD_189733``). Set
    ``PAGAIA_SIMBAD=0`` to disable SIMBAD lookups entirely.
    """
    if os.environ.get("PAGAIA_SIMBAD", "1").lower() in {"0", "false", "no", "off"}:
        return {}

    key = normalize(name)
    if key in _cache:
        return dict(_cache[key])

    query = name.replace("_", " ")
    for server in _servers():
        if time.monotonic() < _down_until.get(server, 0.0):
            continue
        try:
            found = lookup_gaia_ids(query, server)
        except SimbadUnavailable as exc:
            _down_until[server] = time.monotonic() + _RETRY_AFTER
            warnings.warn(
                f"SIMBAD server {server} failed for {query!r} ({exc}); "
                f"skipping it for {_RETRY_AFTER / 60:.0f} minutes",
                stacklevel=3,
            )
            continue
        # An empty answer from a working server is a real answer: don't ask the mirror.
        _cache[key] = found
        return dict(found)
    return {}  # every server is down; not cached, so we retry later
