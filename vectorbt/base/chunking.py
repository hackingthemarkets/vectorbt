# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Extensions to `vectorbt.utils.chunking`."""

import attr
import uuid

import numpy as np
from numba.typed import List

from vectorbt import _typing as tp
from vectorbt.utils.chunking import (
    ArgGetter,
    ChunkMeta,
    ChunkMapper,
    ArraySelector,
    ArraySlicer
)
from vectorbt.utils.parsing import match_ann_arg


def column_stack(results: list) -> tp.MaybeTuple[list]:
    """Stack columns from each array in results. Supports multiple arrays per result."""
    if isinstance(results[0], (tuple, list, List)):
        return tuple(map(np.column_stack, zip(*results)))
    return np.column_stack(results)


def row_stack(results: list) -> tp.MaybeTuple[list]:
    """Stack rows from each array in results. Supports multiple arrays per result."""
    if isinstance(results[0], (tuple, list, List)):
        return tuple(map(np.row_stack, zip(*results)))
    return np.row_stack(results)


def concat(results: list) -> tp.MaybeTuple[list]:
    """Concatenate elements from each array in results. Supports multiple arrays per result."""
    if isinstance(results[0], (tuple, list, List)):
        return tuple(map(np.concatenate, zip(*results)))
    return np.concatenate(results)


def get_group_lens_slice(group_lens: tp.Array1d, chunk_meta: ChunkMeta) -> slice:
    """Get slice of each chunk in group lengths."""
    group_lens_cumsum = np.cumsum(group_lens[:chunk_meta.end])
    start = group_lens_cumsum[chunk_meta.start] - group_lens[chunk_meta.start]
    end = group_lens_cumsum[-1]
    return slice(start, end)


@attr.s(frozen=True)
class GroupLensMapper(ChunkMapper, ArgGetter):
    """Class for mapping chunk metadata using group lengths."""

    arg_query: tp.AnnArgQuery = attr.ib(default='group_lens')

    def map(self, chunk_meta: ChunkMeta, ann_args: tp.Optional[tp.AnnArgs] = None, **kwargs) -> ChunkMeta:
        group_lens = self.get_arg(ann_args)
        group_lens_slice = get_group_lens_slice(group_lens, chunk_meta)
        return ChunkMeta(
            uuid=str(uuid.uuid4()),
            idx=chunk_meta.idx,
            start=group_lens_slice.start,
            end=group_lens_slice.stop,
            indices=None
        )


group_lens_mapper = GroupLensMapper()
"""Default instance of `GroupLensMapper`."""


@attr.s(frozen=True)
class FlexSpecifier:
    """Class with an attribute for specifying `flex_2d`."""

    flex_2d: tp.Union[bool, tp.AnnArgQuery] = attr.ib(default='flex_2d')
    """`flex_2d` or the query to match in the arguments."""

    def get_flex_2d(self, ann_args: tp.AnnArgs) -> bool:
        """Get `flex_2d` from the arguments."""
        if isinstance(self.flex_2d, bool):
            return self.flex_2d
        return match_ann_arg(ann_args, self.flex_2d)


@attr.s(frozen=True)
class FlexArraySelector(ArraySelector, FlexSpecifier):
    """Class for selecting one element from a NumPy array's axis flexibly based on the chunk index.

    The result is intended to be used together with `vectorbt.base.indexing.flex_select_auto_nb`."""

    def take(self, obj: tp.ArrayLike, chunk_meta: ChunkMeta,
             ann_args: tp.Optional[tp.AnnArgs] = None, **kwargs) -> tp.ArrayLike:
        flex_2d = self.get_flex_2d(ann_args)
        obj = np.asarray(obj)
        if obj.ndim == 0:
            return obj
        if obj.ndim == 1:
            if obj.shape[0] == 1:
                return obj
            if self.axis == 1:
                if flex_2d:
                    if self.keep_dims:
                        return obj[chunk_meta.idx:chunk_meta.idx + 1]
                    return obj[chunk_meta.idx]
                return obj
            if flex_2d:
                return obj
            if self.keep_dims:
                return obj[chunk_meta.idx:chunk_meta.idx + 1]
            return obj[chunk_meta.idx]
        if obj.ndim == 2:
            if self.axis == 1:
                if obj.shape[1] == 1:
                    return obj
                if self.keep_dims:
                    return obj[: chunk_meta.idx:chunk_meta.idx + 1]
                return obj[: chunk_meta.idx]
            if obj.shape[0] == 1:
                return obj
            if self.keep_dims:
                return obj[chunk_meta.idx:chunk_meta.idx + 1, :]
            return obj[chunk_meta.idx, :]
        raise ValueError(f"FlexArraySelector supports max 2 dimensions, not {obj.ndim}")


@attr.s(frozen=True)
class FlexArraySlicer(ArraySlicer, FlexSpecifier):
    """Class for selecting one element from a NumPy array's axis flexibly based on the chunk index.

    The result is intended to be used together with `vectorbt.base.indexing.flex_select_auto_nb`."""

    def take(self, obj: tp.ArrayLike, chunk_meta: ChunkMeta,
             ann_args: tp.Optional[tp.AnnArgs] = None, **kwargs) -> tp.ArrayLike:
        flex_2d = self.get_flex_2d(ann_args)
        obj = np.asarray(obj)
        if obj.ndim == 0:
            return obj
        if obj.ndim == 1:
            if obj.shape[0] == 1:
                return obj
            if self.axis == 1:
                if flex_2d:
                    return obj[chunk_meta.start:chunk_meta.end]
                return obj
            if flex_2d:
                return obj
            return obj[chunk_meta.start:chunk_meta.end]
        if obj.ndim == 2:
            if self.axis == 1:
                if obj.shape[1] == 1:
                    return obj
                return obj[:, chunk_meta.start:chunk_meta.end]
            if obj.shape[0] == 1:
                return obj
            return obj[chunk_meta.start:chunk_meta.end, :]
        raise ValueError(f"FlexArraySlicer supports max 2 dimensions, not {obj.ndim}")
