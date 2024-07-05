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

from __future__ import annotations

from dash import dcc, html

from app_configs import (
    CLASSICAL_TAB_LABEL,
    DESCRIPTION,
    DWAVE_TAB_LABEL,
    MAIN_HEADER,
    SCENARIOS,
    SHOW_CQM,
    SOLVER_TIME,
    THEME_COLOR_SECONDARY,
    THUMBNAIL,
)
from src.job_shop_scheduler import HybridSamplerType, SamplerType

SAMPLER_TYPES = {
    SamplerType.HYBRID: "Quantum Hybrid" if SHOW_CQM else "Quantum Hybrid (NL)",
    SamplerType.HIGHS: "Classical (HiGHS)",
}
HYBRID_SAMPLER_TYPES = {
    HybridSamplerType.NL: "Nonlinear (NL)",
    HybridSamplerType.CQM: "Constrained Quadratic Model (CQM)"
}


def description_card():
    """A Div containing dashboard title & descriptions."""
    return html.Div(
        id="description-card",
        children=[html.H1(MAIN_HEADER), html.P(DESCRIPTION)],
    )


def dropdown(
    label: str, id: str, options: list, wrapper_id: str = "", wrapper_class_name: str = ""
) -> html.Div:
    """Slider element for value selection."""
    return html.Div(
        id=wrapper_id,
        className=wrapper_class_name,
        children=[
            html.Label(label),
            dcc.Dropdown(
                id=id,
                options=options,
                value=options[0]["value"],
                clearable=False,
                searchable=False,
            ),
        ],
    )


def checklist(label: str, id: str, options: list) -> html.Div:
    """Slider element for value selection."""
    return html.Div([
        html.Label(label),
        dcc.Checklist(
            id=id,
            options=options,
            value=[options[0]["value"]],
        )
    ])


def generate_graph(visible: bool, type: str, index: int) -> html.Div:
    """Generates graph either hidden or visible."""
    return html.Div(
        id={
            "type": f"gantt-chart-{'visible' if visible else 'hidden'}-wrapper",
            "index": index,
        },
        className="graph" if visible else "display-none",
        children=[
            dcc.Graph(
                id={"type": f"gantt-chart-{type}", "index": index},
                responsive=True,
                config={"displayModeBar": False},
            ),
        ],
    )


def generate_solution_tab(label: str, title: str, tab: str, index: int) -> dcc.Tab:
    """Generates solution tab containing, solution graphs, sort functionality, and
    problem details dropdown.

    Returns:
        dcc.Tab: A Tab containing the solution graph and problem details.
    """
    return dcc.Tab(
        label=label,
        id=f"{tab}-tab",
        className="tab",
        value=f"{tab}-tab",
        disabled=True,
        children=[
            html.Div(
                className="solution-card",
                children=[
                    html.Div(
                        className="gantt-chart-card",
                        children=[
                            html.Div(
                                className="gantt-heading",
                                children=[
                                    html.H3(
                                        [title, html.Span(id=f"{tab}-gantt-title-span")],
                                        className="gantt-title",
                                    ),
                                    html.Button(
                                        id={"type": "gantt-heading-button", "index": index},
                                        className="gantt-heading-button",
                                        children="Sort by start time",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="graph-wrapper",
                                children=[
                                    generate_graph(True, "jobsort", index),
                                    generate_graph(False, "startsort", index),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        [
                            html.Hr(),
                            html.Div(problem_details(tab, index), className="problem-details"),
                        ],
                        className="problem-details-parent",
                    ),
                ],
            ),
        ],
    )


def generate_control_card() -> html.Div:
    """Generates the control card for the dashboard.

    Contains the dropdowns for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the dropdowns for selecting the scenario,
        model, and solver.
    """

    scenario_options = [{"label": scenario, "value": scenario} for scenario in SCENARIOS]
    sampler_options = [
        {"label": label, "value": sampler_type.value}
        for sampler_type, label in SAMPLER_TYPES.items()
    ]
    hybrid_sampler_options = [
        {"label": label, "value": hybrid_sampler_type.value}
        for hybrid_sampler_type, label in HYBRID_SAMPLER_TYPES.items()
    ]

    return html.Div(
        id="control-card",
        children=[
            dropdown(
                "Scenario (jobs x operations)",
                "scenario-select",
                scenario_options,
            ),
            checklist(
                "Solver (hybrid and/or classical)",
                "solver-select",
                sorted(sampler_options, key=lambda op: op["value"]),
            ),
            dropdown(
                "Quantum Hybrid Solver",
                "hybrid-select",
                sorted(hybrid_sampler_options, key=lambda op: op["value"]),
                "hybrid-select-wrapper",
                "" if SHOW_CQM else "display-none",
            ),
            html.Label("Solver Time Limit (seconds)"),
            dcc.Input(
                id="solver-time-limit",
                type="number",
                **SOLVER_TIME,
            ),
            html.Div(
                id="button-group",
                children=[
                    html.Button(id="run-button", children="Run Optimization", n_clicks=0),
                    html.Button(
                        id="cancel-button",
                        children="Cancel Optimization",
                        n_clicks=0,
                        className="display-none",
                    ),
                ],
            ),
        ],
    )


def generate_problem_details_table(
    scenario: str, solver: str, num_jobs: int, time_limit: int, num_operations: int, wall_clock_time: float
) -> html.Tbody:
    """Generate the problem details table.

    Args:
        scenario: The scenario that was optimized.
        solver: The solver used for optimization.
        num_jobs: The number of jobs in the scenario.
        time_limit: The solver time limit.
        num_operations: The number of operations in the scenario.
        wall_clock_time: The overall time to optimize the scenario.

    Returns:
        html.Tbody: Tbody containing table rows for problem details.
    """

    table_rows = (
        ("Scenario", scenario, "Solver", solver),
        ("Number of Jobs", num_jobs, "Solver Time Limit", f"{time_limit}s"),
        ("Number of Operations", num_operations, "Wall Clock Time", f"{round(wall_clock_time, 2)}s")
    )

    return html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in table_rows])


def problem_details(solver: str, index: int) -> html.Div:
    """Generate the problem details section.

    Args:
        solver: Which solver tab to generate the section for. Either "dwave" or "highs"
        index: Unique element id to differentiate matching elements.

    Returns:
        html.Div: Div containing a collapsable table.
    """
    return html.Div(
        [
            html.Div(
                id={"type": "to-collapse-class", "index": index},
                className="details-collapse-wrapper collapsed",
                children=[
                    html.Div(
                        className="details-collapse-title",
                        children=[
                            html.H5(id=f"{solver}-stats-makespan", className="stats-makespan"),
                            html.Button(
                                id={"type": "collapse-trigger", "index": index},
                                className="details-collapse",
                                children=[
                                    html.H5("Problem Details"),
                                    html.Div(className="collapse-arrow"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="details-to-collapse",
                        children=[
                            html.Table(
                                className="solution-stats-table",
                                id=f"{solver}-solution-stats-table",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


# set the application HTML
def set_html(app):
    app.layout = html.Div(
        id="app-container",
        children=[
            dcc.Store("running-dwave"),
            dcc.Store("running-classical"),
            # Banner
            html.Div(id="banner", children=[html.Img(src=THUMBNAIL)]),
            html.Div(
                id="columns",
                children=[
                    # Left column
                    html.Div(
                        id={"type": "to-collapse-class", "index": 0},
                        className="left-column",
                        children=[
                            html.Div(
                                [  # Fixed width Div to collapse
                                    html.Div(
                                        [  # Padding and content wrapper
                                            description_card(),
                                            generate_control_card(),
                                        ]
                                    )
                                ]
                            ),
                            html.Div(
                                html.Button(
                                    id={"type": "collapse-trigger", "index": 0},
                                    className="left-column-collapse",
                                    children=[html.Div(className="collapse-arrow")],
                                ),
                            ),
                        ],
                    ),
                    # Right column
                    html.Div(
                        id="right-column",
                        children=[
                            dcc.Tabs(
                                id="tabs",
                                value="input-tab",
                                children=[
                                    dcc.Tab(
                                        label="Input",
                                        value="input-tab",
                                        className="tab",
                                        children=[
                                            html.Div(
                                                className="gantt-chart-card",
                                                children=[
                                                    html.Div(
                                                        className="gantt-heading",
                                                        children=[
                                                            html.H3(
                                                                "Unscheduled Jobs and Operations",
                                                                className="gantt-title",
                                                            ),
                                                            html.Button(
                                                                id={
                                                                    "type": "gantt-heading-button",
                                                                    "index": 0,
                                                                },
                                                                className="gantt-heading-button",
                                                                children="Show Conflicts",
                                                                n_clicks=0,
                                                            ),
                                                        ],
                                                    ),
                                                    dcc.Loading(
                                                        id="loading-icon-input",
                                                        parent_className="graph-wrapper",
                                                        type="circle",
                                                        delay_show=300,
                                                        color=THEME_COLOR_SECONDARY,
                                                        children=[
                                                            generate_graph(True, "unscheduled", 0),
                                                            generate_graph(False, "conflicts", 0),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    generate_solution_tab(
                                        DWAVE_TAB_LABEL, "Quantum Hybrid Solver", "dwave", 1
                                    ),
                                    generate_solution_tab(
                                        CLASSICAL_TAB_LABEL, "Classical Solver (HiGHS)", "highs", 2
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
