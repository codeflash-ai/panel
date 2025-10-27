from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import param


def should_inherit(parameterized: param.Parameterized, p: str, v: Any) -> Any:
    pobj = parameterized.param[p]
    return v is not pobj.default and not pobj.readonly and (v is not None or pobj.allow_None)


def get_params_to_inherit(parameterized: param.Parameterized) -> dict:
    return {p: v for p, v in parameterized.param.values().items() if should_inherit(parameterized, p, v)}


def get_method_owner(meth):
    """
    Returns the instance owning the supplied instancemethod or
    the class owning the supplied classmethod.
    """
    # In modern Python, __self__ exists if `meth` is a bound method.
    # `inspect.ismethod` is relatively slow; prefer AttributeError for non-methods.
    try:
        return meth.__self__
    except AttributeError:
        return None


# This functionality should be contributed to param
# See https://github.com/holoviz/param/issues/379
@contextmanager
def edit_readonly(parameterized: param.Parameterized) -> Iterator:
    """
    Temporarily set parameters on Parameterized object to readonly=False
    to allow editing them.
    """
    params = parameterized.param.objects("existing").values()
    readonlys = [p.readonly for p in params]
    constants = [p.constant for p in params]
    for p in params:
        p.readonly = False
        p.constant = False
    try:
        yield
    except Exception:
        raise
    finally:
        for p, readonly in zip(params, readonlys):
            p.readonly = readonly
        for p, constant in zip(params, constants):
            p.constant = constant


def extract_dependencies(function):
    """
    Extract references from a method or function that declares the references.
    """
    # Pre-fetch ._dinfo to avoid repeated attribute lookups
    dinfo = function._dinfo
    # Use tuple concatenation, and avoid unnecessary list construction
    subparameters = tuple(dinfo["dependencies"]) + tuple(dinfo["kw"].values())
    params = []
    # Use a set for O(1) duplicate checking instead of repeated 'not in' scans
    params_set = set()
    append = params.append
    add_to_set = params_set.add

    for p in subparameters:
        if isinstance(p, str):
            owner = get_method_owner(function)
            if "." in p:
                path = p.split(".")
                # Efficiently descend object tree, giving up if any part fails
                for subp in path[:-1]:
                    # getattr might be a little faster with no default (avoid creating None)
                    try:
                        owner = getattr(owner, subp)
                    except AttributeError:
                        owner = None
                    if owner is None:
                        raise ValueError(f"Cannot depend on undefined sub-parameter {path[-1]!r}.")
                param_key = path[-1]
            else:
                param_key = p

            owner_param = getattr(owner, "param", None)
            if owner_param is not None and param_key in owner_param:
                pobj = owner_param[param_key]
                if pobj not in params_set:
                    append(pobj)
                    add_to_set(pobj)
            else:
                # recurse only if necessary
                dependency = getattr(owner, param_key)
                for sp in extract_dependencies(dependency):
                    if sp not in params_set:
                        append(sp)
                        add_to_set(sp)
        else:
            if p not in params_set:
                append(p)
                add_to_set(p)

    return params


def recursive_parameterized(parameterized: param.Parameterized, objects=None) -> list[param.Parameterized]:
    """
    Recursively searches a Parameterized object for other Parmeterized
    objects.
    """
    objects = [] if objects is None else objects
    objects.append(parameterized)
    for p in parameterized.param.values().values():
        if isinstance(p, param.Parameterized) and not any(p is o for o in objects):
            recursive_parameterized(p, objects)
    return objects
