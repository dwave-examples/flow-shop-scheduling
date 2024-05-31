# Copyright 2024 D-Wave Systems Inc.
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

"""This file stores input parameters for the app."""

import json

# Sets Dash debug which hides and shows Dash debug menu.
# Set to True if developing and False if demoing.
# App should be restarted to see change.
DEBUG = False

# THEME_COLOR is used for the button, text, and banner and should be dark
# and pass accessibility checks with white: https://webaim.org/resources/contrastchecker/
# THEME_COLOR_SECONDARY can be light or dark and is used for sliders, loading icon, and tabs
THEME_COLOR = "#074C91"  # D-Wave dark blue default #074C91
THEME_COLOR_SECONDARY = "#2A7DE1"  # D-Wave blue default #2A7DE1

THUMBNAIL = "assets/dwave_logo.svg"

APP_TITLE = "FSS Demo"
MAIN_HEADER = "Flow Shop Scheduling"
DESCRIPTION = """\
Run the flow shop scheduling problem for several different scenarios.
Explore the Gantt Chart for solution details.
"""

CLASSICAL_TAB_LABEL = "Classical Results"
DWAVE_TAB_LABEL = "Hybrid Solver Results"

SHOW_CQM = True

# The list of scenarios that the user can choose from in the app.
# These can be found in the 'input' directory.
SCENARIOS = {
    "20x5": "tai20_5.txt",
    "20x10": "tai20_10.txt",
    "20x20": "tai20_20.txt",
    "50x5": "tai50_5.txt",
    "50x10": "tai50_10.txt",
    "50x20": "tai50_20.txt",
    "100x5": "tai100_5.txt",
    "100x10": "tai100_10.txt",
    "100x20": "tai100_20.txt",
    "200x10": "tai200_10.txt",
    "200x20": "tai200_20.txt",
    "500x20": "tai500_20.txt",
}

# solver time limits in seconds (value means default)
SOLVER_TIME = {
    "min": 5,
    "max": 300,
    "step": 5,
    "value": 5,
}

# The list of resources that the user can choose from in the app
RESOURCE_NAMES = json.load(open("./src/data/resource_names.json", "r"))["industrial"]
