__all__ = ["add_alias", "list_aliases"]

from ._aliases import add_alias, list_aliases
from . import _resolve

__getattr__ = _resolve.make_getattr(
    __name__,
    {
        "DR3": _resolve.TableSpec("gaiadr3.gaia_source"),
        "DR4": _resolve.TableSpec("gaiadr4.gaia_source"),
    },
)