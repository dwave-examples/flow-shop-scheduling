#    Copyright 2024 D-Wave Systems Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import diskcache
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import DiskcacheManager

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

from src.model_data import FlowShopData

Y_AXIS_LABEL = "Job"
COLOR_LABEL = "Operation"  # must be operation label


def get_minimum_task_times(flow_shop_data: FlowShopData) -> pd.DataFrame:
    """Takes a FlowShopData object, gets the minimum time each
    task can be completed by, and generates the Jobs to Be Scheduled
    Gantt chart.

    Args:
        flow_shop_data (FlowShopData): The data for the flow shop scheduling problem.

    Returns:
        pd.DataFrame: A DataFrame of the jobs to be scheduled including Task, Start, Finish,
        Operation, and delta.
    """
    task_data = []
    for tasks in flow_shop_data.job_tasks.values():
        start_time = 0
        for task in tasks:
            end_time = start_time + task.duration
            task_data.append(
                {
                    Y_AXIS_LABEL: task.job,
                    "Start": start_time,
                    "Finish": end_time,
                    COLOR_LABEL: task.resource,
                    "Conflicts": "No",
                }
            )
            start_time = end_time

    def tasks_overlap(task_i, task_j):
        """Returns True if tasks a and b overlap"""
        interval_a, interval_b = sorted(
            ((task_i["Start"], task_i["Finish"]), (task_j["Start"], task_j["Finish"]))
        )
        return interval_b[0] < interval_a[1]

    # Calculate scheduling conflicts
    for i, task_i in enumerate(task_data):
        for j, task_j in enumerate(task_data[i + 1 :]):
            if task_i[COLOR_LABEL] == task_j[COLOR_LABEL] and tasks_overlap(task_i, task_j):
                task_data[i]["Conflicts"] = task_data[i + 1 + j]["Conflicts"] = "Yes"

    df = pd.DataFrame(task_data)
    df["delta"] = df.Finish - df.Start
    df[Y_AXIS_LABEL] = df[Y_AXIS_LABEL].astype(str)
    df[COLOR_LABEL] = df[COLOR_LABEL].astype(str)
    return df


def get_empty_figure(message: str) -> go.Figure:
    """Generates an empty chart figure message.
    This is used to replace the chart object
    when no chart is available.

    Args:
        message (str): The message to display in the center of the chart.

    Returns:
        go.Figure: A Plotly figure object containing the message.
    """
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 28},
            }
        ],
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10),
    )
    return fig


def generate_gantt_chart(
    df: pd.DataFrame = None, sort_by: str = "JobInt", show_conflicts: bool = False
) -> go.Figure:
    """Generates a Gantt chart of the unscheduled tasks for the given scenario.

    Args:
        df (pd.DataFrame): A DataFrame containing the data to plot. If this is
            not None, then the scenario argument will be ignored.
        sort_by (str): How to sort the jobs. Usually by job (``"JobInt"``) or start time (``"Start"``).

    Returns:
        go.Figure: A Plotly figure object.
    """
    if df[Y_AXIS_LABEL].dtype == "object":
        df["JobInt"] = df[Y_AXIS_LABEL].str.replace(Y_AXIS_LABEL, "").astype(int)
    else:
        df["JobInt"] = df[Y_AXIS_LABEL]

    df["delta"] = df.Finish - df.Start

    df[COLOR_LABEL] = df[COLOR_LABEL].astype(str)
    df[Y_AXIS_LABEL] = df[Y_AXIS_LABEL].astype(str)

    # get the unique resource labels in order
    color_labels = sorted(df[COLOR_LABEL].unique(), key=lambda r: int(r.split(".")[0]))
    num_items = len(color_labels)
    colorscale = "Agsunset"
    colors = px.colors.sample_colorscale(
        colorscale, [n / (num_items - 1) for n in range(num_items)]
    )
    color_map = dict(zip(color_labels, colors))

    df = df.sort_values(by=[sort_by], ascending=False)
    df = df.drop(columns=["JobInt"])

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y=Y_AXIS_LABEL,
        color=COLOR_LABEL,
        pattern_shape="Conflicts" if show_conflicts else None,
        pattern_shape_map={"Yes": "/", "No": ""},
        color_discrete_sequence=[color_map[label] for label in color_labels],
        category_orders={COLOR_LABEL: color_labels},
    )

    # Update legend to remove conflict text and duplicates.
    unique_labels = set()
    for i, trace in enumerate(fig.select_traces()):
        label = trace.legendgroup.split(",")[0]
        if label not in unique_labels:
            trace.update({"name": label, "legendrank": i})
            unique_labels.add(label)
        else:
            trace.update({"showlegend": False})

    fig.update_legends({"title": {"text": COLOR_LABEL}})  # Update legend title.

    for index, data in enumerate(fig.data):
        resource = data.name.split(",")[0]
        fig.data[index].x = [
            df[(df[Y_AXIS_LABEL] == job) & (df[COLOR_LABEL] == resource)].delta.tolist()[0]
            for job in data.y
        ]

    fig.layout.xaxis.type = "linear"
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10),
        xaxis_title="Time Period",
    )
    return fig
