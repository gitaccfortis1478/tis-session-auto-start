"""
daily_scheduler.py

Runs once per day (e.g. at Windows logon) and:

1. Runs todays_schedule.py to generate today's CSV.
2. Reads today's CSV.
3. Creates one Windows Task Scheduler task per session.
4. Schedules each session to start randomly between
   EARLY_MINUTES before the scheduled time and the
   scheduled time itself.
5. Uses a truncated normal distribution for the random time.
6. Removes previously-created session tasks for today.
7. Exits.

Requirements:
    pip install pywin32

Run this script once manually first to verify everything.
"""

from __future__ import annotations
import win32com.client
import csv
import random
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from scipy.stats import truncnorm
import time

import constant_details
from utilities import empty_directory, log_details, start_logging, complete_logging


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = constant_details.BASE_DIR

UPCOMING_SCHEDULES_DIR = constant_details.UPCOMING_SCHEDULES_DIR

PYTHON_EXE = constant_details.PYTHON_EXE

TODAYS_SCHEDULE_SCRIPT = constant_details.TODAYS_SCHEDULE_SCRIPT

SESSION_STARTER_SCRIPT = constant_details.SESSION_STARTER_SCRIPT

SESSION_ENDER_SCRIPT = constant_details.SESSION_ENDER_SCRIPT

SESSION_STARTER_ARGUMENT_NAME = constant_details.SESSION_STARTER_ARGUMENT_NAME

SESSION_ENDER_ARGUMENT_NAME = constant_details.SESSION_ENDER_ARGUMENT_NAME


# All tasks created by this script use this prefix.
TASK_PREFIX = "TIS Mentor Session - "


# Number of minutes before the scheduled session that
# the session is allowed to start.
EARLY_MINUTES = 5
LATE_MINUTES = 5


# Normal distribution parameters.
#
# We sample "minutes early".
#
# Mean = 3.5 means the average launch is around
# 3.5 minutes before the scheduled start.
#
# STDDEV = 1.25 gives reasonable variation.
NORMAL_MEAN = 3.5
NORMAL_STDDEV = 1.25


# Task Scheduler settings.
TASK_AUTHOR = "TIS Mentor Auto Scheduler"

TASK_DESCRIPTION = (
    "Automatically generated TIS Mentor session task."
)


# ============================================================
# TASK SCHEDULER CONSTANTS
# ============================================================

# Task creation/update.
TASK_CREATE_OR_UPDATE = 6

# Trigger type: time-based.
TASK_TRIGGER_TIME = 1

# Action type: execute a program.
TASK_ACTION_EXEC = 0

# Logon type: interactive token.
TASK_LOGON_INTERACTIVE_TOKEN = 3

# Run level: highest privileges.
TASK_RUNLEVEL_HIGHEST = 1


# ============================================================
# GENERAL HELPERS
# ============================================================

def run_todays_schedule() -> None:
    """
    Run todays_schedule.py and wait until it finishes.
    """

    log_details("Running today's schedule generator...")

    result = subprocess.run(
        [
            str(PYTHON_EXE),
            str(TODAYS_SCHEDULE_SCRIPT),
        ],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )

    if result.stdout:
        log_details(result.stdout)

    if result.stderr:
        log_details(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(
            "todays_schedule.py failed with "
            f"exit code {result.returncode}"
        )


def get_today_csv() -> Path:
    """
    Return today's CSV file.

    Expected filename:
        YYYY-MM-DD.csv
    """

    today = datetime.now().strftime("%Y-%m-%d")

    csv_path = BASE_DIR / UPCOMING_SCHEDULES_DIR / f"{today}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Today's schedule CSV does not exist:\n{csv_path}"
        )

    return csv_path


def read_sessions(csv_path: Path) -> list[dict]:
    """
    Read sessions from today's CSV.

    Expected columns:

        ID
        Date
        Student
        Course
        Start Time
        End Time
    """

    sessions = []

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "ID",
            "Date",
            "Student",
            "Course",
            "Start Time",
            "End Time"
        }

        missing = required_columns - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                "CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:

            start_time_text = row["Start Time"].strip()

            if not start_time_text:
                continue

            start_time = datetime.strptime(
                start_time_text,
                "%Y-%m-%d %H:%M:%S",
            )

            end_time_text = row["End Time"].strip()

            if not end_time_text:
                continue

            end_time = datetime.strptime(
                end_time_text,
                "%Y-%m-%d %H:%M:%S",
            )

            sessions.append(
                {
                    "ID": row["ID"],
                    "date": row["Date"],
                    "student": row["Student"],
                    "course": row["Course"],
                    "start_time": start_time,
                    "end_time": end_time
                }
            )

    return sessions


# ============================================================
# RANDOM START TIME
# ============================================================

def random_session_start(
    start_time: datetime,
) -> datetime:
    """
    Pick a random start time between:

        start_time - EARLY_MINUTES
        and
        start_time

    using a truncated normal distribution.

    The normal distribution is centered around
    NORMAL_MEAN minutes early.
    """

    minutes_early = truncnorm.rvs(
        a=(0 - NORMAL_MEAN) / NORMAL_STDDEV,
        b=(EARLY_MINUTES - NORMAL_MEAN) / NORMAL_STDDEV,
        loc=NORMAL_MEAN,
        scale=NORMAL_STDDEV,
    )

    seconds_early = round(minutes_early * 60)

    return start_time - timedelta(
        seconds=seconds_early
    )


def random_session_end(
    end_time: datetime,
) -> datetime:
    """
    Pick a random end time between:

        end_time
        and
        end_time + LATE_MINUTES

    using a truncated normal distribution.

    The normal distribution is centered around
    NORMAL_MEAN minutes late.
    """

    minutes_late = truncnorm.rvs(
        a=(0 - NORMAL_MEAN) / NORMAL_STDDEV,
        b=(LATE_MINUTES - NORMAL_MEAN) / NORMAL_STDDEV,
        loc=NORMAL_MEAN,
        scale=NORMAL_STDDEV,
    )

    seconds_late = round(minutes_late * 60)

    return end_time + timedelta(
        seconds=seconds_late
    )


# ============================================================
# TASK NAME
# ============================================================

def sanitize_task_name(text: str) -> str:
    """
    Make text safe for use as part of a Task Scheduler
    task name.
    """

    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " -_()."
    )

    return "".join(
        character
        for character in text
        if character in allowed
    ).strip()


def make_task_name(session: dict, operation: Literal['start', 'end']) -> str:
    """
    Generate a unique, human-readable Task Scheduler name.
    """

    student = sanitize_task_name(
        session["student"]
    )

    if operation == 'start':
        time = session["start_time"]
    elif operation == 'end':
        time = session["end_time"]

    return (
        f"{TASK_PREFIX}"
        f"{time:%Y-%m-%d %H-%M-%S} - "
        f"{student} "
        f"({operation.upper()})"
    )


# ============================================================
# TASK SCHEDULER CONNECTION
# ============================================================

def connect_to_task_scheduler():
    """
    Connect to Windows Task Scheduler.
    """

    scheduler = win32com.client.Dispatch(
        "Schedule.Service"
    )

    scheduler.Connect()

    return scheduler


# ============================================================
# TASK CLEANUP
# ============================================================

def delete_existing_tasks(
    scheduler,
) -> None:
    """
    Delete existing tasks created by this scheduler.

    Only tasks beginning with TASK_PREFIX are touched.
    """

    root_folder = scheduler.GetFolder("\\")

    tasks = root_folder.GetTasks(0)

    tasks_to_delete = []

    for task in tasks:

        if task.Name.startswith(TASK_PREFIX):
            tasks_to_delete.append(task.Name)

    for task_name in tasks_to_delete:

        log_details(f"Deleting old task: {task_name}")

        try:
            root_folder.DeleteTask(
                task_name,
                0,
            )
        except Exception as exc:
            log_details(
                f"Could not delete {task_name}: {exc}"
            )


# ============================================================
# CREATE TASK
# ============================================================

def create_session_task(
    scheduler,
    session: dict,
    launch_time: datetime,
    operation: Literal['start', 'end'],
    session_id_to_send_details_of: int | None = None,
) -> None:
    """
    Create one Windows Task Scheduler task.
    """

    root_folder = scheduler.GetFolder("\\")

    task_name = make_task_name(session, operation)

    task_definition = scheduler.NewTask(0)

    # --------------------------------------------------------
    # Registration information
    # --------------------------------------------------------

    registration = task_definition.RegistrationInfo

    registration.Author = TASK_AUTHOR

    # --------------------------------------------------------
    # Principal
    # --------------------------------------------------------

    principal = task_definition.Principal

    principal.LogonType = (
        TASK_LOGON_INTERACTIVE_TOKEN
    )

    principal.RunLevel = TASK_RUNLEVEL_HIGHEST

    # --------------------------------------------------------
    # Settings
    # --------------------------------------------------------

    settings = task_definition.Settings

    settings.Enabled = True

    settings.StartWhenAvailable = False

    settings.ExecutionTimeLimit = "PT1H"

    settings.DisallowStartIfOnBatteries = False

    settings.StopIfGoingOnBatteries = False

    settings.AllowHardTerminate = True

    settings.WakeToRun = True

    # Do not run another instance if somehow triggered twice.
    settings.MultipleInstances = 2

    # --------------------------------------------------------
    # Trigger
    # --------------------------------------------------------

    trigger = task_definition.Triggers.Create(
        TASK_TRIGGER_TIME
    )

    trigger.StartBoundary = (
        launch_time.strftime("%Y-%m-%dT%H:%M:%S")
    )

    # This is a one-time trigger.
    trigger.Enabled = True

    # --------------------------------------------------------
    # Action
    # --------------------------------------------------------

    action = task_definition.Actions.Create(
        TASK_ACTION_EXEC
    )
    
    action.Path = str(PYTHON_EXE)
    
    action.WorkingDirectory = str(BASE_DIR)
    
    session_id_arg = session_id_to_send_details_of or ""
    
    if operation == 'start':
        registration.Description = (
            f"{TASK_DESCRIPTION}\n"
            f"Student: {session['student']}\n"
            f"Course: {session['course']}\n"
            f"Scheduled Start: "
            f"{session['start_time']:%Y-%m-%d %H:%M:%S}"
        )
        
        if session_id_to_send_details_of:
            action.Arguments = (
                f'\"{SESSION_STARTER_SCRIPT}\" {SESSION_STARTER_ARGUMENT_NAME} {session_id_arg}'
            )
        else:
            action.Arguments = (
                f'\"{SESSION_STARTER_SCRIPT}\"'
            )
        
    elif operation == 'end':
        registration.Description = (
            f"{TASK_DESCRIPTION}\n"
            f"Student: {session['student']}\n"
            f"Course: {session['course']}\n"
            f"Scheduled End: "
            f"{session['end_time']:%Y-%m-%d %H:%M:%S}"
        )
        
        if session_id_to_send_details_of:
            action.Arguments = (
                f'\"{SESSION_ENDER_SCRIPT}\" {SESSION_ENDER_ARGUMENT_NAME} {session_id_arg}'
            )
        else:
            action.Arguments = (
                f'\"{SESSION_ENDER_SCRIPT}\"'
            )
        

    # --------------------------------------------------------
    # Register task
    # --------------------------------------------------------

    root_folder.RegisterTaskDefinition(
        task_name,
        task_definition,
        TASK_CREATE_OR_UPDATE,
        "",
        "",
        TASK_LOGON_INTERACTIVE_TOKEN,
        "",
    )
    
    if operation == 'start':
        scheduled_time = session['start_time']
    elif operation == 'end':
        scheduled_time = session['end_time']
    
    
    log_details(
        f"Created task:\n"
        f"  {task_name}\n"
        f"  Scheduled: "
        f"{scheduled_time:%Y-%m-%d %H:%M:%S}\n"
        f"  Launch:    "
        f"{launch_time:%Y-%m-%d %H:%M:%S}"
    )


# ============================================================
# MAIN
# ============================================================

def main():
    
    start_logging()

    log_details("=" * 70)
    log_details("TIS Mentor Daily Scheduler")
    log_details("=" * 70)

    now = datetime.now()

    # --------------------------------------------------------
    # 1. Generate today's CSV
    # --------------------------------------------------------

    run_todays_schedule()

    # --------------------------------------------------------
    # 2. Locate today's CSV
    # --------------------------------------------------------

    csv_path = get_today_csv()

    log_details(f"\nSchedule file: {csv_path}")

    # --------------------------------------------------------
    # 3. Read today's sessions
    # --------------------------------------------------------

    sessions = read_sessions(csv_path)

    log_details(
        f"Found {len(sessions)} session(s)."
    )

    if not sessions:
        log_details("Nothing to schedule.")
        return

    # --------------------------------------------------------
    # 4. Connect to Task Scheduler
    # --------------------------------------------------------

    scheduler = connect_to_task_scheduler()

    # --------------------------------------------------------
    # 5. Remove existing generated tasks
    # --------------------------------------------------------

    log_details("\nCleaning up old session tasks...")

    delete_existing_tasks(scheduler)

    # --------------------------------------------------------
    # 6. Create today's tasks
    # --------------------------------------------------------

    log_details("\nCreating today's upcoming session tasks...\n")

    created = 0
    skipped = 0
    
    for i, session in enumerate(sessions):
    
        session_start_time = session["start_time"]
        session_end_time = session["end_time"]
        
        current_session_id = session["ID"]
        previous_session_id = None
        
        launch_time = random_session_start(session_start_time)
                
        if i != 0:
            previous_session = sessions[i - 1]
            previous_session_id = previous_session["ID"]
        
        create_session_task(
            scheduler,
            session,
            launch_time,
            operation='start',
            session_id_to_send_details_of=previous_session_id
        )
        
        created += 1

        # Check the next session, if there is one.
        if i + 1 < len(sessions):

            upcoming_session = sessions[i + 1]
            upcoming_session_end_time = upcoming_session["end_time"]
            
            time_difference = (upcoming_session_end_time - session_start_time)

            # Assign a task to end the session if the next session starts more than 15 mins after the current one
            
            if time_difference > timedelta(minutes=15):
                launch_time = random_session_end(session_end_time)
                
                create_session_task(
                    scheduler,
                    session,
                    launch_time,
                    operation='end',
                    session_id_to_send_details_of=current_session_id
                )
                
                created += 1

        else:
            launch_time = random_session_end(session_end_time)
            
            create_session_task(
                scheduler,
                session,
                launch_time,
                operation='end',
                session_id_to_send_details_of=current_session_id
            )
            
            created += 1

        # ----------------------------------------------------
        # If login happened after the selected launch time,
        # don't create a task in the past.
        # ----------------------------------------------------

    #     if launch_time <= now:

    #         log_details(
    #             f"SKIPPED: {session['student']} "
    #             f"at {scheduled_time:%H:%M:%S} "
    #             f"(launch time already passed)"
    #         )

    #         skipped += 1

    #         continue

    #     create_session_task(
    #         scheduler,
    #         session,
    #         launch_time,
    #     )

    #     created += 1
        
    # # # # # # # 

    # for session in sessions:

    #     scheduled_time = session["start_time"]

    #     # Pick random launch time.
    #     launch_time = random_session_start(
    #         scheduled_time
    #     )

    #     # ----------------------------------------------------
    #     # If login happened after the selected launch time,
    #     # don't create a task in the past.
    #     # ----------------------------------------------------

    #     if launch_time <= now:

    #         log_details(
    #             f"SKIPPED: {session['student']} "
    #             f"at {scheduled_time:%H:%M:%S} "
    #             f"(launch time already passed)"
    #         )

    #         skipped += 1

    #         continue

    #     create_session_task(
    #         scheduler,
    #         session,
    #         launch_time,
    #     )

    #     created += 1
    
    
    

    # --------------------------------------------------------
    # 7. Summary
    # --------------------------------------------------------

    log_details("\n" + "=" * 70)
    log_details("Scheduling complete")
    log_details("=" * 70)

    log_details(f"Sessions found:   {len(sessions)}")
    log_details(f"Tasks created:    {created}")
    log_details(f"Sessions skipped: {skipped}")
    
    complete_logging()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
