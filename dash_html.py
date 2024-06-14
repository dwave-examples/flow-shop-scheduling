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
    SHOW_CQM,
    MAIN_HEADER,
    SCENARIOS,
    SOLVER_TIME,
    THUMBNAIL
)

SOLVER_OPTIONS = ["Quantum Hybrid (CQM)", "Quantum Hybrid (NL)", "Classical (HiGHS)"]


def description_card():
    """A Div containing dashboard title & descriptions."""
    return html.Div(
        id="description-card",
        children=[html.H1(MAIN_HEADER), html.P(DESCRIPTION)],
    )


def dropdown(label: str, id: str, options: list) -> html.Div:
    """Slider element for value selection."""
    return html.Div(
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


def generate_control_card() -> html.Div:
    """Generates the control card for the dashboard.

    Contains the dropdowns for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the dropdowns for selecting the scenario,
        model, and solver.
    """

    scenario_options = [{"label": scenario, "value": scenario} for scenario in SCENARIOS]
    solver_options = [
        {"label": solver_value, "value": i} for i, solver_value in enumerate(SOLVER_OPTIONS)
    ]

    return html.Div(
        id="control-card",
        children=[
            dropdown(
                "Scenario (jobs x operations)",
                "scenario-select",
                scenario_options,
            ),
            html.Label("Solver (hybrid and/or classical)"),
            dcc.Checklist(
                id="solver-select",
                options=solver_options,
                value=[solver_options[2]["value"]],
                className="" if SHOW_CQM else "hide-cqm",
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


def problem_details(solver: str) -> html.Div:
    """generate the problem details section.

    Args:
        solver: Which solver tab to generate the section for. Either "dwave" or "highs"

    Returns:
        html.Div: Div containing a collapsable table.
    """
    return html.Div(
        [
            html.Div(
                id={"type": "to-collapse-class", "index": 1 if solver == "dwave" else 2},
                className="details-collapse-wrapper collapsed",
                children=[
                    html.Button(
                        id={"type": "collapse-trigger", "index": 1 if solver == "dwave" else 2},
                        className="details-collapse",
                        children=[
                            html.H5("Problem Details"),
                            html.Div(className="collapse-arrow"),
                        ],
                    ),
                    html.Div(
                        className="details-to-collapse",
                        children=[
                            html.Table(
                                className="solution-stats-table",
                                children=[
                                    html.Tbody(
                                        children=[
                                            html.Tr(
                                                [
                                                    html.Td("Scenario"),
                                                    html.Td(id=f"{solver}-stats-scenario"),
                                                    html.Td("Solver"),
                                                    html.Td(id=f"{solver}-stats-solver"),
                                                ]
                                            ),
                                            html.Tr(
                                                [
                                                    html.Td("Number of Jobs"),
                                                    html.Td(id=f"{solver}-stats-jobs"),
                                                    html.Td("Solver Time Limit [s]"),
                                                    html.Td(id=f"{solver}-stats-time-limit"),
                                                ]
                                            ),
                                            html.Tr(
                                                [
                                                    html.Td("Number of Operations"),
                                                    html.Td(id=f"{solver}-stats-resources"),
                                                    html.Td("Wall Clock Time [s]"),
                                                    html.Td(id=f"{solver}-stats-wall-clock-time"),
                                                ]
                                            ),
                                        ],
                                    ),
                                ],
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
                                            html.Div(
                                                ["initial child"],
                                                id="output-clientside",
                                                style={"display": "none"},
                                            ),
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
                                                html.Div(
                                                    id="unscheduled-gantt-chart-card",
                                                    className="gantt-chart-card",
                                                    children=[
                                                        html.H3(
                                                            "Unscheduled Jobs and Operations",
                                                            className="gantt-title",
                                                        ),
                                                        dcc.Loading(
                                                            id="loading-icon-input",
                                                            children=[
                                                                dcc.Graph(
                                                                    className="gantt-div",
                                                                    id="unscheduled-gantt-chart",
                                                                    responsive=True,
                                                                    config={"displayModeBar": False},
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                className="gantt-chart-card-parent",
                                            )
                                        ],
                                    ),
                                    dcc.Tab(
                                        label=DWAVE_TAB_LABEL,
                                        value="dwave-tab",
                                        id="dwave-tab",
                                        className="tab",
                                        disabled=True,
                                        children=[
                                            html.Div(
                                                html.Div(
                                                    id="optimized-gantt-chart-card",
                                                    className="gantt-chart-card",
                                                    children=[
                                                        html.Div(
                                                            [
                                                                html.H3(
                                                                    "D-Wave Hybrid Solver",
                                                                    className="gantt-title",
                                                                ),
                                                                html.Button(id={"type": "sort-button", "index": 0}, children="Sort by start time", n_clicks=0),
                                                            ],
                                                            className="gantt-heading-button",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dcc.Graph(
                                                                    id={"type": "gantt-chart-jobsort", "index": 0},
                                                                    responsive=True,
                                                                    className="gantt-div",
                                                                    config={"displayModeBar": False},
                                                                ),
                                                                dcc.Graph(
                                                                    id={"type": "gantt-chart-startsort", "index": 0},
                                                                    responsive=True,
                                                                    className="display-none",
                                                                    config={"displayModeBar": False},
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Hr(),
                                                                html.Div(
                                                                    [
                                                                        html.H5(id="dwave-stats-make-span"),
                                                                        problem_details("dwave"),
                                                                    ],
                                                                    className="problem-details"
                                                                ),
                                                            ],
                                                            className="problem-details-parent",
                                                        ),
                                                    ],
                                                ),
                                                className="gantt-chart-card-parent",
                                            ),
                                        ],
                                    ),
                                    dcc.Tab(
                                        label=CLASSICAL_TAB_LABEL,
                                        id="highs-tab",
                                        className="tab",
                                        value="highs-tab",
                                        disabled=True,
                                        children=[
                                            html.Div(
                                                html.Div(
                                                    id="highs-gantt-chart-card",
                                                    className="gantt-chart-card",
                                                    children=[
                                                        html.Div(
                                                            [
                                                                html.H3(
                                                                    "HiGHS Classical Solver",
                                                                    className="gantt-title",
                                                                ),
                                                                html.Button(id={"type": "sort-button", "index": 1}, children="Sort by start time", n_clicks=0),
                                                            ],
                                                            className="gantt-heading-button",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dcc.Graph(
                                                                    id={"type": "gantt-chart-jobsort", "index": 1},
                                                                    responsive=True,
                                                                    className="gantt-div",
                                                                    config={"displayModeBar": False},
                                                                ),
                                                                dcc.Graph(
                                                                    id={"type": "gantt-chart-startsort", "index": 1},
                                                                    responsive=True,
                                                                    className="display-none",
                                                                    config={"displayModeBar": False},
                                                                ),
                                                            ]
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Hr(),
                                                                html.Div(
                                                                    [
                                                                        html.H5(id="highs-stats-make-span"),
                                                                        problem_details("highs"),
                                                                    ],
                                                                    className="problem-details"
                                                                ),
                                                            ],
                                                            className="problem-details-parent",
                                                        ),
                                                    ],
                                                ),
                                                className="gantt-chart-card-parent",
                                            ),
                                        ],
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
