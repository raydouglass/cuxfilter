from typing import Dict, Type
import bokeh.embed.util as u
import panel as pn
import uuid
from panel.io.server import _origin_url, get_server
from bokeh.embed import server_document
import re

from .charts.core.core_chart import BaseChart
from .datatile import DataTile
from .layouts import single_feature
from .charts.panel_widgets import data_size_indicator
from .assets import screengrab, get_open_port
from .themes import light

_server_info = (
    "<b>Running server:</b>"
    '<a target="_blank" href="https://localhost:{port}">'
    "https://localhost:{port}</a>"
)
EXEC_MIME = "application/vnd.holoviews_exec.v0+json"
HTML_MIME = "text/html"


def app(panel_obj, notebook_url="localhost:8888", port=0):
    """
    Displays a bokeh server app inline in the notebook.
    Arguments
    ---------
    notebook_url: str
        URL to the notebook server
    port: int (optional, default=0)
        Allows specifying a specific port
    """
    from IPython.display import publish_display_data

    if callable(notebook_url):
        origin = notebook_url(None)
    else:
        origin = _origin_url(notebook_url)
    server_id = uuid.uuid4().hex
    server = get_server(
        panel_obj, port, origin, start=True, show=False, server_id=server_id
    )

    url = "http://%s%s%d%s" % (notebook_url, "/proxy/", server.port, "/")

    script = server_document(url, resources=None)

    publish_display_data(
        {HTML_MIME: script, EXEC_MIME: ""},
        metadata={EXEC_MIME: {"server_id": server_id}},
    )
    return server


class DashBoard:
    """
    A cuxfilter GPU DashBoard object.
    Examples
    --------

    Create a dashboard

    >>> import cudf
    >>> import cuxfilter
    >>> from cuxfilter.charts import bokehfrom cuxfilter.charts import bokeh
    >>> df = cudf.DataFrame(
    >>>     {'key': [0, 1, 2, 3, 4], 'val':[float(i + 10) for i in range(5)]}
    >>> )
    >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
    >>> line_chart_1 = bokeh.line(
    >>>     'key', 'val', data_points=5, add_interaction=False
    >>> )
    >>> line_chart_2 = bokeh.bar(
    >>>     'val', 'key', data_points=5, add_interaction=False
    >>> )
    >>> d = cux_df.dashboard([line_chart_1, line_chart_2])
    >>> d
    `cuxfilter DashBoard
    [title] Markdown(str)
    [chart1] Column(sizing_mode='scale_both', width=1600)
        [0] Bokeh(Figure)
    [chart2] Column(sizing_mode='scale_both', width=1600)
        [0] Bokeh(Figure)`
    """

    _charts: Dict[str, Type[BaseChart]]
    _data_tiles: Dict[str, Type[DataTile]]
    _query_str_dict: Dict[str, str]
    _active_view: str = ""
    _dashboard = None
    _theme = None

    def __init__(
        self,
        charts=[],
        data=None,
        layout=single_feature,
        theme=light,
        title="Dashboard",
        data_size_widget=True,
        warnings=False,
    ):
        self._backup_data = data
        self._data = self._backup_data
        self._charts = dict()
        self._data_tiles = dict()
        self._query_str_dict = dict()
        self._data_size_widget = data_size_widget
        if self._data_size_widget:
            temp_chart = data_size_indicator()
            self._charts[temp_chart.name] = temp_chart
            self._charts[temp_chart.name].initiate_chart(self)

        if len(charts) > 0:
            for chart in charts:
                self._charts[chart.name] = chart
                chart.initiate_chart(self)

        self._title = title
        self._dashboard = layout()
        self._theme = theme
        # handle dashboard warnings
        if not warnings:
            u.log.disabled = True

    @property
    def charts(self):
        """
        Charts in the dashboard as a dictionary.
        """
        return self._charts

    @property
    def title(self):
        """
        Title of the dashboard.
        """
        return self._title

    @title.setter
    def title(self, value):
        if type(value) == str:
            self._title = value
        else:
            raise TypeError("title must be of type str")

    @property
    def data_size_widget(self):
        """
        Data_size_widget flag.
        """
        return self._data_size_widget

    @data_size_widget.setter
    def data_size_widget(self, value):
        if type(value) == bool:
            self._data_size_widget = value
        else:
            raise TypeError("data_size_widget must be of type bool")

    @property
    def warnings(self):
        """
        Layout warnings flag.
        """
        return self._warnings

    @warnings.setter
    def warnings(self, value):
        if type(value) == bool:
            self._warnings = value
        else:
            raise TypeError("warnings must be of type bool")

    def add_charts(self, charts=[]):
        """
        Adding more charts to the dashboard, after it has been initialized.
        Parameters
        ----------
        charts: list
            list of cuxfilter.charts objects

        Notes
        -----
            After adding the charts, re-run the dashboard.app()
            or dashboard.show() cell to see the updated charts.

        Examples
        --------

        >>> import cudf
        >>> import cuxfilter
        >>> from cuxfilter.charts import bokeh
        >>> df = cudf.DataFrame(
        >>>     {
        >>>         'key': [0, 1, 2, 3, 4],
        >>>         'val':[float(i + 10) for i in range(5)]
        >>>     }
        >>> )
        >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
        >>> line_chart_1 = bokeh.line(
        >>>     'key', 'val', data_points=5, add_interaction=False
        >>> )
        >>> d = cux_df.dashboard([line_chart_1])
        >>> line_chart_2 = bokeh.bar(
        >>>     'val', 'key', data_points=5, add_interaction=False
        >>> )
        >>> d.add_charts([line_chart_2])

        """
        self._data_tiles = {}
        if len(self._active_view) > 0:
            self._charts[self._active_view].datatile_loaded_state = False
            self._active_view = ""

        if len(charts) > 0:
            for chart in charts:
                if chart not in self._charts:
                    self._charts[chart.name] = chart
                    chart.initiate_chart(self)

    def _query(self, query_str, inplace=False):
        """
        Query the cudf.DataFrame, inplace or create a copy based on the
        value of inplace.
        """
        if inplace:
            if len(query_str) > 0:
                # print('inplace querying')
                self._data = self._backup_data.query(query_str).copy()
            else:
                self._data = self._backup_data
        else:
            temp_data = self._backup_data.query(query_str)
            return temp_data

    def _generate_query_str(self, ignore_chart=""):
        """
        Generate query string based on current crossfiltered state of
        the dashboard.
        """
        popped_value = None

        if (
            type(ignore_chart) != str
            and len(ignore_chart.name) > 0
            and ignore_chart.name in self._query_str_dict
        ):
            popped_value = self._query_str_dict.pop(ignore_chart.name, None)

        return_query_str = " and ".join(list(self._query_str_dict.values()))

        # adding the popped value to the query_str_dict again
        if popped_value is not None:
            self._query_str_dict[ignore_chart.name] = popped_value

        return return_query_str

    def export(self):
        """
        Export the cudf.DataFrame based on the current filtered state of
        the dashboard.

        Also prints the query string of the current state of the dashboard.
        Returns
        -------
        cudf.DataFrame

        Examples
        --------
        >>> import cudf
        >>> import cuxfilter
        >>> from cuxfilter.charts import bokeh
        >>> df = cudf.DataFrame(
        >>>     {
        >>>         'key': [0, 1, 2, 3, 4],
        >>>         'val':[float(i + 10) for i in range(5)]
        >>>     }
        >>> )
        >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
        >>> line_chart_1 = bokeh.line(
        >>>     'key', 'val', data_points=5, add_interaction=False
        >>> )
        >>> line_chart_2 = bokeh.bar(
        >>>     'val', 'key', data_points=5, add_interaction=False
        >>> )
        >>> d = cux_df.dashboard([line_chart_1, line_chart_2])
        >>> d.app() #or d.show()
        displays dashboard
        do some visual querying/ crossfiltering

        >>> queried_df = d.export()
        final query 2<=key<=4


        """
        # Compute query for currently active chart, and consider its
        # current state as final state
        if self._active_view == "":
            print("no querying done, returning original dataframe")
            return self._backup_data
        else:
            self._charts[self._active_view].compute_query_dict(
                self._query_str_dict
            )

            if len(self._generate_query_str()) > 0:
                print("final query", self._generate_query_str())
                return self._backup_data.query(self._generate_query_str())
            else:
                print("no querying done, returning original dataframe")
                return self._backup_data

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        template_obj = self._dashboard.generate_dashboard(
            self._title, self._charts, self._theme
        )
        cls = "#### cuxfilter " + type(self).__name__
        spacer = "\n    "
        objs = [
            "[%s] %s" % (name, obj.__repr__())
            for name, obj in template_obj._render_items.items()
        ]
        template = "{cls}{spacer}{spacer}{objs}"
        return template.format(
            cls=cls, objs=("%s" % spacer).join(objs), spacer=spacer
        )

    def _repr_mimebundle_(self, include=None, exclude=None):
        str_repr = self.__repr__()
        server_info = pn.pane.HTML("")
        return pn.Column(str_repr, server_info, width=800)._repr_mimebundle_(
            include, exclude
        )

    def _get_server(
        self,
        port=0,
        websocket_origin=None,
        loop=None,
        show=False,
        start=False,
        **kwargs,
    ):
        return get_server(
            self._dashboard.generate_dashboard(
                self._title, self._charts, self._theme
            ),
            port,
            websocket_origin,
            loop,
            show,
            start,
            **kwargs,
        )

    async def preview(self):
        """
        Preview(Async) all the charts in a jupyter cell, non interactive(no
        backend server). Mostly intended to save notebook state for blogs,
        documentation while still rendering the dashboard.

        Notes
        -----
        Png format

        Examples
        --------

        >>> import cudf
        >>> import cuxfilter
        >>> from cuxfilter.charts import bokeh
        >>> df = cudf.DataFrame(
        >>>     {
        >>>         'key': [0, 1, 2, 3, 4],
        >>>         'val':[float(i + 10) for i in range(5)]
        >>>     }
        >>> )
        >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
        >>> line_chart_1 = bokeh.line(
        >>>     'key', 'val', data_points=5, add_interaction=False
        >>> )
        >>> line_chart_2 = bokeh.bar(
        >>>     'val', 'key', data_points=5, add_interaction=False
        >>> )
        >>> d = cux_df.dashboard([line_chart_1, line_chart_2])
        >>> await d.preview()
        displays charts in the dashboard
        """
        port = get_open_port()
        url = "localhost:" + str(port)
        temp_server = self._get_server(
            port=port, websocket_origin=url, show=False, start=True
        )
        await screengrab("http://" + url)
        temp_server.stop()
        from IPython.core.display import Image, display

        display(Image("temp.png"))

    def app(self, notebook_url="", port: int = 0):
        """
        Run the dashboard with a bokeh backend server within the notebook.
        Parameters
        ----------
        url: str, optional
            url of the notebook(including the port).
            Can use localhost instead of ip if running locally

        port: int, optional
            Port number bokeh uses for it's two communication protocol.
            Default is random open port. Recommended to set this value if
            running jupyter remotely and only few ports are exposed.

        Examples
        --------

        >>> import cudf
        >>> import cuxfilter
        >>> from cuxfilter.charts import bokeh
        >>> df = cudf.DataFrame(
        >>>     {
        >>>         'key': [0, 1, 2, 3, 4],
        >>>         'val':[float(i + 10) for i in range(5)]
        >>>     }
        >>> )
        >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
        >>> line_chart_1 = bokeh.line(
        >>>     'key', 'val', data_points=5, add_interaction=False
        >>> )
        >>> d = cux_df.dashboard([line_chart_1])
        >>> d.app(notebook_url='localhost:8888')

        """
        url = re.compile(r"https?://(www\.)?")
        notebook_url = url.sub("", notebook_url).strip().strip("/")
        if len(notebook_url) > 0:
            self.server = app(
                self._dashboard.generate_dashboard(
                    self._title, self._charts, self._theme
                ),
                notebook_url=notebook_url,
                port=port,
            )
        else:
            self.server = app(
                self._dashboard.generate_dashboard(
                    self._title, self._charts, self._theme
                )
            )

    def show(self, notebook_url="", port=0, threaded=False, **kwargs):
        """
        Run the dashboard with a bokeh backend server within the notebook.
        Parameters
        ----------
        url: str, optional
            - URL where you want to run the dashboard as a web-app,
            including the port number.
            - Can use localhost instead of ip if running locally.
            - Has to be an open port.

        Examples
        --------

        >>> import cudf
        >>> import cuxfilter
        >>> from cuxfilter.charts import bokeh
        >>> df = cudf.DataFrame(
        >>>     {
        >>>         'key': [0, 1, 2, 3, 4],
        >>>         'val':[float(i + 10) for i in range(5)]
        >>>     }
        >>> )
        >>> cux_df = cuxfilter.DataFrame.from_dataframe(df)
        >>> line_chart_1 = bokeh.line(
        >>>     'key', 'val', data_points=5, add_interaction=False
        >>> )
        >>> d = cux_df.dashboard([line_chart_1])
        >>> d.show(url='localhost:8889')

        """
        url = re.compile(r"https?://(www\.)?")
        notebook_url = url.sub("", notebook_url).strip().strip("/")
        if len(notebook_url) > 0:
            if port == 0:
                port = get_open_port()

            dashboard_url = "http://%s%s%d%s" % (
                notebook_url,
                "/proxy/",
                port,
                "/",
            )
            print("Dashboard running at " + dashboard_url)

            try:
                self.server = self._get_server(
                    port=port,
                    websocket_origin=notebook_url,
                    show=False,
                    start=True,
                    threaded=threaded,
                    **kwargs,
                )
            except OSError:
                self.server.stop()
                self.server = self._get_server(
                    port=port,
                    websocket_origin=notebook_url,
                    show=False,
                    start=True,
                    threaded=threaded,
                    **kwargs,
                )
        else:
            self.server = self._dashboard.generate_dashboard(
                self._title, self._charts, self._theme
            ).show(threaded=threaded)

    def stop(self):
        """
        stop the bokeh server
        """
        if self.server._stopped is False:
            self.server.stop()
            self.server._tornado.stop()

    def _reload_charts(self, data=None, include_cols=[], ignore_cols=[]):
        """
        Reload charts with current self._data state.
        """
        if data is None:
            data = self._data
        if len(include_cols) == 0:
            include_cols = list(self._charts.keys())
        # reloading charts as per current data state
        for chart in self._charts.values():
            if chart.name not in ignore_cols and chart.name in include_cols:
                self._charts[chart.name].reload_chart(data, True)

    def _calc_data_tiles(self, cumsum=True):
        """
        Calculate data tiles for all aggregate type charts.
        """
        query_str = self._generate_query_str(self._charts[self._active_view])

        # NO DATATILES for scatter types, as they are essentially all
        # points in the dataset
        if "scatter" not in self._active_view:
            for chart in list(self._charts.values()):
                if not chart.use_data_tiles:
                    # if chart.chart_type == 'view_dataframe':
                    #     self._data_tiles[chart.name] = self._data
                    # else:
                    self._data_tiles[chart.name] = None
                elif self._active_view != chart.name:
                    temp_query_str = self._generate_query_str(
                        ignore_chart=chart
                    )

                    if temp_query_str == query_str:
                        self._data_tiles[chart.name] = DataTile(
                            self._charts[self._active_view],
                            chart,
                            dtype="pandas",
                            cumsum=cumsum,
                        ).calc_data_tile(self._data)
                    elif len(temp_query_str) == 0:
                        self._data_tiles[chart.name] = DataTile(
                            self._charts[self._active_view],
                            chart,
                            dtype="pandas",
                            cumsum=cumsum,
                        ).calc_data_tile(self._backup_data)
                    else:
                        self._data_tiles[chart.name] = DataTile(
                            self._charts[self._active_view],
                            chart,
                            dtype="pandas",
                            cumsum=cumsum,
                        ).calc_data_tile(
                            self._query(temp_query_str, inplace=False)
                        )

        self._charts[self._active_view].datatile_loaded_state = True

    def _query_datatiles_by_range(self, query_tuple):
        """
        Update each chart using the updated values after querying
        the datatiles using query_tuple.
        Parameters
        ----------
        query_tuple: tuple
            (min_val, max_val) of the query

        """
        for chart in self._charts.values():
            if (
                self._active_view != chart.name
                and "widget" not in chart.chart_type
            ):
                chart.query_chart_by_range(
                    self._charts[self._active_view],
                    query_tuple,
                    self._data_tiles[chart.name],
                )

    def _query_datatiles_by_indices(self, old_indices, new_indices):
        """
        Update each chart using the updated values after querying the
        datatiles using new_indices.
        """
        for chart in self._charts.values():
            if (
                self._active_view != chart.name
                and "widget" not in chart.chart_type
            ):
                chart.query_chart_by_indices(
                    self._charts[self._active_view],
                    old_indices,
                    new_indices,
                    self._data_tiles[chart.name],
                )

    def _reset_current_view(self, new_active_view: BaseChart):
        """
        Reset current view and assign new view as the active view.
        """
        if len(self._active_view) == 0:
            self._active_view = new_active_view.name
            return -1

        self._charts[self._active_view].compute_query_dict(
            self._query_str_dict
        )

        # resetting the loaded state
        self._charts[self._active_view].datatile_loaded_state = False

        # switching the active view
        self._active_view = new_active_view.name

        self._query_str_dict.pop(self._active_view, None)
        # generate query_str to query self._data based on current active view,
        # before changing the active_view
        query_str = self._generate_query_str(self._charts[self._active_view])
        # execute the query_str using cudf.query()
        self._query(query_str, inplace=True)
        self._reload_charts(ignore_cols=[self._active_view])
