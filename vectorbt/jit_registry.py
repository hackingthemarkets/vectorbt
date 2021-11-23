# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Global registry for jitted functions.

Jitting is a process of just-in-time compiling functions to make their execution faster.
A jitter is a decorator that wraps a regular Python function and returns the decorated function.
Depending upon a jitter, this decorated function has the same or at least a similar signature
to the function that has been decorated. Jitters take various jitter-specific options
to change the behavior of execution; that is, a single regular Python function can be
decorated by multiple jitter instances (for example, one jitter for decorating a function
with `numba.jit` and another jitter for doing the same with `parallel=True` flag).

In addition to jitters, vectorbt introduces the concept of tasks. One task can be
executed by multiple jitter types (such as NumPy, Numba, and JAX). For example, one
can create a task that converts price into returns and implements it using NumPy and Numba.
Those implementations are registered by `JITRegistry` as `JitableSetup` instances, are stored
in `JITRegistry.jitable_setups`, and can be uniquely identified by the task id and jitter type.
Note that `JitableSetup` instances contain only information on how to decorate a function.

The decorated function itself and the jitter that has been used are registered as a `JittedSetup`
instance and stored in `JITRegistry.jitted_setups`. It acts as a cache to quickly retrieve an
already decorated function and to avoid recompilation.

Let's implement a task that takes a sum over an array using both NumPy and Numba:

```python-repl
>>> import vectorbt as vbt
>>> import numpy as np

>>> @vbt.register_jitted(task_id_or_func='sum')
... def sum_np(a):
...     return a.sum()

>>> @vbt.register_jitted(task_id_or_func='sum')
... def sum_nb(a):
...     out = 0.
...     for i in range(a.shape[0]):
...         out += a[i]
...     return out
```

We can see that two new jitable setups were registered:

```python-repl
>>> vbt.jit_registry.jit_registry.jitable_setups['sum']
{vectorbt.utils.jitting.NumPyJitter: <vectorbt.jit_registry.JitableSetup at 0x7fef114aa6d8>,
 vectorbt.utils.jitting.NumbaJitter: <vectorbt.jit_registry.JitableSetup at 0x7fef114aaa90>}
```

Moreover, two jitted setups were registered for our decorated functions:

```python-repl
>>> from vectorbt.jit_registry import jit_registry, JitableSetup

>>> hash_np = JitableSetup.get_hash('sum', 'np')
>>> jit_registry.jitted_setups[hash_np]
{3527539: <vectorbt.jit_registry.JittedSetup at 0x7fef114aaac8>}

>>> hash_nb = JitableSetup.get_hash('sum', 'nb')
>>> jit_registry.jitted_setups[hash_nb]
{-2214287351923578620: <vectorbt.jit_registry.JittedSetup at 0x7fef16b55b70>}
```

These setups contain decorated functions with the options passed during the registration.
When we call `JITRegistry.resolve` without any additional keyword arguments,
`JITRegistry` returns exactly these functions:

```python-repl
>>> jitted_func = jit_registry.resolve('sum', jitter='nb')
>>> jitted_func
CPUDispatcher(<function sum_nb at 0x7fef16a99f28>)

>>> jitted_func.targetoptions
{'parallel': False, 'nopython': True, 'nogil': True, 'boundscheck': False}
```

Once we pass any other option, the Python function will be redecorated, and another `JittedOption`
instance will be registered:

```python-repl
>>> jitted_func = jit_registry.resolve('sum', jitter='nb', nopython=False)
>>> jitted_func
CPUDispatcher(<function sum_nb at 0x7fef16a99f28>)

>>> jitted_func.targetoptions
{'parallel': False, 'nopython': False, 'nogil': True, 'boundscheck': False}

>>> jit_registry.jitted_setups[hash_nb]
{-2214287351923578620: <vectorbt.jit_registry.JittedSetup at 0x7fef16b55b70>,
 -2214288625816173245: <vectorbt.jit_registry.JittedSetup at 0x7fef1140e080>}
```

## Templates

Templates can be used to, based on the current context, dynamically select the jitter or
keyword arguments for jitting. For example, let's pick the NumPy jitter over any other
jitter if there are more than two of them for a given task:

```python-repl
>>> jit_registry.resolve('sum', jitter=vbt.RepEval("'nb' if 'nb' in task_setups else None"))
<function __main__.sum_np(a)>
```

## Disabling

In the case we want to disable jitting, we can simply pass `disable=True` to `JITRegistry.resolve`:

```python-repl
>>> py_func = jit_registry.resolve('sum', jitter='nb', disable=True)
>>> py_func
<function __main__.sum_nb(a)>
```

We can also disable jitting globally:

```python-repl
>>> vbt.settings.jitting['disable'] = True

>>> jit_registry.resolve('sum', jitter='nb')
<function __main__.sum_nb(a)>
```

!!! hint
    If we don't plan to use any additional options and we have only one jitter registered per task,
    we can also disable resolution to increase performance.

!!! warning
    Disabling jitting globally only applies to functions resolved using `JITRegistry.resolve`.
    Any decorated function that is being called directly will be executed as usual.

## Jitted option

Since most functions that call other jitted functions in vectorbt have a `jitted` argument,
you can pass `jitted` as a dictionary with options, as a string denoting the jitter, or False
to disable jitting (see `vectorbt.utils.jitting.resolve_jitted_option`):

```python-repl
>>> def sum_arr(arr, jitted=None):
...     func = jit_registry.resolve_option('sum', jitted)
...     return func(arr)

>>> arr = np.random.uniform(size=1000000)

>>> %timeit sum_arr(arr, jitted='np')
319 µs ± 3.35 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)

>>> %timeit sum_arr(arr, jitted='nb')
1.09 ms ± 4.13 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)

>>> %timeit sum_arr(arr, jitted=dict(jitter='nb', disable=True))
133 ms ± 2.32 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)
```

!!! hint
    A good rule of thumb is: whenever a caller function accepts a `jitted` argument,
    the jitted functions it calls are most probably resolved using `JITRegistry.resolve_option`.

## Changing options upon registration

Options are usually specified upon registration using `register_jitted`:

```python-repl
>>> from numba import prange

>>> @vbt.register_jitted(parallel=True, tags={'can_parallel'})
... def sum_parallel_nb(a):
...     out = np.empty(a.shape[1])
...     for col in prange(a.shape[1]):
...         total = 0.
...         for i in range(a.shape[0]):
...             total += a[i, col]
...         out[col] = total
...     return out

>>> sum_parallel_nb.targetoptions
{'nopython': True, 'nogil': True, 'parallel': True, 'boundscheck': False}
```

But what if we wanted to change the registration options of vectorbt's own jitable functions,
such as `vectorbt.generic.nb.diff_nb`? For example, let's disable caching for all Numba functions.

```python-repl
>>> vbt.settings.jitting.jitters['nb']['override_options'] = dict(cache=False)
```

Since all functions have already been registered, the above statement has no effect:

```python-repl
>>> jit_registry.jitable_setups['vectorbt.generic.nb.diff_nb']['nb'].jitter_kwargs
{'cache': True}
```

In order for them to be applied, we need to save the settings to a file and
load them before all functions are imported:

```python-repl
>>> vbt.settings.save('my_settings')
```

Let's restart the runtime and instruct vectorbt to load the file with settings before anything else:

```python-repl
>>> import os
>>> os.environ['VBT_SETTINGS_PATH'] = "my_settings"

>>> from vectorbt.jit_registry import jit_registry
>>> jit_registry.jitable_setups['vectorbt.generic.nb.diff_nb']['nb'].jitter_kwargs
{'cache': False}
```

We can also change the registration options for some specific tasks:

```python-repl
>>> vbt.settings.jitting.jitters['nb']['override_setup_options'] = \\
...     {'vectorbt.generic.nb.diff_nb': dict(cache=False)}
```

## Changing options upon resolution

Another approach but without the need to restart the runtime is by changing the options
upon resolution using `JITRegistry.resolve_option`:

```python-repl
>>> # On specific Numba function
>>> vbt.settings.jitting.setup_kwargs[('vectorbt.generic.nb.diff_nb', 'nb')] = dict(nogil=False)

>>> jit_registry.resolve('vectorbt.generic.nb.diff_nb', jitter='nb').targetoptions
{'nopython': True, 'nogil': False, 'parallel': False, 'boundscheck': False}

>>> jit_registry.resolve('sum', jitter='nb').targetoptions
{'nopython': True, 'nogil': True, 'parallel': False, 'boundscheck': False}

>>> # On each Numba function
>>> vbt.settings.jitting.jitter_kwargs['nb'] = dict(nogil=False)

>>> jit_registry.resolve('vectorbt.generic.nb.diff_nb', jitter='nb').targetoptions
{'nopython': True, 'nogil': False, 'parallel': False, 'boundscheck': False}

>>> jit_registry.resolve('sum', jitter='nb').targetoptions
{'nopython': True, 'nogil': False, 'parallel': False, 'boundscheck': False}
```

## Building custom jitters

Let's build a custom jitter on top of `vectorbt.utils.jitting.NumbaJitter` that converts
any argument that contains a Pandas object to a 2-dimensional NumPy array prior to decoration:

```python-repl
>>> from functools import wraps
>>> from vectorbt.utils.jitting import NumbaJitter
>>> import pandas as pd

>>> class SafeNumbaJitter(NumbaJitter):
...     def decorate(self, py_func, tags=None):
...         if self.wrapping_disabled:
...             return py_func
...
...         @wraps(py_func)
...         def wrapper(*args, **kwargs):
...             new_args = ()
...             for arg in args:
...                 if isinstance(arg, pd.Series):
...                     arg = np.expand_dims(arg.values, 1)
...                 elif isinstance(arg, pd.DataFrame):
...                     arg = arg.values
...                 new_args += (arg,)
...             new_kwargs = dict()
...             for k, v in kwargs.items():
...                 if isinstance(v, pd.Series):
...                     v = np.expand_dims(v.values, 1)
...                 elif isinstance(v, pd.DataFrame):
...                     v = v.values
...                 new_kwargs[k] = v
...             return NumbaJitter.decorate(self, py_func, tags=tags)(*new_args, **new_kwargs)
...         return wrapper
```

After we have defined our jitter class, we need to register it globally:

```python-repl
>>> vbt.settings.jitting.jitters['safe_nb'] = dict(cls=SafeNumbaJitter)
```

Finally, we can execute any Numba function by specifying our new jitter:

```python-repl
>>> func = jit_registry.resolve(
...     task_id_or_func=vbt.generic.nb.diff_nb,
...     jitter='safe_nb',
...     allow_new=True
... )
>>> func(pd.DataFrame([[1, 2], [3, 4]]))
array([[nan, nan],
       [ 2.,  2.]])
```

Whereas executing the same func using the vanilla Numba jitter causes an error:

```python-repl
>>> func = jit_registry.resolve(task_id_or_func=vbt.generic.nb.diff_nb)
>>> func(pd.DataFrame([[1, 2], [3, 4]]))
Failed in nopython mode pipeline (step: nopython frontend)
non-precise type pyobject
```

!!! note
    Make sure to pass a function as `task_id_or_func` if the jitted function hasn't been registered yet.

    This jitter cannot be used for decorating Numba functions that should be called
    from other Numba functions since the convertion operation is done using Python.
"""

from vectorbt import _typing as tp
from vectorbt.utils import checks
from vectorbt.utils.config import merge_dicts, atomic_dict
from vectorbt.utils.template import RepEval, deep_substitute, CustomTemplate
from vectorbt.utils.jitting import (
    Jitter,
    resolve_jitted_kwargs,
    resolve_jitter_type,
    resolve_jitter,
    get_id_of_jitter_type,
    get_func_suffix
)
from vectorbt.utils.docs import SafeToStr, prepare_for_doc
from vectorbt.utils.hashing import Hashable


class JitableSetup(Hashable, SafeToStr):
    """Class that represents a jitable setup.

    !!! note
        Hashed solely by `task_id` and `jitter_id`."""

    @staticmethod
    def get_hash(task_id: tp.Hashable, jitter_id: tp.Hashable) -> int:
        return hash((
            task_id,
            jitter_id
        ))

    def __init__(self,
                 task_id: tp.Hashable,
                 jitter_id: tp.Hashable,
                 py_func: tp.Callable,
                 jitter_kwargs: tp.KwargsLike = None,
                 tags: tp.SetLike = None) -> None:
        if jitter_kwargs is None:
            jitter_kwargs = {}
        if tags is None:
            tags = set()

        self._task_id = task_id
        self._jitter_id = jitter_id
        self._py_func = py_func
        self._jitter_kwargs = jitter_kwargs
        self._tags = tags

    @property
    def task_id(self) -> tp.Hashable:
        """Task id."""
        return self._task_id

    @property
    def jitter_id(self) -> tp.Hashable:
        """Jitter id."""
        return self._jitter_id

    @property
    def py_func(self) -> tp.Callable:
        """Python function to be jitted."""
        return self._py_func

    @property
    def jitter_kwargs(self) -> tp.DictLike:
        """Keyword arguments passed to `vectorbt.utils.jitting.resolve_jitter`."""
        return self._jitter_kwargs

    @property
    def tags(self) -> set:
        """Set of tags."""
        return self._tags

    def to_dict(self) -> dict:
        """Convert this instance to a dict."""
        return dict(
            task_id=self.task_id,
            jitter_id=self.jitter_id,
            py_func=self.py_func,
            jitter_kwargs=self.jitter_kwargs,
            tags=self.tags
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(" \
               f"task_id={self.task_id}, " \
               f"jitter_id={self.jitter_id}, " \
               f"py_func={self.py_func}, " \
               f"jitter_kwargs={prepare_for_doc(self.jitter_kwargs)}, " \
               f"tags={self.tags})"

    @property
    def hash_key(self) -> tuple:
        return (
            self.task_id,
            self.jitter_id
        )


class JittedSetup(Hashable, SafeToStr):
    """Class that represents a jitted setup.

    !!! note
        Hashed solely by sorted config of `jitter`. That is, two jitters with the same config
        will yield the same hash and the function won't be re-decorated."""

    @staticmethod
    def get_hash(jitter: Jitter) -> int:
        return hash(tuple(sorted(jitter.config.items())))

    def __init__(self, jitter: Jitter, jitted_func: tp.Callable) -> None:
        self._jitter = jitter
        self._jitted_func = jitted_func

    @property
    def jitter(self) -> Jitter:
        """Jitter that decorated the function."""
        return self._jitter

    @property
    def jitted_func(self) -> tp.Callable:
        """Decorated function."""
        return self._jitted_func

    def to_dict(self) -> dict:
        """Convert this instance to a dict."""
        return dict(
            jitter=self.jitter,
            jitted_func=self.jitted_func
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(" \
               f"jitter={self.jitter}, " \
               f"jitted_func={self.jitted_func})"

    @property
    def hash_key(self) -> tuple:
        return tuple(sorted(self.jitter.config.items()))


class JITRegistry:
    """Class that registers jitted functions."""

    def __init__(self) -> None:
        self._jitable_setups = {}
        self._jitted_setups = {}

    @property
    def jitable_setups(self) -> tp.Dict[tp.Hashable, tp.Dict[tp.Hashable, JitableSetup]]:
        """Dict of registered `JitableSetup` instances by `task_id` and `jitter_id`."""
        return self._jitable_setups

    @property
    def jitted_setups(self) -> tp.Dict[int, tp.Dict[int, JittedSetup]]:
        """Nested dict of registered `JittedSetup` instances by hash of their `JitableSetup` instance."""
        return self._jitted_setups

    def register_jitable_setup(self,
                               task_id: tp.Hashable,
                               jitter_id: tp.Hashable,
                               py_func: tp.Callable,
                               jitter_kwargs: tp.KwargsLike = None,
                               tags: tp.Optional[set] = None) -> JitableSetup:
        """Register a jitable setup."""
        jitable_setup = JitableSetup(
            task_id=task_id,
            jitter_id=jitter_id,
            py_func=py_func,
            jitter_kwargs=jitter_kwargs,
            tags=tags
        )
        if task_id not in self.jitable_setups:
            self.jitable_setups[task_id] = dict()
        if jitter_id not in self.jitable_setups[task_id]:
            self.jitable_setups[task_id][jitter_id] = jitable_setup
        return jitable_setup

    def register_jitted_setup(self,
                              jitable_setup: JitableSetup,
                              jitter: Jitter,
                              jitted_func: tp.Callable) -> JittedSetup:
        """Register a jitted setup."""
        jitable_setup_hash = hash(jitable_setup)
        jitted_setup = JittedSetup(
            jitter=jitter,
            jitted_func=jitted_func
        )
        jitted_setup_hash = hash(jitted_setup)
        if jitable_setup_hash in self.jitted_setups:
            if jitted_setup_hash in self.jitted_setups[jitable_setup_hash]:
                raise ValueError(f"Jitted setup with task id '{jitable_setup.task_id}' and "
                                 f"jitter {jitter} already registered")
        if jitable_setup_hash not in self.jitted_setups:
            self.jitted_setups[jitable_setup_hash] = dict()
        if jitted_setup_hash not in self.jitted_setups[jitable_setup_hash]:
            self.jitted_setups[jitable_setup_hash][jitted_setup_hash] = jitted_setup
        return jitted_setup

    def decorate_and_register(self,
                              task_id: tp.Hashable,
                              py_func: tp.Callable,
                              jitter: tp.Optional[tp.JitterLike] = None,
                              jitter_kwargs: tp.KwargsLike = None,
                              tags: tp.Optional[set] = None):
        """Decorate a jitable function and register both jitable and jitted setups."""
        jitter = resolve_jitter(jitter=jitter, py_func=py_func, **jitter_kwargs)
        jitter_id = get_id_of_jitter_type(jitter.__class__)
        if jitter_id is None:
            raise ValueError("Jitter id cannot be None: is jitter registered globally?")
        jitable_setup = self.register_jitable_setup(
            task_id,
            jitter_id,
            py_func,
            jitter_kwargs=jitter_kwargs,
            tags=tags
        )
        jitted_func = jitter.decorate(py_func, tags=tags)
        self.register_jitted_setup(
            jitable_setup,
            jitter,
            jitted_func
        )
        return jitted_func

    def match_jitable_setups(self, expression: tp.Optional[str] = None,
                             mapping: tp.KwargsLike = None) -> tp.Set[JitableSetup]:
        """Match jitable setups against an expression with each setup being a mapping."""
        matched_setups = set()
        for setups_by_jitter_id in self.jitable_setups.values():
            for setup in setups_by_jitter_id.values():
                if expression is None:
                    result = True
                else:
                    result = RepEval(expression).substitute(mapping=merge_dicts(setup.to_dict(), mapping))
                    checks.assert_instance_of(result, bool)

                if result:
                    matched_setups.add(setup)
        return matched_setups

    def match_jitted_setups(self, jitable_setup: JitableSetup, expression: tp.Optional[str] = None,
                            mapping: tp.KwargsLike = None) -> tp.Set[JittedSetup]:
        """Match jitted setups of a jitable setup against an expression with each setup a mapping."""
        matched_setups = set()
        for setup in self.jitted_setups[hash(jitable_setup)].values():
            if expression is None:
                result = True
            else:
                result = RepEval(expression).substitute(mapping=merge_dicts(setup.to_dict(), mapping))
                checks.assert_instance_of(result, bool)

            if result:
                matched_setups.add(setup)
        return matched_setups

    def resolve(self,
                task_id_or_func: tp.Union[tp.Hashable, tp.Callable],
                jitter: tp.Optional[tp.Union[tp.JitterLike, CustomTemplate]] = None,
                disable: tp.Optional[tp.Union[bool, CustomTemplate]] = None,
                disable_resolution: tp.Optional[bool] = None,
                allow_new: tp.Optional[bool] = None,
                register_new: tp.Optional[bool] = None,
                return_missing_task: bool = False,
                template_mapping: tp.Optional[tp.Mapping] = None,
                tags: tp.Optional[set] = None,
                **jitter_kwargs) -> tp.Union[tp.Hashable, tp.Callable]:
        """Resolve jitted function for the given task id.

        For details on the format of `task_id_or_func`, see `register_jitted`.

        `jitter_kwargs` are merged with `jitting.task_kwargs`, `jitting.jitter_kwargs`,
         and `jitting.setup_kwargs` in `vectorbt._settings.settings`.

        Templates are substituted in `jitter`, `disable`, and `jitter_kwargs`.

        Set `disable` to True to return the Python function without decoration.
        If `disable_resolution` is enabled globally, `task_id_or_func` is returned unchanged.

        !!! note
            `disable` is only being used by `JITRegistry`, not `vectorbt.utils.jitting`.

        !!! note
            If there are more than one jitted setups registered for a single task id,
            make sure to provide a jitter.

        If no jitted setup of type `JittedSetup` was found and `allow_new` is True,
        decorates and returns the function supplied as `task_id_or_func` (otherwise throws an error).

        Set `return_missing_task` to True to return `task_id_or_func` if it cannot be found
        in `JITRegistry.jitable_setups`.
        """
        from vectorbt._settings import settings
        jitting_cfg = settings['jitting']

        if disable_resolution is None:
            disable_resolution = jitting_cfg['disable_resolution']
        if disable_resolution:
            return task_id_or_func

        if allow_new is None:
            allow_new = jitting_cfg['allow_new']
        if register_new is None:
            register_new = jitting_cfg['register_new']

        if hasattr(task_id_or_func, 'py_func'):
            py_func = task_id_or_func.py_func
            task_id = py_func.__module__ + '.' + py_func.__name__
        elif callable(task_id_or_func):
            py_func = task_id_or_func
            task_id = py_func.__module__ + '.' + py_func.__name__
        else:
            py_func = None
            task_id = task_id_or_func

        if task_id not in self.jitable_setups:
            if not allow_new:
                if return_missing_task:
                    return task_id_or_func
                raise KeyError(f"Task id '{task_id}' not registered")
        task_setups = self.jitable_setups.get(task_id, dict())

        template_mapping = merge_dicts(
            jitting_cfg['template_mapping'],
            template_mapping,
            dict(
                task_id=task_id,
                py_func=py_func,
                task_setups=atomic_dict(task_setups)
            )
        )
        jitter = deep_substitute(jitter, template_mapping, sub_id='jitter')

        if jitter is None and py_func is not None:
            jitter = get_func_suffix(py_func)

        if jitter is None:
            if len(task_setups) > 1:
                raise ValueError(f"There are multiple registered setups for task id '{task_id}'. "
                                 f"Please specify the jitter.")
            elif len(task_setups) == 0:
                raise ValueError(f"There are no registered setups for task id '{task_id}'")
            jitable_setup = list(task_setups.values())[0]
            jitter = jitable_setup.jitter_id
            jitter_id = jitable_setup.jitter_id
        else:
            jitter_type = resolve_jitter_type(jitter=jitter)
            jitter_id = get_id_of_jitter_type(jitter_type)
            if jitter_id not in task_setups:
                if not allow_new:
                    raise KeyError(f"Jitable setup with task id '{task_id}' and "
                                   f"jitter id '{jitter_id}' not registered")
                jitable_setup = None
            else:
                jitable_setup = task_setups[jitter_id]
        if jitter_id is None:
            raise ValueError("Jitter id cannot be None: is jitter registered globally?")
        if jitable_setup is None and py_func is None:
            raise ValueError(f"Unable to find Python function for task id '{task_id}' "
                             f"and jitter id '{jitter_id}'")

        template_mapping = merge_dicts(
            template_mapping,
            dict(
                jitter_id=jitter_id,
                jitter=jitter,
                jitable_setup=jitable_setup
            )
        )
        disable = deep_substitute(disable, template_mapping, sub_id='disable')
        if disable is None:
            disable = jitting_cfg['disable']
        if disable:
            if jitable_setup is None:
                return py_func
            return jitable_setup.py_func

        if not isinstance(jitter, Jitter):
            jitter_kwargs = merge_dicts(
                jitable_setup.jitter_kwargs if jitable_setup is not None else None,
                jitting_cfg['jitter_kwargs'].get(jitter_id, {}),
                jitting_cfg['task_kwargs'].get(task_id, {}),
                jitting_cfg['setup_kwargs'].get((task_id, jitter_id), {}),
                jitter_kwargs
            )
            jitter_kwargs = deep_substitute(jitter_kwargs, template_mapping, sub_id='jitter_kwargs')
            jitter = resolve_jitter(jitter=jitter, **jitter_kwargs)

        if jitable_setup is not None:
            jitable_hash = hash(jitable_setup)
            jitted_hash = JittedSetup.get_hash(jitter)
            if jitable_hash in self.jitted_setups and jitted_hash in self.jitted_setups[jitable_hash]:
                return self.jitted_setups[jitable_hash][jitted_hash].jitted_func
        else:
            if register_new:
                return self.decorate_and_register(
                    task_id=task_id,
                    py_func=py_func,
                    jitter=jitter,
                    jitter_kwargs=jitter_kwargs,
                    tags=tags
                )
            return jitter.decorate(py_func, tags=tags)

        jitted_func = jitter.decorate(jitable_setup.py_func, tags=jitable_setup.tags)
        self.register_jitted_setup(jitable_setup, jitter, jitted_func)

        return jitted_func

    def resolve_option(self, task_id: tp.Union[tp.Hashable, tp.Callable],
                       option: tp.JittedOption, **kwargs) -> tp.Union[tp.Hashable, tp.Callable]:
        """Resolve `option` using `vectorbt.utils.jitting.resolve_jitted_kwargs` and call `JITRegistry.resolve`."""
        kwargs = resolve_jitted_kwargs(option=option, **kwargs)
        if kwargs is None:
            kwargs = dict(disable=True)
        return self.resolve(task_id, **kwargs)


jit_registry = JITRegistry()
"""Default registry of type `JITRegistry`."""


def register_jitted(py_func: tp.Optional[tp.Callable] = None,
                    task_id_or_func: tp.Optional[tp.Union[tp.Hashable, tp.Callable]] = None,
                    registry: JITRegistry = jit_registry,
                    tags: tp.Optional[set] = None,
                    **options) -> tp.Callable:
    """Decorate and register a jitable function using `JITRegistry.decorate_and_register`.

    If `task_id_or_func` is a callable, gets replaced by the callable's module name and function name.
    Additionally, the function name may contain a suffix pointing at the jitter (such as `_nb`).

    Options are merged in the following order:

    * `your_jitter.options` in `vectorbt._settings.settings`
    * `**options`
    * `your_jitter.task_options` in `vectorbt._settings.settings` with task id as key
    * `your_jitter.override_options` in `vectorbt._settings.settings`"""

    def decorator(_py_func: tp.Callable) -> tp.Callable:
        nonlocal options

        from vectorbt._settings import settings
        jitting_cfg = settings['jitting']

        wrapped_task_id = _py_func.__module__ + '.' + _py_func.__name__
        if task_id_or_func is None:
            task_id = wrapped_task_id
        elif hasattr(task_id_or_func, 'py_func'):
            task_id = task_id_or_func.py_func.__module__ + '.' + task_id_or_func.py_func.__name__
        elif callable(task_id_or_func):
            task_id = task_id_or_func.__module__ + '.' + task_id_or_func.__name__
        else:
            task_id = task_id_or_func

        jitter = options.pop('jitter', None)
        jitter_type = resolve_jitter_type(jitter=jitter, py_func=_py_func)
        jitter_id = get_id_of_jitter_type(jitter_type)

        jitter_cfg = jitting_cfg['jitters'].get(jitter_id, {})
        if len(jitter_cfg.get('options', {})) > 0:
            options = merge_dicts(jitter_cfg['options'], options)
        if len(jitter_cfg.get('override_setup_options', {})) > 0:
            override_setup_options = jitter_cfg['override_setup_options'].get(task_id, {})
            if len(override_setup_options) > 0:
                options = merge_dicts(options, override_setup_options)
        if len(jitter_cfg.get('override_options', {})) > 0:
            options = merge_dicts(options, jitter_cfg['override_options'])

        return registry.decorate_and_register(
            task_id=task_id,
            py_func=_py_func,
            jitter=jitter,
            jitter_kwargs=options,
            tags=tags
        )

    if py_func is None:
        return decorator
    return decorator(py_func)