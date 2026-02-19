# Copyright 2024 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pathlib
import time
from typing import NamedTuple

import dash
import plotly.graph_objs as go
from dash import MATCH, ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from demo_interface import generate_table

from demo_configs import (
    CLASSICAL_TAB_LABEL,
    DWAVE_TAB_LABEL,
    SCENARIOS,
    SHOW_CQM,
)
from src.generate_charts import generate_gantt_chart, get_empty_figure, get_minimum_task_times
from flow_shop_scheduler import run_shop_scheduler
from src.model_data import FlowShopData
from src.demo_enums import HybridSolverType, SolverType

BASE_PATH = pathlib.Path(__file__).parent.resolve()
DATA_PATH = BASE_PATH.joinpath("input").resolve()



@dash.callback(
    Output({"type": "to-collapse-class", "index": MATCH}, "className"),
    Output({"type": "collapse-trigger", "index": MATCH}, "aria-expanded"),
    inputs=[
        Input({"type": "collapse-trigger", "index": MATCH}, "n_clicks"),
        State({"type": "to-collapse-class", "index": MATCH}, "className"),
    ],
    prevent_initial_call=True,
)
def toggle_left_column(collapse_trigger: int, to_collapse_class: str) -> tuple[str, str]:
    """Toggles a 'collapsed' class that hides and shows some aspect of the UI.

    Args:
        collapse_trigger (int): The (total) number of times a collapse button has been clicked.
        to_collapse_class (str): Current class name of the thing to collapse, 'collapsed' if not
            visible, empty string if visible.

    Returns:
        str: The new class name of the thing to collapse.
        str: The aria-expanded value.
    """

    classes = to_collapse_class.split(" ") if to_collapse_class else []
    if "collapsed" in classes:
        classes.remove("collapsed")
        return " ".join(classes), "true"
    return to_collapse_class + " collapsed" if to_collapse_class else "collapsed", "false"


@dash.callback(
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
        return "" if SolverType.HYBRID.value in selected_solvers else "display-none"

    raise PreventUpdate


@dash.callback(
    Output("dwave-tab", "label"),
    Output("dwave-tab", "disabled"),
    Output("dwave-tab", "className"),
    Output("running-dwave", "data"),
    Output("highs-tab", "label"),
    Output("highs-tab", "disabled"),
    Output("highs-tab", "className"),
    Output("running-classical", "data"),
    Output("run-button", "className"),
    Output("cancel-button", "className"),
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
            *(running if SolverType.HYBRID.value in solvers else [dash.no_update] * 4),
            *(running if SolverType.HIGHS.value in solvers else [dash.no_update] * 4),
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


@dash.callback(
    Output("run-button", "className", allow_duplicate=True),
    Output("cancel-button", "className", allow_duplicate=True),
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


@dash.callback(
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


@dash.callback(
    Output({"type": "gantt-chart-jobsort", "index": 1}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 1}, "figure"),
    Output("dwave-stats-makespan", "children"),
    Output({"type": "problem-details", "index": 1}, "children"),
    Output("dwave-tab", "disabled", allow_duplicate=True),
    Output("dwave-gantt-title-span", "children"),
    Output("dwave-tab", "className", allow_duplicate=True),
    Output("dwave-tab", "label", allow_duplicate=True),
    Output("running-dwave", "data", allow_duplicate=True),
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

    if SolverType.HYBRID.value not in solvers:
        return RunOptimizationHybridReturn(
            dwave_tab_class="tab",
            dwave_tab_label=DWAVE_TAB_LABEL,
            running_dwave=False
        )

    start = time.perf_counter()
    model_data = FlowShopData()
    filename = SCENARIOS[scenario]

    model_data.load_from_file(DATA_PATH.joinpath(filename))

    running_cqm = hybrid_solver is HybridSolverType.CQM.value

    results = run_shop_scheduler(
        model_data,
        use_scipy_solver=False,
        use_cqm_solver=running_cqm,
        solver_time_limit=time_limit,
    )

    fig_jobsort = generate_gantt_chart(results, sort_by="JobInt")
    fig_startsort = generate_gantt_chart(results, sort_by="Start")

    # ("Scenario", scenario, "Solver", solver),
    # ("Number of Jobs", num_jobs, "Solver Time Limit", f"{time_limit}s"),
    # ("Number of Operations", num_operations, "Wall Clock Time", f"{round(wall_clock_time, 2)}s")

    solution_stats_table = generate_table(
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


@dash.callback(
    Output({"type": "gantt-chart-jobsort", "index": 2}, "figure"),
    Output({"type": "gantt-chart-startsort", "index": 2}, "figure"),
    Output("highs-stats-makespan", "children"),
    Output({"type": "problem-details", "index": 2}, "children"),
    Output("highs-tab", "disabled", allow_duplicate=True),
    Output({"type": "gantt-heading-button", "index": 2}, "style"),
    Output("highs-tab", "className", allow_duplicate=True),
    Output("highs-tab", "label", allow_duplicate=True),
    Output("running-classical", "data", allow_duplicate=True),
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

    if SolverType.HIGHS.value not in solvers:
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

    solution_stats_table = generate_table(
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


@dash.callback(
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
