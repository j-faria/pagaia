__version__ = "0.0.1"

from ._resolve import TableSpec, make_getattr

__getattr__ = make_getattr(
    __name__,
    {
        "DR3": TableSpec("gaiadr3.gaia_source"),
        "DR4": TableSpec("gaiadr4.gaia_source"),
    },
)