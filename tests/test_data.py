import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
import pytz

import vectorbt as vbt
from vectorbt.utils.config import merge_dicts
from vectorbt.utils.datetime_ import to_timezone

seed = 42


# ############# Global ############# #

def setup_module():
    if os.environ.get('VBT_DISABLE_CACHING', '0') == '1':
        vbt.settings.caching['disable_machinery'] = True
    vbt.settings.pbar['disable'] = True
    vbt.settings.numba['check_func_suffix'] = True


def teardown_module():
    vbt.settings.reset()


# ############# base.py ############# #


class MyData(vbt.Data):
    @classmethod
    def fetch_symbol(cls, symbol, shape=(5, 3), start_date=datetime(2020, 1, 1),
                     columns=None, index_mask=None, column_mask=None, return_arr=False,
                     tz_localize=None, is_update=False):
        np.random.seed(seed)
        a = np.empty(shape, dtype=object)
        if a.ndim == 1:
            for i in range(a.shape[0]):
                a[i] = str(symbol) + '_' + str(i)
                if is_update:
                    a[i] += '_u'
        else:
            for col in range(a.shape[1]):
                for i in range(a.shape[0]):
                    a[i, col] = str(symbol) + '_' + str(col) + '_' + str(i)
                    if is_update:
                        a[i, col] += '_u'
        if return_arr:
            return a
        index = [start_date + timedelta(days=i) for i in range(a.shape[0])]
        if a.ndim == 1:
            sr = pd.Series(a, index=index, name=columns)
            if index_mask is not None:
                sr = sr.loc[index_mask]
            if tz_localize is not None:
                sr = sr.tz_localize(tz_localize)
            return sr
        df = pd.DataFrame(a, index=index, columns=columns)
        if index_mask is not None:
            df = df.loc[index_mask]
        if column_mask is not None:
            df = df.loc[:, column_mask]
        if tz_localize is not None:
            df = df.tz_localize(tz_localize)
        return df

    def update_symbol(self, symbol, n=1, **kwargs):
        fetch_kwargs = self.select_symbol_kwargs(symbol, self.fetch_kwargs)
        fetch_kwargs['start_date'] = self.last_index[symbol]
        shape = fetch_kwargs.pop('shape', (5, 3))
        new_shape = (n, shape[1]) if len(shape) > 1 else (n,)
        kwargs = merge_dicts(fetch_kwargs, kwargs)
        return self.fetch_symbol(symbol, shape=new_shape, is_update=True, **kwargs)


class TestData:
    def test_config(self, tmp_path):
        data = MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2'])
        assert MyData.loads(data.dumps()) == data
        data.save(tmp_path / 'data')
        assert MyData.load(tmp_path / 'data') == data

    def test_fetch(self):
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), return_arr=True).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ]
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3), return_arr=True).data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_4', '0_1_4', '0_2_4']
                ]
            )
        )
        index = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=timezone.utc
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,)).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), columns='feat0').data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index,
                name='feat0'
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3)).data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_4', '0_1_4', '0_2_4']
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_4', '0_1_4', '0_2_4']
                ],
                index=index,
                columns=pd.Index(['feat0', 'feat1', 'feat2'], dtype='object'))
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,)).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,)).data[1],
            pd.Series(
                [
                    '1_0',
                    '1_1',
                    '1_2',
                    '1_3',
                    '1_4'
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3)).data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_4', '0_1_4', '0_2_4']
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3)).data[1],
            pd.DataFrame(
                [
                    ['1_0_0', '1_1_0', '1_2_0'],
                    ['1_0_1', '1_1_1', '1_2_1'],
                    ['1_0_2', '1_1_2', '1_2_2'],
                    ['1_0_3', '1_1_3', '1_2_3'],
                    ['1_0_4', '1_1_4', '1_2_4']
                ],
                index=index
            )
        )
        index2 = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=pytz.utc
        ).tz_convert(to_timezone('Europe/Berlin'))
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), tz_localize='UTC', tz_convert='Europe/Berlin').data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index2
            )
        )
        index_mask = vbt.symbol_dict({
            0: [False, True, True, True, True],
            1: [True, True, True, True, False]
        })
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan').data[0],
            pd.Series(
                [
                    np.nan,
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan').data[1],
            pd.Series(
                [
                    '1_0',
                    '1_1',
                    '1_2',
                    '1_3',
                    np.nan
                ],
                index=index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop').data[0],
            pd.Series(
                [
                    '0_1',
                    '0_2',
                    '0_3'
                ],
                index=index[1:4]
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop').data[1],
            pd.Series(
                [
                    '1_1',
                    '1_2',
                    '1_3'
                ],
                index=index[1:4]
            )
        )
        column_mask = vbt.symbol_dict({
            0: [False, True, True],
            1: [True, True, False]
        })
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan').data[0],
            pd.DataFrame(
                [
                    [np.nan, np.nan, np.nan],
                    [np.nan, '0_1_1', '0_2_1'],
                    [np.nan, '0_1_2', '0_2_2'],
                    [np.nan, '0_1_3', '0_2_3'],
                    [np.nan, '0_1_4', '0_2_4']
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan').data[1],
            pd.DataFrame(
                [
                    ['1_0_0', '1_1_0', np.nan],
                    ['1_0_1', '1_1_1', np.nan],
                    ['1_0_2', '1_1_2', np.nan],
                    ['1_0_3', '1_1_3', np.nan],
                    [np.nan, np.nan, np.nan]
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop').data[0],
            pd.DataFrame(
                [
                    ['0_1_1'],
                    ['0_1_2'],
                    ['0_1_3']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop').data[1],
            pd.DataFrame(
                [
                    ['1_1_1'],
                    ['1_1_2'],
                    ['1_1_3']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        with pytest.raises(Exception):
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='raise', missing_columns='nan')
        with pytest.raises(Exception):
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='raise')
        with pytest.raises(Exception):
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='test', missing_columns='nan')
        with pytest.raises(Exception):
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='test')

    def test_update(self):
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), return_arr=True).update().data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u'
                ]
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), return_arr=True).update(n=2).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u',
                    '0_1_u'
                ]
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3), return_arr=True).update().data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_0_u', '0_1_0_u', '0_2_0_u']
                ]
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3), return_arr=True).update(n=2).data[0],
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_0_u', '0_1_0_u', '0_2_0_u'],
                    ['0_0_1_u', '0_1_1_u', '0_2_1_u']
                ]
            )
        )
        index = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=timezone.utc
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,)).update().data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u'
                ],
                index=index
            )
        )
        updated_index = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00',
                '2020-01-06 00:00:00'
            ],
            freq='D',
            tz=timezone.utc
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,)).update(n=2).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u',
                    '0_1_u'
                ],
                index=updated_index
            )
        )
        index2 = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=pytz.utc
        ).tz_convert(to_timezone('Europe/Berlin'))
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), tz_localize='UTC', tz_convert='Europe/Berlin')
                .update(tz_localize=None).data[0],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u'
                ],
                index=index2
            )
        )
        index_mask = vbt.symbol_dict({
            0: [False, True, True, True, True],
            1: [True, True, True, True, False]
        })
        update_index_mask = vbt.symbol_dict({
            0: [True],
            1: [False]
        })
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan')
                .update(index_mask=update_index_mask).data[0],
            pd.Series(
                [
                    np.nan,
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u'
                ],
                index=index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan')
                .update(index_mask=update_index_mask).data[1],
            pd.Series(
                [
                    '1_0',
                    '1_1',
                    '1_2',
                    '1_3',
                    np.nan
                ],
                index=index
            )
        )
        update_index_mask2 = vbt.symbol_dict({
            0: [True, False, False],
            1: [True, False, True]
        })
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan')
                .update(n=3, index_mask=update_index_mask2).data[0],
            pd.Series(
                [
                    np.nan,
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_0_u',
                    np.nan
                ],
                index=updated_index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='nan')
                .update(n=3, index_mask=update_index_mask2).data[1],
            pd.Series(
                [
                    '1_0',
                    '1_1',
                    '1_2',
                    '1_0_u',
                    np.nan,
                    '1_2_u',
                ],
                index=updated_index
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop')
                .update(index_mask=update_index_mask).data[0],
            pd.Series(
                [
                    '0_1',
                    '0_2',
                    '0_3'
                ],
                index=index[1:4]
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop')
                .update(index_mask=update_index_mask).data[1],
            pd.Series(
                [
                    '1_1',
                    '1_2',
                    '1_3'
                ],
                index=index[1:4]
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop')
                .update(n=3, index_mask=update_index_mask2).data[0],
            pd.Series(
                [
                    '0_1',
                    '0_2',
                    '0_3'
                ],
                index=index[1:4]
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch([0, 1], shape=(5,), index_mask=index_mask, missing_index='drop')
                .update(n=3, index_mask=update_index_mask2).data[1],
            pd.Series(
                [
                    '1_1',
                    '1_2',
                    '1_0_u'
                ],
                index=index[1:4]
            )
        )
        column_mask = vbt.symbol_dict({
            0: [False, True, True],
            1: [True, True, False]
        })
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan')
                .update(index_mask=update_index_mask).data[0],
            pd.DataFrame(
                [
                    [np.nan, np.nan, np.nan],
                    [np.nan, '0_1_1', '0_2_1'],
                    [np.nan, '0_1_2', '0_2_2'],
                    [np.nan, '0_1_3', '0_2_3'],
                    [np.nan, '0_1_0_u', '0_2_0_u']
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan')
                .update(index_mask=update_index_mask).data[1],
            pd.DataFrame(
                [
                    ['1_0_0', '1_1_0', np.nan],
                    ['1_0_1', '1_1_1', np.nan],
                    ['1_0_2', '1_1_2', np.nan],
                    ['1_0_3', '1_1_3', np.nan],
                    [np.nan, np.nan, np.nan]
                ],
                index=index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan')
                .update(n=3, index_mask=update_index_mask2).data[0],
            pd.DataFrame(
                [
                    [np.nan, np.nan, np.nan],
                    [np.nan, '0_1_1', '0_2_1'],
                    [np.nan, '0_1_2', '0_2_2'],
                    [np.nan, '0_1_3', '0_2_3'],
                    [np.nan, '0_1_0_u', '0_2_0_u'],
                    [np.nan, np.nan, np.nan]
                ],
                index=updated_index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='nan', missing_columns='nan')
                .update(n=3, index_mask=update_index_mask2).data[1],
            pd.DataFrame(
                [
                    ['1_0_0', '1_1_0', np.nan],
                    ['1_0_1', '1_1_1', np.nan],
                    ['1_0_2', '1_1_2', np.nan],
                    ['1_0_0_u', '1_1_0_u', np.nan],
                    [np.nan, np.nan, np.nan],
                    ['1_0_2_u', '1_1_2_u', np.nan]
                ],
                index=updated_index
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop')
                .update(index_mask=update_index_mask).data[0],
            pd.DataFrame(
                [
                    ['0_1_1'],
                    ['0_1_2'],
                    ['0_1_3']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop')
                .update(index_mask=update_index_mask).data[1],
            pd.DataFrame(
                [
                    ['1_1_1'],
                    ['1_1_2'],
                    ['1_1_3']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop')
                .update(n=3, index_mask=update_index_mask2).data[0],
            pd.DataFrame(
                [
                    ['0_1_1'],
                    ['0_1_2'],
                    ['0_1_3']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
                         missing_index='drop', missing_columns='drop')
                .update(n=3, index_mask=update_index_mask2).data[1],
            pd.DataFrame(
                [
                    ['1_1_1'],
                    ['1_1_2'],
                    ['1_1_0_u']
                ],
                index=index[1:4],
                columns=pd.Int64Index([1], dtype='int64')
            )
        )
        assert MyData.fetch(
            [0, 1], shape=(5, 3),
            index_mask=index_mask, column_mask=column_mask,
            missing_index='drop', missing_columns='drop').last_index == \
               {0: index[4], 1: index[3]}
        assert MyData.fetch(
            [0, 1], shape=(5, 3),
            index_mask=index_mask, column_mask=column_mask,
            missing_index='drop', missing_columns='drop') \
                   .update(n=3, index_mask=update_index_mask2).last_index == \
               {0: updated_index[4], 1: updated_index[5]}

    def test_concat(self):
        index = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=timezone.utc
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), columns='feat0').concat()['feat0'],
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index,
                name=0
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5,), columns='feat0').concat()['feat0'],
            pd.DataFrame(
                [
                    ['0_0', '1_0'],
                    ['0_1', '1_1'],
                    ['0_2', '1_2'],
                    ['0_3', '1_3'],
                    ['0_4', '1_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat0'],
            pd.Series(
                [
                    '0_0_0',
                    '0_0_1',
                    '0_0_2',
                    '0_0_3',
                    '0_0_4'
                ],
                index=index,
                name=0
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat1'],
            pd.Series(
                [
                    '0_1_0',
                    '0_1_1',
                    '0_1_2',
                    '0_1_3',
                    '0_1_4'
                ],
                index=index,
                name=0
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat2'],
            pd.Series(
                [
                    '0_2_0',
                    '0_2_1',
                    '0_2_2',
                    '0_2_3',
                    '0_2_4'
                ],
                index=index,
                name=0
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat0'],
            pd.DataFrame(
                [
                    ['0_0_0', '1_0_0'],
                    ['0_0_1', '1_0_1'],
                    ['0_0_2', '1_0_2'],
                    ['0_0_3', '1_0_3'],
                    ['0_0_4', '1_0_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat1'],
            pd.DataFrame(
                [
                    ['0_1_0', '1_1_0'],
                    ['0_1_1', '1_1_1'],
                    ['0_1_2', '1_1_2'],
                    ['0_1_3', '1_1_3'],
                    ['0_1_4', '1_1_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).concat()['feat2'],
            pd.DataFrame(
                [
                    ['0_2_0', '1_2_0'],
                    ['0_2_1', '1_2_1'],
                    ['0_2_2', '1_2_2'],
                    ['0_2_3', '1_2_3'],
                    ['0_2_4', '1_2_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )

    def test_get(self):
        index = pd.DatetimeIndex(
            [
                '2020-01-01 00:00:00',
                '2020-01-02 00:00:00',
                '2020-01-03 00:00:00',
                '2020-01-04 00:00:00',
                '2020-01-05 00:00:00'
            ],
            freq='D',
            tz=timezone.utc
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5,), columns='feat0').get(),
            pd.Series(
                [
                    '0_0',
                    '0_1',
                    '0_2',
                    '0_3',
                    '0_4'
                ],
                index=index,
                name='feat0'
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).get(),
            pd.DataFrame(
                [
                    ['0_0_0', '0_1_0', '0_2_0'],
                    ['0_0_1', '0_1_1', '0_2_1'],
                    ['0_0_2', '0_1_2', '0_2_2'],
                    ['0_0_3', '0_1_3', '0_2_3'],
                    ['0_0_4', '0_1_4', '0_2_4']
                ],
                index=index,
                columns=pd.Index(['feat0', 'feat1', 'feat2'], dtype='object')
            )
        )
        pd.testing.assert_series_equal(
            MyData.fetch(0, shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).get('feat0'),
            pd.Series(
                [
                    '0_0_0',
                    '0_0_1',
                    '0_0_2',
                    '0_0_3',
                    '0_0_4'
                ],
                index=index,
                name='feat0'
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5,), columns='feat0').get(),
            pd.DataFrame(
                [
                    ['0_0', '1_0'],
                    ['0_1', '1_1'],
                    ['0_2', '1_2'],
                    ['0_3', '1_3'],
                    ['0_4', '1_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).get('feat0'),
            pd.DataFrame(
                [
                    ['0_0_0', '1_0_0'],
                    ['0_0_1', '1_0_1'],
                    ['0_0_2', '1_0_2'],
                    ['0_0_3', '1_0_3'],
                    ['0_0_4', '1_0_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).get(['feat0', 'feat1'])[0],
            pd.DataFrame(
                [
                    ['0_0_0', '1_0_0'],
                    ['0_0_1', '1_0_1'],
                    ['0_0_2', '1_0_2'],
                    ['0_0_3', '1_0_3'],
                    ['0_0_4', '1_0_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )
        pd.testing.assert_frame_equal(
            MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).get()[0],
            pd.DataFrame(
                [
                    ['0_0_0', '1_0_0'],
                    ['0_0_1', '1_0_1'],
                    ['0_0_2', '1_0_2'],
                    ['0_0_3', '1_0_3'],
                    ['0_0_4', '1_0_4']
                ],
                index=index,
                columns=pd.Int64Index([0, 1], dtype='int64', name='symbol')
            )
        )

    def test_indexing(self):
        assert MyData.fetch([0, 1], shape=(5,), columns='feat0').iloc[:3].wrapper == \
               MyData.fetch([0, 1], shape=(3,), columns='feat0').wrapper
        assert MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2']).iloc[:3].wrapper == \
               MyData.fetch([0, 1], shape=(3, 3), columns=['feat0', 'feat1', 'feat2']).wrapper
        assert MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2'])['feat0'].wrapper == \
               MyData.fetch([0, 1], shape=(5,), columns='feat0').wrapper
        assert MyData.fetch([0, 1], shape=(5, 3), columns=['feat0', 'feat1', 'feat2'])[['feat0']].wrapper == \
               MyData.fetch([0, 1], shape=(5, 1), columns=['feat0']).wrapper

    def test_stats(self):
        index_mask = vbt.symbol_dict({
            0: [False, True, True, True, True],
            1: [True, True, True, True, False]
        })
        column_mask = vbt.symbol_dict({
            0: [False, True, True],
            1: [True, True, False]
        })
        data = MyData.fetch(
            [0, 1], shape=(5, 3), index_mask=index_mask, column_mask=column_mask,
            missing_index='nan', missing_columns='nan', columns=['feat0', 'feat1', 'feat2'])

        stats_index = pd.Index([
            'Start', 'End', 'Period', 'Total Symbols', 'Null Counts: 0', 'Null Counts: 1'
        ], dtype='object')
        pd.testing.assert_series_equal(
            data.stats(),
            pd.Series([
                pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC'),
                pd.Timestamp('2020-01-05 00:00:00+0000', tz='UTC'),
                pd.Timedelta('5 days 00:00:00'),
                2, 2.3333333333333335, 2.3333333333333335
            ],
                index=stats_index,
                name='agg_func_mean'
            )
        )
        pd.testing.assert_series_equal(
            data.stats(column='feat0'),
            pd.Series([
                pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC'),
                pd.Timestamp('2020-01-05 00:00:00+0000', tz='UTC'),
                pd.Timedelta('5 days 00:00:00'),
                2, 5, 1
            ],
                index=stats_index,
                name='feat0'
            )
        )
        pd.testing.assert_series_equal(
            data.stats(group_by=True),
            pd.Series([
                pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC'),
                pd.Timestamp('2020-01-05 00:00:00+0000', tz='UTC'),
                pd.Timedelta('5 days 00:00:00'),
                2, 7, 7
            ],
                index=stats_index,
                name='group'
            )
        )
        pd.testing.assert_series_equal(
            data['feat0'].stats(),
            data.stats(column='feat0')
        )
        pd.testing.assert_series_equal(
            data.replace(wrapper=data.wrapper.replace(group_by=True)).stats(),
            data.stats(group_by=True)
        )
        stats_df = data.stats(agg_func=None)
        assert stats_df.shape == (3, 6)
        pd.testing.assert_index_equal(stats_df.index, data.wrapper.columns)
        pd.testing.assert_index_equal(stats_df.columns, stats_index)


# ############# custom.py ############# #

class TestCustom:
    def test_csv_data(self, tmp_path):
        sr = pd.Series(np.arange(10))
        sr.to_csv(tmp_path / 'temp.csv')
        csv_data = vbt.CSVData.fetch(tmp_path / 'temp.csv')
        pd.testing.assert_series_equal(
            csv_data.get(),
            sr
        )
        csv_data = vbt.CSVData.fetch(tmp_path / 'temp.csv', start_row=2, end_row=3)
        pd.testing.assert_series_equal(
            csv_data.get(),
            sr.iloc[2:4]
        )
        df = pd.DataFrame(np.arange(20).reshape((10, 2)))
        df.columns = pd.MultiIndex.from_tuples([('1', '2'), ('3', '4')], names=['a', 'b'])
        df.to_csv(tmp_path / 'temp.csv')
        csv_data = vbt.CSVData.fetch(tmp_path / 'temp.csv', header=[0, 1], start_row=0, end_row=1)
        pd.testing.assert_frame_equal(
            csv_data.get(),
            df.iloc[:2]
        )
        assert csv_data.returned_kwargs[tmp_path / 'temp.csv'] == {'last_row': 1}
        csv_data = csv_data.update()
        pd.testing.assert_frame_equal(
            csv_data.get(),
            df.iloc[:2]
        )
        assert csv_data.returned_kwargs[tmp_path / 'temp.csv'] == {'last_row': 1}
        csv_data = csv_data.update(end_row=2)
        csv_data.get()
        pd.testing.assert_frame_equal(
            csv_data.get(),
            df.iloc[:3]
        )
        assert csv_data.returned_kwargs[tmp_path / 'temp.csv'] == {'last_row': 2}
        csv_data = csv_data.update(end_row=None)
        pd.testing.assert_frame_equal(
            csv_data.get(),
            df
        )
        assert csv_data.returned_kwargs[tmp_path / 'temp.csv'] == {'last_row': 9}

    def test_hdf_data(self, tmp_path):
        sr = pd.Series(np.arange(10))
        sr.to_hdf(tmp_path / 'temp.h5', 's')
        hdf_data = vbt.HDFData.fetch('s', path=tmp_path / 'temp.h5')
        pd.testing.assert_series_equal(
            hdf_data.get(),
            sr
        )
        hdf_data = vbt.HDFData.fetch('s', path=tmp_path / 'temp.h5', start_row=2, end_row=3)
        pd.testing.assert_series_equal(
            hdf_data.get(),
            sr.iloc[2:4]
        )
        df = pd.DataFrame(np.arange(20).reshape((10, 2)))
        df.columns = pd.MultiIndex.from_tuples([('1', '2'), ('3', '4')], names=['a', 'b'])
        df.to_hdf(tmp_path / 'temp.h5', 'df')
        hdf_data = vbt.HDFData.fetch('df', path=tmp_path / 'temp.h5', header=[0, 1], start_row=0, end_row=1)
        pd.testing.assert_frame_equal(
            hdf_data.get(),
            df.iloc[:2]
        )
        assert hdf_data.returned_kwargs['df'] == {'last_row': 1}
        hdf_data = hdf_data.update()
        pd.testing.assert_frame_equal(
            hdf_data.get(),
            df.iloc[:2]
        )
        assert hdf_data.returned_kwargs['df'] == {'last_row': 1}
        hdf_data = hdf_data.update(end_row=2)
        hdf_data.get()
        pd.testing.assert_frame_equal(
            hdf_data.get(),
            df.iloc[:3]
        )
        assert hdf_data.returned_kwargs['df'] == {'last_row': 2}
        hdf_data = hdf_data.update(end_row=None)
        pd.testing.assert_frame_equal(
            hdf_data.get(),
            df
        )
        assert hdf_data.returned_kwargs['df'] == {'last_row': 9}

    def test_random_data(self):
        pd.testing.assert_series_equal(
            vbt.RandomData.fetch(start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.Series(
                [100.49671415301123, 100.35776307348756, 101.00776880200878, 102.54614727815496, 102.3060320136544],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D')
            )
        )
        pd.testing.assert_frame_equal(
            vbt.RandomData.fetch(num_paths=2, start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.DataFrame(
                [
                    [100.49671415301123, 99.7658630430508],
                    [100.35776307348756, 101.34137833772823],
                    [101.00776880200878, 102.11910727009419],
                    [102.54614727815496, 101.63968421831567],
                    [102.3060320136544, 102.1911405333112]
                ],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D'),
                columns=pd.Index([0, 1], name='path')
            )
        )
        pd.testing.assert_frame_equal(
            vbt.RandomData.fetch([0, 1], start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.DataFrame(
                [
                    [100.49671415301123, 100.49671415301123],
                    [100.35776307348756, 100.35776307348756],
                    [101.00776880200878, 101.00776880200878],
                    [102.54614727815496, 102.54614727815496],
                    [102.3060320136544, 102.3060320136544]
                ],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D'),
                columns=pd.Index([0, 1], name='symbol')
            )
        )

    def test_gbm_data(self):
        pd.testing.assert_series_equal(
            vbt.GBMData.fetch(start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.Series(
                [100.49292505095792, 100.34905764408163, 100.99606643427086, 102.54091282498935, 102.29597577584751],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D')
            )
        )
        pd.testing.assert_frame_equal(
            vbt.GBMData.fetch(num_paths=2, start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.DataFrame(
                [
                    [100.49292505095792, 99.76114874768454],
                    [100.34905764408163, 101.34402779029647],
                    [100.99606643427086, 102.119662952671],
                    [102.54091282498935, 101.6362789823718],
                    [102.29597577584751, 102.1841061387023]
                ],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D'),
                columns=pd.Index([0, 1], name='path')
            )
        )
        pd.testing.assert_frame_equal(
            vbt.GBMData.fetch([0, 1], start='2021-01-01 UTC', end='2021-01-05 UTC', seed=42).get(),
            pd.DataFrame(
                [
                    [100.49292505095792, 100.49292505095792],
                    [100.34905764408163, 100.34905764408163],
                    [100.99606643427086, 100.99606643427086],
                    [102.54091282498935, 102.54091282498935],
                    [102.29597577584751, 102.29597577584751]
                ],
                index=pd.DatetimeIndex([
                    datetime(2021, 1, 1),
                    datetime(2021, 1, 2),
                    datetime(2021, 1, 3),
                    datetime(2021, 1, 4),
                    datetime(2021, 1, 5)
                ], dtype='datetime64[ns, UTC]', freq='D'),
                columns=pd.Index([0, 1], name='symbol')
            )
        )


# ############# updater.py ############# #

class TestDataUpdater:
    def test_update(self):
        data = MyData.fetch(0, shape=(5,), return_arr=True)
        updater = vbt.DataUpdater(data)
        updater.update()
        assert updater.data == data.update()
        assert updater.config['data'] == data.update()

    def test_update_every(self):
        data = MyData.fetch(0, shape=(5,), return_arr=True)
        kwargs = dict(call_count=0)

        class DataUpdater(vbt.DataUpdater):
            def update(self, kwargs):
                super().update()
                kwargs['call_count'] += 1
                if kwargs['call_count'] == 5:
                    raise vbt.CancelledError

        updater = DataUpdater(data)
        updater.update_every(kwargs=kwargs)
        for i in range(5):
            data = data.update()
        assert updater.data == data
        assert updater.config['data'] == data
