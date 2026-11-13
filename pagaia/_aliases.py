"""Registry of human-friendly star names -> Gaia source ids

Built-in aliases are hard-coded in this file. Aliases added with
:func:`add_alias` are saved to a JSON file so they are available across Python
sessions.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import warnings
from pathlib import Path

# normalized name -> {release: source_id}; always = built-ins + user file
_ALIASES: dict[str, dict[str, int]] = {}
_loaded_from: Path | None = None

_RELEASE_RE = re.compile(r"^DR\d+$")
_RELEASE_PREFIX_RE = re.compile(r"^dr\d+")

# --- built-in aliases (Gaia DR3 source_ids) --------------------------------
_BUILTIN = [
    (("Barnard's Star", "Barnard"), 4472832130942575872),
    (("Proxima Centauri", "Proxima Cen", "Proxima"), 5853498713190525696),
    (("Wolf 359",), 3864972938605115520),
    (("TRAPPIST-1",), 2635476908753563008),
]


def normalize(name: str) -> str:
    """Case-fold and drop everything that is not a letter or digit.

    "Barnard's Star", "barnards_star", and "BarnardsStar" all map to
    "barnardsstar", so a name with spaces or quotes can be registered and still
    be reachable through a valid Python identifier like ``Barnards_Star``.
    """
    return re.sub(r"[\W_]+", "", name.casefold())


def _validate(name: str, gaia_id, release: str) -> tuple[str, str, int]:
    key = normalize(name)
    if not key:
        raise ValueError(f"invalid alias name {name!r}")
    if key.isdigit() or _RELEASE_PREFIX_RE.match(key):
        # These would be parsed as a Gaia id or a release prefix instead
        raise ValueError(
            f"alias {name!r} is ambiguous: it must not be only digits "
            "or start with a release name like 'DR3'"
        )
    release = release.upper()
    if not _RELEASE_RE.match(release):
        raise ValueError(f"invalid release {release!r}, expected e.g. 'DR3'")
    try:
        source_id = int(gaia_id)
    except (TypeError, ValueError):
        raise ValueError(f"invalid Gaia id {gaia_id!r}") from None
    if source_id <= 0:
        raise ValueError(f"invalid Gaia id {gaia_id!r}")
    return key, release, source_id


# --- persistence -----------------------------------------------------------
def config_path() -> Path:
    """Location of the user alias file (override with ``PAGAIA_ALIAS_FILE``)."""
    env = os.environ.get("PAGAIA_ALIAS_FILE")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "pagaia" / "aliases.json"


def _read_file(path: Path) -> dict:
    """Return the file content as ``{key: {"name": str, "ids": {release: id}}}``."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw["aliases"]
        if not isinstance(entries, dict):
            raise TypeError("'aliases' must be an object")
        return entries
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        backup = path.with_suffix(".json.bak")
        try:
            path.replace(backup)
            where = f"moved to {backup}"
        except OSError:
            where = "left in place"
        warnings.warn(f"ignoring unreadable alias file {path} ({exc}); {where}", stacklevel=3)
        return {}


def _write_file(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory, then atomically replace
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".aliases-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"version": 1, "aliases": entries}, fh, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _reload() -> None:
    """Rebuild the registry from the built-ins plus the user file."""
    global _loaded_from
    path = config_path()
    _ALIASES.clear()
    for names, gaia_id in _BUILTIN:
        for name in names:
            key, release, sid = _validate(name, gaia_id, "DR3")
            _ALIASES.setdefault(key, {})[release] = sid
    for key, entry in _read_file(path).items():
        try:
            for release, gaia_id in entry["ids"].items():
                k, rel, sid = _validate(entry.get("name", key), gaia_id, release)
                _ALIASES.setdefault(k, {})[rel] = sid
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            warnings.warn(f"skipping bad alias entry {key!r} in {path}: {exc}", stacklevel=2)
    _loaded_from = path


def _ensure_loaded() -> None:
    # Lazy, so `import pagaia` never reads/writes from the disk; also reloads if
    # PAGAIA_ALIAS_FILE changes
    if _loaded_from != config_path():
        _reload()


# --- public API ------------------------------------------------------------
def add_alias(name: str, gaia_id: int | str, release: str = "DR3") -> None:
    """Register ``name`` as an alias for ``gaia_id`` and save it to disk.

    Source ids are specific for each Gaia release, so the same alias can have
    one id per release. Re-registering an alias for the same release replaces
    the old one.

    >>> add_alias("Gliese 710", 4270814637616488064)
    >>> from pagaia import Gliese_710
    """
    key, release, source_id = _validate(name, gaia_id, release)
    _ensure_loaded()

    old = _ALIASES.get(key, {}).get(release)
    if old is not None and old != source_id:
        warnings.warn(
            f"alias {name!r} already pointed to {release} source_id {old}; "
            f"replacing it with {source_id}",
            stacklevel=2,
        )
    _ALIASES.setdefault(key, {})[release] = source_id

    path = config_path()
    try:
        entries = _read_file(path)
        entry = entries.setdefault(key, {"name": name, "ids": {}})
        entry["name"] = name
        entry["ids"][release] = source_id
        _write_file(path, entries)
    except OSError as exc:
        warnings.warn(
            f"could not save alias to {path} ({exc}); "
            "it is only available in this session",
            stacklevel=2,
        )


def remove_alias(name: str, release: str | None = None) -> None:
    """Remove a user-defined alias (all releases, or just ``release``).

    Built-in aliases cannot be removed, only overridden with :func:`add_alias`.
    """
    key = normalize(name)
    path = config_path()
    entries = _read_file(path)
    entry = entries.get(key)
    if entry is None:
        raise KeyError(f"no user-defined alias {name!r}")
    if release is None:
        del entries[key]
    else:
        if entry["ids"].pop(release.upper(), None) is None:
            raise KeyError(f"alias {name!r} has no user-defined {release.upper()} id")
        if not entry["ids"]:
            del entries[key]
    _write_file(path, entries)
    _reload()  # also restores a built-in that was being overridden


def get_ids(name: str) -> dict[str, int]:
    """Return ``{release: source_id}`` for an alias (empty if unknown)."""
    _ensure_loaded()
    return dict(_ALIASES.get(normalize(name), {}))


def list_aliases() -> dict[str, dict[str, int]]:
    """Return a copy of the registry, with normalized names as keys."""
    _ensure_loaded()
    return {k: dict(v) for k, v in sorted(_ALIASES.items())}
