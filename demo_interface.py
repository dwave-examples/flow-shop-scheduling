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

from __future__ import annotations
from enum import EnumType

from dash import dcc, html
import dash_mantine_components as dmc

from demo_configs import (
    CLASSICAL_TAB_LABEL,
    DESCRIPTION,
    DWAVE_TAB_LABEL,
    MAIN_HEADER,
    SCENARIOS,
    SOLVER_TIME,
    THUMBNAIL,
)
from src.demo_enums import HybridSolverType, SolverType

THEME_COLOR = "#2d4376"


def dropdown(label: str, id: str, options: list) -> html.Div:
    """Dropdown element for option selection.

    Args:
        label: The title that goes above the dropdown.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
    """
    return html.Div(
        className="dropdown-wrapper",
        children=[
            html.Label(label, htmlFor=id),
            dmc.Select(
                id=id,
                data=options,
                value=options[0]["value"],
                allowDeselect=False,
            ),
        ],
    )


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


def generate_solution_tab(title: str, tab: str, index: int) -> dmc.TabsPanel:
    """Generates solution tab containing, solution graphs, sort functionality, and
    problem details dropdown.

    Returns:
        dmc.TabsPanel: A Tab containing the solution graph and problem details.
    """
    return dmc.TabsPanel(
        value=f"{tab}-tab",
        tabIndex=11+index,
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
                                    html.Div([
                                        html.H2(
                                            [title, html.Span(id=f"{tab}-gantt-title-span")],
                                            className="gantt-title",
                                        ),
                                        html.H4([
                                            "Makespan: ",
                                            html.Span(id=f"{tab}-makespan")
                                        ], className="makespan"),
                                    ]),
                                    html.Button(
                                        id={"type": "gantt-heading-button", "index": index},
                                        className="button button-small",
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
                ],
            ),
        ],
    )


def generate_options(options: list | EnumType, str_val: bool=False) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    if isinstance(options, EnumType):
        return [{"label": option.label, "value": f"{option.value}" if str_val else option.value} for option in options]

    return [{"label": option, "value": f"{option}" if str_val else option} for option in options]


def generate_settings_form() -> html.Div:
    """This function generates settings for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the settings for selecting the scenario, model, and solver.
    """

    scenario_options = generate_options(SCENARIOS, True)

    return html.Div(
        className="settings",
        children=[
            dropdown(
                "Scenario (jobs x operations)",
                "scenario-select",
                scenario_options,
            ),
            dmc.CheckboxGroup(
                id="solver-select",
                label="Solvers",
                value=[f"{SolverType.HYBRID.value}", f"{SolverType.HIGHS.value}"],
                children=dmc.Group(
                    [
                        dmc.Checkbox(
                            label=SolverType.HYBRID.label,
                            value=f"{SolverType.HYBRID.value}",
                            color=THEME_COLOR,
                        ),
                        dmc.RadioGroup(
                            children=dmc.Group(
                                [
                                    dmc.Radio(
                                        s.label,
                                        value=f"{s.value}",
                                        color=THEME_COLOR
                                    ) for s in HybridSolverType
                                ]
                            ),
                            id="hybrid-select",
                            value=f"{HybridSolverType.STRIDE.value}",
                            size="sm",
                            deselectable=False,
                            style={"display": "none"},
                        ),
                        dmc.Checkbox(
                            label=SolverType.HIGHS.label,
                            value=f"{SolverType.HIGHS.value}",
                            color=THEME_COLOR
                        ),
                    ],
                ),
            ),
            html.Label("Solver Time Limit (seconds)", htmlFor="solver-time-limit"),
            dmc.NumberInput(
                id="solver-time-limit",
                type="number",
                **SOLVER_TIME,
            ),
        ],
    )


def generate_run_buttons() -> html.Div:
    """Run and cancel buttons to run the optimization."""
    return html.Div(
        id="button-group",
        children=[
            html.Button("Run Optimization", id="run-button", className="button"),
            html.Button(
                "Cancel Optimization",
                id="cancel-button",
                className="button",
                style={"display": "none"},
            ),
        ],
    )


def create_interface():
    """Set the application HTML."""
    return html.Div(
        id="app-container",
        children=[
            html.A(  # Skip link for accessibility
                "Skip to main content",
                href="#main-content",
                id="skip-to-main",
                className="skip-link",
                tabIndex=1,
            ),
            dcc.Store("running-dwave"),
            dcc.Store("running-classical"),
            html.Main(
                className="columns-main",
                id="main-content",
                children=[
                    # Left column
                    html.Div(
                        id={"type": "to-collapse-class", "index": 0},
                        className="left-column",
                        children=[
                            html.Div(
                                className="left-column-layer-1",  # Fixed width Div to collapse
                                children=[
                                    html.Div(
                                        className="left-column-layer-2",  # Padding and content wrapper
                                        children=[
                                            html.Div(
                                                [
                                                    html.H1(MAIN_HEADER),
                                                    html.P(DESCRIPTION),
                                                ],
                                                className="title-section",
                                            ),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        html.Div(
                                                            [
                                                                generate_settings_form(),
                                                                generate_run_buttons(),
                                                            ],
                                                            className="settings-and-buttons",
                                                        ),
                                                        className="settings-and-buttons-wrapper",
                                                    ),
                                                    # Left column collapse button
                                                    html.Div(
                                                        html.Button(
                                                            id={
                                                                "type": "collapse-trigger",
                                                                "index": 0,
                                                            },
                                                            className="left-column-collapse",
                                                            title="Collapse sidebar",
                                                            children=[
                                                                html.Div(className="collapse-arrow")
                                                            ],
                                                            **{"aria-expanded": "true"},
                                                        ),
                                                    ),
                                                ],
                                                className="form-section",
                                            ),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    ),
                    # Right column
                    html.Div(
                        className="right-column",
                        children=[
                            dmc.Tabs(
                                id="tabs",
                                value="input-tab",
                                color="white",
                                children=[
                                    html.Header(
                                        className="banner",
                                        children=[
                                            html.Nav(
                                                [
                                                    dmc.TabsList(
                                                        [
                                                            dmc.TabsTab("Input", value="input-tab"),
                                                            dmc.TabsTab(
                                                                DWAVE_TAB_LABEL,
                                                                value="dwave-tab",
                                                                id="dwave-tab",
                                                                disabled=True,
                                                            ),
                                                            dmc.TabsTab(
                                                                CLASSICAL_TAB_LABEL,
                                                                value="highs-tab",
                                                                id="highs-tab",
                                                                disabled=True,
                                                            ),
                                                        ]
                                                    ),
                                                ]
                                            ),
                                            html.Img(src=THUMBNAIL, alt="D-Wave logo"),
                                        ],
                                    ),
                                    dmc.TabsPanel(
                                        value="input-tab",
                                        tabIndex="12",
                                        children=[
                                            html.Div(
                                                className="gantt-chart-card",
                                                children=[
                                                    html.Div(
                                                        className="gantt-heading",
                                                        children=[
                                                            html.H2(
                                                                "Unscheduled Jobs and Operations",
                                                                className="gantt-title",
                                                            ),
                                                            html.Button(
                                                                id={
                                                                    "type": "gantt-heading-button",
                                                                    "index": 0,
                                                                },
                                                                className="button button-small",
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
                                                        color=THEME_COLOR,
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
                                        "Quantum Hybrid Solver", "dwave", 1
                                    ),
                                    generate_solution_tab(
                                        "Classical Solver (HiGHS)", "highs", 2
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
