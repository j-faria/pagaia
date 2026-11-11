from ._resolve import TableSpec, make_getattr

__getattr__ = make_getattr(
    __name__,
    {
        "DR3": TableSpec("gaiadr3.nss_two_body_orbit"),
        "DR4": TableSpec("gaiadr4.nss_two_body_orbit"),
    },
)