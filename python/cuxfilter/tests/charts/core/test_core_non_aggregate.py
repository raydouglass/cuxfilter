import pytest
import cudf

from cuxfilter.charts.core.non_aggregate.core_non_aggregate import (
    BaseNonAggregate,
)
from cuxfilter.dashboard import DashBoard
from cuxfilter.layouts import chart_view


class TestCoreNonAggregateChart:
    def test_variables(self):
        bnac = BaseNonAggregate()

        # BaseChart variables
        assert bnac.chart_type is None
        assert bnac.x is None
        assert bnac.y is None
        assert bnac.aggregate_fn == "count"
        assert bnac.color is None
        assert bnac.height == 0
        assert bnac.width == 0
        assert bnac.add_interaction is True
        assert bnac.chart is None
        assert bnac.source is None
        assert bnac.source_backup is None
        assert bnac.data_points == 0
        assert bnac._library_specific_params == {}
        assert bnac._stride is None
        assert bnac.stride_type == int
        assert bnac.min_value == 0.0
        assert bnac.max_value == 0.0
        assert bnac.x_label_map == {}
        assert bnac.y_label_map == {}

        # test chart name setter
        bnac.x = "test_x"
        bnac.chart_type = "test_chart_type"

        assert bnac.name == "test_x_test_chart_type"

        # BaseNonAggregateChart variables
        assert bnac.use_data_tiles is False
        assert bnac.reset_event is None
        assert bnac.x_range is None
        assert bnac.y_range is None
        assert bnac.aggregate_col is None

    @pytest.mark.parametrize("stride, _stride", [(1, 1), (None, None), (0, 1)])
    def test_stride(self, stride, _stride):
        bnac = BaseNonAggregate()
        bnac.stride = stride
        assert bnac._stride == _stride

    def test_label_mappers(self):
        bnac = BaseNonAggregate()
        library_specific_params = {
            "x_label_map": {"a": 1, "b": 2},
            "y_label_map": {"a": 1, "b": 2},
        }
        bnac.library_specific_params = library_specific_params

        assert bnac.x_label_map == {"a": 1, "b": 2}
        assert bnac.y_label_map == {"a": 1, "b": 2}

    @pytest.mark.parametrize("chart, _chart", [(None, None), (1, 1)])
    def test_view(self, chart, _chart):
        bnac = BaseNonAggregate()
        bnac.chart = chart
        bnac.width = 400

        assert str(bnac.view()) == str(chart_view(_chart, width=bnac.width))

    def test_get_selection_geometry_callback(self):
        bnac = BaseNonAggregate()

        df = cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]})
        dashboard = DashBoard(data=df)

        assert (
            bnac.get_selection_geometry_callback(dashboard).__name__
            == "selection_callback"
        )
        assert callable(type(bnac.get_selection_geometry_callback(dashboard)))

    def test_selection_callback(self):
        bnac = BaseNonAggregate()
        bnac.x = "a"
        bnac.y = "b"
        bnac.chart_type = "temp"
        self.result = None

        def t_function(data, patch_update=False):
            self.result = data

        bnac.reload_chart = t_function
        df = cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]})
        dashboard = DashBoard(data=df)

        dashboard._active_view = bnac.name

        t = bnac.get_selection_geometry_callback(dashboard)
        t(xmin=1, xmax=2, ymin=3, ymax=4)
        assert self.result.equals(df.query("1<=a<=2 and 3<=b<=4"))

    @pytest.mark.parametrize(
        "data, _data",
        [
            (cudf.DataFrame(), cudf.DataFrame()),
            (
                cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]}),
                cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]}),
            ),
        ],
    )
    def test_calculate_source(self, data, _data):
        """
        Calculate source just calls to the format_source_data function
        which is implemented by chart types inheriting this class.
        """
        bnac = BaseNonAggregate()
        self.result = None

        def t_function(data, patch_update=False):
            self.result = data

        bnac.format_source_data = t_function

        bnac.calculate_source(data)
        assert self.result.equals(_data)

    @pytest.mark.parametrize(
        "x_range, y_range, query",
        [
            ((1, 2), (3, 4), "1<=a <= 2 and 3<=b <= 4"),
            ((0, 2), (3, 5), "0<=a <= 2 and 3<=b <= 5"),
        ],
    )
    def test_compute_query_dict(self, x_range, y_range, query):
        bnac = BaseNonAggregate()
        bnac.chart_type = "test"
        bnac.x = "a"
        bnac.y = "b"
        bnac.x_range = x_range
        bnac.y_range = y_range

        df = cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]})
        dashboard = DashBoard(data=df)

        bnac.compute_query_dict(dashboard._query_str_dict)

        assert dashboard._query_str_dict["a_test"] == query

    @pytest.mark.parametrize(
        "add_interaction, reset_event, event_1, event_2",
        [
            (True, None, "selection_callback", None),
            (True, "test_event", "selection_callback", "reset_callback"),
            (False, "test_event", None, "reset_callback"),
        ],
    )
    def test_add_events(self, add_interaction, reset_event, event_1, event_2):
        bnac = BaseNonAggregate()
        bnac.add_interaction = add_interaction
        bnac.reset_event = reset_event

        df = cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]})
        dashboard = DashBoard(data=df)

        self.event_1 = None
        self.event_2 = None

        def t_func(fn):
            self.event_1 = fn.__name__

        def t_func1(event, fn):
            self.event_2 = fn.__name__

        bnac.add_selection_geometry_event = t_func
        bnac.add_event = t_func1

        bnac.add_events(dashboard)

        assert self.event_1 == event_1
        assert self.event_2 == event_2

    def test_add_reset_event(self):
        bnac = BaseNonAggregate()
        bnac.chart_type = "test"
        bnac.x = "a"
        bnac.x_range = (0, 2)
        bnac.y_range = (3, 5)

        df = cudf.DataFrame({"a": [1, 2, 2], "b": [3, 4, 5]})
        dashboard = DashBoard(data=df)
        dashboard._active_view = "a_test"

        def t_func1(event, fn):
            fn("event")

        bnac.add_event = t_func1

        bnac.add_reset_event(dashboard)

        assert bnac.x_range is None
        assert bnac.y_range is None
        assert dashboard._active_view == "a_test"

    def test_query_chart_by_range(self):
        bnac = BaseNonAggregate()
        bnac.chart_type = "test"
        bnac.x = "a"

        bnac_1 = BaseNonAggregate()
        bnac_1.chart_type = "test"
        bnac_1.x = "b"

        query_tuple = (4, 5)

        df = cudf.DataFrame({"a": [1, 2, 3, 4], "b": [3, 4, 5, 6]})
        bnac.source = df

        self.result = None
        self.patch_update = None

        def t_func(data, patch_update):
            self.result = data
            self.patch_update = patch_update

        # creating a dummy reload chart fn as its not implemented in core
        # non aggregate chart class
        bnac.reload_chart = t_func

        bnac.query_chart_by_range(
            active_chart=bnac_1, query_tuple=query_tuple, datatile=None
        )

        assert self.result.to_string() == "   a  b\n1  2  4\n2  3  5"
        assert self.patch_update is False

    @pytest.mark.parametrize(
        "new_indices, result",
        [
            ([4, 5], "   a  b\n1  2  4\n2  3  5"),
            ([], "   a  b\n0  1  3\n1  2  4\n2  3  5\n3  4  6"),
            ([3], "   a  b\n0  1  3"),
        ],
    )
    def test_query_chart_by_indices(self, new_indices, result):
        bnac = BaseNonAggregate()
        bnac.chart_type = "test"
        bnac.x = "a"

        bnac_1 = BaseNonAggregate()
        bnac_1.chart_type = "test"
        bnac_1.x = "b"

        new_indices = new_indices

        df = cudf.DataFrame({"a": [1, 2, 3, 4], "b": [3, 4, 5, 6]})
        bnac.source = df

        self.result = None
        self.patch_update = None

        def t_func(data, patch_update):
            self.result = data
            self.patch_update = patch_update

        # creating a dummy reload chart fn as its not implemented in core
        # non aggregate chart class
        bnac.reload_chart = t_func

        bnac.query_chart_by_indices(
            active_chart=bnac_1,
            old_indices=[],
            new_indices=new_indices,
            datatile=None,
        )

        assert self.result.to_string() == result
        assert self.patch_update is False
