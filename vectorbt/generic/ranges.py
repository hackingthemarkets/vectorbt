# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Base class for working with range records.

Range records capture information on ranges. They are useful for analyzing duration of processes,
such as drawdowns, trades, and positions. They also come in handy when analyzing distance between events,
such as entry and exit signals.

Each range has a starting point and an ending point. For example, the points for `range(20)`
are 0 and 20 (not 19!) respectively.

!!! note
    Be aware that if a range hasn't ended in a column, its `end_idx` will point at the latest index.
    Make sure to account for this when computing custom metrics involving duration.

```python-repl
>>> import vectorbt as vbt
>>> import numpy as np
>>> import pandas as pd

>>> start = '2019-01-01 UTC'  # crypto is in UTC
>>> end = '2020-01-01 UTC'
>>> price = vbt.YFData.fetch('BTC-USD', start=start, end=end).get('Close')
>>> fast_ma = vbt.MA.run(price, 10)
>>> slow_ma = vbt.MA.run(price, 50)
>>> fast_below_slow = fast_ma.ma_above(slow_ma)

>>> ranges = vbt.Ranges.from_ts(fast_below_slow, wrapper_kwargs=dict(freq='d'))

>>> ranges.records_readable
   Range Id  Column           Start Timestamp             End Timestamp  \\
0         0       0 2019-02-19 00:00:00+00:00 2019-07-25 00:00:00+00:00
1         1       0 2019-08-08 00:00:00+00:00 2019-08-19 00:00:00+00:00
2         2       0 2019-11-01 00:00:00+00:00 2019-11-20 00:00:00+00:00

   Status
0  Closed
1  Closed
2  Closed

>>> ranges.duration.max(wrap_kwargs=dict(to_timedelta=True))
Timedelta('156 days 00:00:00')
```

## From accessors

Moreover, all generic accessors have a property `ranges` and a method `get_ranges`:

```python-repl
>>> # vectorbt.generic.accessors.GenericAccessor.ranges.coverage
>>> fast_below_slow.vbt.ranges.coverage
0.5081967213114754
```

## Stats

!!! hint
    See `vectorbt.generic.stats_builder.StatsBuilderMixin.stats` and `Ranges.metrics`.

```python-repl
>>> df = pd.DataFrame({
...     'a': [1, 2, np.nan, np.nan, 5, 6],
...     'b': [np.nan, 2, np.nan, 4, np.nan, 6]
... })
>>> ranges = df.vbt(freq='d').ranges

>>> ranges['a'].stats()
Start                             0
End                               5
Period              6 days 00:00:00
Coverage            4 days 00:00:00
Overlap Coverage    0 days 00:00:00
Total Records                     2
Duration: Min       2 days 00:00:00
Duration: Median    2 days 00:00:00
Duration: Max       2 days 00:00:00
Duration: Mean      2 days 00:00:00
Duration: Std       0 days 00:00:00
Name: a, dtype: object
```

`Ranges.stats` also supports (re-)grouping:

```python-repl
>>> ranges.stats(group_by=True)
Start                                       0
End                                         5
Period                        6 days 00:00:00
Coverage                      5 days 00:00:00
Overlap Coverage              2 days 00:00:00
Total Records                               5
Duration: Min                 1 days 00:00:00
Duration: Median              1 days 00:00:00
Duration: Max                 2 days 00:00:00
Duration: Mean                1 days 09:36:00
Duration: Std       0 days 13:08:43.228968446
Name: group, dtype: object
```

## Plots

!!! hint
    See `vectorbt.generic.plots_builder.PlotsBuilderMixin.plots` and `Ranges.subplots`.

`Ranges` class has a single subplot based on `Ranges.plot`:

```python-repl
>>> ranges['a'].plots()
```

![](/docs/img/ranges_plots.svg)
"""

import numpy as np

from vectorbt import _typing as tp
from vectorbt.base.reshaping import to_pd_array, to_2d_array
from vectorbt.base.wrapping import ArrayWrapper
from vectorbt.ch_registry import ch_registry
from vectorbt.generic import nb
from vectorbt.generic.enums import RangeStatus, range_dt
from vectorbt.jit_registry import jit_registry
from vectorbt.records.base import Records
from vectorbt.records.decorators import override_field_config, attach_fields, attach_shortcut_properties
from vectorbt.records.mapped_array import MappedArray
from vectorbt.utils.colors import adjust_lightness
from vectorbt.utils.config import resolve_dict, merge_dicts, Config, ReadonlyConfig, HybridConfig

__pdoc__ = {}

ranges_field_config = ReadonlyConfig(
    dict(
        dtype=range_dt,
        settings=dict(
            id=dict(
                title='Range Id'
            ),
            idx=dict(
                name='end_idx'  # remap field of Records
            ),
            start_idx=dict(
                title='Start Timestamp',
                mapping='index'
            ),
            end_idx=dict(
                title='End Timestamp',
                mapping='index'
            ),
            status=dict(
                title='Status',
                mapping=RangeStatus
            )
        )
    )
)
"""_"""

__pdoc__['ranges_field_config'] = f"""Field config for `Ranges`.

```json
{ranges_field_config.stringify()}
```
"""

ranges_attach_field_config = ReadonlyConfig(
    dict(
        status=dict(
            attach_filters=True
        )
    )
)
"""_"""

__pdoc__['ranges_attach_field_config'] = f"""Config of fields to be attached to `Ranges`.

```json
{ranges_attach_field_config.stringify()}
```
"""

ranges_shortcut_config = ReadonlyConfig(
    dict(
        mask=dict(
            obj_type='array'
        ),
        duration=dict(
            obj_type='mapped_array'
        ),
        avg_duration=dict(
            obj_type='red_array'
        ),
        max_duration=dict(
            obj_type='red_array'
        ),
        coverage=dict(
            obj_type='red_array'
        ),
        overlap_coverage=dict(
            method_name='get_coverage',
            obj_type='red_array',
            method_kwargs=dict(overlapping=True)
        )
    )
)
"""_"""

__pdoc__['ranges_shortcut_config'] = f"""Config of shortcut properties to be attached to `Ranges`.

```json
{ranges_shortcut_config.stringify()}
```
"""

RangesT = tp.TypeVar("RangesT", bound="Ranges")


@attach_shortcut_properties(ranges_shortcut_config)
@attach_fields(ranges_attach_field_config)
@override_field_config(ranges_field_config)
class Ranges(Records):
    """Extends `Records` for working with range records.

    Requires `records_arr` to have all fields defined in `vectorbt.generic.enums.range_dt`."""

    @property
    def field_config(self) -> Config:
        return self._field_config

    @classmethod
    def from_records(cls: tp.Type[RangesT],
                     wrapper: ArrayWrapper,
                     records: tp.RecordArray,
                     ts: tp.Optional[tp.ArrayLike] = None,
                     attach_ts: bool = True,
                     **kwargs) -> RangesT:
        """Build `Trades` from records."""
        return cls(wrapper, records, ts=ts if attach_ts else None, **kwargs)

    def __init__(self,
                 wrapper: ArrayWrapper,
                 records_arr: tp.RecordArray,
                 ts: tp.Optional[tp.SeriesFrame] = None,
                 **kwargs) -> None:
        Records.__init__(
            self,
            wrapper,
            records_arr,
            ts=ts,
            **kwargs
        )
        self._ts = ts

    def indexing_func(self: RangesT, pd_indexing_func: tp.PandasIndexingFunc, **kwargs) -> RangesT:
        """Perform indexing on `Ranges`."""
        new_wrapper, new_records_arr, _, col_idxs = \
            Records.indexing_func_meta(self, pd_indexing_func, **kwargs)
        if self.ts is not None:
            new_ts = to_2d_array(self.ts)[:, col_idxs]
        else:
            new_ts = None
        return self.replace(
            wrapper=new_wrapper,
            records_arr=new_records_arr,
            ts=new_ts
        )

    @classmethod
    def from_ts(cls: tp.Type[RangesT],
                ts: tp.ArrayLike,
                gap_value: tp.Optional[tp.Scalar] = None,
                attach_ts: bool = True,
                jitted: tp.JittedOption = None,
                chunked: tp.ChunkedOption = None,
                wrapper_kwargs: tp.KwargsLike = None,
                **kwargs) -> RangesT:
        """Build `Ranges` from time series `ts`.

        Searches for sequences of

        * True values in boolean data (False acts as a gap),
        * positive values in integer data (-1 acts as a gap), and
        * non-NaN values in any other data (NaN acts as a gap).

        `**kwargs` will be passed to `Ranges.__init__`."""
        if wrapper_kwargs is None:
            wrapper_kwargs = {}

        ts_pd = to_pd_array(ts)
        ts_arr = to_2d_array(ts_pd)
        if gap_value is None:
            if np.issubdtype(ts_arr.dtype, np.bool_):
                gap_value = False
            elif np.issubdtype(ts_arr.dtype, np.integer):
                gap_value = -1
            else:
                gap_value = np.nan
        func = jit_registry.resolve_option(nb.get_ranges_nb, jitted)
        func = ch_registry.resolve_option(func, chunked)
        records_arr = func(ts_arr, gap_value)
        wrapper = ArrayWrapper.from_obj(ts_pd, **wrapper_kwargs)
        return cls(wrapper, records_arr, ts=ts_pd if attach_ts else None, **kwargs)

    @property
    def ts(self) -> tp.Optional[tp.SeriesFrame]:
        """Original time series that records are built from (optional)."""
        if self._ts is None:
            return None
        return self.wrapper.wrap(self._ts, group_by=False)

    def get_mask(self,
                group_by: tp.GroupByLike = None,
                jitted: tp.JittedOption = None,
                chunked: tp.ChunkedOption = None,
                wrap_kwargs: tp.KwargsLike = None) -> tp.SeriesFrame:
        """Get mask from ranges.

        See `vectorbt.generic.nb.ranges_to_mask_nb`."""
        col_map = self.col_mapper.get_col_map(group_by=group_by)
        func = jit_registry.resolve_option(nb.ranges_to_mask_nb, jitted)
        func = ch_registry.resolve_option(func, chunked)
        mask = func(
            self.get_field_arr('start_idx'),
            self.get_field_arr('end_idx'),
            self.get_field_arr('status'),
            col_map,
            len(self.wrapper.index)
        )
        return self.wrapper.wrap(mask, group_by=group_by, **resolve_dict(wrap_kwargs))

    def get_duration(self,
                     jitted: tp.JittedOption = None,
                     chunked: tp.ChunkedOption = None,
                     **kwargs) -> MappedArray:
        """Get duration of each range (in raw format)."""
        func = jit_registry.resolve_option(nb.range_duration_nb, jitted)
        func = ch_registry.resolve_option(func, chunked)
        duration = func(
            self.get_field_arr('start_idx'),
            self.get_field_arr('end_idx'),
            self.get_field_arr('status')
        )
        return self.map_array(duration, **kwargs)

    def get_avg_duration(self,
                         group_by: tp.GroupByLike = None,
                         jitted: tp.JittedOption = None,
                         chunked: tp.ChunkedOption = None,
                         wrap_kwargs: tp.KwargsLike = None,
                         **kwargs) -> tp.MaybeSeries:
        """Get average range duration (as timedelta)."""
        wrap_kwargs = merge_dicts(dict(to_timedelta=True, name_or_index='avg_duration'), wrap_kwargs)
        return self.duration.mean(
            group_by=group_by,
            jitted=jitted,
            chunked=chunked,
            wrap_kwargs=wrap_kwargs,
            **kwargs
        )

    def get_max_duration(self,
                         group_by: tp.GroupByLike = None,
                         jitted: tp.JittedOption = None,
                         chunked: tp.ChunkedOption = None,
                         wrap_kwargs: tp.KwargsLike = None,
                         **kwargs) -> tp.MaybeSeries:
        """Get maximum range duration (as timedelta)."""
        wrap_kwargs = merge_dicts(dict(to_timedelta=True, name_or_index='max_duration'), wrap_kwargs)
        return self.duration.max(
            group_by=group_by,
            jitted=jitted,
            chunked=chunked,
            wrap_kwargs=wrap_kwargs,
            **kwargs
        )

    def get_coverage(self,
                     overlapping: bool = False,
                     normalize: bool = True,
                     group_by: tp.GroupByLike = None,
                     jitted: tp.JittedOption = None,
                     chunked: tp.ChunkedOption = None,
                     wrap_kwargs: tp.KwargsLike = None) -> tp.MaybeSeries:
        """Get coverage, that is, the number of steps that are covered by all ranges.

        See `vectorbt.generic.nb.range_coverage_nb`."""
        col_map = self.col_mapper.get_col_map(group_by=group_by)
        index_lens = self.wrapper.grouper.get_group_lens(group_by=group_by) * self.wrapper.shape[0]
        func = jit_registry.resolve_option(nb.range_coverage_nb, jitted)
        func = ch_registry.resolve_option(func, chunked)
        coverage = func(
            self.get_field_arr('start_idx'),
            self.get_field_arr('end_idx'),
            self.get_field_arr('status'),
            col_map,
            index_lens,
            overlapping=overlapping,
            normalize=normalize
        )
        wrap_kwargs = merge_dicts(dict(name_or_index='coverage'), wrap_kwargs)
        return self.wrapper.wrap_reduced(coverage, group_by=group_by, **wrap_kwargs)

    # ############# Stats ############# #

    @property
    def stats_defaults(self) -> tp.Kwargs:
        """Defaults for `Ranges.stats`.

        Merges `vectorbt.records.base.Records.stats_defaults` and
        `ranges.stats` from `vectorbt._settings.settings`."""
        from vectorbt._settings import settings
        ranges_stats_cfg = settings['ranges']['stats']

        return merge_dicts(
            Records.stats_defaults.__get__(self),
            ranges_stats_cfg
        )

    _metrics: tp.ClassVar[Config] = HybridConfig(
        dict(
            start=dict(
                title='Start',
                calc_func=lambda self: self.wrapper.index[0],
                agg_func=None,
                tags='wrapper'
            ),
            end=dict(
                title='End',
                calc_func=lambda self: self.wrapper.index[-1],
                agg_func=None,
                tags='wrapper'
            ),
            period=dict(
                title='Period',
                calc_func=lambda self: len(self.wrapper.index),
                apply_to_timedelta=True,
                agg_func=None,
                tags='wrapper'
            ),
            coverage=dict(
                title='Coverage',
                calc_func='coverage',
                overlapping=False,
                normalize=False,
                apply_to_timedelta=True,
                tags=['ranges', 'coverage']
            ),
            overlap_coverage=dict(
                title='Overlap Coverage',
                calc_func='coverage',
                overlapping=True,
                normalize=False,
                apply_to_timedelta=True,
                tags=['ranges', 'coverage']
            ),
            total_records=dict(
                title='Total Records',
                calc_func='count',
                tags='records'
            ),
            duration=dict(
                title='Duration',
                calc_func='duration.describe',
                post_calc_func=lambda self, out, settings: {
                    'Min': out.loc['min'],
                    'Median': out.loc['50%'],
                    'Max': out.loc['max'],
                    'Mean': out.loc['mean'],
                    'Std': out.loc['std']
                },
                apply_to_timedelta=True,
                tags=['ranges', 'duration']
            ),
        )
    )

    @property
    def metrics(self) -> Config:
        return self._metrics

    # ############# Plotting ############# #

    def plot(self,
             column: tp.Optional[tp.Label] = None,
             top_n: int = 5,
             plot_zones: bool = True,
             ts_trace_kwargs: tp.KwargsLike = None,
             start_trace_kwargs: tp.KwargsLike = None,
             end_trace_kwargs: tp.KwargsLike = None,
             open_shape_kwargs: tp.KwargsLike = None,
             closed_shape_kwargs: tp.KwargsLike = None,
             add_trace_kwargs: tp.KwargsLike = None,
             xref: str = 'x',
             yref: str = 'y',
             fig: tp.Optional[tp.BaseFigure] = None,
             **layout_kwargs) -> tp.BaseFigure:  # pragma: no cover
        """Plot ranges.

        Args:
            column (str): Name of the column to plot.
            top_n (int): Filter top N range records by maximum duration.
            plot_zones (bool): Whether to plot zones.
            ts_trace_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Scatter` for `Ranges.ts`.
            start_trace_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Scatter` for start values.
            end_trace_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Scatter` for end values.
            open_shape_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Figure.add_shape` for open zones.
            closed_shape_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Figure.add_shape` for closed zones.
            add_trace_kwargs (dict): Keyword arguments passed to `add_trace`.
            xref (str): X coordinate axis.
            yref (str): Y coordinate axis.
            fig (Figure or FigureWidget): Figure to add traces to.
            **layout_kwargs: Keyword arguments for layout.

        ## Example

        ```python-repl
        >>> import vectorbt as vbt
        >>> from datetime import datetime, timedelta
        >>> import pandas as pd

        >>> price = pd.Series([1, 2, 1, 2, 3, 2, 1, 2], name='Price')
        >>> price.index = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(len(price))]
        >>> vbt.Ranges.from_ts(price >= 2, wrapper_kwargs=dict(freq='1 day')).plot()
        ```

        ![](/docs/img/ranges_plot.svg)
        """
        from vectorbt.opt_packages import assert_can_import
        assert_can_import('plotly')
        import plotly.graph_objects as go
        from vectorbt.utils.figure import make_figure, get_domain
        from vectorbt._settings import settings
        plotting_cfg = settings['plotting']

        self_col = self.select_one(column=column, group_by=False)
        if top_n is not None:
            self_col = self_col.apply_mask(self_col.duration.top_n_mask(top_n))

        if ts_trace_kwargs is None:
            ts_trace_kwargs = {}
        ts_trace_kwargs = merge_dicts(dict(
            line=dict(
                color=plotting_cfg['color_schema']['blue']
            )
        ), ts_trace_kwargs)
        if start_trace_kwargs is None:
            start_trace_kwargs = {}
        if end_trace_kwargs is None:
            end_trace_kwargs = {}
        if open_shape_kwargs is None:
            open_shape_kwargs = {}
        if closed_shape_kwargs is None:
            closed_shape_kwargs = {}
        if add_trace_kwargs is None:
            add_trace_kwargs = {}

        if fig is None:
            fig = make_figure()
        fig.update_layout(**layout_kwargs)
        y_domain = get_domain(yref, fig)

        if self_col.ts is not None:
            fig = self_col.ts.vbt.plot(trace_kwargs=ts_trace_kwargs, add_trace_kwargs=add_trace_kwargs, fig=fig)

        if self_col.count() > 0:
            # Extract information
            id_ = self_col.get_field_arr('id')
            id_title = self_col.get_field_title('id')

            start_idx = self_col.get_map_field_to_index('start_idx')
            start_idx_title = self_col.get_field_title('start_idx')
            if self_col.ts is not None:
                start_val = self_col.ts.loc[start_idx]
            else:
                start_val = np.full(len(start_idx), 0)

            end_idx = self_col.get_map_field_to_index('end_idx')
            end_idx_title = self_col.get_field_title('end_idx')
            if self_col.ts is not None:
                end_val = self_col.ts.loc[end_idx]
            else:
                end_val = np.full(len(end_idx), 0)

            duration = np.vectorize(str)(self_col.wrapper.to_timedelta(
                self_col.duration.values, to_pd=True, silence_warnings=True))

            status = self_col.get_field_arr('status')

            # Plot start markers
            start_customdata = id_[:, None]
            start_scatter = go.Scatter(
                x=start_idx,
                y=start_val,
                mode='markers',
                marker=dict(
                    symbol='diamond',
                    color=plotting_cfg['contrast_color_schema']['blue'],
                    size=7,
                    line=dict(
                        width=1,
                        color=adjust_lightness(plotting_cfg['contrast_color_schema']['blue'])
                    )
                ),
                name='Start',
                customdata=start_customdata,
                hovertemplate=f"{id_title}: %{{customdata[0]}}"
                              f"<br>{start_idx_title}: %{{x}}"
            )
            start_scatter.update(**start_trace_kwargs)
            fig.add_trace(start_scatter, **add_trace_kwargs)

            closed_mask = status == RangeStatus.Closed
            if closed_mask.any():
                # Plot end markers
                closed_end_customdata = np.stack((
                    id_[closed_mask],
                    duration[closed_mask]
                ), axis=1)
                closed_end_scatter = go.Scatter(
                    x=end_idx[closed_mask],
                    y=end_val[closed_mask],
                    mode='markers',
                    marker=dict(
                        symbol='diamond',
                        color=plotting_cfg['contrast_color_schema']['green'],
                        size=7,
                        line=dict(
                            width=1,
                            color=adjust_lightness(plotting_cfg['contrast_color_schema']['green'])
                        )
                    ),
                    name='Closed',
                    customdata=closed_end_customdata,
                    hovertemplate=f"{id_title}: %{{customdata[0]}}"
                                  f"<br>{end_idx_title}: %{{x}}"
                                  f"<br>Duration: %{{customdata[1]}}"
                )
                closed_end_scatter.update(**end_trace_kwargs)
                fig.add_trace(closed_end_scatter, **add_trace_kwargs)

                if plot_zones:
                    # Plot closed range zones
                    for i in range(len(id_[closed_mask])):
                        fig.add_shape(**merge_dicts(dict(
                            type="rect",
                            xref=xref,
                            yref="paper",
                            x0=start_idx[closed_mask][i],
                            y0=y_domain[0],
                            x1=end_idx[closed_mask][i],
                            y1=y_domain[1],
                            fillcolor='teal',
                            opacity=0.2,
                            layer="below",
                            line_width=0,
                        ), closed_shape_kwargs))

            open_mask = status == RangeStatus.Open
            if open_mask.any():
                # Plot end markers
                open_end_customdata = np.stack((
                    id_[open_mask],
                    duration[open_mask]
                ), axis=1)
                open_end_scatter = go.Scatter(
                    x=end_idx[open_mask],
                    y=end_val[open_mask],
                    mode='markers',
                    marker=dict(
                        symbol='diamond',
                        color=plotting_cfg['contrast_color_schema']['orange'],
                        size=7,
                        line=dict(
                            width=1,
                            color=adjust_lightness(plotting_cfg['contrast_color_schema']['orange'])
                        )
                    ),
                    name='Open',
                    customdata=open_end_customdata,
                    hovertemplate=f"{id_title}: %{{customdata[0]}}"
                                  f"<br>{end_idx_title}: %{{x}}"
                                  f"<br>Duration: %{{customdata[1]}}"
                )
                open_end_scatter.update(**end_trace_kwargs)
                fig.add_trace(open_end_scatter, **add_trace_kwargs)

                if plot_zones:
                    # Plot open range zones
                    for i in range(len(id_[open_mask])):
                        fig.add_shape(**merge_dicts(dict(
                            type="rect",
                            xref=xref,
                            yref="paper",
                            x0=start_idx[open_mask][i],
                            y0=y_domain[0],
                            x1=end_idx[open_mask][i],
                            y1=y_domain[1],
                            fillcolor='orange',
                            opacity=0.2,
                            layer="below",
                            line_width=0,
                        ), open_shape_kwargs))

        return fig

    @property
    def plots_defaults(self) -> tp.Kwargs:
        """Defaults for `Ranges.plots`.

        Merges `vectorbt.records.base.Records.plots_defaults` and
        `ranges.plots` from `vectorbt._settings.settings`."""
        from vectorbt._settings import settings
        ranges_plots_cfg = settings['ranges']['plots']

        return merge_dicts(
            Records.plots_defaults.__get__(self),
            ranges_plots_cfg
        )

    _subplots: tp.ClassVar[Config] = Config(
        dict(
            plot=dict(
                title="Ranges",
                check_is_not_grouped=True,
                plot_func='plot',
                tags='ranges'
            )
        )
    )

    @property
    def subplots(self) -> Config:
        return self._subplots


Ranges.override_field_config_doc(__pdoc__)
Ranges.override_metrics_doc(__pdoc__)
Ranges.override_subplots_doc(__pdoc__)
