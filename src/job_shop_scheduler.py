"""
This module contains the JobShopSchedulingCQM class, which is used to build and
solve a Job Shop Scheduling problem using CQM.

"""
from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING
import warnings

import pandas as pd
from dimod import Binary, ConstrainedQuadraticModel, Integer
from dwave.system import LeapHybridCQMSampler

sys.path.append("./src")
import utils.scipy_solver as scipy_solver
import utils.plot_schedule as job_plotter
from model_data import JobShopData
from utils.greedy import GreedyJobShop
from utils.utils import print_cqm_stats, write_solution_to_file

from nlsolver import HSSNLSolver
from dwave.optimization.generators import flow_shop_scheduling

if TYPE_CHECKING:
    import dwave.optimization


def generate_greedy_makespan(job_data: JobShopData, num_samples: int = 100) -> int:
    """This function generates random samples using the greedy algorithm; it will keep the
    top keep_pct percent of samples.

    Args:
        job_data (JobShopData): An instance of the JobShopData class
        num_samples (int, optional): The number of samples to take (number of times
            the GreedyJobShop algorithm is run). Defaults to 100.

    Returns:
        int: The best makespan found by the greedy algorithm.
    """
    solutions = []
    for _ in range(num_samples):
        greedy = GreedyJobShop(job_data)
        task_assignments = greedy.solve()
        solutions.append(max([v[1] for v in task_assignments.values()]))
    best_greedy = min(solutions)

    return best_greedy


class JobShopSchedulingModel:
    """Builds and solves a Job Shop Scheduling problem using CQM or the NL Solver.

    Args:
        model_data (JobShopData): The data for the job shop scheduling
        max_makespan (int, optional): The maximum makespan allowed for the schedule.
            If None, the makespan will be set to a value that is greedy_mulitiplier
            times the makespan found by the greedy algorithm. Defaults to None.
        greedy_multiplier (float, optional): The multiplier to apply to the greedy makespan,
            to get the upperbound on the makespan. Defaults to 1.4.

    Attributes:
        model_data (JobShopData): The data for the job shop scheduling
        cqm (ConstrainedQuadraticModel): The CQM model
        nl_model (nlsolver.Model): The NL Solver model
        solution (dict): The solution to the problem
        makespan (int): The final makespan of the schedule
        max_makespan (int): The maximum makespan allowed for the schedule

    """

    def __init__(
        self, model_data: JobShopData, max_makespan: int = None, greedy_multiplier: float = 1.4
    ):
        self.model_data = model_data
        self.cqm = None
        self.nl_model = None

        # CQM specifics
        self._x = {}
        self._y = {}
        self._makespan_var = {}
        self._best_sample_cqm = {}

        # solution and makespan results
        self.solution = {}
        self.makespan = 0
        self.max_makespan = max_makespan or generate_greedy_makespan(model_data) * greedy_multiplier

    def define_cqm_model(self) -> None:
        """Define CQM model."""
        self.cqm = ConstrainedQuadraticModel()

    def create_nl_model(self) -> None:
        """Create NL model."""
        self.nl_model = flow_shop_scheduling(processing_times=self.model_data.processing_times)

    def define_cqm_variables(self) -> None:
        """Define CQM variables."""
        # Define make span as an integer variable
        self._makespan_var = Integer("makespan", lower_bound=0, upper_bound=self.max_makespan)

        # Define integer variable for start time of using machine i for job j
        self._x = {}
        for job in self.model_data.jobs:
            for resource in self.model_data.resources:
                task = self.model_data.get_resource_job_tasks(job=job, resource=resource)
                lb, ub = self.model_data.get_task_time_bounds(task, self.max_makespan)
                self._x[(job, resource)] = Integer(
                    "x{}_{}".format(job, resource), lower_bound=lb, upper_bound=ub
                )

        # Add binary variable which equals to 1 if job j precedes job k on
        # machine i
        self._y = {
            (j, k, i): Binary("y{}_{}_{}".format(j, k, i))
            for j in self.model_data.jobs
            for k in self.model_data.jobs
            for i in self.model_data.resources
        }

    def define_cqm_objective(self) -> None:
        """Define objective function, which is to minimize
        the makespan of the schedule.

        Modifies:
            self.cqm: adds the objective function to the CQM model
        """
        self.cqm.set_objective(self._makespan_var)

    def add_precedence_constraints(self) -> None:
        """Adds precedence constraints to the CQM.

        Precedence constraints ensures that all operations of a job are
        executed in the given order.

        Modifies:
            self.cqm: adds precedence constraints to the CQM model
        """
        for job in self.model_data.jobs:  # job
            for prev_task, curr_task in zip(
                self.model_data.job_tasks[job][:-1], self.model_data.job_tasks[job][1:]
            ):
                machine_curr = curr_task.resource
                machine_prev = prev_task.resource
                self.cqm.add_constraint(
                    self._x[(job, machine_curr)] - self._x[(job, machine_prev)] >= prev_task.duration,
                    label="pj{}_m{}".format(job, machine_curr),
                )

    def add_disjunctive_constraints(self) -> None:
        """Adds disjunctive constraints to the CQM.

        This function adds the disjunctive constraints the prevent two jobs
        from being scheduled on the same machine at the same time. This is a
        non-quadratic alternative to the quadratic overlap constraint.

        Modifies:
            self.cqm: adds disjunctive constraints to the CQM model
        """
        V = self.max_makespan
        for j in self.model_data.jobs:
            for k in self.model_data.jobs:
                if j < k:
                    for i in self.model_data.resources:
                        task_k = self.model_data.get_resource_job_tasks(job=k, resource=i)
                        self.cqm.add_constraint(
                            self._x[(j, i)]
                            - self._x[(k, i)]
                            - task_k.duration
                            + self._y[(j, k, i)] * V
                            >= 0,
                            label="disjunction1{}_j{}_m{}".format(j, k, i),
                        )

                        task_j = self.model_data.get_resource_job_tasks(job=j, resource=i)
                        self.cqm.add_constraint(
                            self._x[(k, i)]
                            - self._x[(j, i)]
                            - task_j.duration
                            + (1 - self._y[(j, k, i)]) * V
                            >= 0,
                            label="disjunction2{}_j{}_m{}".format(j, k, i),
                        )

    def add_makespan_constraint(self) -> None:
        """Adds makespan constraints to the CQM.

        Ensures that the make span is at least the largest completion time of
        the last operation of all jobs.

        Modifies:
            self.cqm: adds the makespan constraint to the CQM model
        """
        for job in self.model_data.jobs:
            last_job_task = self.model_data.job_tasks[job][-1]
            last_machine = last_job_task.resource
            self.cqm.add_constraint(
                self._makespan_var - self._x[(job, last_machine)] >= last_job_task.duration,
                label="makespan_ctr{}".format(job),
            )

    def call_cqm_solver(self, time_limit: int, profile: str) -> None:
        """Calls CQM solver.

        Args:
            time_limit (int): time limit in second
            profile (str): The profile variable to pass to the Sampler. Defaults to None.
            See documentation at
            https://docs.ocean.dwavesys.com/en/stable/docs_cloud/reference/generated/dwave.cloud.config.load_config.html#dwave.cloud.config.load_config

        Modifies:
            self.solution: the solution to the problem
            self.makespan: the final makespan of the schedule
        """
        sampler = LeapHybridCQMSampler(profile=profile)
        min_time_limit = sampler.min_time_limit(self.cqm)
        if time_limit is not None:
            time_limit = max(min_time_limit, time_limit)
        raw_sampleset = sampler.sample_cqm(self.cqm, time_limit=time_limit, label="Job Shop Demo")
        feasible_sampleset = raw_sampleset.filter(lambda d: d.is_feasible)
        num_feasible = len(feasible_sampleset)
        if num_feasible > 0:
            best_samples = feasible_sampleset.truncate(min(10, num_feasible))
        else:
            warnings.warn("Warning: CQM did not find feasible solution")
            best_samples = raw_sampleset.truncate(10)

        self._best_sample_cqm = best_samples.first.sample

        self.solution = {
            (j, i): (
                self.model_data.get_resource_job_tasks(job=j, resource=i),
                self._best_sample_cqm[self._x[(j, i)].variables[0]],
                self.model_data.get_resource_job_tasks(job=j, resource=i).duration,
            )
            for i in self.model_data.resources
            for j in self.model_data.jobs
        }

        self.makespan = self._best_sample_cqm["makespan"]

    def _calculate_end_times(self) -> list[list[int]]:
        """Calculate the end-times for the FSS job results.

        Helper function to calculate the end-times for the FSS job
        results obtained from the NL Solver. Taken directly from the
        FSS generator in the NL Solver generators module.

        Update when symbol labels are supported.

        Returns:
            list[list[int]]: end-times from the problem results
        """
        times = self.model_data.processing_times
        num_machines, num_jobs = len(times), len(times[0])

        order = next(self.nl_model.iter_decisions()).state(0).astype(int)

        end_times = []
        for machine_m in range(num_machines):

            machine_m_times = []
            if machine_m == 0:

                for job_j in range(num_jobs):

                    if job_j == 0:
                        machine_m_times.append(times[machine_m, :][order[job_j]])
                    else:
                        end_job_j = times[machine_m, :][order[job_j]]
                        end_job_j += machine_m_times[-1]
                        machine_m_times.append(end_job_j)

            else:

                for job_j in range(num_jobs):

                    if job_j == 0:
                        end_job_j = end_times[machine_m - 1][job_j]
                        end_job_j += times[machine_m, :][order[job_j]]
                        machine_m_times.append(end_job_j)
                    else:
                        end_job_j = max(end_times[machine_m - 1][job_j], machine_m_times[-1])
                        end_job_j += times[machine_m, :][order[job_j]]
                        machine_m_times.append(end_job_j)

            end_times.append(machine_m_times)

        return end_times

    def call_nl_solver(self, time_limit: int) -> None:
        """Calls NL solver.

        Args:
            time_limit (int): time limit in second

        Modifies:
            self.solution: the solution to the problem
        """
        _ = HSSNLSolver().solve(self.nl_model, time_limit=time_limit)

        end_times = self._calculate_end_times(self.nl_model)

        for machine_idx, machine_times in enumerate(end_times):
            for job_idx, end_time in enumerate(machine_times):
                job = int(next(self.nl_model.iter_decisions()).state()[job_idx])

                resource = self.model_data.resource_names[machine_idx]
                task = self.model_data.get_resource_job_tasks(job=str(job), resource=resource)
                self.solution[(str(job), resource)] = task, end_time - task.duration, task.duration

    def call_scipy_solver(self, time_limit: int = 100):
        """This function calls the HiGHS via SciPy and returns the solution

        Args:
            time_limit (int, optional): The maximum amount of time to
            allow the HiGHS solver to before returning. Defaults to 100.

        Modifies:
            self.solution: the solution to the problem
        """
        solver = scipy_solver.SciPyCQMSolver()
        sol = solver.sample_cqm(cqm=self.cqm, time_limit=time_limit)
        self.solution = {}
        if len(sol) == 0:
            warnings.warn("Warning: HiGHS did not find feasible solution")
            return
        best_sol = sol.first.sample

        for var, val in best_sol.items():

            if var.startswith("x"):
                job, machine = var[1:].split("_")
                task = self.model_data.get_resource_job_tasks(job=job, resource=machine)
                self.solution[(job, machine)] = task, val, task.duration

    def solution_as_dataframe(self) -> pd.DataFrame:
        """This function returns the solution as a pandas DataFrame

        Returns:
            pd.DataFrame: A pandas DataFrame containing the solution
        """
        df_rows = []
        for (j, i), (task, start, dur) in self.solution.items():
            df_rows.append([j, task, start, start + dur, i])
        df = pd.DataFrame(df_rows, columns=["Job", "Task", "Start", "Finish", "Resource"])
        return df


def run_shop_scheduler(
    job_data: JobShopData,
    solver_time_limit: int = 60,
    use_scipy_solver: bool = False,
    use_nl_solver: bool = False,
    verbose: bool = False,
    out_sol_file: str = None,
    out_plot_file: str = None,
    profile: str = None,
    max_makespan: int = None,
    greedy_multiplier: float = 1.4,
) -> pd.DataFrame:
    """This function runs the job shop scheduler on the given data.

    Args:
        job_data (JobShopData): A JobShopData object that holds the data for this job shop
            scheduling problem.
        solver_time_limit (int, optional): Upperbound on how long the schedule can be; leave empty to
            auto-calculate an appropriate value. Defaults to None.
        use_scipy_solver (bool, optional): Whether to use the HiGHS via SciPy solver instead of the CQM solver.
            Overridden by ``use_nl_solver`` if both are True. Defaults to False.
        use_nl_solver (bool, optional): Whether to use the HiGHS via SciPy solver instead of the CQM solver.
            Overrides the ``use_scipy_solver`` argument when both are True. Defaults to False.
        verbose (bool, optional): Whether to print verbose output. Defaults to False.
        out_sol_file (str, optional): Path to the output solution file. Defaults to None.
        out_plot_file (str, optional): Path to the output plot file. Defaults to None.
        profile (str, optional): The profile variable to pass to the Sampler. Defaults to None.
        max_makespan (int, optional): Upperbound on how long the schedule can be; leave empty to
            auto-calculate an appropriate value. Defaults to None.
        greedy_multiplier (float, optional): The multiplier to apply to the greedy makespan,
            to get the upperbound on the makespan. Defaults to 1.4.

    Returns:
        pd.DataFrame: A DataFrame that has the following columns: Task, Start, Finish, and
        Resource.

    """
    model = JobShopSchedulingModel(
        model_data=job_data, max_makespan=max_makespan, greedy_multiplier=greedy_multiplier
    )

    if verbose:
        print_cqm_stats(model.cqm)

    if use_nl_solver:
        model.create_nl_model()
        model.call_nl_solver(time_limit=solver_time_limit)
    else:
        model.define_cqm_model()
        model.define_cqm_variables()

        model.add_precedence_constraints()
        model.add_disjunctive_constraints()
        model.add_makespan_constraint()

        model.define_cqm_objective()

        if use_scipy_solver:
            model.call_scipy_solver(time_limit=solver_time_limit)
        else:
            model.call_cqm_solver(time_limit=solver_time_limit, profile=profile)

    # Write solution to a file.
    if out_sol_file is not None:
        write_solution_to_file(job_data, model.solution, model.makespan, out_sol_file)

    # Plot solution
    if out_plot_file is not None:
        job_plotter.plot_solution(job_data, model.solution, out_plot_file)

    df = model.solution_as_dataframe()
    return df


if __name__ == "__main__":
    """Modeling and solving Job Shop Scheduling using CQM solver."""

    # Instantiate the parser
    parser = argparse.ArgumentParser(
        description="Job Shop Scheduling Using LeapHybridCQMSampler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--instance",
        type=str,
        help="path to the input instance file; ",
        default="input/instance5_5.txt",
    )

    parser.add_argument("-tl", "--time_limit", type=int, help="time limit in seconds", default=10)

    parser.add_argument(
        "-os",
        "--output_solution",
        type=str,
        help="path to the output solution file",
        default="output/solution.txt",
    )

    parser.add_argument(
        "-op",
        "--output_plot",
        type=str,
        help="path to the output plot file",
        default="output/schedule.png",
    )

    parser.add_argument(
        "-m",
        "--use_scipy_solver",
        action="store_true",
        help="Whether to use the HiGHS solver instead of the hybrid solver",
    )

    parser.add_argument(
        "-m",
        "--use_nl_solver",
        action="store_false",
        help="Whether to use the NL solver instead of the CQM solver",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", default=True, help="Whether to print verbose output"
    )

    parser.add_argument(
        "-p",
        "--profile",
        type=str,
        help="The profile variable to pass to the Sampler. Defaults to None.",
        default=None,
    )

    parser.add_argument(
        "-mm",
        "--max_makespan",
        type=int,
        help="Upperbound on how long the schedule can be; leave empty to auto-calculate an appropriate value.",
        default=None,
    )

    # Parse input arguments.
    args = parser.parse_args()
    input_file = args.instance
    time_limit = args.time_limit
    out_plot_file = args.output_plot
    out_sol_file = args.output_solution
    max_makespan = args.max_makespan
    profile = args.profile
    use_scipy_solver = args.use_scipy_solver
    use_nl_solver = args.use_nl_solver
    verbose = args.verbose

    job_data = JobShopData()
    job_data.load_from_file(input_file)

    results = run_shop_scheduler(
        job_data,
        time_limit,
        verbose=verbose,
        use_scipy_solver=use_scipy_solver,
        use_nl_solver=use_nl_solver,
        profile=profile,
        max_makespan=max_makespan,
        out_sol_file=out_sol_file,
        out_plot_file=out_plot_file,
    )
