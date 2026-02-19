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
    SHOW_CQM,
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


def checklist(label: str, id: str, options: list, values: list, inline: bool = True) -> html.Div:
    """Checklist element for option selection.

    Args:
        label: The title that goes above the checklist.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        values: A list of values that should be preselected in the checklist.
        inline: Whether the options of the checklist are displayed beside or below each other.
    """
    return html.Div(
        className="checklist-wrapper",
        children=[
            html.Label(label, htmlFor=id),
            dcc.Checklist(
                id=id,
                className=f"checklist{' checklist--inline' if inline else ''}",
                inline=inline,
                options=options,
                value=values,
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
                                    html.H2(
                                        [title, html.Span(id=f"{tab}-gantt-title-span")],
                                        className="gantt-title",
                                    ),
                                    html.Button(
                                        id={"type": "gantt-heading-button", "index": index},
                                        className="button",
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
                            html.Div([
                                html.H5(id=f"{tab}-stats-makespan", className="stats-makespan"),
                                problem_details(index)
                            ], className="problem-details"),
                        ],
                        className="problem-details-parent",
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
    solver_options = generate_options(SolverType, False)
    hybrid_solver_options = generate_options(HybridSolverType, True)

    return html.Div(
        className="settings",
        children=[
            dropdown(
                "Scenario (jobs x operations)",
                "scenario-select",
                scenario_options,
            ),
            checklist(
                "Solver (hybrid and/or classical)",
                "solver-select",
                sorted(solver_options, key=lambda op: op["value"]),
                [0, 1],
            ),
            html.Div(
                dropdown(
                    "Quantum Hybrid Solver",
                    "hybrid-select",
                    sorted(hybrid_solver_options, key=lambda op: op["value"]),
                ),
                id="hybrid-select-wrapper",
                className="" if SHOW_CQM else "display-none",
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


def generate_table(table_data: dict[str, list]) -> html.Table:
    """Generates a table containing table_data.

    Args:
        table_data: A dictionary of table header keys and table column values.

    Returns:
        html.Table: An HTML table containing table_data.
    """
    table_columns = table_data.values()
    num_rows = len(next(iter(table_columns)))

    return html.Table(
        className="problem-details-table",
        children=[
            html.Thead(html.Tr([html.Th(table_header) for table_header in table_data.keys()])),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(column[i]) for column in table_columns
                        ]
                    ) for i in range(num_rows)
                ]
            ),
        ],
    )


def problem_details(index: int) -> html.Div:
    """Generate the problem details section.

    Args:
        index: Unique element id to differentiate matching elements.
            Must be different from left column collapse button.

    Returns:
        html.Div: Div containing a collapsable table.
    """
    return html.Div(
        id={"type": "to-collapse-class", "index": index},
        className="details-collapse-wrapper collapsed",
        children=[
            # Problem details collapsible button and header
            html.Button(
                id={"type": "collapse-trigger", "index": index},
                className="details-collapse",
                children=[
                    html.H5("Problem Details"),
                    html.Div(className="collapse-arrow"),
                ],
                **{"aria-expanded": "true"},
            ),
            html.Div(
                className="details-to-collapse",
                id={"type": "problem-details", "index": index}
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
                                                                className="button",
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
