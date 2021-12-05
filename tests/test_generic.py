import os
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from numba import njit
from sklearn.model_selection import TimeSeriesSplit

import vectorbt as vbt
from vectorbt.generic import nb

seed = 42

day_dt = np.timedelta64(86400000000000)

df = pd.DataFrame({
    'a': [1, 2, 3, 4, np.nan],
    'b': [np.nan, 4, 3, 2, 1],
    'c': [1, 2, np.nan, 2, 1]
}, index=pd.DatetimeIndex([
    datetime(2018, 1, 1),
    datetime(2018, 1, 2),
    datetime(2018, 1, 3),
    datetime(2018, 1, 4),
    datetime(2018, 1, 5)
]))
group_by = np.array(['g1', 'g1', 'g2'])


# ############# Global ############# #

def setup_module():
    if os.environ.get('VBT_DISABLE_CACHING', '0') == '1':
        vbt.settings.caching['disable_machinery'] = True
    vbt.settings.pbar['disable'] = True
    vbt.settings.numba['check_func_suffix'] = True
    vbt.settings.chunking['n_chunks'] = 2


def teardown_module():
    vbt.settings.reset()


# ############# accessors.py ############# #


class TestAccessors:
    def test_indexing(self):
        assert df.vbt['a'].min() == df['a'].vbt.min()

    def test_set_by_mask(self):
        np.testing.assert_array_equal(
            nb.set_by_mask_1d_nb(
                np.array([1, 2, 3, 1, 2, 3]),
                np.array([True, False, False, True, False, False]),
                0
            ),
            np.array([0, 2, 3, 0, 2, 3])
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_1d_nb(
                np.array([1, 2, 3, 1, 2, 3]),
                np.array([True, False, False, True, False, False]),
                0.
            ),
            np.array([0., 2., 3., 0., 2., 3.])
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_nb(
                np.array([1, 2, 3, 1, 2, 3])[:, None],
                np.array([True, False, False, True, False, False])[:, None],
                0
            ),
            np.array([0, 2, 3, 0, 2, 3])[:, None]
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_nb(
                np.array([1, 2, 3, 1, 2, 3])[:, None],
                np.array([True, False, False, True, False, False])[:, None],
                0.
            ),
            np.array([0., 2., 3., 0., 2., 3.])[:, None]
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_mult_1d_nb(
                np.array([1, 2, 3, 1, 2, 3]),
                np.array([True, False, False, True, False, False]),
                np.array([0, -1, -1, 0, -1, -1])
            ),
            np.array([0, 2, 3, 0, 2, 3])
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_mult_1d_nb(
                np.array([1, 2, 3, 1, 2, 3]),
                np.array([True, False, False, True, False, False]),
                np.array([0., -1., -1., 0., -1., -1.])
            ),
            np.array([0., 2., 3., 0., 2., 3.])
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_mult_nb(
                np.array([1, 2, 3, 1, 2, 3])[:, None],
                np.array([True, False, False, True, False, False])[:, None],
                np.array([0, -1, -1, 0, -1, -1])[:, None]
            ),
            np.array([0, 2, 3, 0, 2, 3])[:, None]
        )
        np.testing.assert_array_equal(
            nb.set_by_mask_mult_nb(
                np.array([1, 2, 3, 1, 2, 3])[:, None],
                np.array([True, False, False, True, False, False])[:, None],
                np.array([0., -1., -1., 0., -1., -1.])[:, None]
            ),
            np.array([0., 2., 3., 0., 2., 3.])[:, None]
        )

    def test_shuffle(self):
        pd.testing.assert_series_equal(
            df['a'].vbt.shuffle(seed=seed),
            pd.Series(
                np.array([2.0, np.nan, 3.0, 1.0, 4.0]),
                index=df['a'].index,
                name=df['a'].name
            )
        )
        np.testing.assert_array_equal(
            df['a'].vbt.shuffle(seed=seed).values,
            nb.shuffle_1d_nb(df['a'].values, seed=seed)
        )
        pd.testing.assert_frame_equal(
            df.vbt.shuffle(seed=seed),
            pd.DataFrame(
                np.array([
                    [2., 2., 2.],
                    [np.nan, 4., 1.],
                    [3., 3., 2.],
                    [1., np.nan, 1.],
                    [4., 1., np.nan]
                ]),
                index=df.index,
                columns=df.columns
            )
        )

    @pytest.mark.parametrize(
        "test_value",
        [-1, 0., np.nan],
    )
    def test_fillna(self, test_value):
        pd.testing.assert_series_equal(df['a'].vbt.fillna(test_value), df['a'].fillna(test_value))
        pd.testing.assert_frame_equal(df.vbt.fillna(test_value), df.fillna(test_value))
        pd.testing.assert_series_equal(
            pd.Series([1, 2, 3]).vbt.fillna(-1),
            pd.Series([1, 2, 3]))
        pd.testing.assert_series_equal(
            pd.Series([False, True, False]).vbt.fillna(False),
            pd.Series([False, True, False]))
        pd.testing.assert_frame_equal(
            df.vbt.fillna(test_value, chunked=True),
            df.vbt.fillna(test_value, chunked=False)
        )

    @pytest.mark.parametrize(
        "test_n",
        [1, 2, 3, 4, 5],
    )
    def test_bshift(self, test_n):
        pd.testing.assert_series_equal(df['a'].vbt.bshift(test_n), df['a'].shift(-test_n))
        np.testing.assert_array_equal(
            df['a'].vbt.bshift(test_n).values,
            nb.bshift_1d_nb(df['a'].values, test_n)
        )
        pd.testing.assert_frame_equal(df.vbt.bshift(test_n), df.shift(-test_n))
        pd.testing.assert_series_equal(
            pd.Series([1, 2, 3]).vbt.bshift(1, fill_value=-1),
            pd.Series([2, 3, -1])
        )
        pd.testing.assert_series_equal(
            pd.Series([True, True, True]).vbt.bshift(1, fill_value=False),
            pd.Series([True, True, False])
        )
        pd.testing.assert_frame_equal(
            df.vbt.bshift(test_n, chunked=True),
            df.vbt.bshift(test_n, chunked=False)
        )

    @pytest.mark.parametrize(
        "test_n",
        [1, 2, 3, 4, 5],
    )
    def test_fshift(self, test_n):
        pd.testing.assert_series_equal(df['a'].vbt.fshift(test_n), df['a'].shift(test_n))
        np.testing.assert_array_equal(
            df['a'].vbt.fshift(test_n).values,
            nb.fshift_1d_nb(df['a'].values, test_n)
        )
        pd.testing.assert_frame_equal(df.vbt.fshift(test_n), df.shift(test_n))
        pd.testing.assert_series_equal(
            pd.Series([1, 2, 3]).vbt.fshift(1, fill_value=-1),
            pd.Series([-1, 1, 2])
        )
        pd.testing.assert_series_equal(
            pd.Series([True, True, True]).vbt.fshift(1, fill_value=False),
            pd.Series([False, True, True])
        )
        pd.testing.assert_frame_equal(
            df.vbt.fshift(test_n, chunked=True),
            df.vbt.fshift(test_n, chunked=False)
        )

    def test_diff(self):
        pd.testing.assert_series_equal(df['a'].vbt.diff(), df['a'].diff())
        np.testing.assert_array_equal(df['a'].vbt.diff().values, nb.diff_1d_nb(df['a'].values))
        pd.testing.assert_frame_equal(df.vbt.diff(), df.diff())
        pd.testing.assert_frame_equal(df.vbt.diff(
            jitted=dict(parallel=True)), df.vbt.diff(jitted=dict(parallel=False)))
        pd.testing.assert_frame_equal(df.vbt.diff(chunked=True), df.vbt.diff(chunked=False))

    def test_pct_change(self):
        pd.testing.assert_series_equal(df['a'].vbt.pct_change(), df['a'].pct_change(fill_method=None))
        np.testing.assert_array_equal(df['a'].vbt.pct_change().values, nb.pct_change_1d_nb(df['a'].values))
        pd.testing.assert_frame_equal(df.vbt.pct_change(), df.pct_change(fill_method=None))
        pd.testing.assert_frame_equal(df.vbt.pct_change(
            jitted=dict(parallel=True)), df.vbt.pct_change(jitted=dict(parallel=False)))
        pd.testing.assert_frame_equal(df.vbt.pct_change(chunked=True), df.vbt.pct_change(chunked=False))

    def test_bfill(self):
        pd.testing.assert_series_equal(df['b'].vbt.bfill(), df['b'].bfill())
        pd.testing.assert_frame_equal(df.vbt.bfill(), df.bfill())
        pd.testing.assert_frame_equal(df.vbt.bfill(chunked=True), df.vbt.bfill(chunked=False))

    def test_ffill(self):
        pd.testing.assert_series_equal(df['a'].vbt.ffill(), df['a'].ffill())
        pd.testing.assert_frame_equal(df.vbt.ffill(), df.ffill())
        pd.testing.assert_frame_equal(df.vbt.ffill(chunked=True), df.vbt.ffill(chunked=False))

    def test_product(self):
        assert df['a'].vbt.product() == df['a'].product()
        pd.testing.assert_series_equal(df.vbt.product(), df.product().rename('product'))
        pd.testing.assert_series_equal(df.vbt.product(
            jitted=dict(parallel=True)), df.vbt.product(jitted=dict(parallel=False)))
        pd.testing.assert_series_equal(df.vbt.product(chunked=True), df.vbt.product(chunked=False))

    def test_cumsum(self):
        pd.testing.assert_series_equal(df['a'].vbt.cumsum(), df['a'].cumsum().ffill().fillna(0))
        pd.testing.assert_frame_equal(df.vbt.cumsum(), df.cumsum().ffill().fillna(0))
        pd.testing.assert_frame_equal(df.vbt.cumsum(
            jitted=dict(parallel=True)), df.vbt.cumsum(jitted=dict(parallel=False)))
        pd.testing.assert_frame_equal(df.vbt.cumsum(chunked=True), df.vbt.cumsum(chunked=False))

    def test_cumprod(self):
        pd.testing.assert_series_equal(df['a'].vbt.cumprod(), df['a'].cumprod().ffill().fillna(1))
        pd.testing.assert_frame_equal(df.vbt.cumprod(), df.cumprod().ffill().fillna(1))
        pd.testing.assert_frame_equal(df.vbt.cumprod(
            jitted=dict(parallel=True)), df.vbt.cumprod(jitted=dict(parallel=False)))
        pd.testing.assert_frame_equal(df.vbt.cumprod(chunked=True), df.vbt.cumprod(chunked=False))

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    def test_rolling_min(self, test_window, test_minp):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.rolling_min(test_window, minp=test_minp),
            df['a'].rolling(test_window, min_periods=test_minp).min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_min(test_window, minp=test_minp),
            df.rolling(test_window, min_periods=test_minp).min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_min(test_window),
            df.rolling(test_window).min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_min(test_window, jitted=dict(parallel=True)),
            df.vbt.rolling_min(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_min(test_window, chunked=True),
            df.vbt.rolling_min(test_window, chunked=False)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    def test_rolling_max(self, test_window, test_minp):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.rolling_max(test_window, minp=test_minp),
            df['a'].rolling(test_window, min_periods=test_minp).max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_max(test_window, minp=test_minp),
            df.rolling(test_window, min_periods=test_minp).max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_max(test_window),
            df.rolling(test_window).max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_max(test_window, jitted=dict(parallel=True)),
            df.vbt.rolling_max(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_max(test_window, chunked=True),
            df.vbt.rolling_max(test_window, chunked=False)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    def test_rolling_mean(self, test_window, test_minp):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.rolling_mean(test_window, minp=test_minp),
            df['a'].rolling(test_window, min_periods=test_minp).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_mean(test_window, minp=test_minp),
            df.rolling(test_window, min_periods=test_minp).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_mean(test_window),
            df.rolling(test_window).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_mean(test_window, jitted=dict(parallel=True)),
            df.vbt.rolling_mean(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_mean(test_window, chunked=True),
            df.vbt.rolling_mean(test_window, chunked=False)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    @pytest.mark.parametrize("test_ddof", [0, 1])
    def test_rolling_std(self, test_window, test_minp, test_ddof):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.rolling_std(test_window, minp=test_minp, ddof=test_ddof),
            df['a'].rolling(test_window, min_periods=test_minp).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_std(test_window, minp=test_minp, ddof=test_ddof),
            df.rolling(test_window, min_periods=test_minp).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_std(test_window),
            df.rolling(test_window).std()
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_std(test_window, jitted=dict(parallel=True)),
            df.vbt.rolling_std(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_std(test_window, chunked=True),
            df.vbt.rolling_std(test_window, chunked=False)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    @pytest.mark.parametrize("test_adjust", [False, True])
    def test_ewm_mean(self, test_window, test_minp, test_adjust):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.ewm_mean(test_window, minp=test_minp, adjust=test_adjust),
            df['a'].ewm(span=test_window, min_periods=test_minp, adjust=test_adjust).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_mean(test_window, minp=test_minp, adjust=test_adjust),
            df.ewm(span=test_window, min_periods=test_minp, adjust=test_adjust).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_mean(test_window),
            df.ewm(span=test_window).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_mean(test_window, jitted=dict(parallel=True)),
            df.vbt.ewm_mean(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_mean(test_window, chunked=True),
            df.vbt.ewm_mean(test_window, chunked=False)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    @pytest.mark.parametrize("test_adjust", [False, True])
    @pytest.mark.parametrize("test_ddof", [0, 1])
    def test_ewm_std(self, test_window, test_minp, test_adjust, test_ddof):
        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.ewm_std(test_window, minp=test_minp, adjust=test_adjust, ddof=test_ddof),
            df['a'].ewm(span=test_window, min_periods=test_minp, adjust=test_adjust).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_std(test_window, minp=test_minp, adjust=test_adjust, ddof=test_ddof),
            df.ewm(span=test_window, min_periods=test_minp, adjust=test_adjust).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_std(test_window),
            df.ewm(span=test_window).std()
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_std(test_window, jitted=dict(parallel=True)),
            df.vbt.ewm_std(test_window, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.ewm_std(test_window, chunked=True),
            df.vbt.ewm_std(test_window, chunked=False)
        )

    @pytest.mark.parametrize(
        "test_minp",
        [1, 3]
    )
    def test_expanding_min(self, test_minp):
        pd.testing.assert_series_equal(
            df['a'].vbt.expanding_min(minp=test_minp),
            df['a'].expanding(min_periods=test_minp).min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_min(minp=test_minp),
            df.expanding(min_periods=test_minp).min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_min(),
            df.expanding().min()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_min(jitted=dict(parallel=True)),
            df.vbt.expanding_min(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_min(chunked=True),
            df.vbt.expanding_min(chunked=False)
        )

    @pytest.mark.parametrize(
        "test_minp",
        [1, 3]
    )
    def test_expanding_max(self, test_minp):
        pd.testing.assert_series_equal(
            df['a'].vbt.expanding_max(minp=test_minp),
            df['a'].expanding(min_periods=test_minp).max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_max(minp=test_minp),
            df.expanding(min_periods=test_minp).max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_max(),
            df.expanding().max()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_max(jitted=dict(parallel=True)),
            df.vbt.expanding_max(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_max(chunked=True),
            df.vbt.expanding_max(chunked=False)
        )

    @pytest.mark.parametrize(
        "test_minp",
        [1, 3]
    )
    def test_expanding_mean(self, test_minp):
        pd.testing.assert_series_equal(
            df['a'].vbt.expanding_mean(minp=test_minp),
            df['a'].expanding(min_periods=test_minp).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_mean(minp=test_minp),
            df.expanding(min_periods=test_minp).mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_mean(),
            df.expanding().mean()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_mean(jitted=dict(parallel=True)),
            df.vbt.expanding_mean(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_mean(chunked=True),
            df.vbt.expanding_mean(chunked=False)
        )

    @pytest.mark.parametrize("test_minp", [1, 3])
    @pytest.mark.parametrize("test_ddof", [0, 1])
    def test_expanding_std(self, test_minp, test_ddof):
        pd.testing.assert_series_equal(
            df['a'].vbt.expanding_std(minp=test_minp, ddof=test_ddof),
            df['a'].expanding(min_periods=test_minp).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_std(minp=test_minp, ddof=test_ddof),
            df.expanding(min_periods=test_minp).std(ddof=test_ddof)
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_std(),
            df.expanding().std()
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_std(jitted=dict(parallel=True)),
            df.vbt.expanding_std(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_std(chunked=True),
            df.vbt.expanding_std(chunked=False)
        )

    def test_map(self):
        @njit
        def mult_nb(x, y):
            return x * y

        @njit
        def mult_meta_nb(i, col, x, y):
            return x[i, col] * y

        pd.testing.assert_series_equal(
            df['a'].vbt.map(mult_nb, 2),
            df['a'].map(lambda x: x * 2)
        )
        pd.testing.assert_frame_equal(
            df.vbt.map(mult_nb, 2),
            df.applymap(lambda x: x * 2)
        )
        pd.testing.assert_frame_equal(
            df.vbt.map(mult_nb, 2, jitted=dict(parallel=True)),
            df.vbt.map(mult_nb, 2, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(None)))
        pd.testing.assert_frame_equal(
            df.vbt.map(mult_nb, 2, chunked=chunked),
            df.vbt.map(mult_nb, 2, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.map(mult_meta_nb, df.vbt.to_2d_array(), 2, wrapper=df.vbt.wrapper),
            df.vbt.map(mult_nb, 2)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.map(
                mult_meta_nb, df.vbt.to_2d_array(), 2, wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.map(
                mult_meta_nb, df.vbt.to_2d_array(), 2, wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), None)))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.map(mult_meta_nb, df.vbt.to_2d_array(), 2, wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.map(mult_meta_nb, df.vbt.to_2d_array(), 2, wrapper=df.vbt.wrapper, chunked=False)
        )

        @njit
        def mult_meta2_nb(i, col, x, y):
            return x[i, col] * y[i, col]

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.map(
                mult_meta2_nb,
                vbt.RepEval("to_2d_array(x)"),
                vbt.RepEval("to_2d_array(y)"),
                broadcast_named_args=dict(
                    x=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    y=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array)
            ),
            pd.DataFrame([
                [1, 2, 3],
                [2, 4, 6],
                [3, 6, 9],
                [4, 8, 12],
                [5, 10, 15]
            ], index=df.index, columns=df.columns)
        )

    def test_apply_along_axis(self):
        @njit
        def pow_nb(x, y):
            return x ** y

        @njit
        def pow_meta_nb(col, x, y):
            return x[:, col] ** y

        @njit
        def row_pow_meta_nb(i, x, y):
            return x[i, :] ** y

        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=0),
            df.apply(pow_nb, args=(2,), axis=0, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=0, jitted=dict(parallel=True)),
            df.vbt.apply_along_axis(pow_nb, 2, axis=0, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(None)))
        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=0, chunked=chunked),
            df.vbt.apply_along_axis(pow_nb, 2, axis=0, chunked=False)
        )
        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=1),
            df.apply(pow_nb, args=(2,), axis=1, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=1, jitted=dict(parallel=True)),
            df.vbt.apply_along_axis(pow_nb, 2, axis=1, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.apply_along_axis(pow_nb, 2, axis=1, chunked=chunked),
            df.vbt.apply_along_axis(pow_nb, 2, axis=1, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                row_pow_meta_nb, df.vbt.to_2d_array(), 2, axis=0, wrapper=df.vbt.wrapper),
            df.vbt.apply_along_axis(pow_nb, 2, axis=0),
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                row_pow_meta_nb, df.vbt.to_2d_array(), 2, axis=0,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.apply_along_axis(
                row_pow_meta_nb, df.vbt.to_2d_array(), 2, axis=0,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=0), None)))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                row_pow_meta_nb, df.vbt.to_2d_array(), 2, axis=0, wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.apply_along_axis(
                row_pow_meta_nb, df.vbt.to_2d_array(), 2, axis=0, wrapper=df.vbt.wrapper, chunked=False),
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta_nb, df.vbt.to_2d_array(), 2, axis=1, wrapper=df.vbt.wrapper),
            df.vbt.apply_along_axis(pow_nb, 2, axis=1),
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta_nb, df.vbt.to_2d_array(), 2, axis=1, wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta_nb, df.vbt.to_2d_array(), 2, axis=1, wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), None)))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta_nb, df.vbt.to_2d_array(), 2, axis=1, wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta_nb, df.vbt.to_2d_array(), 2, axis=1, wrapper=df.vbt.wrapper, chunked=False),
        )

        @njit
        def pow_meta2_nb(col, x, y):
            return x[:, col] ** y[:, col]

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.apply_along_axis(
                pow_meta2_nb,
                vbt.RepEval("to_2d_array(x)"),
                vbt.RepEval("to_2d_array(y)"),
                broadcast_named_args=dict(
                    x=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    y=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array)
            ),
            pd.DataFrame([
                [1, 1, 1],
                [2, 4, 8],
                [3, 9, 27],
                [4, 16, 64],
                [5, 25, 125]
            ], index=df.index, columns=df.columns)
        )

    @pytest.mark.parametrize("test_window", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("test_minp", [1, None])
    def test_rolling_apply(self, test_window, test_minp):
        @njit
        def mean_nb(x):
            return np.nanmean(x)

        @njit
        def mean_meta_nb(from_i, to_i, col, x):
            return np.nanmean(x[from_i:to_i, col])

        if test_minp is None:
            test_minp = test_window
        pd.testing.assert_series_equal(
            df['a'].vbt.rolling_apply(test_window, mean_nb, minp=test_minp),
            df['a'].rolling(test_window, min_periods=test_minp).apply(mean_nb, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_apply(test_window, mean_nb, minp=test_minp),
            df.rolling(test_window, min_periods=test_minp).apply(mean_nb, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_apply(test_window, mean_nb, minp=test_minp, jitted=dict(parallel=True)),
            df.vbt.rolling_apply(test_window, mean_nb, minp=test_minp, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.rolling_apply(test_window, mean_nb, minp=test_minp, chunked=True),
            df.vbt.rolling_apply(test_window, mean_nb, minp=test_minp, chunked=False)
        )
        result = df.vbt.rolling_apply(test_window, mean_nb, minp=1)
        result.iloc[:test_minp - 1] = np.nan
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.rolling_apply(
                test_window, mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper),
            result
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.rolling_apply(
                test_window, mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.rolling_apply(
                test_window, mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.rolling_apply(
                test_window, mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.rolling_apply(
                test_window, mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, chunked=False)
        )

        @njit
        def mean_diff_meta_nb(from_i, to_i, col, x, y):
            return np.nanmean(x[from_i:to_i, col]) / np.nanmean(y[from_i:to_i, col])

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.rolling_apply(
                3,
                mean_diff_meta_nb,
                vbt.RepEval("to_2d_array(x)"),
                vbt.RepEval("to_2d_array(y)"),
                broadcast_named_args=dict(
                    x=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    y=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array)
            ),
            pd.DataFrame([
                [np.nan, np.nan, np.nan],
                [np.nan, np.nan, np.nan],
                [2.0, 1.0, 0.6666666666666666],
                [3.0, 1.5, 1.0],
                [4.0, 2.0, 1.3333333333333333]
            ], index=df.index, columns=df.columns)
        )

    @pytest.mark.parametrize(
        "test_minp",
        [1, 3]
    )
    def test_expanding_apply(self, test_minp):
        @njit
        def mean_nb(x):
            return np.nanmean(x)

        @njit
        def mean_meta_nb(from_i, to_i, col, x):
            return np.nanmean(x[from_i:to_i, col])

        pd.testing.assert_series_equal(
            df['a'].vbt.expanding_apply(mean_nb, minp=test_minp),
            df['a'].expanding(min_periods=test_minp).apply(mean_nb, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_apply(mean_nb, minp=test_minp),
            df.expanding(min_periods=test_minp).apply(mean_nb, raw=True)
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_apply(mean_nb, minp=test_minp, jitted=dict(parallel=True)),
            df.vbt.expanding_apply(mean_nb, minp=test_minp, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.expanding_apply(mean_nb, minp=test_minp, chunked=True),
            df.vbt.expanding_apply(mean_nb, minp=test_minp, chunked=False)
        )
        result = df.vbt.expanding_apply(mean_nb, minp=1)
        result.iloc[:test_minp - 1] = np.nan
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.expanding_apply(
                mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper),
            result
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.expanding_apply(
                mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.expanding_apply(
                mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.expanding_apply(
                mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.expanding_apply(
                mean_meta_nb, df.vbt.to_2d_array(),
                minp=test_minp, wrapper=df.vbt.wrapper, chunked=False)
        )

    def test_groupby_apply(self):
        @njit
        def mean_nb(x):
            return np.nanmean(x)

        @njit
        def mean_meta_nb(idxs, group, col, x):
            return np.nanmean(x[idxs, col])

        pd.testing.assert_series_equal(
            df['a'].vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb),
            df['a'].groupby(np.asarray([1, 1, 2, 2, 3])).apply(lambda x: mean_nb(x.values))
        )
        pd.testing.assert_frame_equal(
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb),
            df.groupby(np.asarray([1, 1, 2, 2, 3])).agg({
                'a': lambda x: mean_nb(x.values),
                'b': lambda x: mean_nb(x.values),
                'c': lambda x: mean_nb(x.values)
            }),  # any clean way to do column-wise grouping in pandas?
        )
        pd.testing.assert_frame_equal(
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb, jitted=dict(parallel=True)),
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb, chunked=True),
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.groupby_apply(
                np.asarray([1, 1, 2, 2, 3]), mean_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper),
            df.vbt.groupby_apply(np.asarray([1, 1, 2, 2, 3]), mean_nb)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.groupby_apply(
                np.asarray([1, 1, 2, 2, 3]), mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.groupby_apply(
                np.asarray([1, 1, 2, 2, 3]), mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.groupby_apply(
                np.asarray([1, 1, 2, 2, 3]), mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.groupby_apply(
                np.asarray([1, 1, 2, 2, 3]), mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, chunked=False),
        )

        @njit
        def mean_diff_meta_nb(idxs, group, col, x, y):
            return np.nanmean(x[idxs, col]) / np.nanmean(y[idxs, col])

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.groupby_apply(
                vbt.RepEval('group_by_evenly_nb(wrapper.shape[0], 2)'),
                mean_diff_meta_nb,
                vbt.RepEval("to_2d_array(x)"),
                vbt.RepEval("to_2d_array(y)"),
                broadcast_named_args=dict(
                    x=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    y=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(
                    to_2d_array=vbt.base.reshaping.to_2d_array,
                    group_by_evenly_nb=vbt.base.grouping.group_by_evenly_nb
                )
            ),
            pd.DataFrame([
                [2.0, 1.0, 0.6666666666666666],
                [4.5, 2.25, 1.5]
            ], columns=df.columns)
        )

    @pytest.mark.parametrize(
        "test_freq",
        ['1h', '3d', '1w'],
    )
    def test_resample_apply(self, test_freq):
        @njit
        def mean_nb(x):
            return np.nanmean(x)

        @njit
        def mean_meta_nb(idxs, group, col, x):
            return np.nanmean(x[idxs, col])

        pd.testing.assert_series_equal(
            df['a'].vbt.resample_apply(test_freq, mean_nb),
            df['a'].resample(test_freq).apply(lambda x: mean_nb(x.values))
        )
        pd.testing.assert_frame_equal(
            df.vbt.resample_apply(test_freq, mean_nb),
            df.resample(test_freq).apply(lambda x: mean_nb(x.values))
        )
        pd.testing.assert_frame_equal(
            df.vbt.resample_apply(test_freq, mean_nb, jitted=dict(parallel=True)),
            df.vbt.resample_apply(test_freq, mean_nb, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.resample_apply(test_freq, mean_nb, chunked=True),
            df.vbt.resample_apply(test_freq, mean_nb, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.resample_apply(
                test_freq, mean_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper),
            df.vbt.resample_apply(test_freq, mean_nb)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.resample_apply(
                test_freq, mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.resample_apply(
                test_freq, mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.resample_apply(
                test_freq, mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.resample_apply(
                test_freq, mean_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, chunked=False),
        )

        @njit
        def mean_diff_meta_nb(idxs, group, col, x, y):
            return np.nanmean(x[idxs, col]) / np.nanmean(y[idxs, col])

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.resample_apply(
                '2d',
                mean_diff_meta_nb,
                vbt.RepEval("to_2d_array(x)"),
                vbt.RepEval("to_2d_array(y)"),
                broadcast_named_args=dict(
                    x=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    y=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(
                    to_2d_array=vbt.base.reshaping.to_2d_array,
                    group_by_evenly_nb=vbt.base.grouping.group_by_evenly_nb
                )
            ),
            pd.DataFrame([
                [1.5, 0.75, 0.5],
                [3.5, 1.75, 1.1666666666666667],
                [5.0, 2.5, 1.6666666666666667]
            ], index=pd.DatetimeIndex(
                ['2018-01-01', '2018-01-03', '2018-01-05'],
                dtype='datetime64[ns]',
                freq='2D'
            ), columns=df.columns)
        )

    def test_apply_and_reduce(self):
        @njit
        def every_nth_nb(a, n):
            return a[::n]

        @njit
        def sum_nb(a, b):
            return np.nansum(a) + b

        @njit
        def every_nth_meta_nb(col, a, n):
            return a[::n, col]

        @njit
        def sum_meta_nb(col, a, b):
            return np.nansum(a) + b

        assert df['a'].vbt.apply_and_reduce(every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,)) == \
               df['a'].iloc[::2].sum() + 3
        pd.testing.assert_series_equal(
            df.vbt.apply_and_reduce(every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,)),
            df.iloc[::2].sum().rename('apply_and_reduce') + 3
        )
        pd.testing.assert_series_equal(
            df.vbt.apply_and_reduce(
                every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,), jitted=dict(parallel=True)),
            df.vbt.apply_and_reduce(
                every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,), jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(apply_args=vbt.ArgsTaker(None, ), reduce_args=vbt.ArgsTaker(None, )))
        pd.testing.assert_series_equal(
            df.vbt.apply_and_reduce(every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,), chunked=chunked),
            df.vbt.apply_and_reduce(every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,), chunked=False)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.apply_and_reduce(
                every_nth_meta_nb, sum_meta_nb, apply_args=(df.vbt.to_2d_array(), 2,),
                reduce_args=(3,), wrapper=df.vbt.wrapper),
            df.vbt.apply_and_reduce(every_nth_nb, sum_nb, apply_args=(2,), reduce_args=(3,))
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.apply_and_reduce(
                every_nth_meta_nb, sum_meta_nb, apply_args=(df.vbt.to_2d_array(), 2,), reduce_args=(3,),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.apply_and_reduce(
                every_nth_meta_nb, sum_meta_nb, apply_args=(df.vbt.to_2d_array(), 2,), reduce_args=(3,),
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(
            apply_args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), None), reduce_args=vbt.ArgsTaker(None, )))
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.apply_and_reduce(
                every_nth_meta_nb, sum_meta_nb, apply_args=(df.vbt.to_2d_array(), 2,), reduce_args=(3,),
                wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.apply_and_reduce(
                every_nth_meta_nb, sum_meta_nb, apply_args=(df.vbt.to_2d_array(), 2,), reduce_args=(3,),
                wrapper=df.vbt.wrapper, chunked=False),
        )

        @njit
        def every_2nd_sum_meta_nb(col, a, b):
            return a[::2, col] + b[::2, col]

        @njit
        def sum_meta2_nb(col, a):
            return np.nansum(a)

        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.apply_and_reduce(
                every_2nd_sum_meta_nb,
                sum_meta2_nb,
                apply_args=(
                    vbt.RepEval("to_2d_array(a)"),
                    vbt.RepEval("to_2d_array(b)")
                ),
                broadcast_named_args=dict(
                    a=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    b=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array)
            ),
            pd.Series([12, 15, 18], index=df.columns, name='apply_and_reduce')
        )

    def test_reduce(self):
        @njit
        def sum_nb(a):
            return np.nansum(a)

        @njit
        def sum_meta_nb(col, a):
            return np.nansum(a[:, col])

        @njit
        def sum_grouped_meta_nb(from_col, to_col, group, a):
            return np.nansum(a[:, from_col:to_col])

        assert df['a'].vbt.reduce(sum_nb) == df['a'].sum()
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb),
            df.sum().rename('reduce')
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb, jitted=dict(parallel=True)),
            df.vbt.reduce(sum_nb, jitted=dict(parallel=False))
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb, chunked=True),
            df.vbt.reduce(sum_nb, chunked=False)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(sum_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper),
            df.vbt.reduce(sum_nb)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                sum_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper, jitted=dict(parallel=False)),
        )
        count_chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper, chunked=count_chunked),
            pd.DataFrame.vbt.reduce(
                sum_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper, chunked=False),
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb, group_by=group_by),
            pd.Series([20.0, 6.0], index=['g1', 'g2']).rename('reduce')
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb, group_by=group_by, flatten=True, order='C'),
            df.vbt.reduce(sum_nb, group_by=group_by)
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(sum_nb, group_by=group_by, flatten=True, order='F'),
            df.vbt.reduce(sum_nb, group_by=group_by)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta_nb, df.vbt.to_2d_array(), wrapper=df.vbt.wrapper, group_by=group_by),
            df.vbt.reduce(sum_nb, group_by=group_by)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1, mapper=vbt.GroupLensMapper(0)), )))
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=chunked),
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta_nb, df.vbt.to_2d_array(),
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=False),
        )

        @njit
        def sum_meta2_nb(col, a, b):
            return np.nansum(a[:, col]) + np.nansum(b[:, col])

        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_meta2_nb,
                vbt.RepEval("to_2d_array(a)"),
                vbt.RepEval("to_2d_array(b)"),
                broadcast_named_args=dict(
                    a=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    b=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array)
            ),
            pd.Series([20, 25, 30], index=df.columns, name='reduce')
        )

        @njit
        def sum_grouped_meta2_nb(from_col, to_col, group, a, b):
            return np.nansum(a[:, from_col:to_col]) + np.nansum(b[:, from_col:to_col])

        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                sum_grouped_meta2_nb,
                vbt.RepEval("to_2d_array(a)"),
                vbt.RepEval("to_2d_array(b)"),
                broadcast_named_args=dict(
                    a=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    b=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array),
                group_by=group_by
            ),
            pd.Series([45, 30], index=['g1', 'g2'], name='reduce')
        )

    def test_reduce_to_idx(self):
        @njit
        def argmax_nb(a):
            a = a.copy()
            a[np.isnan(a)] = -np.inf
            return np.argmax(a)

        @njit
        def argmax_meta_nb(col, a):
            a = a[:, col].copy()
            a[np.isnan(a)] = -np.inf
            return np.argmax(a)

        @njit
        def argmax_grouped_meta_nb(from_col, to_col, group, a):
            a = a[:, from_col:to_col].flatten()
            a[np.isnan(a)] = -np.inf
            return np.argmax(a) // (to_col - from_col)

        assert df['a'].vbt.reduce(argmax_nb, returns_idx=True) == df['a'].idxmax()
        pd.testing.assert_series_equal(
            df.vbt.reduce(argmax_nb, returns_idx=True),
            df.idxmax().rename('reduce')
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(argmax_nb, returns_idx=True, jitted=dict(parallel=True)),
            df.vbt.reduce(argmax_nb, returns_idx=True, jitted=dict(parallel=False))
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(argmax_nb, returns_idx=True, chunked=True),
            df.vbt.reduce(argmax_nb, returns_idx=True, chunked=False)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True, wrapper=df.vbt.wrapper),
            df.vbt.reduce(argmax_nb, returns_idx=True)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        count_chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, chunked=count_chunked),
            pd.DataFrame.vbt.reduce(
                argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, chunked=False)
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(argmax_nb, returns_idx=True, group_by=group_by, flatten=True, order='C'),
            pd.Series(['2018-01-02', '2018-01-02'], dtype='datetime64[ns]', index=['g1', 'g2']).rename('reduce')
        )
        pd.testing.assert_series_equal(
            df.vbt.reduce(argmax_nb, returns_idx=True, group_by=group_by, flatten=True, order='F'),
            pd.Series(['2018-01-04', '2018-01-02'], dtype='datetime64[ns]', index=['g1', 'g2']).rename('reduce')
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, group_by=group_by),
            df.vbt.reduce(argmax_nb, group_by=group_by, returns_idx=True, flatten=True)
        )
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, group_by=group_by, flatten=True, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, group_by=group_by, flatten=True, jitted=dict(parallel=False)),
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1, mapper=vbt.GroupLensMapper(0)), )))
        pd.testing.assert_series_equal(
            pd.DataFrame.vbt.reduce(
                argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, group_by=group_by, flatten=True, chunked=chunked),
            pd.DataFrame.vbt.reduce(
                argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                wrapper=df.vbt.wrapper, group_by=group_by, flatten=True, chunked=False),
        )

    def test_reduce_to_array(self):
        @njit
        def min_and_max_nb(a):
            out = np.empty(2)
            out[0] = np.nanmin(a)
            out[1] = np.nanmax(a)
            return out

        @njit
        def min_and_max_meta_nb(col, a):
            out = np.empty(2)
            out[0] = np.nanmin(a[:, col])
            out[1] = np.nanmax(a[:, col])
            return out

        @njit
        def min_and_max_grouped_meta_nb(from_col, to_col, group, a):
            out = np.empty(2)
            out[0] = np.nanmin(a[:, from_col:to_col])
            out[1] = np.nanmax(a[:, from_col:to_col])
            return out

        pd.testing.assert_series_equal(
            df['a'].vbt.reduce(
                min_and_max_nb, returns_array=True,
                wrap_kwargs=dict(name_or_index=['min', 'max'])),
            pd.Series([np.nanmin(df['a']), np.nanmax(df['a'])], index=['min', 'max'], name='a')
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(
                min_and_max_nb, returns_array=True,
                wrap_kwargs=dict(name_or_index=['min', 'max'])),
            df.apply(lambda x: pd.Series(np.asarray([np.nanmin(x), np.nanmax(x)]), index=['min', 'max']), axis=0)
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(min_and_max_nb, returns_array=True, jitted=dict(parallel=True)),
            df.vbt.reduce(min_and_max_nb, returns_array=True, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(min_and_max_nb, returns_array=True, chunked=True),
            df.vbt.reduce(min_and_max_nb, returns_array=True, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_meta_nb, df.vbt.to_2d_array(), returns_array=True, wrapper=df.vbt.wrapper),
            df.vbt.reduce(min_and_max_nb, returns_array=True)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                min_and_max_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        count_chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, chunked=count_chunked),
            pd.DataFrame.vbt.reduce(
                min_and_max_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, chunked=False)
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(
                min_and_max_nb, returns_array=True, group_by=group_by,
                wrap_kwargs=dict(name_or_index=['min', 'max'])),
            pd.DataFrame([[1.0, 1.0], [4.0, 2.0]], index=['min', 'max'], columns=['g1', 'g2'])
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(min_and_max_nb, returns_array=True, group_by=group_by, flatten=True, order='C'),
            df.vbt.reduce(min_and_max_nb, returns_array=True, group_by=group_by)
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(min_and_max_nb, returns_array=True, group_by=group_by, flatten=True, order='F'),
            df.vbt.reduce(min_and_max_nb, returns_array=True, group_by=group_by)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_grouped_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by),
            df.vbt.reduce(min_and_max_nb, returns_array=True, group_by=group_by)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_grouped_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                min_and_max_grouped_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1, mapper=vbt.GroupLensMapper(0)), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                min_and_max_grouped_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=chunked),
            pd.DataFrame.vbt.reduce(
                min_and_max_grouped_meta_nb, df.vbt.to_2d_array(), returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=False)
        )

    def test_reduce_to_idx_array(self):
        @njit
        def argmin_and_argmax_nb(a):
            # nanargmin and nanargmax
            out = np.empty(2)
            _a = a.copy()
            _a[np.isnan(_a)] = np.inf
            out[0] = np.argmin(_a)
            _a = a.copy()
            _a[np.isnan(_a)] = -np.inf
            out[1] = np.argmax(_a)
            return out

        @njit
        def argmin_and_argmax_meta_nb(col, a):
            # nanargmin and nanargmax
            out = np.empty(2)
            _a = a[:, col].copy()
            _a[np.isnan(_a)] = np.inf
            out[0] = np.argmin(_a)
            _a = a[:, col].copy()
            _a[np.isnan(_a)] = -np.inf
            out[1] = np.argmax(_a)
            return out

        @njit
        def argmin_and_argmax_grouped_meta_nb(from_col, to_col, group, a):
            # nanargmin and nanargmax
            out = np.empty(2)
            _a = a[:, from_col:to_col].flatten()
            _a[np.isnan(_a)] = np.inf
            out[0] = np.argmin(_a)
            _a = a[:, from_col:to_col].flatten()
            _a[np.isnan(_a)] = -np.inf
            out[1] = np.argmax(_a)
            return out // (to_col - from_col)

        pd.testing.assert_series_equal(
            df['a'].vbt.reduce(
                argmin_and_argmax_nb, returns_idx=True, returns_array=True,
                wrap_kwargs=dict(name_or_index=['idxmin', 'idxmax'])),
            pd.Series([df['a'].idxmin(), df['a'].idxmax()], index=['idxmin', 'idxmax'], name='a')
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(
                argmin_and_argmax_nb, returns_idx=True, returns_array=True,
                wrap_kwargs=dict(name_or_index=['idxmin', 'idxmax'])),
            df.apply(lambda x: pd.Series(np.asarray([x.idxmin(), x.idxmax()]), index=['idxmin', 'idxmax']), axis=0)
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True, jitted=dict(parallel=True)),
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True, chunked=True),
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                returns_array=True, wrapper=df.vbt.wrapper),
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                returns_array=True, wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                returns_array=True, wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        count_chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                returns_array=True, wrapper=df.vbt.wrapper, chunked=count_chunked),
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_meta_nb, df.vbt.to_2d_array(), returns_idx=True,
                returns_array=True, wrapper=df.vbt.wrapper, chunked=False)
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True,
                          flatten=True, order='C', group_by=group_by,
                          wrap_kwargs=dict(name_or_index=['idxmin', 'idxmax'])),
            pd.DataFrame([['2018-01-01', '2018-01-01'], ['2018-01-02', '2018-01-02']],
                         dtype='datetime64[ns]', index=['idxmin', 'idxmax'], columns=['g1', 'g2'])
        )
        pd.testing.assert_frame_equal(
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True, returns_array=True,
                          flatten=True, order='F', group_by=group_by,
                          wrap_kwargs=dict(name_or_index=['idxmin', 'idxmax'])),
            pd.DataFrame([['2018-01-01', '2018-01-01'], ['2018-01-04', '2018-01-02']],
                         dtype='datetime64[ns]', index=['idxmin', 'idxmax'], columns=['g1', 'g2'])
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_grouped_meta_nb, df.vbt.to_2d_array(),
                returns_idx=True, returns_array=True, wrapper=df.vbt.wrapper, group_by=group_by),
            df.vbt.reduce(argmin_and_argmax_nb, returns_idx=True,
                          returns_array=True, group_by=group_by, flatten=True)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True, returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True, returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1, mapper=vbt.GroupLensMapper(0)), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True, returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=chunked),
            pd.DataFrame.vbt.reduce(
                argmin_and_argmax_grouped_meta_nb, df.vbt.to_2d_array(), returns_idx=True, returns_array=True,
                wrapper=df.vbt.wrapper, group_by=group_by, chunked=False)
        )

    def test_squeeze_grouped(self):
        @njit
        def mean_nb(a):
            return np.nanmean(a)

        @njit
        def mean_grouped_meta_nb(i, from_col, to_col, group, a):
            return np.nanmean(a[i, from_col:to_col])

        pd.testing.assert_frame_equal(
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by),
            pd.DataFrame([
                [1.0, 1.0],
                [3.0, 2.0],
                [3.0, np.nan],
                [3.0, 2.0],
                [1.0, 1.0]
            ], index=df.index, columns=['g1', 'g2'])
        )
        pd.testing.assert_frame_equal(
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by, jitted=dict(parallel=True)),
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by, chunked=True),
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by, chunked=False)
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.squeeze_grouped(
                mean_grouped_meta_nb, df.vbt.to_2d_array(), group_by=group_by, wrapper=df.vbt.wrapper),
            df.vbt.squeeze_grouped(mean_nb, group_by=group_by),
        )
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.squeeze_grouped(
                mean_grouped_meta_nb, df.vbt.to_2d_array(), group_by=group_by,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=True)),
            pd.DataFrame.vbt.squeeze_grouped(
                mean_grouped_meta_nb, df.vbt.to_2d_array(), group_by=group_by,
                wrapper=df.vbt.wrapper, jitted=dict(parallel=False))
        )
        chunked = dict(arg_take_spec=dict(args=vbt.ArgsTaker(vbt.ArraySlicer(axis=1, mapper=vbt.GroupLensMapper(1)), )))
        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.squeeze_grouped(
                mean_grouped_meta_nb, df.vbt.to_2d_array(), group_by=group_by,
                wrapper=df.vbt.wrapper, chunked=chunked),
            pd.DataFrame.vbt.squeeze_grouped(
                mean_grouped_meta_nb, df.vbt.to_2d_array(), group_by=group_by,
                wrapper=df.vbt.wrapper, chunked=False)
        )

        @njit
        def sum_grouped_meta_nb(i, from_col, to_col, group, a, b):
            return np.nansum(a[i, from_col:to_col]) + np.nansum(b[i, from_col:to_col])

        pd.testing.assert_frame_equal(
            pd.DataFrame.vbt.squeeze_grouped(
                sum_grouped_meta_nb,
                vbt.RepEval("to_2d_array(a)"),
                vbt.RepEval("to_2d_array(b)"),
                broadcast_named_args=dict(
                    a=pd.Series([1, 2, 3, 4, 5], index=df.index),
                    b=pd.DataFrame([[1, 2, 3]], columns=df.columns)
                ),
                template_mapping=dict(to_2d_array=vbt.base.reshaping.to_2d_array),
                group_by=group_by
            ),
            pd.DataFrame([
                [5, 4],
                [7, 5],
                [9, 6],
                [11, 7],
                [13, 8]
            ], index=df.index, columns=['g1', 'g2'])
        )

    def test_flatten_grouped(self):
        pd.testing.assert_frame_equal(
            df.vbt.flatten_grouped(group_by=group_by, order='C'),
            pd.DataFrame([
                [1.0, 1.0],
                [np.nan, np.nan],
                [2.0, 2.0],
                [4.0, np.nan],
                [3.0, np.nan],
                [3.0, np.nan],
                [4.0, 2.0],
                [2.0, np.nan],
                [np.nan, 1.0],
                [1.0, np.nan]
            ], index=np.repeat(df.index, 2), columns=['g1', 'g2'])
        )
        pd.testing.assert_frame_equal(
            df.vbt.flatten_grouped(group_by=group_by, order='F'),
            pd.DataFrame([
                [1.0, 1.0],
                [2.0, 2.0],
                [3.0, np.nan],
                [4.0, 2.0],
                [np.nan, 1.0],
                [np.nan, np.nan],
                [4.0, np.nan],
                [3.0, np.nan],
                [2.0, np.nan],
                [1.0, np.nan]
            ], index=np.tile(df.index, 2), columns=['g1', 'g2'])
        )
        pd.testing.assert_series_equal(
            pd.DataFrame([[False, True], [False, True]]).vbt.flatten_grouped(group_by=True, order='C'),
            pd.Series([False, True, False, True], name='group')
        )
        pd.testing.assert_series_equal(
            pd.DataFrame([[False, True], [False, True]]).vbt.flatten_grouped(group_by=True, order='F'),
            pd.Series([False, False, True, True], name='group')
        )

    @pytest.mark.parametrize(
        "test_name,test_func",
        [
            ('min', lambda x, **kwargs: x.min(**kwargs)),
            ('max', lambda x, **kwargs: x.max(**kwargs)),
            ('mean', lambda x, **kwargs: x.mean(**kwargs)),
            ('median', lambda x, **kwargs: x.median(**kwargs)),
            ('std', lambda x, **kwargs: x.std(**kwargs, ddof=0)),
            ('count', lambda x, **kwargs: x.count(**kwargs)),
            ('sum', lambda x, **kwargs: x.sum(**kwargs))
        ],
    )
    def test_funcs(self, test_name, test_func):
        # numeric
        assert test_func(df['a'].vbt) == test_func(df['a'])
        pd.testing.assert_series_equal(
            test_func(df.vbt),
            test_func(df).rename(test_name)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, group_by=group_by),
            pd.Series([
                test_func(df[['a', 'b']].stack()),
                test_func(df['c'])
            ], index=['g1', 'g2']).rename(test_name)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, use_jitted=True),
            test_func(df.vbt, use_jitted=False)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, use_jitted=True, jitted=dict(parallel=True)),
            test_func(df.vbt, use_jitted=True, jitted=dict(parallel=False))
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, use_jitted=True, chunked=True),
            test_func(df.vbt, use_jitted=True, chunked=False)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, wrap_kwargs=dict(to_timedelta=True)),
            test_func(df).rename(test_name) * day_dt
        )
        # boolean
        bool_ts = df == df
        assert test_func(bool_ts['a'].vbt) == test_func(bool_ts['a'])
        pd.testing.assert_series_equal(
            test_func(bool_ts.vbt),
            test_func(bool_ts).rename(test_name)
        )

    @pytest.mark.parametrize(
        "test_name,test_func",
        [
            ('idxmin', lambda x, **kwargs: x.idxmin(**kwargs)),
            ('idxmax', lambda x, **kwargs: x.idxmax(**kwargs))
        ],
    )
    def test_arg_funcs(self, test_name, test_func):
        assert test_func(df['a'].vbt) == test_func(df['a'])
        pd.testing.assert_series_equal(
            test_func(df.vbt),
            test_func(df).rename(test_name)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, chunked=True),
            test_func(df.vbt, chunked=False)
        )
        pd.testing.assert_series_equal(
            test_func(df.vbt, group_by=group_by),
            pd.Series([
                test_func(df[['a', 'b']].stack())[0],
                test_func(df['c'])
            ], index=['g1', 'g2'], dtype='datetime64[ns]').rename(test_name)
        )

    def test_describe(self):
        pd.testing.assert_series_equal(
            df['a'].vbt.describe(),
            df['a'].describe()
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(percentiles=None),
            df.describe(percentiles=None)
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(percentiles=[]),
            df.describe(percentiles=[])
        )
        test_against = df.describe(percentiles=np.arange(0, 1, 0.1))
        pd.testing.assert_frame_equal(
            df.vbt.describe(percentiles=np.arange(0, 1, 0.1)),
            test_against
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(percentiles=np.arange(0, 1, 0.1), group_by=group_by),
            pd.DataFrame({
                'g1': df[['a', 'b']].stack().describe(percentiles=np.arange(0, 1, 0.1)).values,
                'g2': df['c'].describe(percentiles=np.arange(0, 1, 0.1)).values
            }, index=test_against.index)
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(jitted=dict(parallel=True)),
            df.vbt.describe(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(chunked=True),
            df.vbt.describe(chunked=False)
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(group_by=group_by, jitted=dict(parallel=True)),
            df.vbt.describe(group_by=group_by, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.describe(group_by=group_by, chunked=True),
            df.vbt.describe(group_by=group_by, chunked=False)
        )

    def test_value_counts(self):
        pd.testing.assert_series_equal(
            df['a'].vbt.value_counts(),
            pd.Series(
                np.array([1, 1, 1, 1, 1]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0, np.nan], dtype='float64'),
                name='a'
            )
        )
        mapping = {1.: 'one', 2.: 'two', 3.: 'three', 4.: 'four'}
        pd.testing.assert_series_equal(
            df['a'].vbt.value_counts(mapping=mapping),
            pd.Series(
                np.array([1, 1, 1, 1, 1]),
                index=pd.Index(['one', 'two', 'three', 'four', None], dtype='object'),
                name='a'
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(),
            pd.DataFrame(
                np.array([
                    [1, 1, 2],
                    [1, 1, 2],
                    [1, 1, 0],
                    [1, 1, 0],
                    [1, 1, 1]
                ]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0, np.nan], dtype='float64'),
                columns=df.columns
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(jitted=dict(parallel=True)),
            df.vbt.value_counts(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(chunked=True),
            df.vbt.value_counts(chunked=False)
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(axis=0),
            pd.DataFrame(
                np.array([
                    [2, 0, 0, 0, 2], [0, 2, 0, 2, 0], [0, 0, 2, 0, 0], [0, 1, 0, 1, 0], [1, 0, 1, 0, 1]
                ]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0, np.nan], dtype='float64'),
                columns=df.index
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(axis=0, jitted=dict(parallel=True)),
            df.vbt.value_counts(axis=0, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(axis=0, chunked=True),
            df.vbt.value_counts(axis=0, chunked=False)
        )
        pd.testing.assert_series_equal(
            df.vbt.value_counts(axis=-1),
            pd.Series(
                np.array([
                    4, 4, 2, 2, 3
                ]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0, np.nan], dtype='float64'),
                name='value_counts'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt.value_counts(axis=-1, jitted=dict(parallel=True)),
            df.vbt.value_counts(axis=-1, jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(group_by=group_by),
            pd.DataFrame(
                np.array([
                    [2, 2],
                    [2, 2],
                    [2, 0],
                    [2, 0],
                    [2, 1]
                ]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0, np.nan], dtype='float64'),
                columns=pd.Index(['g1', 'g2'], dtype='object')
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(sort_uniques=False),
            pd.DataFrame(
                np.array([
                    [1, 1, 2],
                    [1, 1, 2],
                    [1, 1, 0],
                    [1, 1, 0],
                    [1, 1, 1]
                ]),
                index=pd.Float64Index([1.0, 2.0, 4.0, 3.0, np.nan], dtype='float64'),
                columns=df.columns
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(sort=True),
            pd.DataFrame(
                np.array([
                    [1, 1, 2],
                    [1, 1, 2],
                    [1, 1, 1],
                    [1, 1, 0],
                    [1, 1, 0]
                ]),
                index=pd.Float64Index([1.0, 2.0, np.nan, 3.0, 4.0], dtype='float64'),
                columns=df.columns
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(sort=True, ascending=True),
            pd.DataFrame(
                np.array([
                    [1, 1, 0],
                    [1, 1, 0],
                    [1, 1, 1],
                    [1, 1, 2],
                    [1, 1, 2]
                ]),
                index=pd.Float64Index([3.0, 4.0, np.nan, 1.0, 2.0], dtype='float64'),
                columns=df.columns
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(sort=True, normalize=True),
            pd.DataFrame(
                np.array([
                    [0.06666666666666667, 0.06666666666666667, 0.13333333333333333],
                    [0.06666666666666667, 0.06666666666666667, 0.13333333333333333],
                    [0.06666666666666667, 0.06666666666666667, 0.06666666666666667],
                    [0.06666666666666667, 0.06666666666666667, 0.0],
                    [0.06666666666666667, 0.06666666666666667, 0.0]
                ]),
                index=pd.Float64Index([1.0, 2.0, np.nan, 3.0, 4.0], dtype='float64'),
                columns=df.columns
            )
        )
        pd.testing.assert_frame_equal(
            df.vbt.value_counts(sort=True, normalize=True, dropna=True),
            pd.DataFrame(
                np.array([
                    [0.08333333333333333, 0.08333333333333333, 0.16666666666666666],
                    [0.08333333333333333, 0.08333333333333333, 0.16666666666666666],
                    [0.08333333333333333, 0.08333333333333333, 0.0],
                    [0.08333333333333333, 0.08333333333333333, 0.0]
                ]),
                index=pd.Float64Index([1.0, 2.0, 3.0, 4.0], dtype='float64'),
                columns=df.columns
            )
        )

    def test_drawdown(self):
        pd.testing.assert_series_equal(
            df['a'].vbt.drawdown(),
            df['a'] / df['a'].expanding().max() - 1
        )
        pd.testing.assert_frame_equal(
            df.vbt.drawdown(),
            df / df.expanding().max() - 1
        )
        pd.testing.assert_frame_equal(
            df.vbt.drawdown(jitted=dict(parallel=True)),
            df.vbt.drawdown(jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.drawdown(chunked=True),
            df.vbt.drawdown(chunked=False)
        )

    def test_drawdowns(self):
        assert type(df['a'].vbt.drawdowns) is vbt.Drawdowns
        assert df['a'].vbt.drawdowns.wrapper.freq == df['a'].vbt.wrapper.freq
        assert df['a'].vbt.drawdowns.wrapper.ndim == df['a'].ndim
        assert df.vbt.drawdowns.wrapper.ndim == df.ndim

    def test_to_mapped(self):
        np.testing.assert_array_equal(
            df.vbt.to_mapped().values,
            np.array([1., 2., 3., 4., 4., 3., 2., 1., 1., 2., 2., 1.])
        )
        np.testing.assert_array_equal(
            df.vbt.to_mapped().col_arr,
            np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2])
        )
        np.testing.assert_array_equal(
            df.vbt.to_mapped().idx_arr,
            np.array([0, 1, 2, 3, 1, 2, 3, 4, 0, 1, 3, 4])
        )
        np.testing.assert_array_equal(
            df.vbt.to_mapped(dropna=False).values,
            np.array([1., 2., 3., 4., np.nan, np.nan, 4., 3., 2., 1., 1., 2., np.nan, 2., 1.])
        )
        np.testing.assert_array_equal(
            df.vbt.to_mapped(dropna=False).col_arr,
            np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2])
        )
        np.testing.assert_array_equal(
            df.vbt.to_mapped(dropna=False).idx_arr,
            np.array([0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4])
        )

    def test_zscore(self):
        pd.testing.assert_series_equal(
            df['a'].vbt.zscore(),
            (df['a'] - df['a'].mean()) / df['a'].std(ddof=0)
        )
        pd.testing.assert_frame_equal(
            df.vbt.zscore(),
            (df - df.mean()) / df.std(ddof=0)
        )

    def test_split(self):
        splitter = TimeSeriesSplit(n_splits=2)
        (train_df, train_indexes), (test_df, test_indexes) = df['a'].vbt.split(splitter)
        pd.testing.assert_frame_equal(
            train_df,
            pd.DataFrame(
                np.array([
                    [1.0, 1.0],
                    [2.0, 2.0],
                    [3.0, 3.0],
                    [np.nan, 4.0]
                ]),
                index=pd.RangeIndex(start=0, stop=4, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03', '2018-01-04'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                train_indexes[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            test_df,
            pd.DataFrame(
                np.array([
                    [4.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                test_indexes[i],
                target[i]
            )
        (train_df, train_indexes), (test_df, test_indexes) = df.vbt.split(splitter)
        pd.testing.assert_frame_equal(
            train_df,
            pd.DataFrame(
                np.array([
                    [1.0, np.nan, 1.0, 1.0, np.nan, 1.0],
                    [2.0, 4.0, 2.0, 2.0, 4.0, 2.0],
                    [3.0, 3.0, np.nan, 3.0, 3.0, np.nan],
                    [np.nan, np.nan, np.nan, 4.0, 2.0, 2.0]
                ]),
                index=pd.RangeIndex(start=0, stop=4, step=1),
                columns=pd.MultiIndex.from_tuples([
                    (0, 'a'),
                    (0, 'b'),
                    (0, 'c'),
                    (1, 'a'),
                    (1, 'b'),
                    (1, 'c')
                ], names=['split_idx', None])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03', '2018-01-04'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                train_indexes[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            test_df,
            pd.DataFrame(
                np.array([
                    [4.0, 2.0, 2.0, np.nan, 1.0, 1.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.MultiIndex.from_tuples([
                    (0, 'a'),
                    (0, 'b'),
                    (0, 'c'),
                    (1, 'a'),
                    (1, 'b'),
                    (1, 'c')
                ], names=['split_idx', None])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                test_indexes[i],
                target[i]
            )

    def test_range_split(self):
        pd.testing.assert_frame_equal(
            df['a'].vbt.range_split(n=2)[0],
            pd.DataFrame(
                np.array([
                    [1., 4.],
                    [2., np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df['a'].vbt.range_split(n=2)[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df['a'].vbt.range_split(range_len=2)[0],
            pd.DataFrame(
                np.array([
                    [1., 2., 3., 4.],
                    [2., 3., 4., np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1, 2, 3], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02', '2018-01-03'], dtype='datetime64[ns]', name='split_1', freq=None),
            pd.DatetimeIndex(['2018-01-03', '2018-01-04'], dtype='datetime64[ns]', name='split_2', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_3', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df['a'].vbt.range_split(range_len=2)[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df['a'].vbt.range_split(range_len=2, n=3)[0],
            pd.DataFrame(
                np.array([
                    [1., 3., 4.],
                    [2., 4., np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1, 2], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-03', '2018-01-04'], dtype='datetime64[ns]', name='split_1', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_2', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df['a'].vbt.range_split(range_len=2, n=3)[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df['a'].vbt.range_split(range_len=3, n=2)[0],
            pd.DataFrame(
                np.array([
                    [1., 3.],
                    [2., 4.],
                    [3., np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=3, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-03', '2018-01-04', '2018-01-05'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df['a'].vbt.range_split(range_len=3, n=2)[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df.vbt.range_split(n=2)[0],
            pd.DataFrame(
                np.array([
                    [1.0, np.nan, 1.0, 4.0, 2.0, 2.0],
                    [2.0, 4.0, 2.0, np.nan, 1.0, 1.0]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.MultiIndex.from_arrays([
                    pd.Int64Index([0, 0, 0, 1, 1, 1], dtype='int64', name='split_idx'),
                    pd.Index(['a', 'b', 'c', 'a', 'b', 'c'], dtype='object')
                ])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df.vbt.range_split(n=2)[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df.vbt.range_split(start_idxs=[0, 1], end_idxs=[2, 3])[0],
            pd.DataFrame(
                np.array([
                    [1.0, np.nan, 1.0, 2.0, 4.0, 2.0],
                    [2.0, 4.0, 2.0, 3.0, 3.0, np.nan],
                    [3.0, 3.0, np.nan, 4.0, 2.0, 2.0]
                ]),
                index=pd.RangeIndex(start=0, stop=3, step=1),
                columns=pd.MultiIndex.from_arrays([
                    pd.Int64Index([0, 0, 0, 1, 1, 1], dtype='int64', name='split_idx'),
                    pd.Index(['a', 'b', 'c', 'a', 'b', 'c'], dtype='object')
                ])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02', '2018-01-03', '2018-01-04'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df.vbt.range_split(start_idxs=[0, 1], end_idxs=[2, 3])[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df.vbt.range_split(start_idxs=df.index[[0, 1]], end_idxs=df.index[[2, 3]])[0],
            pd.DataFrame(
                np.array([
                    [1.0, np.nan, 1.0, 2.0, 4.0, 2.0],
                    [2.0, 4.0, 2.0, 3.0, 3.0, np.nan],
                    [3.0, 3.0, np.nan, 4.0, 2.0, 2.0]
                ]),
                index=pd.RangeIndex(start=0, stop=3, step=1),
                columns=pd.MultiIndex.from_arrays([
                    pd.Int64Index([0, 0, 0, 1, 1, 1], dtype='int64', name='split_idx'),
                    pd.Index(['a', 'b', 'c', 'a', 'b', 'c'], dtype='object')
                ])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02', '2018-01-03', '2018-01-04'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df.vbt.range_split(start_idxs=df.index[[0, 1]], end_idxs=df.index[[2, 3]])[1][i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df.vbt.range_split(start_idxs=df.index[[0]], end_idxs=df.index[[2, 3]])[0],
            pd.DataFrame(
                np.array([
                    [1.0, np.nan, 1.0, 1.0, np.nan, 1.0],
                    [2.0, 4.0, 2.0, 2.0, 4.0, 2.0],
                    [3.0, 3.0, np.nan, 3.0, 3.0, np.nan],
                    [np.nan, np.nan, np.nan, 4.0, 2.0, 2.0]
                ]),
                index=pd.RangeIndex(start=0, stop=4, step=1),
                columns=pd.MultiIndex.from_arrays([
                    pd.Int64Index([0, 0, 0, 1, 1, 1], dtype='int64', name='split_idx'),
                    pd.Index(['a', 'b', 'c', 'a', 'b', 'c'], dtype='object')
                ])
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03', '2018-01-04'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                df.vbt.range_split(start_idxs=df.index[[0]], end_idxs=df.index[[2, 3]])[1][i],
                target[i]
            )
        with pytest.raises(Exception):
            df.vbt.range_split()
        with pytest.raises(Exception):
            df.vbt.range_split(start_idxs=[0, 1])
        with pytest.raises(Exception):
            df.vbt.range_split(end_idxs=[2, 4])
        with pytest.raises(Exception):
            df.vbt.range_split(min_len=10)
        with pytest.raises(Exception):
            df.vbt.range_split(n=10)

    def test_rolling_split(self):
        (df1, indexes1), (df2, indexes2), (df3, indexes3) = df['a'].vbt.rolling_split(
            window_len=4, set_lens=(1, 1), left_to_right=False)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 2.0],
                    [2.0, 3.0]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02', '2018-01-03'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df2,
            pd.DataFrame(
                np.array([
                    [3.0, 4.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-03'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes2[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df3,
            pd.DataFrame(
                np.array([
                    [4.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes3[i],
                target[i]
            )
        (df1, indexes1), (df2, indexes2), (df3, indexes3) = df['a'].vbt.rolling_split(
            window_len=4, set_lens=(1, 1), left_to_right=True)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 2.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df2,
            pd.DataFrame(
                np.array([
                    [2.0, 3.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-03'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes2[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df3,
            pd.DataFrame(
                np.array([
                    [3.0, 4.0],
                    [4.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-03', '2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes3[i],
                target[i]
            )
        (df1, indexes1), (df2, indexes2), (df3, indexes3) = df['a'].vbt.rolling_split(
            window_len=4, set_lens=(0.25, 0.25), left_to_right=[False, True])
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 2.0],
                    [2.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-02'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df2,
            pd.DataFrame(
                np.array([
                    [3.0, 3.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-03'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-03'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes2[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df3,
            pd.DataFrame(
                np.array([
                    [4.0, 4.0],
                    [np.nan, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes3[i],
                target[i]
            )
        df1, indexes1 = df['a'].vbt.rolling_split(window_len=2, n=2)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 4.0],
                    [2.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        df1, indexes1 = df['a'].vbt.rolling_split(window_len=0.4, n=2)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 4.0],
                    [2.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=2, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04', '2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        with pytest.raises(Exception):
            df.vbt.rolling_split()
        with pytest.raises(Exception):
            df.vbt.rolling_split(window_len=3, set_lens=(3, 1))
        with pytest.raises(Exception):
            df.vbt.rolling_split(window_len=1, set_lens=(1, 1))
        with pytest.raises(Exception):
            df.vbt.rolling_split(n=2, min_len=10)
        with pytest.raises(Exception):
            df.vbt.rolling_split(n=10)

    def test_expanding_split(self):
        (df1, indexes1), (df2, indexes2), (df3, indexes3) = df['a'].vbt.expanding_split(
            min_len=4, set_lens=(1, 1), left_to_right=False)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 1.0],
                    [2.0, 2.0],
                    [np.nan, 3.0]
                ]),
                index=pd.RangeIndex(start=0, stop=3, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df2,
            pd.DataFrame(
                np.array([
                    [3.0, 4.0]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-03'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes2[i],
                target[i]
            )
        pd.testing.assert_frame_equal(
            df3,
            pd.DataFrame(
                np.array([
                    [4.0, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=1, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-04'], dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-05'], dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes3[i],
                target[i]
            )
        df1, indexes1 = df['a'].vbt.expanding_split(n=2, min_len=2)
        pd.testing.assert_frame_equal(
            df1,
            pd.DataFrame(
                np.array([
                    [1.0, 1.0],
                    [2.0, 2.0],
                    [np.nan, 3.0],
                    [np.nan, 4.0],
                    [np.nan, np.nan]
                ]),
                index=pd.RangeIndex(start=0, stop=5, step=1),
                columns=pd.Int64Index([0, 1], dtype='int64', name='split_idx')
            )
        )
        target = [
            pd.DatetimeIndex(['2018-01-01', '2018-01-02'],
                             dtype='datetime64[ns]', name='split_0', freq=None),
            pd.DatetimeIndex(['2018-01-01', '2018-01-02', '2018-01-03', '2018-01-04', '2018-01-05'],
                             dtype='datetime64[ns]', name='split_1', freq=None)
        ]
        for i in range(len(target)):
            pd.testing.assert_index_equal(
                indexes1[i],
                target[i]
            )
        with pytest.raises(Exception):
            df.vbt.expanding_split(n=2, min_len=10)
        with pytest.raises(Exception):
            df.vbt.expanding_split(n=10)

    def test_crossed_above(self):
        sr1 = pd.Series([np.nan, 3, 2, 1, 2, 3, 4])
        sr2 = pd.Series([1, 2, 3, 4, 3, 2, 1])
        pd.testing.assert_series_equal(
            sr1.vbt.crossed_above(sr2),
            pd.Series([False, False, False, False, False, True, False])
        )
        pd.testing.assert_series_equal(
            sr1.vbt.crossed_above(sr2, wait=1),
            pd.Series([False, False, False, False, False, False, True])
        )
        sr3 = pd.Series([1, 2, 3, np.nan, 5, 1, 5])
        sr4 = pd.Series([3, 2, 1, 1, 1, 5, 1])
        pd.testing.assert_series_equal(
            sr3.vbt.crossed_above(sr4),
            pd.Series([False, False, True, False, False, False, True])
        )
        pd.testing.assert_series_equal(
            sr3.vbt.crossed_above(sr4, wait=1),
            pd.Series([False, False, False, False, False, False, False])
        )
        pd.testing.assert_frame_equal(
            df.vbt.crossed_above(df.iloc[:, ::-1], jitted=dict(parallel=True)),
            df.vbt.crossed_above(df.iloc[:, ::-1], jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.crossed_above(df.iloc[:, ::-1], chunked=True),
            df.vbt.crossed_above(df.iloc[:, ::-1], chunked=False)
        )

    def test_crossed_below(self):
        sr1 = pd.Series([np.nan, 3, 2, 1, 2, 3, 4])
        sr2 = pd.Series([1, 2, 3, 4, 3, 2, 1])
        pd.testing.assert_series_equal(
            sr1.vbt.crossed_below(sr2),
            pd.Series([False, False, True, False, False, False, False])
        )
        pd.testing.assert_series_equal(
            sr1.vbt.crossed_below(sr2, wait=1),
            pd.Series([False, False, False, True, False, False, False])
        )
        sr3 = pd.Series([1, 2, 3, np.nan, 5, 1, 5])
        sr4 = pd.Series([3, 2, 1, 1, 1, 5, 1])
        pd.testing.assert_series_equal(
            sr3.vbt.crossed_above(sr4),
            pd.Series([False, False, True, False, False, False, True])
        )
        pd.testing.assert_series_equal(
            sr3.vbt.crossed_above(sr4, wait=1),
            pd.Series([False, False, False, False, False, False, False])
        )
        pd.testing.assert_frame_equal(
            df.vbt.crossed_below(df.iloc[:, ::-1], jitted=dict(parallel=True)),
            df.vbt.crossed_below(df.iloc[:, ::-1], jitted=dict(parallel=False))
        )
        pd.testing.assert_frame_equal(
            df.vbt.crossed_below(df.iloc[:, ::-1], chunked=True),
            df.vbt.crossed_below(df.iloc[:, ::-1], chunked=False)
        )

    def test_stats(self):
        stats_index = pd.Index([
            'Start', 'End', 'Period', 'Count', 'Mean', 'Std', 'Min', 'Median', 'Max', 'Min Index', 'Max Index'
        ], dtype='object')
        pd.testing.assert_series_equal(
            df.vbt.stats(),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                4.0, 2.1666666666666665, 1.0531130555537456, 1.0, 2.1666666666666665, 3.3333333333333335
            ],
                index=stats_index[:-2],
                name='agg_func_mean'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt.stats(column='a'),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                4, 2.5, 1.2909944487358056, 1.0, 2.5, 4.0,
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-04 00:00:00')
            ],
                index=stats_index,
                name='a'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt.stats(column='g1', group_by=group_by),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                8, 2.5, 1.1952286093343936, 1.0, 2.5, 4.0,
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-02 00:00:00')
            ],
                index=stats_index,
                name='g1'
            )
        )
        pd.testing.assert_series_equal(
            df['c'].vbt.stats(),
            df.vbt.stats(column='c')
        )
        pd.testing.assert_series_equal(
            df['c'].vbt.stats(),
            df.vbt.stats(column='c', group_by=False)
        )
        pd.testing.assert_series_equal(
            df.vbt(group_by=group_by)['g2'].stats(),
            df.vbt(group_by=group_by).stats(column='g2')
        )
        pd.testing.assert_series_equal(
            df.vbt(group_by=group_by)['g2'].stats(),
            df.vbt.stats(column='g2', group_by=group_by)
        )
        stats_df = df.vbt.stats(agg_func=None)
        assert stats_df.shape == (3, 11)
        pd.testing.assert_index_equal(stats_df.index, df.vbt.wrapper.columns)
        pd.testing.assert_index_equal(stats_df.columns, stats_index)

    def test_mapping_stats(self):
        mapping = {x: 'test_' + str(x) for x in pd.unique(df.values.flatten())}
        stats_index = pd.Index([
            'Start', 'End', 'Period', 'Value Counts: test_1.0',
            'Value Counts: test_2.0', 'Value Counts: test_3.0',
            'Value Counts: test_4.0', 'Value Counts: test_nan'
        ], dtype='object')
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping).stats(),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                1.3333333333333333, 1.3333333333333333, 0.6666666666666666, 0.6666666666666666, 1.0
            ],
                index=stats_index,
                name='agg_func_mean'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping).stats(column='a'),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                1, 1, 1, 1, 1
            ],
                index=stats_index,
                name='a'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping).stats(column='g1', group_by=group_by),
            pd.Series([
                pd.Timestamp('2018-01-01 00:00:00'),
                pd.Timestamp('2018-01-05 00:00:00'),
                pd.Timedelta('5 days 00:00:00'),
                2, 2, 2, 2, 2
            ],
                index=stats_index,
                name='g1'
            )
        )
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping).stats(),
            df.vbt.stats(settings=dict(mapping=mapping))
        )
        pd.testing.assert_series_equal(
            df['c'].vbt(mapping=mapping).stats(settings=dict(incl_all_keys=True)),
            df.vbt(mapping=mapping).stats(column='c')
        )
        pd.testing.assert_series_equal(
            df['c'].vbt(mapping=mapping).stats(settings=dict(incl_all_keys=True)),
            df.vbt(mapping=mapping).stats(column='c', group_by=False)
        )
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping, group_by=group_by)['g2'].stats(settings=dict(incl_all_keys=True)),
            df.vbt(mapping=mapping, group_by=group_by).stats(column='g2')
        )
        pd.testing.assert_series_equal(
            df.vbt(mapping=mapping, group_by=group_by)['g2'].stats(settings=dict(incl_all_keys=True)),
            df.vbt(mapping=mapping).stats(column='g2', group_by=group_by)
        )
        stats_df = df.vbt(mapping=mapping).stats(agg_func=None)
        assert stats_df.shape == (3, 8)
        pd.testing.assert_index_equal(stats_df.index, df.vbt.wrapper.columns)
        pd.testing.assert_index_equal(stats_df.columns, stats_index)
