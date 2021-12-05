# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Extensions to `vectorbt.utils.chunking`."""

import numpy as np

from vectorbt import _typing as tp
from vectorbt.base.chunking import GroupLensMapper, FlexArraySlicer, group_lens_mapper
from vectorbt.portfolio.enums import SimulationOutput
from vectorbt.records.chunking import merge_records
from vectorbt.utils.chunking import ChunkMeta, ArraySlicer
from vectorbt.utils.config import ReadonlyConfig
from vectorbt.utils.template import Rep

flex_1d_array_gl_slicer = FlexArraySlicer(axis=1, mapper=group_lens_mapper, flex_2d=True)
"""Flexible 1-dim array slicer along the column axis based on group lengths."""

flex_array_gl_slicer = FlexArraySlicer(axis=1, mapper=group_lens_mapper)
"""Flexible 2-dim array slicer along the column axis based on group lengths."""


def get_init_cash_slicer(ann_args: tp.AnnArgs) -> ArraySlicer:
    """Get slicer for `init_cash` based on cash sharing."""
    cash_sharing = ann_args['cash_sharing']['value']
    if cash_sharing:
        return FlexArraySlicer(axis=0, flex_2d=True)
    return flex_1d_array_gl_slicer


def get_cash_deposits_slicer(ann_args: tp.AnnArgs) -> ArraySlicer:
    """Get slicer for `cash_deposits` based on cash sharing."""
    cash_sharing = ann_args['cash_sharing']['value']
    if cash_sharing:
        return FlexArraySlicer(axis=1)
    return flex_array_gl_slicer


def in_outputs_merge_func(results: tp.List[SimulationOutput],
                          chunk_meta: tp.Iterable[ChunkMeta],
                          ann_args: tp.AnnArgs,
                          mapper: GroupLensMapper):
    """Merge chunks of in-output objects.

    Concatenates 1-dim arrays, stacks columns of 2-dim arrays, and fixes and concatenates record arrays
    using `vectorbt.records.chunking.merge_records`. Other objects will throw an error."""
    in_outputs = dict()
    for k, v in results[0].in_outputs._asdict().items():
        if not isinstance(v, np.ndarray):
            raise TypeError(f"Cannot merge in-output object '{k}' of type {type(v)}")
        if v.ndim == 2:
            in_outputs[k] = np.column_stack([getattr(r.in_outputs, k) for r in results])
        elif v.ndim == 1:
            if v.dtype.fields is None:
                in_outputs[k] = np.concatenate([getattr(r.in_outputs, k) for r in results])
            else:
                records = [getattr(r.in_outputs, k) for r in results]
                in_outputs[k] = merge_records(records, chunk_meta, ann_args=ann_args, mapper=mapper)
        else:
            raise ValueError(f"Cannot merge in-output object '{k}' with number of dimensions {v.ndim}")
    return type(results[0].in_outputs)(**in_outputs)


def merge_sim_outs(results: tp.List[SimulationOutput],
                   chunk_meta: tp.Iterable[ChunkMeta],
                   ann_args: tp.AnnArgs,
                   mapper: GroupLensMapper,
                   in_outputs_merge_func: tp.Callable = in_outputs_merge_func,
                   **kwargs) -> SimulationOutput:
    """Merge chunks of `vectorbt.portfolio.enums.SimulationOutput` instances.

    If `SimulationOutput.in_outputs` is not None, must provide `in_outputs_merge_func` or similar."""
    order_records = [r.order_records for r in results]
    order_records = merge_records(order_records, chunk_meta, ann_args=ann_args, mapper=mapper)

    log_records = [r.log_records for r in results]
    log_records = merge_records(log_records, chunk_meta, ann_args=ann_args, mapper=mapper)

    target_shape = ann_args['target_shape']['value']
    if results[0].cash_earnings.shape == target_shape:
        cash_earnings = np.column_stack([r.cash_earnings for r in results])
    else:
        cash_earnings = results[0].cash_earnings
    if results[0].call_seq is not None:
        call_seq = np.column_stack([r.call_seq for r in results])
    else:
        call_seq = None
    if results[0].in_outputs is not None:
        in_outputs = in_outputs_merge_func(results, chunk_meta, ann_args, mapper, **kwargs)
    else:
        in_outputs = None
    return SimulationOutput(
        order_records=order_records,
        log_records=log_records,
        cash_earnings=cash_earnings,
        call_seq=call_seq,
        in_outputs=in_outputs
    )


merge_sim_outs_config = ReadonlyConfig(
    dict(
        merge_func=merge_sim_outs,
        merge_kwargs=dict(
            chunk_meta=Rep("chunk_meta"),
            ann_args=Rep("ann_args"),
            mapper=group_lens_mapper
        )
    )
)
"""Config for merging using `merge_sim_outs`."""
