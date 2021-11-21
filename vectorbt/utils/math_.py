# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Math utilities."""

import numpy as np

from vectorbt._settings import settings
from vectorbt.jit_registry import register_jitted

_use_tol = settings['math']['use_tol']
_rel_tol = settings['math']['rel_tol']
_abs_tol = settings['math']['abs_tol']


@register_jitted(cache=True)
def is_close_nb(a: float,
                b: float,
                use_tol: bool = _use_tol,
                rel_tol: float = _rel_tol,
                abs_tol: float = _abs_tol) -> bool:
    """Tell whether two values are approximately equal."""
    if np.isnan(a) or np.isnan(b):
        return False
    if np.isinf(a) or np.isinf(b):
        return False
    if a == b:
        return True
    return use_tol and abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


@register_jitted(cache=True)
def is_close_or_less_nb(a: float,
                        b: float,
                        use_tol: bool = _use_tol,
                        rel_tol: float = _rel_tol,
                        abs_tol: float = _abs_tol) -> bool:
    """Tell whether the first value is approximately less than or equal to the second value."""
    if use_tol and is_close_nb(a, b, rel_tol=rel_tol, abs_tol=abs_tol):
        return True
    return a < b


@register_jitted(cache=True)
def is_less_nb(a: float,
               b: float,
               use_tol: bool = _use_tol,
               rel_tol: float = _rel_tol,
               abs_tol: float = _abs_tol) -> bool:
    """Tell whether the first value is approximately less than the second value."""
    if use_tol and is_close_nb(a, b, rel_tol=rel_tol, abs_tol=abs_tol):
        return False
    return a < b


@register_jitted(cache=True)
def is_addition_zero_nb(a: float,
                        b: float,
                        use_tol: bool = _use_tol,
                        rel_tol: float = _rel_tol,
                        abs_tol: float = _abs_tol) -> bool:
    """Tell whether addition of two values yields zero."""
    if use_tol:
        if np.sign(a) != np.sign(b):
            return is_close_nb(abs(a), abs(b), rel_tol=rel_tol, abs_tol=abs_tol)
        return is_close_nb(a + b, 0., rel_tol=rel_tol, abs_tol=abs_tol)
    return a == -b


@register_jitted(cache=True)
def add_nb(a: float,
           b: float,
           use_tol: bool = _use_tol,
           rel_tol: float = _rel_tol,
           abs_tol: float = _abs_tol) -> float:
    """Add two floats."""
    if use_tol and is_addition_zero_nb(a, b, rel_tol=rel_tol, abs_tol=abs_tol):
        return 0.
    return a + b
