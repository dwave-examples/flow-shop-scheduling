"""
This file is forked from apps/dash-clinical-analytics/app.py under the following license

MIT License

Copyright (c) 2019 Plotly

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Modifications are licensed under

Apache License, Version 2.0
(see ./LICENSE for details)

"""

import pathlib
import time
from enum import Enum

import dash
import diskcache
import plotly.graph_objs as go
from dash import DiskcacheManager, ctx, MATCH
from dash.dependencies import ClientsideFunction, Input, Output, State
from dash.exceptions import PreventUpdate

from dash_html import set_html

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

# Fix Dash long callbacks crashing on macOS 10.13+ (also potentially not working
# on other POSIX systems), caused by https://bugs.python.org/issue33725
# (aka "beware of multithreaded process forking").
#
# Note: default start method has already been changed to "spawn" on darwin in
# the `multiprocessing` library, but its fork, `multiprocess` still hasn't caught up.
# (see docs: https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods)
import multiprocess
if multiprocess.get_start_method(allow_none=True) is None:
    multiprocess.set_start_method('spawn')

from app_configs import (
    APP_TITLE,
    CLASSICAL_TAB_LABEL,
    DEBUG,
    DWAVE_TAB_LABEL,
    SCENARIOS,
    THEME_COLOR,
    THEME_COLOR_SECONDARY,
)
from src.generate_charts import generate_gantt_chart, get_empty_figure, get_minimum_task_times
from src.job_shop_scheduler import run_shop_scheduler
from src.model_data import JobShopData

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    prevent_initial_callbacks="initial_duplicate",
    background_callback_manager=background_callback_manager,
)
app.title = APP_TITLE

server = app.server
app.config.suppress_callback_exceptions = True

BASE_PATH = pathlib.Path(__file__).parent.resolve()
DATA_PATH = BASE_PATH.joinpath("input").resolve()

# Generates css file and variable using THEME_COLOR and THEME_COLOR_SECONDARY settings
css = f"""/* Generated theme settings css file, see app.py */
:root {{
    --theme: {THEME_COLOR};
    --theme-secondary: {THEME_COLOR_SECONDARY};
}}
"""
with open("assets/theme.css", "w") as f:
    f.write(css)


class SamplerType(Enum):
    CQM = 0
    NL = 1
    HIGHS = 2


@app.callback(
    Output({"type": "to-collapse-class", "index": MATCH}, "className"),
    inputs=[
        Input({"type": "collapse-trigger", "index": MATCH}, "n_clicks"),
        State({"type": "to-collapse-class", "index": MATCH}, "className"),
    ],
    prevent_initial_call=True,
)
def toggle_left_column(collapse_trigger: int, to_collapse_class: str) -> str:
    """Toggles a 'collapsed' class that hides and shows some aspect of the UI.

    Args:
        collapse_trigger (int): The (total) number of times a collapse button has been clicked.
        to_collapse_class (str): Current class name of the thing to collapse, 'collapsed' if not visible, empty string if visible

    Returns:
        str: The new class name of the section to collapse.
    """
    classes = to_collapse_class.split(" ") if to_collapse_class else []
    if "collapsed" in classes:
        classes.remove("collapsed")
        return " ".join(classes)
    return to_collapse_class + " collapsed" if to_collapse_class else "collapsed"


@app.callback(
    Output("solver-select", "options"),
    inputs=[
        Input("solver-select", "value"),
        State("solver-select", "options"),
    ],
    prevent_initial_call=True,
)
def update_solvers_selected(
    selected_solvers: list[int],
    solver_options: list[dict]
) -> list[dict]:
    """Disable NL/CQM solver checkboxes when the other one is selected.

    Note, can be removed if CQM solver is not in use.

    Args:
        selected_solvers (list[int]): Currently selected solvers.
        solver_options (list[dict]): List of solver checkbox options.

    Returns:
        list: Updated list of solver checkbox options.
    """

    if SamplerType.CQM.value in selected_solvers:
        solver_options[1]["disabled"] = True
        return solver_options

    elif SamplerType.NL.value in selected_solvers:
        solver_options[0]["disabled"] = True
        return solver_options

    solver_options[0]["disabled"] = False
    solver_options[1]["disabled"] = False
    return solver_options


@app.callback(
    Output("dwave-tab", "label", allow_duplicate=True),
    Output("highs-tab", "label", allow_duplicate=True),
    Output("dwave-tab", "disabled", allow_duplicate=True),
    Output("highs-tab", "disabled", allow_duplicate=True),
    Output("dwave-tab", "className", allow_duplicate=True),
    Output("highs-tab", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("cancel-button", "className", allow_duplicate=True),
    Output("running-dwave", "data", allow_duplicate=True),
    Output("running-classical", "data", allow_duplicate=True),
    Output("tabs", "value"),
    [
        Input("run-button", "n_clicks"),
        Input("cancel-button", "n_clicks"),
        State("solver-select", "value"),
    ],
)
def update_tab_loading_state(
    run_click: int, cancel_click: int, solvers: list[str]
) -> tuple[str, str, bool, bool, str, str, str, str, bool, bool, str]:
    """Updates the tab loading state after the run button
    or cancel button has been clicked.

    Args:
        run_click (int): The number of times the run button has been clicked.
        cancel_click (int): The number of times the cancel button has been clicked.
        solvers (list[str]): The list of selected solvers.

    Returns:
        str: The label for the D-Wave tab.
        str: The label for the Classical tab.
        bool: True if D-Wave tab should be disabled, False otherwise.
        bool: True if Classical tab should be disabled, False otherwise.
        str: Class name for the D-Wave tab.
        str: Class name for the Classical tab.
        str: Run button class.
        str: Cancel button class.
        bool: Whether Hybrid is running.
        bool: Whether HiGHS is running.
        str: The value of the tab that should be active.
    """

    if ctx.triggered_id == "run-button" and run_click > 0:
        run_hybrid = SamplerType.CQM.value in solvers or SamplerType.NL.value in solvers
        run_highs = SamplerType.HIGHS.value in solvers

        return (
            "Loading..." if run_hybrid else dash.no_update,
            "Loading..." if run_highs else dash.no_update,
            True if run_hybrid else dash.no_update,
            True if run_highs else dash.no_update,
            "tab",
            "tab",
            "display-none",
            "",
            run_hybrid,
            run_highs,
            "input-tab",
        )
    if ctx.triggered_id == "cancel-button" and cancel_click > 0:
        return (
            DWAVE_TAB_LABEL,
            CLASSICAL_TAB_LABEL,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            "",
            "display-none",
            False,
            False,
            dash.no_update,
        )
    raise PreventUpdate


@app.callback(
    Output("run-button", "className"),
    Output("cancel-button", "className"),
    background=True,
    inputs=[
        Input("running-dwave", "data"),
        Input("running-classical", "data"),
    ],
    prevent_initial_call=True,
)
def update_button_visibility(running_dwave: bool, running_classical: bool) -> tuple[str, str]:
    """Updates the visibility of the run and cancel buttons.

    Args:
        running_dwave (bool): Whether the D-Wave solver is running.
        running_classical (bool): Whether the Classical solver is running.

    Returns:
        str: Run button class.
        str: Cancel button class.
    """
    if not running_classical and not running_dwave:
        return "", "display-none"

    return "display-none", ""


@app.callback(
    Output({"type": "gantt-chart-jobsort", "index": MATCH}, "className"),
    Output({"type": "gantt-chart-startsort", "index": MATCH}, "className"),
    Output({"type": "sort-button", "index": MATCH}, "children"),
    inputs=[
        Input({"type": "sort-button", "index": MATCH}, "n_clicks"),
        State({"type": "sort-button", "index": MATCH}, "children"),
    ],
    prevent_initial_call=True,
)
def switch_gantt_chart(new_click: int, sort_button_text: str) -> tuple[str, str, str]:
    """Switch between the results plot sorted by job or by start time.

    Args:
        new_click (int): The number of times the sort button has been clicked.
        sort_button_text: The text in the sort button (indicating how to sort the plot).

    Return:
        str: The results class name sorted by job (whether hidden or displayed).
        str: The results class name sorted by start time (whether hidden or displayed).
        str: The new text of the sort button.
    """
    if sort_button_text == "Sort by start time":
        return "display-none", "gantt-div", "Sort by job"
    return "gantt-div", "display-none", "Sort by start time"


@app.callback(
    Output({"type": "gantt-chart-jobsort", "index": 0}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 0}, "figure"),
    Output("dwave-stats-make-span", "children"),
    Output("dwave-stats-time-limit", "children"),
    Output("dwave-stats-wall-clock-time", "children"),
    Output("dwave-stats-scenario", "children"),
    Output("dwave-stats-solver", "children"),
    Output("dwave-stats-jobs", "children"),
    Output("dwave-stats-resources", "children"),
    Output("dwave-tab", "className"),
    Output("dwave-tab", "label"),
    Output("dwave-tab", "disabled"),
    Output("running-dwave", "data"),
    background=True,
    inputs=[
        Input("run-button", "n_clicks"),
        State("solver-select", "value"),
        State("scenario-select", "value"),
        State("solver-time-limit", "value"),
    ],
    cancel=[Input("cancel-button", "n_clicks")],
    prevent_initial_call=True,
)
def run_optimization_hybrid(
    run_click: int, solvers: list[int], scenario: str, time_limit: int
) -> tuple[go.Figure, go.Figure, str, str, str, str, str, str, str, str, str, bool, bool]:
    """Runs optimization using the D-Wave hybrid solver.

    Args:
        run_click (int): The number of times the run button has been clicked.
        solvers (list[int]): The solvers that have been selected.
        scenario (str): The scenario to use for the optimization.
        time_limit (int): The time limit for the optimization.

    Returns:
        go.Figure: Gantt chart for the D-Wave hybrid solver sorted by job.
        go.Figure: Gantt chart for the D-Wave hybrid solver sorted by start time.
        str: Final make-span for the D-Wave tab.
        str: Set time limit for the D-Wave tab.
        str: Wall clock time for the D-Wave tab.
        str: Scenario for the D-Wave tab.
        str: Solver for the D-Wave tab.
        str: Number of jobs for the D-Wave tab.
        str: Number of resources the D-Wave tab.
        str: Class name for the D-Wave tab.
        str: The label for the D-Wave tab.
        bool: True if D-Wave tab should be disabled, False otherwise.
        bool: Whether D-Wave solver is running.
    """
    if ctx.triggered_id != "run-button" or run_click == 0:
        raise PreventUpdate

    if SamplerType.CQM.value not in solvers and SamplerType.NL.value not in solvers:
        return (*([dash.no_update] * 9), "tab", DWAVE_TAB_LABEL, dash.no_update, False)

    start = time.perf_counter()
    model_data = JobShopData()
    filename = SCENARIOS[scenario]

    model_data.load_from_file(DATA_PATH.joinpath(filename))

    results = run_shop_scheduler(
        model_data,
        use_scipy_solver=False,
        use_nl_solver=SamplerType.NL.value in solvers,
        solver_time_limit=time_limit,
    )

    fig_jobsort = generate_gantt_chart(results, sort_by="JobInt")
    fig_startsort = generate_gantt_chart(results, sort_by="Start")

    table = (
        f"Make-span: {int(results['Finish'].max())}",
        time_limit,
        round(time.perf_counter() - start, 2),
        scenario,
        "NL Solver" if SamplerType.NL.value in solvers else "CQM Solver",
        model_data.get_job_count(),
        model_data.get_resource_count(),
        )

    return (fig_jobsort, fig_startsort, *table, "tab-success", DWAVE_TAB_LABEL, False, False)


@app.callback(
    Output({"type": "gantt-chart-jobsort", "index": 1}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 1}, "figure"),
    Output("highs-stats-make-span", "children"),
    Output("highs-stats-time-limit", "children"),
    Output("highs-stats-wall-clock-time", "children"),
    Output("highs-stats-scenario", "children"),
    Output("highs-stats-solver", "children"),
    Output("highs-stats-jobs", "children"),
    Output("highs-stats-resources", "children"),
    Output("highs-tab", "className"),
    Output("highs-tab", "label"),
    Output("highs-tab", "disabled"),
    Output("running-classical", "data"),
    background=True,
    inputs=[
        Input("run-button", "n_clicks"),
        State("solver-select", "value"),
        State("scenario-select", "value"),
        State("solver-time-limit", "value"),
    ],
    cancel=[Input("cancel-button", "n_clicks")],
    prevent_initial_call=True,
)
def run_optimization_scipy(
    run_click: int, solvers: list[int], scenario: str, time_limit: int
) -> tuple[go.Figure, go.Figure, str, str, str, str, str, str, str, str, str, bool, bool]:
    """Runs optimization using the HiGHS solver.

    Args:
        run_click (int): The number of times the run button has been
            clicked.
        solvers (list[int]): The solvers that have been selected.
        scenario (str): The scenario to use for the optimization.
        time_limit (int): The time limit for the optimization.

    Returns:
        go.Figure: Gantt chart for the Classical solver sorted by job.
        go.Figure: Gantt chart for the Classical solver sorted by start time.
        str: Final make-span for the Classical tab.
        str: Set time limit for the Classical tab.
        str: Wall clock time for the Classical tab.
        str: Scenario for the Classical tab.
        str: Solver for the Classical tab.
        str: Number of jobs for the Classical tab.
        str: Number of resources the Classical tab.
        str: Class name for the Classical tab.
        str: The label for the Classical tab.
        bool: True if Classical tab should be disabled, False otherwise.
        bool: Whether Classical solver is running.
    """
    if ctx.triggered_id != "run-button" or run_click == 0:
        raise PreventUpdate

    if SamplerType.HIGHS.value not in solvers:
        return (*([dash.no_update] * 9), "tab", CLASSICAL_TAB_LABEL, dash.no_update, False)

    start = time.perf_counter()
    model_data = JobShopData()
    filename = SCENARIOS[scenario]

    model_data.load_from_file(DATA_PATH.joinpath(filename))

    results = run_shop_scheduler(
        model_data,
        use_scipy_solver=True,
        solver_time_limit=time_limit,
    )

    if results.empty:
        fig = get_empty_figure("No solution found for Classical solver")
        table = (
            "Make-span: 0",
            time_limit,
            round(time.perf_counter() - start, 2),
            scenario,
            "HiGHS",
            model_data.get_job_count(),
            model_data.get_resource_count(),
            )
        return (fig, fig, *table, "tab-fail", CLASSICAL_TAB_LABEL, False, False)

    fig_jobsort = generate_gantt_chart(results, sort_by="JobInt")
    fig_startsort = generate_gantt_chart(results, sort_by="Start")

    table = (
        f"Make-span: {int(results['Finish'].max())}",
        time_limit,
        round(time.perf_counter() - start, 2),
        scenario,
        "HiGHS",
        model_data.get_job_count(),
        model_data.get_resource_count(),
        )
    return (fig_jobsort, fig_startsort, *table, "tab-success", CLASSICAL_TAB_LABEL, False, False)


@app.callback(
    Output("unscheduled-gantt-chart", "figure"),
    [
        Input("scenario-select", "value"),
    ],
)
def generate_unscheduled_gantt_chart(scenario: str) -> go.Figure:
    """Generates a Gantt chart of the unscheduled tasks for the given scenario.

    Args:
        scenario (str): The name of the scenario; must be a key in SCENARIOS.

    Returns:
        go.Figure: A Plotly figure object with the input data
    """
    model_data = JobShopData()

    model_data.load_from_file(DATA_PATH.joinpath(SCENARIOS[scenario]))
    df = get_minimum_task_times(model_data)
    fig = generate_gantt_chart(df)
    return fig


# import the html code and sets it in the app
# creates the visual layout and app (see `dash_html.py`)
set_html(app)


app.clientside_callback(
    ClientsideFunction(namespace="clientside", function_name="resize"),
    Output("output-clientside", "children"),
    [Input("wait_time_table", "children")],
)


# Run the server
if __name__ == "__main__":
    app.run_server(debug=DEBUG)
