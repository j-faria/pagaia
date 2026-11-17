<p align="center">
  <img src="https://raw.githubusercontent.com/j-faria/pagaia/refs/heads/main/docs/assets/logo.png"
       alt="Pagaia — Python tools for Gaia data"
       width="320">
</p>


### To install

```bash
pip install pagaia
```

### To use

```python
from pagaia import DR3_4472832130942575872 as barnard

from pagaia.nss import DR3_1712614124767394816 as gaia3
```

or with aliases

```python
from pagaia import barnard  # built-in alias

import pagaia
pagaia.add_alias('my favorite star', 123456789)
from pagaia import my_favorite_star
```

or querying Simbad

```python
from pagaia import HD10180
```

---

### What's in a target?

```python
>>> from pagaia import gaia3

>>> gaia3.columns

['solution_id',
 'source_id',
 'ref_epoch',
 ...
 'ra',
 'ra_error',
 'dec',
 'dec_error',
 'parallax',
 'parallax_error',
 ...
 'ruwe',
 'radial_velocity',
 'radial_velocity_error',
 ...
]
```

which can be accessed as

```python
>>> gaia3['ra']
np.float64(203.16332673930077)
```

or 

```python
>>> gaia3.val.ra, gaia3.err.ra
(np.float64(203.16332673930077), np.float32(0.011661524))
```

Same for information from the NSS

```python
>>> from pagaia.nss import gaia3

>>> gaia3.columns

['solution_id',
 'source_id',
 'nss_solution_type',
 ...
 'a_thiele_innes',
 'a_thiele_innes_error',
 'b_thiele_innes',
 'b_thiele_innes_error',
 ...
 'period',
 't_periastron',
 'eccentricity',
 'inclination',
 ...
 'goodness_of_fit',
 'astrometric_jitter'
]
```
