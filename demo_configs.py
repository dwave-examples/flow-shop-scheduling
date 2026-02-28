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

"""This file stores input parameters for the app."""

import json

THUMBNAIL = "static/dwave_logo.svg"

APP_TITLE = "FSS Demo"
MAIN_HEADER = "Flow Shop Scheduling"
DESCRIPTION = """\
Run the cargo-loading themed flow shop scheduling (FSS) problem for several
different scenarios. Each job must execute, in order, all operations listed
on the right.
"""

CLASSICAL_TAB_LABEL = "Classical Results"
DWAVE_TAB_LABEL = "Hybrid Results"

SHOW_CQM = True

# The list of scenarios (sorted by jobs, then operations) that the user
# can choose from in the app. These can be found in the 'input' directory.
# Only the first Taillard instance for each size is loaded directly.
SCENARIOS = {
    "Carlier 12x5": "car3",
    "Carlier 13x4": "car2",
    "Carlier 14x4": "car4",
    "Reeves 20x5": "reC01",  # reC03, reC05
    "Taillard 20x5": "tai20_5.txt",
    "Heller 20x10": "hel2",
    "Taillard 20x10": "tai20_10.txt",
    "Reeves 20x10": "reC07",  # reC09, reC11
    "Reeves 20x15": "reC13",  # reC15, reC17
    "Taillard 20x20": "tai20_20.txt",
    "Reeves 30x10": "reC19",  # reC21, reC23
    # "Reeves 30x15": "reC25",  #reC27, reC29
    # "Taillard 50x5": "tai50_5.txt",
    # "Reeves 50x10": "reC31",  #reC33, reC35
    # "Taillard 50x10": "tai50_10.txt",
    # "Taillard 50x20": "tai50_20.txt",
    # "Reeves 75x20": "reC37",  #reC39, reC41
    # "Taillard 100x5": "tai100_5.txt",
    # "Heller 100x10": "hel1",
    # "Taillard 100x10": "tai100_10.txt",
    # "Taillard 100x20": "tai100_20.txt",
    # "Taillard 200x10": "tai200_10.txt",
    # "Taillard 200x20": "tai200_20.txt",
    # "Taillard 500x20": "tai500_20.txt",
}

OR_INSTANCES = "flowshop1.txt"

# solver time limits in seconds (value means default)
SOLVER_TIME = {
    "min": 5,
    "max": 300,
    "step": 5,
    "value": 10,
}

# The list of resources that the user can choose from in the app
RESOURCE_NAMES = json.load(open("./src/data/resource_names.json", "r"))
