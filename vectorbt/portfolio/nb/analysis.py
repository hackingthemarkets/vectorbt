# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Numba-compiled functions.

Provides an arsenal of Numba-compiled functions that are used for portfolio
modeling, such as generating and filling orders. These only accept NumPy arrays and
other Numba-compatible types.

!!! note
    vectorbt treats matrices as first-class citizens and expects input arrays to be
    2-dim, unless function has suffix `_1d` or is meant to be input to another function.

    All functions passed as argument must be Numba-compiled.

    Records must retain the order they were created in.

!!! warning
    Accumulation of roundoff error possible.
    See [here](https://en.wikipedia.org/wiki/Round-off_error#Accumulation_of_roundoff_error) for explanation.

    Rounding errors can cause trades and positions to not close properly.

    Example:

        >>> print('%.50f' % 0.1)  # has positive error
        0.10000000000000000555111512312578270211815834045410

        >>> # many buy transactions with positive error -> cannot close position
        >>> sum([0.1 for _ in range(1000000)]) - 100000
        1.3328826753422618e-06

        >>> print('%.50f' % 0.3)  # has negative error
        0.29999999999999998889776975374843459576368331909180

        >>> # many sell transactions with negative error -> cannot close position
        >>> 300000 - sum([0.3 for _ in range(1000000)])
        5.657668225467205e-06

    While vectorbt has implemented tolerance checks when comparing floats for equality,
    adding/subtracting small amounts large number of times may still introduce a noticable
    error that cannot be corrected post factum.

    To mitigate this issue, avoid repeating lots of micro-transactions of the same sign.
    For example, reduce by `np.inf` or `position_now` to close a long/short position.

    See `vectorbt.utils.math_` for current tolerance values.
"""

from numba import prange

from vectorbt.base import chunking as base_ch
from vectorbt.ch_registry import register_chunkable
from vectorbt.portfolio import chunking as portfolio_ch
from vectorbt.portfolio.nb.core import *
from vectorbt.records import chunking as records_ch
from vectorbt.returns import nb as returns_nb_
from vectorbt.utils import chunking as ch
from vectorbt.utils.math_ import is_close_nb, add_nb
from vectorbt.utils.template import RepFunc


# ############# Assets ############# #


@register_jitted(cache=True)
def get_long_size_nb(position_before: float, position_now: float) -> float:
    """Get long size."""
    if position_before <= 0 and position_now <= 0:
        return 0.
    if position_before >= 0 and position_now < 0:
        return -position_before
    if position_before < 0 and position_now >= 0:
        return position_now
    return add_nb(position_now, -position_before)


@register_jitted(cache=True)
def get_short_size_nb(position_before: float, position_now: float) -> float:
    """Get short size."""
    if position_before >= 0 and position_now >= 0:
        return 0.
    if position_before >= 0 and position_now < 0:
        return -position_now
    if position_before < 0 and position_now >= 0:
        return position_before
    return add_nb(position_before, -position_now)


@register_chunkable(
    size=records_ch.ColLensSizer(arg_query='col_map'),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1),
        order_records=ch.ArraySlicer(axis=0, mapper=records_ch.col_idxs_mapper),
        col_map=records_ch.ColMapSlicer(),
        init_position=base_ch.FlexArraySlicer(axis=1, flex_2d=True),
        direction=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def asset_flow_nb(target_shape: tp.Shape,
                  order_records: tp.RecordArray,
                  col_map: tp.ColMap,
                  init_position: tp.FlexArray = np.asarray(0.),
                  direction: int = Direction.Both) -> tp.Array2d:
    """Get asset flow series per column.

    Returns the total transacted amount of assets at each time step."""
    col_idxs, col_lens = col_map
    col_start_idxs = np.cumsum(col_lens) - col_lens
    out = np.full(target_shape, 0., dtype=np.float_)

    for col in prange(col_lens.shape[0]):
        col_len = col_lens[col]
        if col_len == 0:
            continue
        last_id = -1
        position_now = flex_select_auto_nb(init_position, 0, col, True)

        for c in range(col_len):
            order_record = order_records[col_idxs[col_start_idxs[col] + c]]

            if order_record['id'] < last_id:
                raise ValueError("Ids must come in ascending order per column")
            last_id = order_record['id']

            i = order_record['idx']
            side = order_record['side']
            size = order_record['size']

            if side == OrderSide.Sell:
                size *= -1
            new_position_now = add_nb(position_now, size)
            if direction == Direction.LongOnly:
                asset_flow = get_long_size_nb(position_now, new_position_now)
            elif direction == Direction.ShortOnly:
                asset_flow = get_short_size_nb(position_now, new_position_now)
            else:
                asset_flow = size
            out[i, col] = add_nb(out[i, col], asset_flow)
            position_now = new_position_now
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='asset_flow', axis=1),
    arg_take_spec=dict(
        asset_flow=ch.ArraySlicer(axis=1),
        init_position=base_ch.FlexArraySlicer(axis=1, flex_2d=True)
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def assets_nb(asset_flow: tp.Array2d, init_position: tp.FlexArray = np.asarray(0.)) -> tp.Array2d:
    """Get asset series per column.

    Returns the current position at each time step."""
    out = np.empty_like(asset_flow)
    for col in prange(asset_flow.shape[1]):
        position_now = flex_select_auto_nb(init_position, 0, col, True)
        for i in range(asset_flow.shape[0]):
            flow_value = asset_flow[i, col]
            position_now = add_nb(position_now, flow_value)
            out[i, col] = position_now
    return out


@register_jitted(cache=True)
def longonly_assets_nb(assets: tp.Array2d) -> tp.Array2d:
    """Get long-only assets."""
    return np.where(assets > 0, assets, 0.)


@register_jitted(cache=True)
def shortonly_assets_nb(assets: tp.Array2d) -> tp.Array2d:
    """Get short-only assets."""
    return np.where(assets < 0, -assets, 0.)


@register_jitted
def position_mask_grouped_nb(position_mask: tp.Array2d, group_lens: tp.Array1d) -> tp.Array2d:
    """Get whether in position for each row and group."""
    return generic_nb.squeeze_grouped_nb(position_mask, group_lens, generic_nb.any_reduce_nb)


@register_jitted
def position_coverage_grouped_nb(position_mask: tp.Array2d, group_lens: tp.Array1d) -> tp.Array2d:
    """Get coverage of position for each row and group."""
    return generic_nb.reduce_grouped_nb(position_mask, group_lens, generic_nb.mean_reduce_nb)


# ############# Cash ############# #


@register_jitted(cache=True)
def get_free_cash_diff_nb(position_before: float,
                          position_now: float,
                          debt_now: float,
                          price: float,
                          fees: float) -> tp.Tuple[float, float]:
    """Get updated debt and free cash flow."""
    size = add_nb(position_now, -position_before)
    final_cash = -size * price - fees
    if is_close_nb(size, 0):
        new_debt = debt_now
        free_cash_diff = 0.
    elif size > 0:
        if position_before < 0:
            if position_now < 0:
                short_size = abs(size)
            else:
                short_size = abs(position_before)
            avg_entry_price = debt_now / abs(position_before)
            debt_diff = short_size * avg_entry_price
            new_debt = add_nb(debt_now, -debt_diff)
            free_cash_diff = add_nb(2 * debt_diff, final_cash)
        else:
            new_debt = debt_now
            free_cash_diff = final_cash
    else:
        if position_now < 0:
            if position_before < 0:
                short_size = abs(size)
            else:
                short_size = abs(position_now)
            short_value = short_size * price
            new_debt = debt_now + short_value
            free_cash_diff = add_nb(final_cash, -2 * short_value)
        else:
            new_debt = debt_now
            free_cash_diff = final_cash
    return new_debt, free_cash_diff


@register_chunkable(
    size=records_ch.ColLensSizer(arg_query='col_map'),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1),
        order_records=ch.ArraySlicer(axis=0, mapper=records_ch.col_idxs_mapper),
        col_map=records_ch.ColMapSlicer(),
        free=None,
        cash_earnings=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def cash_flow_nb(target_shape: tp.Shape,
                 order_records: tp.RecordArray,
                 col_map: tp.ColMap,
                 free: bool = False,
                 cash_earnings: tp.FlexArray = np.asarray(0.),
                 flex_2d: bool = False) -> tp.Array2d:
    """Get (free) cash flow series per column."""
    col_idxs, col_lens = col_map
    col_start_idxs = np.cumsum(col_lens) - col_lens
    out = np.empty(target_shape, dtype=np.float_)

    for col in prange(target_shape[1]):
        for i in range(target_shape[0]):
            out[i, col] = flex_select_auto_nb(cash_earnings, i, col, flex_2d)

    for col in prange(col_lens.shape[0]):
        col_len = col_lens[col]
        if col_len == 0:
            continue
        last_id = -1
        position_now = 0.
        debt_now = 0.

        for c in range(col_len):
            order_record = order_records[col_idxs[col_start_idxs[col] + c]]

            if order_record['id'] < last_id:
                raise ValueError("Ids must come in ascending order per column")
            last_id = order_record['id']

            i = order_record['idx']
            side = order_record['side']
            size = order_record['size']
            price = order_record['price']
            fees = order_record['fees']

            if side == OrderSide.Sell:
                size *= -1
            new_position_now = add_nb(position_now, size)
            if free:
                debt_now, cash_flow = get_free_cash_diff_nb(
                    position_now,
                    new_position_now,
                    debt_now,
                    price,
                    fees
                )
            else:
                cash_flow = -size * price - fees
            out[i, col] = add_nb(out[i, col], cash_flow)
            position_now = new_position_now
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='group_lens', axis=0),
    arg_take_spec=dict(
        arr=ch.ArraySlicer(axis=1, mapper=base_ch.group_lens_mapper),
        group_lens=ch.ArraySlicer(axis=0)
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def sum_grouped_nb(arr: tp.Array2d, group_lens: tp.Array1d) -> tp.Array2d:
    """Squeeze each group of columns into a single column using sum operation."""
    check_group_lens_nb(group_lens, arr.shape[1])
    out = np.empty((arr.shape[0], len(group_lens)), dtype=np.float_)
    group_end_idxs = np.cumsum(group_lens)
    group_start_idxs = group_end_idxs - group_lens

    for group in prange(len(group_lens)):
        from_col = group_start_idxs[group]
        to_col = group_end_idxs[group]
        out[:, group] = np.sum(arr[:, from_col:to_col], axis=1)
    return out


@register_jitted(cache=True)
def cash_flow_grouped_nb(cash_flow: tp.Array2d, group_lens: tp.Array1d) -> tp.Array2d:
    """Get cash flow series per group."""
    return sum_grouped_nb(cash_flow, group_lens)


@register_chunkable(
    size=ch.ArraySizer(arg_query='cash_flow', axis=1),
    arg_take_spec=dict(
        init_cash_raw=None,
        cash_flow=ch.ArraySlicer(axis=1)
    ),
    merge_func=base_ch.concat
)
@register_jitted(cache=True, tags={'can_parallel'})
def align_init_cash_nb(init_cash_raw: int, cash_flow: tp.Array2d) -> tp.Array1d:
    """Align initial cash."""
    out = np.empty(cash_flow.shape[1], dtype=np.float_)
    for col in range(cash_flow.shape[1]):
        cash = 0.
        min_req_cash = np.inf
        for i in range(cash_flow.shape[0]):
            cash += cash_flow[i, col]
            if cash < min_req_cash:
                min_req_cash = cash
        if min_req_cash < 0:
            out[col] = np.abs(min_req_cash)
        else:
            out[col] = 0.
    if init_cash_raw == InitCashMode.AutoAlign:
        out = np.full(out.shape, np.max(out))
    return out


@register_jitted(cache=True)
def init_cash_grouped_nb(init_cash_raw: tp.FlexArray, group_lens: tp.Array1d, cash_sharing: bool) -> tp.Array1d:
    """Get initial cash per group."""
    out = np.empty(group_lens.shape, dtype=np.float_)
    if cash_sharing:
        for group in range(len(group_lens)):
            out[group] = flex_select_auto_nb(init_cash_raw, 0, group, True)
    else:
        from_col = 0
        for group in range(len(group_lens)):
            to_col = from_col + group_lens[group]
            cash_sum = 0.
            for col in range(from_col, to_col):
                cash_sum += flex_select_auto_nb(init_cash_raw, 0, col, True)
            out[group] = cash_sum
            from_col = to_col
    return out


@register_jitted(cache=True)
def init_cash_nb(init_cash_raw: tp.FlexArray, group_lens: tp.Array1d,
                 cash_sharing: bool, split_shared: bool = False) -> tp.Array1d:
    """Get initial cash per column."""
    out = np.empty(np.sum(group_lens), dtype=np.float_)
    if not cash_sharing:
        for col in range(out.shape[0]):
            out[col] = flex_select_auto_nb(init_cash_raw, 0, col, True)
    else:
        from_col = 0
        for group in range(len(group_lens)):
            to_col = from_col + group_lens[group]
            group_len = to_col - from_col
            _init_cash = flex_select_auto_nb(init_cash_raw, 0, group, True)
            for col in range(from_col, to_col):
                if split_shared:
                    out[col] = _init_cash / group_len
                else:
                    out[col] = _init_cash
            from_col = to_col
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='group_lens', axis=0),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1, mapper=base_ch.group_lens_mapper),
        cash_deposits_raw=RepFunc(portfolio_ch.get_cash_deposits_slicer),
        group_lens=ch.ArraySlicer(axis=0),
        cash_sharing=None,
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def cash_deposits_grouped_nb(target_shape: tp.Shape,
                             cash_deposits_raw: tp.FlexArray,
                             group_lens: tp.Array1d,
                             cash_sharing: bool,
                             flex_2d: bool = False) -> tp.Array2d:
    """Get cash deposit series per group."""
    out = np.empty((target_shape[0], len(group_lens)), dtype=np.float_)
    if cash_sharing:
        for group in prange(len(group_lens)):
            for i in range(target_shape[0]):
                out[i, group] = flex_select_auto_nb(cash_deposits_raw, i, group, flex_2d)
    else:
        group_end_idxs = np.cumsum(group_lens)
        group_start_idxs = group_end_idxs - group_lens
        for group in prange(len(group_lens)):
            from_col = group_start_idxs[group]
            to_col = group_end_idxs[group]
            for i in range(target_shape[0]):
                cash_sum = 0.
                for col in range(from_col, to_col):
                    cash_sum += flex_select_auto_nb(cash_deposits_raw, i, col, flex_2d)
                out[i, group] = cash_sum
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='group_lens', axis=0),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1, mapper=base_ch.group_lens_mapper),
        cash_deposits_raw=RepFunc(portfolio_ch.get_cash_deposits_slicer),
        group_lens=ch.ArraySlicer(axis=0),
        cash_sharing=None,
        split_shared=None,
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def cash_deposits_nb(target_shape: tp.Shape,
                     cash_deposits_raw: tp.FlexArray,
                     group_lens: tp.Array1d,
                     cash_sharing: bool,
                     split_shared: bool = False,
                     flex_2d: bool = False) -> tp.Array2d:
    """Get cash deposit series per column."""
    out = np.empty(target_shape, dtype=np.float_)
    if not cash_sharing:
        for col in prange(target_shape[1]):
            for i in range(target_shape[0]):
                out[i, col] = flex_select_auto_nb(cash_deposits_raw, i, col, flex_2d)
    else:
        group_end_idxs = np.cumsum(group_lens)
        group_start_idxs = group_end_idxs - group_lens
        for group in prange(len(group_lens)):
            from_col = group_start_idxs[group]
            to_col = group_end_idxs[group]
            for i in range(target_shape[0]):
                _cash_deposits = flex_select_auto_nb(cash_deposits_raw, i, group, flex_2d)
                for col in range(from_col, to_col):
                    if split_shared:
                        out[i, col] = _cash_deposits / (to_col - from_col)
                    else:
                        out[i, col] = _cash_deposits
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='cash_flow', axis=1),
    arg_take_spec=dict(
        cash_flow=ch.ArraySlicer(axis=1),
        init_cash=base_ch.FlexArraySlicer(axis=1, flex_2d=True),
        cash_deposits=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def cash_nb(cash_flow: tp.Array2d,
            init_cash: tp.FlexArray,
            cash_deposits: tp.FlexArray = np.asarray(0.),
            flex_2d: bool = False) -> tp.Array2d:
    """Get cash series per column."""
    out = np.empty_like(cash_flow)
    for col in prange(cash_flow.shape[1]):
        for i in range(cash_flow.shape[0]):
            if i == 0:
                cash_now = flex_select_auto_nb(init_cash, 0, col, True)
            else:
                cash_now = out[i - 1, col]
            cash_now = add_nb(cash_now, flex_select_auto_nb(cash_deposits, i, col, flex_2d))
            cash_now = add_nb(cash_now, cash_flow[i, col])
            out[i, col] = cash_now
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='group_lens', axis=0),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1, mapper=base_ch.group_lens_mapper),
        cash_flow_grouped=ch.ArraySlicer(axis=1),
        group_lens=ch.ArraySlicer(axis=0),
        init_cash_grouped=base_ch.FlexArraySlicer(axis=1, flex_2d=True),
        cash_deposits_grouped=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def cash_grouped_nb(target_shape: tp.Shape,
                    cash_flow_grouped: tp.Array2d,
                    group_lens: tp.Array1d,
                    init_cash_grouped: tp.FlexArray,
                    cash_deposits_grouped: tp.FlexArray = np.asarray(0.),
                    flex_2d: bool = False) -> tp.Array2d:
    """Get cash series per group."""
    check_group_lens_nb(group_lens, target_shape[1])
    out = np.empty_like(cash_flow_grouped)

    for group in prange(len(group_lens)):
        cash_now = flex_select_auto_nb(init_cash_grouped, 0, group, True)
        for i in range(cash_flow_grouped.shape[0]):
            flow_value = cash_flow_grouped[i, group]
            cash_now = add_nb(cash_now, flex_select_auto_nb(cash_deposits_grouped, i, group, flex_2d))
            cash_now = add_nb(cash_now, flow_value)
            out[i, group] = cash_now
    return out


# ############# Value ############# #


@register_jitted(cache=True)
def init_position_value_nb(close: tp.Array2d, init_position: tp.FlexArray = np.asarray(0.)) -> tp.Array1d:
    """Get initial position value per column."""
    out = np.empty(close.shape[1], dtype=np.float_)
    for col in range(close.shape[1]):
        out[col] = close[0, col] * flex_select_auto_nb(init_position, 0, col, True)
    return out


@register_jitted(cache=True)
def init_value_nb(init_position_value: tp.Array1d, init_cash: tp.FlexArray) -> tp.Array1d:
    """Get initial value per column."""
    out = np.empty(len(init_position_value), dtype=np.float_)
    for col in range(len(init_position_value)):
        _init_cash = flex_select_auto_nb(init_cash, 0, col, True)
        out[col] = _init_cash + init_position_value[col]
    return out


@register_jitted(cache=True)
def init_value_grouped_nb(group_lens: tp.Array1d,
                          init_position_value: tp.Array1d,
                          init_cash_grouped: tp.FlexArray) -> tp.Array1d:
    """Get initial value per group."""
    check_group_lens_nb(group_lens, len(init_position_value))
    out = np.empty(len(group_lens), dtype=np.float_)

    from_col = 0
    for group in range(len(group_lens)):
        to_col = from_col + group_lens[group]
        group_value = flex_select_auto_nb(init_cash_grouped, 0, group, True)
        for col in range(from_col, to_col):
            group_value += init_position_value[col]
        out[group] = group_value
        from_col = to_col
    return out


@register_jitted(cache=True)
def asset_value_nb(close: tp.Array2d, assets: tp.Array2d) -> tp.Array2d:
    """Get asset value series per column."""
    return close * assets


@register_jitted(cache=True)
def asset_value_grouped_nb(asset_value: tp.Array2d, group_lens: tp.Array1d) -> tp.Array2d:
    """Get asset value series per group."""
    return sum_grouped_nb(asset_value, group_lens)


@register_chunkable(
    size=ch.ArraySizer(arg_query='asset_value', axis=1),
    arg_take_spec=dict(
        asset_value=ch.ArraySlicer(axis=1),
        cash=ch.ArraySlicer(axis=1)
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def gross_exposure_nb(asset_value: tp.Array2d, cash: tp.Array2d) -> tp.Array2d:
    """Get gross exposure per column/group."""
    out = np.empty(asset_value.shape, dtype=np.float_)
    for col in prange(asset_value.shape[1]):
        for i in range(asset_value.shape[0]):
            denom = add_nb(asset_value[i, col], cash[i, col])
            if denom == 0:
                out[i, col] = 0.
            else:
                out[i, col] = asset_value[i, col] / denom
    return out


@register_jitted(cache=True)
def value_nb(cash: tp.Array2d, asset_value: tp.Array2d) -> tp.Array2d:
    """Get portfolio value series per column/group."""
    return cash + asset_value


@register_chunkable(
    size=records_ch.ColLensSizer(arg_query='col_map'),
    arg_take_spec=dict(
        target_shape=ch.ShapeSlicer(axis=1),
        close=ch.ArraySlicer(axis=1),
        order_records=ch.ArraySlicer(axis=0, mapper=records_ch.col_idxs_mapper),
        col_map=records_ch.ColMapSlicer(),
        init_position=base_ch.FlexArraySlicer(axis=1, flex_2d=True),
        cash_earnings=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.concat
)
@register_jitted(cache=True, tags={'can_parallel'})
def total_profit_nb(target_shape: tp.Shape,
                    close: tp.Array2d,
                    order_records: tp.RecordArray,
                    col_map: tp.ColMap,
                    init_position: tp.FlexArray = np.asarray(0.),
                    cash_earnings: tp.FlexArray = np.asarray(0.),
                    flex_2d: bool = False) -> tp.Array1d:
    """Get total profit per column.

    A much faster version than the one based on `value_nb`."""
    col_idxs, col_lens = col_map
    col_start_idxs = np.cumsum(col_lens) - col_lens
    assets = np.full(target_shape[1], 0., dtype=np.float_)
    cash = np.full(target_shape[1], 0., dtype=np.float_)
    zero_mask = np.full(target_shape[1], False, dtype=np.bool_)

    for col in prange(target_shape[1]):
        _init_position = flex_select_auto_nb(init_position, 0, col, True)
        if _init_position != 0:
            assets[col] = _init_position
            cash[col] = -close[0, col] * _init_position

        for i in range(target_shape[0]):
            cash[col] += flex_select_auto_nb(cash_earnings, i, col, flex_2d)

    for col in prange(col_lens.shape[0]):
        col_len = col_lens[col]
        if col_len == 0:
            zero_mask[col] = assets[col] == 0 and cash[col] == 0
            continue
        last_id = -1

        for c in range(col_len):
            order_record = order_records[col_idxs[col_start_idxs[col] + c]]

            if order_record['id'] < last_id:
                raise ValueError("Ids must come in ascending order per column")
            last_id = order_record['id']

            # Fill assets
            if order_record['side'] == OrderSide.Buy:
                order_size = order_record['size']
                assets[col] = add_nb(assets[col], order_size)
            else:
                order_size = order_record['size']
                assets[col] = add_nb(assets[col], -order_size)

            # Fill cash balance
            if order_record['side'] == OrderSide.Buy:
                order_cash = order_record['size'] * order_record['price'] + order_record['fees']
                cash[col] = add_nb(cash[col], -order_cash)
            else:
                order_cash = order_record['size'] * order_record['price'] - order_record['fees']
                cash[col] = add_nb(cash[col], order_cash)

    total_profit = cash + assets * close[-1, :]
    total_profit[zero_mask] = 0.
    return total_profit


@register_jitted(cache=True)
def total_profit_grouped_nb(total_profit: tp.Array1d, group_lens: tp.Array1d) -> tp.Array1d:
    """Get total profit per group."""
    check_group_lens_nb(group_lens, total_profit.shape[0])
    out = np.empty(len(group_lens), dtype=np.float_)

    from_col = 0
    for group in range(len(group_lens)):
        to_col = from_col + group_lens[group]
        out[group] = np.sum(total_profit[from_col:to_col])
        from_col = to_col
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='value', axis=1),
    arg_take_spec=dict(
        value=ch.ArraySlicer(axis=1),
        init_value=ch.ArraySlicer(axis=0),
        cash_deposits=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def returns_nb(value: tp.Array2d,
               init_value: tp.Array1d,
               cash_deposits: tp.FlexArray = np.asarray(0.),
               flex_2d: bool = False) -> tp.Array2d:
    """Get return series per column/group."""
    out = np.empty(value.shape, dtype=np.float_)
    for col in prange(value.shape[1]):
        input_value = init_value[col]
        for i in range(value.shape[0]):
            output_value = value[i, col]
            adj_output_value = output_value - flex_select_auto_nb(cash_deposits, i, col, flex_2d)
            out[i, col] = returns_nb_.get_return_nb(input_value, adj_output_value)
            input_value = output_value
    return out


@register_jitted(cache=True)
def get_asset_return_nb(input_asset_value: float, output_asset_value: float, cash_flow: float) -> float:
    """Get asset return from the input and output asset value, and the cash flow."""
    if is_close_nb(input_asset_value, 0):
        return returns_nb_.get_return_nb(-output_asset_value, cash_flow)
    if is_close_nb(output_asset_value, 0):
        return returns_nb_.get_return_nb(input_asset_value, cash_flow)
    if np.sign(input_asset_value) != np.sign(output_asset_value):
        return returns_nb_.get_return_nb(input_asset_value - output_asset_value, cash_flow)
    return returns_nb_.get_return_nb(input_asset_value, output_asset_value + cash_flow)


@register_chunkable(
    size=ch.ArraySizer(arg_query='init_position_value', axis=0),
    arg_take_spec=dict(
        init_position_value=ch.ArraySlicer(axis=0),
        asset_value=ch.ArraySlicer(axis=1),
        cash_flow=ch.ArraySlicer(axis=1)
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def asset_returns_nb(init_position_value: tp.Array1d, asset_value: tp.Array2d, cash_flow: tp.Array2d) -> tp.Array2d:
    """Get asset return series per column/group."""
    out = np.empty_like(cash_flow)
    for col in prange(cash_flow.shape[1]):
        for i in range(cash_flow.shape[0]):
            if i == 0:
                input_asset_value = 0.
                _cash_flow = cash_flow[i, col] - init_position_value[col]
            else:
                input_asset_value = asset_value[i - 1, col]
                _cash_flow = cash_flow[i, col]
            out[i, col] = get_asset_return_nb(input_asset_value, asset_value[i, col], _cash_flow)
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='close', axis=1),
    arg_take_spec=dict(
        close=ch.ArraySlicer(axis=1),
        init_value=base_ch.ArraySlicer(axis=0),
        cash_deposits=base_ch.FlexArraySlicer(axis=1),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def market_value_nb(close: tp.Array2d,
                    init_value: tp.Array1d,
                    cash_deposits: tp.FlexArray = np.asarray(0.),
                    flex_2d: bool = False) -> tp.Array2d:
    """Get market value per column."""
    out = np.empty_like(close)
    for col in prange(close.shape[1]):
        curr_value = init_value[col]
        for i in range(close.shape[0]):
            if i > 0:
                curr_value *= close[i, col] / close[i - 1, col]
            curr_value += flex_select_auto_nb(cash_deposits, i, col, flex_2d)
            out[i, col] = curr_value
    return out


@register_chunkable(
    size=ch.ArraySizer(arg_query='group_lens', axis=0),
    arg_take_spec=dict(
        close=ch.ArraySlicer(axis=1, mapper=base_ch.group_lens_mapper),
        group_lens=ch.ArraySlicer(axis=0),
        init_value=ch.ArraySlicer(axis=0, mapper=base_ch.group_lens_mapper),
        cash_deposits=base_ch.FlexArraySlicer(axis=1, mapper=base_ch.group_lens_mapper),
        flex_2d=None
    ),
    merge_func=base_ch.column_stack
)
@register_jitted(cache=True, tags={'can_parallel'})
def market_value_grouped_nb(close: tp.Array2d,
                            group_lens: tp.Array1d,
                            init_value: tp.Array1d,
                            cash_deposits: tp.FlexArray = np.asarray(0.),
                            flex_2d: bool = False) -> tp.Array2d:
    """Get market value per group."""
    check_group_lens_nb(group_lens, close.shape[1])
    out = np.empty((close.shape[0], len(group_lens)), dtype=np.float_)
    temp = np.empty(close.shape[1], dtype=np.float_)
    group_end_idxs = np.cumsum(group_lens)
    group_start_idxs = group_end_idxs - group_lens

    for group in prange(len(group_lens)):
        from_col = group_start_idxs[group]
        to_col = group_end_idxs[group]

        for i in range(close.shape[0]):
            for col in range(from_col, to_col):
                if i == 0:
                    temp[col] = init_value[col]
                else:
                    temp[col] *= close[i, col] / close[i - 1, col]
                temp[col] += flex_select_auto_nb(cash_deposits, i, col, flex_2d)
            out[i, group] = np.sum(temp[from_col:to_col])
    return out
