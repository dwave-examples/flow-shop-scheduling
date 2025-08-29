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

import argparse
import pathlib
import time
from typing import NamedTuple

import dash
import diskcache
import plotly.graph_objs as go
from dash import MATCH, DiskcacheManager, ctx
from dash.dependencies import ClientsideFunction, Input, Output, State
from dash.exceptions import PreventUpdate

from dash_html import generate_problem_details_table, set_html

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
    multiprocess.set_start_method("spawn")

from app_configs import (
    APP_TITLE,
    CLASSICAL_TAB_LABEL,
    DWAVE_TAB_LABEL,
    SCENARIOS,
    SHOW_CQM,
    THEME_COLOR,
    THEME_COLOR_SECONDARY,
)
from src.generate_charts import generate_gantt_chart, get_empty_figure, get_minimum_task_times
from flow_shop_scheduler import HybridSamplerType, SamplerType, run_shop_scheduler
from src.model_data import FlowShopData

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    prevent_initial_callbacks="initial_duplicate",
    background_callback_manager=background_callback_manager,
)
app.title = APP_TITLE

server = app.server
app.config.suppress_callback_exceptions = True

# Parse debug argument
parser = argparse.ArgumentParser(description="Dash debug setting.")
parser.add_argument(
    "--debug",
    action="store_true",
    help="Add argument to see Dash debug menu and get live reload updates while developing.",
)

args = parser.parse_args()
DEBUG = args.debug

print(f"\nDebug has been set to: {DEBUG}")
if not DEBUG:
    print(
        "Code changes will not be reflected in the app interface and the Dash debug menu will be hidden.",
        "If editing code while the app is running, run the app with `python app.py --debug`.\n",
        sep="\n",
    )

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
    Output("hybrid-select-wrapper", "className"),
    inputs=[
        Input("solver-select", "value"),
    ],
    prevent_initial_call=True,
)
def update_solvers_selected(
    selected_solvers: list[int],
) -> str:
    """Hide NL/CQM selector when Hybrid is unselected. Not applicable when SHOW_CQM is False.

    Args:
        selected_solvers (list[int]): Currently selected solvers.

    Returns:
        str: Class name for hybrid select wrapper.
    """
    if SHOW_CQM:
        return "" if SamplerType.HYBRID.value in selected_solvers else "display-none"

    raise PreventUpdate


@app.callback(
    Output("dwave-tab", "label", allow_duplicate=True),
    Output("dwave-tab", "disabled", allow_duplicate=True),
    Output("dwave-tab", "className", allow_duplicate=True),
    Output("running-dwave", "data", allow_duplicate=True),
    Output("highs-tab", "label", allow_duplicate=True),
    Output("highs-tab", "disabled", allow_duplicate=True),
    Output("highs-tab", "className", allow_duplicate=True),
    Output("running-classical", "data", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("cancel-button", "className", allow_duplicate=True),
    Output("tabs", "value"),
    [
        Input("run-button", "n_clicks"),
        Input("cancel-button", "n_clicks"),
        State("solver-select", "value"),
    ],
)
def update_tab_loading_state(
    run_click: int, cancel_click: int, solvers: list[str]
) -> tuple[str, bool, str, bool, str, bool, str, bool, str, str, str]:
    """Updates the tab loading state after the run button
    or cancel button has been clicked.

    Args:
        run_click (int): The number of times the run button has been clicked.
        cancel_click (int): The number of times the cancel button has been clicked.
        solvers (list[str]): The list of selected solvers.

    Returns:
        str: The label for the D-Wave tab.
        bool: True if D-Wave tab should be disabled, False otherwise.
        str: Class name for the D-Wave tab.
        bool: Whether Hybrid is running.
        str: The label for the Classical tab.
        bool: True if Classical tab should be disabled, False otherwise.
        str: Class name for the Classical tab.
        bool: Whether HiGHS is running.
        str: Run button class.
        str: Cancel button class.
        str: The value of the tab that should be active.
    """

    if ctx.triggered_id == "run-button" and run_click > 0:
        running = ("Loading...", True, "tab", True)
        return (
            *(running if SamplerType.HYBRID.value in solvers else [dash.no_update] * 4),
            *(running if SamplerType.HIGHS.value in solvers else [dash.no_update] * 4),
            "display-none",
            "",
            "input-tab",
        )

    if ctx.triggered_id == "cancel-button" and cancel_click > 0:
        not_running = (dash.no_update, dash.no_update, False)
        return (
            DWAVE_TAB_LABEL,
            *not_running,
            CLASSICAL_TAB_LABEL,
            *not_running,
            "",
            "display-none",
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
    Output({"type": "gantt-chart-visible-wrapper", "index": MATCH}, "children"),
    Output({"type": "gantt-chart-hidden-wrapper", "index": MATCH}, "children"),
    Output({"type": "gantt-heading-button", "index": MATCH}, "children"),
    inputs=[
        Input({"type": "gantt-heading-button", "index": MATCH}, "n_clicks"),
        State({"type": "gantt-heading-button", "index": MATCH}, "children"),
        State({"type": "gantt-chart-visible-wrapper", "index": MATCH}, "children"),
        State({"type": "gantt-chart-hidden-wrapper", "index": MATCH}, "children"),
    ],
    prevent_initial_call=True,
)
def switch_gantt_chart(
    new_click: int, sort_button_text: str, visibleChart: list, hiddenChart: list
) -> tuple[str, str, str]:
    """Switch between the results plot sorted by job or by start time.

    Args:
        new_click (int): The number of times the sort button has been clicked.
        sort_button_text (str): The text of the sort button (indicating how to sort the plot).
        visibleChart (list): The children of the currently visible graph.
        hiddenChart (list): The children of the currently hidden graph.

    Return:
        list: The new graph that should be visible.
        list: The new graph that should be hidden.
        str: The new text of the sort button.
    """
    if ctx.triggered_id["index"] == 0:
        button_text = "Show Conflicts" if sort_button_text == "Hide Conflicts" else "Hide Conflicts"
    else:
        button_text = (
            "Sort by job" if sort_button_text == "Sort by start time" else "Sort by start time"
        )
    return hiddenChart, visibleChart, button_text


class RunOptimizationHybridReturn(NamedTuple):
    """Return type for the ``run_optimization_hybrid`` callback function."""

    gantt_chart_jobsort: go.Figure = dash.no_update
    gantt_chart_startsort: go.Figure = dash.no_update
    dwave_makespan: str = dash.no_update
    dwave_solution_stats_table: list = dash.no_update
    dwave_tab_disabled: bool = dash.no_update
    dwave_gantt_title_span: str = dash.no_update
    dwave_tab_class: str = dash.no_update
    dwave_tab_label: str = dash.no_update
    running_dwave: bool = dash.no_update


@app.callback(
    Output({"type": "gantt-chart-jobsort", "index": 1}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 1}, "figure"),
    Output("dwave-stats-makespan", "children"),
    Output("dwave-solution-stats-table", "children"),
    Output("dwave-tab", "disabled"),
    Output("dwave-gantt-title-span", "children"),
    Output("dwave-tab", "className"),
    Output("dwave-tab", "label"),
    Output("running-dwave", "data"),
    background=True,
    inputs=[
        Input("run-button", "n_clicks"),
        State("solver-select", "value"),
        State("hybrid-select", "value"),
        State("scenario-select", "value"),
        State("solver-time-limit", "value"),
    ],
    cancel=[Input("cancel-button", "n_clicks")],
    prevent_initial_call=True,
)
def run_optimization_hybrid(
    run_click: int, solvers: list[int], hybrid_solver: int, scenario: str, time_limit: int
) -> RunOptimizationHybridReturn:
    """Runs optimization using the D-Wave hybrid solver.

    Args:
        run_click (int): The number of times the run button has been clicked.
        solvers (list[int]): The solvers that have been selected.
        hybrid_solver (int): The hybrid solver that have been selected.
        scenario (str): The scenario to use for the optimization.
        time_limit (int): The time limit for the optimization.

    Returns:
        A NamedTuple (RunOptimizationHybridReturn) containing all outputs to be used when updating the HTML
        template (in ``dash_html.py``). These are:
            go.Figure: Gantt chart for the D-Wave hybrid solver sorted by job.
            go.Figure: Gantt chart for the D-Wave hybrid solver sorted by start time.
            str: Final makespan for the D-Wave tab.
            list: Solution stats table for problem details.
            bool: True if D-Wave tab should be disabled, False otherwise.
            str: Graph title span to add the solver type to.
            str: Class name for the D-Wave tab.
            str: The label for the D-Wave tab.
            bool: Whether D-Wave solver is running.
    """
    if ctx.triggered_id != "run-button" or run_click == 0:
        raise PreventUpdate

    if SamplerType.HYBRID.value not in solvers:
        return RunOptimizationHybridReturn(
            dwave_tab_class="tab",
            dwave_tab_label=DWAVE_TAB_LABEL,
            running_dwave=False
        )

    start = time.perf_counter()
    model_data = FlowShopData()
    filename = SCENARIOS[scenario]

    model_data.load_from_file(DATA_PATH.joinpath(filename))

    running_cqm = hybrid_solver is HybridSamplerType.CQM.value

    results = run_shop_scheduler(
        model_data,
        use_scipy_solver=False,
        use_cqm_solver=running_cqm,
        solver_time_limit=time_limit,
    )

    fig_jobsort = generate_gantt_chart(results, sort_by="JobInt")
    fig_startsort = generate_gantt_chart(results, sort_by="Start")

    solution_stats_table = generate_problem_details_table(
        scenario,
        "CQM Solver" if running_cqm else "NL Solver",
        model_data.get_job_count(),
        time_limit,
        model_data.get_resource_count(),
        time.perf_counter() - start,
    )

    return RunOptimizationHybridReturn(
        gantt_chart_jobsort=fig_jobsort,
        gantt_chart_startsort=fig_startsort,
        dwave_makespan=f"Makespan: {int(results['Finish'].max())}",
        dwave_solution_stats_table=solution_stats_table,
        dwave_tab_disabled=False,
        dwave_gantt_title_span=" (CQM)" if running_cqm else " (NL)",
        dwave_tab_class="tab-success",
        dwave_tab_label=DWAVE_TAB_LABEL,
        running_dwave=False,
    )


class RunOptimizationScipyReturn(NamedTuple):
    """Return type for the ``run_optimization_scipy`` callback function."""

    gantt_chart_jobsort: go.Figure = dash.no_update
    gantt_chart_startsort: go.Figure = dash.no_update
    highs_makespan: str = dash.no_update
    highs_solution_stats_table: list = dash.no_update
    highs_tab_disabled: bool = dash.no_update
    sort_button_style: dict = dash.no_update
    highs_tab_class: str = dash.no_update
    highs_tab_label: str = dash.no_update
    running_classical: bool = dash.no_update


@app.callback(
    Output({"type": "gantt-chart-jobsort", "index": 2}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 2}, "figure"),
    Output("highs-stats-makespan", "children"),
    Output("highs-solution-stats-table", "children"),
    Output("highs-tab", "disabled"),
    Output({"type": "gantt-heading-button", "index": 2}, "style"),
    Output("highs-tab", "className"),
    Output("highs-tab", "label"),
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
) -> RunOptimizationScipyReturn:
    """Runs optimization using the HiGHS solver.

    Args:
        run_click (int): The number of times the run button has been
            clicked.
        solvers (list[int]): The solvers that have been selected.
        scenario (str): The scenario to use for the optimization.
        time_limit (int): The time limit for the optimization.

    Returns:
        A NamedTuple (RunOptimizationScipyReturn) containing all outputs to be used when updating the HTML
        template (in ``dash_html.py``). These are:
            go.Figure: Gantt chart for the Classical solver sorted by job.
            go.Figure: Gantt chart for the Classical solver sorted by start time.
            str: Final makespan for the Classical tab.
            list: Solution stats table for problem details.
            bool: True if Classical tab should be disabled, False otherwise.
            dict: Sort button style, either display none or nothing.
            str: Class name for the Classical tab.
            str: The label for the Classical tab.
            bool: Whether Classical solver is running.
    """
    if ctx.triggered_id != "run-button" or run_click == 0:
        raise PreventUpdate

    if SamplerType.HIGHS.value not in solvers:
        return RunOptimizationScipyReturn(
            highs_tab_class="tab",
            highs_tab_label=CLASSICAL_TAB_LABEL,
            running_classical=False
        )

    start = time.perf_counter()
    model_data = FlowShopData()
    filename = SCENARIOS[scenario]

    model_data.load_from_file(DATA_PATH.joinpath(filename))

    results = run_shop_scheduler(
        model_data,
        use_scipy_solver=True,
        solver_time_limit=time_limit,
    )

    solution_stats_table = generate_problem_details_table(
        scenario,
        "HiGHS",
        model_data.get_job_count(),
        time_limit,
        model_data.get_resource_count(),
        time.perf_counter() - start
    )
    makespan = f"Makespan: {0 if results.empty else int(results['Finish'].max())}"

    if results.empty:
        fig = get_empty_figure("No solution found for Classical solver")
        return RunOptimizationScipyReturn(
            gantt_chart_jobsort=fig,
            gantt_chart_startsort=fig,
            highs_makespan=makespan,
            highs_solution_stats_table=solution_stats_table,
            highs_tab_disabled=False,
            sort_button_style={"display": "none"},
            highs_tab_class="tab-fail",
            highs_tab_label=CLASSICAL_TAB_LABEL,
            running_classical=False,
        )

    fig_jobsort = generate_gantt_chart(results, sort_by="JobInt")
    fig_startsort = generate_gantt_chart(results, sort_by="Start")

    return RunOptimizationScipyReturn(
        gantt_chart_jobsort=fig_jobsort,
        gantt_chart_startsort=fig_startsort,
        highs_makespan=makespan,
        highs_solution_stats_table=solution_stats_table,
        highs_tab_disabled=False,
        sort_button_style={},
        highs_tab_class="tab-success",
        highs_tab_label=CLASSICAL_TAB_LABEL,
        running_classical=False,
    )


@app.callback(
    Output({"type": "gantt-chart-unscheduled", "index": 0}, "figure"),
    Output({"type": "gantt-chart-conflicts", "index": 0}, "figure"),
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
    model_data = FlowShopData()

    model_data.load_from_file(DATA_PATH.joinpath(SCENARIOS[scenario]))
    df = get_minimum_task_times(model_data)
    fig = generate_gantt_chart(df)
    fig_conflicts = generate_gantt_chart(df, show_conflicts=True)
    return fig, fig_conflicts


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
