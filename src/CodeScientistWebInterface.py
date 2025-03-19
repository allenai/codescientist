# ExperimentWebInterface.py
# This is the web interface for the experiment manager.  It requires that the back-end server is also running (ExperimentWebServer.py)

import json
import os
import time
import argparse
import traceback
import requests
import random
import re
from datetime import datetime

import pywebio
from pywebio.input import *
from pywebio.output import *
from pywebio.pin import *
from pywebio.session import run_js

from flask import Flask, send_from_directory, abort, current_app, make_response
from flask import make_response, Response

from pywebio.platform.flask import webio_view

app = Flask(__name__)



# Show main header for all pages
def showHeader():
    # Include FontAwesome
    put_html('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.1/css/all.min.css">')

    # Show a small CodeScientist logo and vertically centered text beside it
    import base64

    FILENAME_LOGO = "images/logo-500.png"

    try:
        # Read and encode the images as base64
        with open(FILENAME_LOGO, "rb") as img_file:
            img_content_logo = base64.b64encode(img_file.read()).decode('utf-8')

        # Single logo
        htmlStr  = f"""<div style="display: flex; align-items: center; width: 100%; height: 50px;">"""
        htmlStr += f"""<div style="width: 100%; text-align: left;">"""
        #htmlStr += f"""<img src="data:image/png;base64,{img_content_logo}" alt="CodeScientist Logo" style="max-width: 100%; height: auto;">"""
        # As above, but make the logo return to the root directory (/) every time it's clicked.
        htmlStr += f"""<a href="/" style="text-decoration: none; color: black;"><img src="data:image/png;base64,{img_content_logo}" alt="CodeScientist Logo" style="max-width: 100%; height: auto;"></a>"""
        htmlStr += f"""</div>"""
        htmlStr += f"""</div>"""
        put_html(htmlStr)


    except Exception as e:
        put_markdown("ERROR: " + str(e))


# Show the queue status from the server
def showQueueStatus():
    # Request the queue status from the server using the `/queuestatus` endpoint.  It will respond with a JSON object.
    endpoint = "http://localhost:5001/queuestatus"
    try:
        payload = {}         # Empty payload
        response = requests.post(endpoint, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            # Make a nice but compact HTML rendering of this information, using FontAwesome icons.
            htmlOut = "<b>Job Queue Status:</b> "
            # First, show total jobs, with a Font Awesome icon
            htmlOut += f"<i class='fas fa-tasks'></i> {response_data['queue_size']} jobs in queue.  "
            # Next, show the number of completed jobs
            htmlOut += f"<i class='fas fa-check-circle'></i> {response_data['processed_tasks']} jobs completed.  "

            # Show the task type historgram.
            histFontAwesomeKeys = {
                "ideation_create_new_ideas": "fa-lightbulb",
                "ingest_paper": "fa-file-alt",
                "run_operationalization_questions": "fa-cogs",
                "run_experiment": "fa-flask",
            }

            # Show the histogram of task types
            htmlOut += "<b>Queued Jobs:</b> "
            #for taskType, count in response_data['queued_task_type_histogram'].items():
            for taskType in histFontAwesomeKeys.keys():
                count = response_data['queued_task_type_histogram'].get(taskType, 0)
                htmlOut += f"<i class='fas {histFontAwesomeKeys[taskType]}' title='{taskType}'></i> ({count}) &nbsp;&nbsp; "

            htmlOut += "<br>"

            # Finally, show the current task being processed, if any
            if (response_data['current_task_being_processed'] is not None):
                htmlOut += f"<i class='fas fa-spinner fa-spin'></i> Currently processing job type: {response_data['current_task_being_processed']}."
            else:
                htmlOut += f"No jobs currently being processed."

            # Experiment workers
            num_running_experiment_threads = response_data.get("num_running_experiment_threads", 0)
            max_experiment_threads = response_data.get("max_experiment_threads", 0)

            htmlOut += f"<br><b>Experiment Workers:</b> {num_running_experiment_threads} / {max_experiment_threads} running.  "
            # Filled circle: <i class="fa-solid fa-circle"></i>
            # Empty circle: <i class="fa-regular fa-circle"></i>
            for i in range(max_experiment_threads):
                if (i < num_running_experiment_threads):
                    htmlOut += f"<i class='fas fa-circle' style='color: black;'></i> "
                else:
                    htmlOut += f"<i class='far fa-circle' style='color: grey;'></i> "
            htmlOut += "<br>"


            # Show the HTML
            put_html(htmlOut)


        else:
            put_text(f"Server returned an error: {response.status_code}")
    except Exception as e:
        put_text(f"Error communicating with the server: {str(e)}")


    pass


# Show the queue status from the server
def showQueueStatusDetails():
    # Request the queue status from the server using the `/queuestatus` endpoint.  It will respond with a JSON object.
    endpoint = "http://localhost:5001/queuedetails"
    try:
        payload = {}         # Empty payload
        response = requests.post(endpoint, json=payload)
        if response.status_code == 200:
            # Get response
            response_data = response.json()

            # Unpack response
            processed_task_summary = response_data['processed_task_summary']    # Dictionary. Key:task_type.  Value: Dictionary with added information: {"total_cost": 0, "min_cost": 0, "max_cost": 0, "avg_cost": 0, "total_time_sec": 0, "min_time_sec": 0, "max_time_sec": 0, "avg_time_sec": 0, "num_success": 0, "num_fail": 0, "total_jobs": 0}
            num_queued_tasks = response_data['num_queued_tasks']                # Integer
            queued_task_details = response_data['queued_task_details']          # Keys: {"task_type": taskType, "added_time": taskAddedTime}
            current_task_being_processed = response_data['current_task_being_processed']    # String, or None

            # Font awesome keys for different task types
            taskFontAwesomeKeys = {
                "ideation_create_new_ideas": "fa-lightbulb",
                "ingest_paper": "fa-file-alt",
                "run_operationalization_questions": "fa-cogs",
                "run_experiment": "fa-flask",
            }

            # First, make a table of the processed tasks, showing all statistics
            put_markdown("## Processed Task Summary")
            table = [
                ["Task Type", "Num Jobs", "Total Cost", "Costs ($) (min/avg/max)", "Time (mins) (min/avg/max)", "Success Rate"]
            ]
            for taskType, taskSummary in processed_task_summary.items():
                # Calculate the success rate
                successRate = 0
                if (taskSummary["total_jobs"] > 0):
                    successRate = taskSummary["num_success"] / taskSummary["total_jobs"]
                successRate = round(successRate * 100, 2)
                taskFontAwesomeStr = f"{taskType}"
                #if (taskType in taskFontAwesomeKeys):
                #    taskFontAwesomeStr = f"<i class='fas {taskFontAwesomeKeys[taskType]}'></i> {taskType}"
                totalCost = round(taskSummary["total_cost"], 2)
                minCost = round(taskSummary["min_cost"], 2)
                maxCost = round(taskSummary["max_cost"], 2)
                avgCost = round(taskSummary["avg_cost"], 2)
                minTimeMins = round(taskSummary["min_time_sec"] / 60, 2)
                avgTimeMins = round(taskSummary["avg_time_sec"] / 60, 2)
                maxTimeMins = round(taskSummary["max_time_sec"] / 60, 2)

                table.append([
                    taskFontAwesomeStr,
                    taskSummary["total_jobs"],
                    totalCost,
                    f"{minCost:.2f} / {avgCost:.2f} / {maxCost:.2f}",
                    f"{minTimeMins:.2f} / {avgTimeMins:.2f} / {maxTimeMins:.2f}",
                    f"{successRate:.1f} %"
                ])

            put_table(table)


            # Next, add the task currently being processed
            put_markdown("## Current Task Being Processed")
            if (current_task_being_processed is not None):
                put_html("<i class='fas fa-spinner fa-spin'></i> Currently processing job type: " + current_task_being_processed)
            else:
                put_html("No tasks currently being processed.")



            # Next, show the queued tasks
            put_markdown("## Queued Task Details")
            put_html("<b>Number of queued tasks:</b> " + str(num_queued_tasks))

            table1 = [
                ["Queue Position", "Task Type", "Time Added"]
            ]

            for idx, taskDetail in enumerate(queued_task_details):
                sanitizedTime = taskDetail["added_time"].replace("T", " ").replace("Z", "").split(".")[0]
                taskType1 = taskDetail["task_type"]
                taskFontAwesomeStr = f"{taskType1}"
                #if (taskType in taskFontAwesomeKeys):
                #    taskFontAwesomeStr = f"<i class='fas {taskFontAwesomeKeys[taskType]}'></i> {taskType}"

                table1.append([
                    idx,
                    taskFontAwesomeStr,
                    sanitizedTime
                ])

            if (len(queued_task_details) <= 0):
                table1.append(["--", "No tasks in queue", "--"])

            put_table(table1)


            # Past tasks run (most recent 10)
            put_markdown("## Recently Processed Tasks")
            last_tasks_completed = response_data['last_tasks_completed']
            table2 = [
                ["Task Type", "Time Completed", "Cost ($)", "Time (mins)", "Success"]
            ]
            for task in last_tasks_completed:
                taskFontAwesomeStr = f"{task['task_type']}"
                #if (task['task_type'] in taskFontAwesomeKeys):
                #    taskFontAwesomeStr = f"<i class='fas {taskFontAwesomeKeys[task['task_type']]}'></i> {task['task_type']}"
                timeSeconds = 0
                if ("time_seconds" in task):
                    timeSeconds = task["time_seconds"]
                if ("runtime_seconds" in task):
                    timeSeconds = task["runtime_seconds"]
                endTimeStr = ""
                if ("end_time" in task):
                    endTimeStr = task["end_time"]
                    # Sanitize
                    endTimeStr = endTimeStr.replace("T", " ").replace("Z", "").split(".")[0]
                totalCost = 0
                if ("total_cost" in task):
                    totalCost = task["total_cost"]
                    totalCost = round(totalCost, 2)

                success = False
                if ("success" in task):
                    success = task["success"]

                table2.append([
                    taskFontAwesomeStr,
                    endTimeStr,
                    str(totalCost),
                    round(timeSeconds / 60, 2),
                    success
                ])

            put_table(table2)

            # Put the raw response for debugging
            # put_markdown("## Raw Response")
            # put_text(json.dumps(response_data, indent=2))


        else:
            put_text(f"Server returned an error: {response.status_code}")
    except Exception as e:
        put_text(f"Error communicating with the server: {str(e)}")


    pass




#
#   Showing the status page
#

def showStatus():
    run_js('window.location.href="/status";')

@app.route('/status', methods=['GET', 'POST'])
def _showStatus():
    def pywebio_show():
        # Inject JavaScript to reload the page when navigating back (otherwise table doesn't populate)
        run_js(""" window.onpageshow = function(event) { if (event.persisted) { window.location.reload() } }; """)

        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Status")

        # Show task queue
        put_markdown("## Task Queue Status Overview")
        showQueueStatus()

        # Show task queue details
        put_markdown("## Task Queue Details")
        showQueueStatusDetails()

    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response





# Helper Function: Ask the server for a list of known codeblock names
def getKnownCodeblockNames():
    try:
        response = requests.get('http://localhost:5001/knowncodeblocknames')
        if response.status_code == 200:
            response_data = response.json()
            codeblock_names = response_data['codeblock_names']
            return codeblock_names
        else:
            put_text(f"Server returned an error: {response.status_code}")
            return None
    except Exception as e:
        put_text(f"Error communicating with the server: {str(e)}")
        return None


# Helper Function: Get a list of all experiments
def getExperimentList():
    try:
        response = requests.get('http://localhost:5001/getexperimentlist')
        if response.status_code == 200:
            response_data = response.json()
            experiment_list = response_data['experiment_list']
            return experiment_list
        else:
            put_text(f"Server returned an error: {response.status_code}")
            return None
    except Exception as e:
        put_text(f"Error communicating with the server: {str(e)}")
        return None



#
#   Adding a new experiment (manually)
#

def showCreateExperimentManual():
    run_js('window.location.href="/newexperimentmanual";')

# Manually add a new experiment
@app.route('/newexperimentmanual', methods=['GET', 'POST'])
def createNewExperimentManual():
    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        put_markdown("# Create a new experiment (manually)")

        # Fetch a list of known codeblock names
        knownCodeblockNames = getKnownCodeblockNames()
        if (knownCodeblockNames is None):
            put_text("Error fetching known codeblock names.  Is the back-end server running?")
            return
        # Sort the codeblock names alphabetically
        knownCodeblockNames = sorted(knownCodeblockNames)

        put_markdown("**Expected Time:** It generally takes 2-60 minutes to run and debug an experiment. It's recommended you describe the experiment as a pilot experiment, using a small amount of data, so that it runs quicker.  You can always run it at scale once it works.")
        put_markdown("**Expected Cost:** TODO")

        # Get user input
        user_input = input_group("Automatically Generate Ideas", [
            # add a selection box for the model to use
            select("Code Generation/Debugging Model to Use:", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "gpt-4o-2024-11-20", "o1-2024-12-17", "o1-mini", "gpt-4o-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"]),
            input("Give the experiment a short name (no spaces -- e.g. my-experiment-123):", name='experiment_name_short'),
            textarea("Describe the experiment in detail:", name='experiment_description', rows=5),
            checkbox("Codeblocks to use:", name='codeblock_names_to_use', options=knownCodeblockNames),
            # What's the maximum time each iteration of the experiment should run for? (default 10 minutes)
            select("Maximum runtime per iteration for mini-pilot experiments (minutes):", name='max_time_per_iteration_pilot_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60], value=10),
            select("Maximum runtime per iteration for full pilots/experiments(minutes):", name='max_time_per_iteration_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180], value=10),
            select("Maximum (hard-limit) runtime for the entire series of experiments (hours):", name='hard_runtime_cutoff_hours', options=[0.05, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], value=6),
            # Maxium number of debug iterations (default 10)
            select("Maximum number of debug iterations:", name='max_debug_iterations', options=[5, 10, 15, 20, 25, 30], value=10),
            # Maximum cost of any LLM calls the experiment makes
            select("Maximum cost of LLM calls within the experiment container, per iteration (USD):", name='max_llm_cost_container', options=[0.10, 0.25, 0.50, 1.0, 2.0, 5.0], value=0.10),
            select("Maximum TOTAL COST of each experiment (hard limit) (USD):", name='max_experiment_cost', options=[0.10, 1.0, 5.0, 10.0, 15.0, 20.0, 25.0], value=0.10),
            # Number of independent threads to try to build and run the experiment on
            select("Number of independent attempts to build and debug this experiment (spawns one thread per attempt; multiplies the cost linearly, but increases diversity/chance of success):", name='num_copies', options=[1, 2, 3, 4, 5], value=1)
        ])

        # hard_runtime_cutoff_seconds
        hard_runtime_cutoff_seconds = int(user_input['hard_runtime_cutoff_hours'] * 3600)

        # Prepare JSON payload
        payload = {
            'model_str': user_input['model_str'],
            'experiment_name_short': user_input['experiment_name_short'],
            'experiment_description': user_input['experiment_description'],
            'codeblock_names_to_use': user_input['codeblock_names_to_use'],
            'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
            'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
            'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
            'max_debug_iterations': user_input['max_debug_iterations'],
            'max_llm_cost_container': user_input['max_llm_cost_container'],
            'max_experiment_cost': user_input['max_experiment_cost'],
            'num_copies': user_input['num_copies'],
            'submission_mode': 'manual',
        }

        # Send POST request to the server
        try:
            response = requests.post('http://localhost:5001/startnewexperiment1', json=payload)
            if response.status_code == 202:
                response_data = response.json()
                put_markdown("## Server Response")
                put_text(json.dumps(response_data, indent=2))
            else:
                put_text(f"Server returned an error: {response.status_code}")
        except Exception as e:
            put_text(f"Error communicating with the server: {str(e)}")


    return webio_view(pywebio_show)()


#
#   New experiment (from an existing idea)
#
@app.route('/newexperimentfromidea/<idea_id>', methods=['GET', 'POST'])
def createNewExperimentFromIdea(idea_id):
    def pywebio_show():
        experiment_prompt = None

        # Clear the output
        clear()

        # Header
        showHeader()

        put_markdown("# Create a new experiment (from an existing idea)")

        # Fetch a list of known codeblock names
        knownCodeblockNames = getKnownCodeblockNames()
        if (knownCodeblockNames is None):
            put_text("Error fetching known codeblock names.  Is the back-end server running?")
            return
        # Sort the codeblock names alphabetically
        knownCodeblockNames = sorted(knownCodeblockNames)

        # Get the existing idea (from the @app.route('/getidea/<id>', methods=['GET']) endpoint)
        # Fetch the idea
        success, idea = get_idea_by_id_from_server(idea_id)
        if (success is False) or (idea is None):
            put_text("Error fetching idea.  Is the back-end server running?")
            return

        def show_idea_details():
            put_markdown("## Idea Details")

            put_markdown(f"**ID:** {idea['id']}")
            put_markdown(f"**Name:** {idea['research_idea_name']}")
            put_markdown(f"**Description:** {idea.get('research_idea_long_description', '')}")
            put_markdown(f"**Hypothesis:** {idea.get('research_idea_hypothesis', '')}")
            put_markdown(f"**Variables:** {idea.get('research_idea_variables', '')}")
            put_markdown(f"**Metric:** {idea.get('research_idea_metric', '')}")
            put_markdown(f"**Pilot:** {idea.get('research_idea_pilot', '')}")
            put_markdown(f"**Design Prompt:** {idea.get('research_idea_design_prompt', '')}")
            put_markdown(f"**Codeblocks:** {idea.get('research_idea_codeblocks', '')}")
            put_markdown(f"**Date Generated:** {idea.get('date_generated', '')}")
            put_markdown(f"**Inspiring Paper IDs:** {idea.get('inspiring_paper_ids', '')}")
            put_markdown(f"**Generated Using Model:** {idea.get('generated_using_model', '')}")


        def show_experiment_form(experiment_prompt):
            clear()
            show_idea_details()
            put_markdown("## Experiment Building Form")

            experiment_short_name = idea["research_idea_name"]
            experiment_prompt_str = experiment_prompt["prompt"]
            experiment_codeblocks = experiment_prompt["codeblocks"]

            # Remove any codeblocks that are not in the known codeblocks list
            experiment_codeblocks = [x for x in experiment_codeblocks if x in knownCodeblockNames]

            put_html("<span style='color: pink;'>Please review the experiment prompt below, and make any desired edits.  Press 'Submit' to begin the experiment.</span>")

            user_input = input_group("Automatically Generate Ideas", [
                # add a selection box for the model to use
                select("Code Generation/Debugging Model to Use:", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "gpt-4o-2024-11-20", "o1-2024-12-17", "o1-mini", "gpt-4o-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"]),
                input("Give the experiment a short name (no spaces -- e.g. my-experiment-123):", name='experiment_name_short', value=experiment_short_name),
                textarea("Describe the experiment in detail:", name='experiment_description', rows=12, value=experiment_prompt_str),
                checkbox("Codeblocks to use:", name='codeblock_names_to_use', options=knownCodeblockNames, value=experiment_codeblocks),
                # What's the maximum time each iteration of the experiment should run for? (default 10 minutes)
                select("Maximum runtime per iteration for mini-pilot experiments (minutes):", name='max_time_per_iteration_pilot_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60], value=10),
                select("Maximum runtime per iteration for full pilots/experiments(minutes):", name='max_time_per_iteration_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180], value=10),
                select("Maximum (hard-limit) runtime for the entire series of experiments (hours):", name='hard_runtime_cutoff_hours', options=[0.05, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], value=6),
                # Maxium number of debug iterations (default 10)
                select("Maximum number of debug iterations:", name='max_debug_iterations', options=[5, 10, 15, 20, 25, 30], value=10),
                # Maximum cost of any LLM calls the experiment makes
                select("Maximum cost of LLM calls within the experiment container, per iteration (USD):", name='max_llm_cost_container', options=[0.10, 0.25, 0.50, 1.0, 2.0, 5.0], value=0.10),
                select("Maximum TOTAL COST of each experiment (hard limit) (USD):", name='max_experiment_cost', options=[0.10, 1.0, 5.0, 10.0, 15.0, 20.0, 25.0], value=0.10),
                # Number of independent threads to try to build and run the experiment on
                select("Number of independent attempts to build and debug this experiment (spawns one thread per attempt; multiplies the cost linearly, but increases diversity/chance of success):", name='num_copies', options=[1, 2, 3, 4, 5], value=1)
            ])

            hard_runtime_cutoff_seconds = int(user_input['hard_runtime_cutoff_hours'] * 3600)

            # TODO: Handle submission
            # Prepare JSON payload
            payload = {
                'model_str': user_input['model_str'],
                'experiment_name_short': user_input['experiment_name_short'],
                'experiment_description': user_input['experiment_description'],
                'codeblock_names_to_use': user_input['codeblock_names_to_use'],
                'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
                'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
                'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
                'max_debug_iterations': user_input['max_debug_iterations'],
                'max_llm_cost_container': user_input['max_llm_cost_container'],
                'max_experiment_cost': user_input['max_experiment_cost'],
                'num_copies': user_input['num_copies'],
                'submission_mode': 'automatic',
                'idea_id': idea_id,
                'original_idea': idea,
                'automatically_generated_experiment_prompt': experiment_prompt
            }

            # Send POST request to the server
            try:
                response = requests.post('http://localhost:5001/startnewexperiment1', json=payload)
                if response.status_code == 202:
                    response_data = response.json()
                    # Print an 'experiment confirmed' message in green
                    put_markdown("## Experiment Submitted")
                    put_html("<span style='color: green;'>Experiment submitted.  The experiment has been added to the queue.  You can the experiment in the experiment list.</span>")

                    put_markdown("## Server Response")
                    put_text(json.dumps(response_data, indent=2))

                else:
                    put_text(f"Server returned an error: {response.status_code}")
            except Exception as e:
                put_text(f"Error communicating with the server: {str(e)}")



        def start_experiment_conversion():
            put_markdown("## Starting Experiment Conversion")
            put_markdown("This process may take up to one minute...")
            # Put a spinner
            put_loading(shape='grow')

            # Ask the server to convert this into an experiment
            # TODO
            success, experiment_prompt = convert_idea_to_experiment_prompt_server(idea_id)
            if (success is False) or (experiment_prompt is None):
                put_text("Error converting idea to experiment.  Is the back-end server running?")
                return

            # Show the experiment prompt
            put_markdown("## Experiment Prompt")
            put_text(json.dumps(experiment_prompt, indent=2))

            show_experiment_form(experiment_prompt)


        # Starts here

        show_idea_details()

        # Add a button to confirm that the user wants to conver this into an experiment
        put_markdown("## Confirm Experiment Creation")
        put_markdown("If you'd like to convert this idea into an experiment prompt, click the button below.  The experiment idea will be converted into an experiment prompt, and provided for editing.  After this, you can select to run the experiment if desired. (This conversion process typically takes up to 1 minute)")
        put_buttons(['Create Experiment'], onclick=lambda _: start_experiment_conversion())

        return

    return webio_view(pywebio_show)()



#
#   Show PDF reports
#
from flask import send_file
@app.route('/pdf/<folder>')
def serve_pdf(folder):
    pdf_path = f'pdfs/{folder}/report.pdf'
    print("Serving PDF: " + pdf_path)
    return send_file(pdf_path, as_attachment=False)


#
#   Batch Autonomous Experimentation
#
def showBatchAutonomousExperiments():
    # This function just redirects to an endpoint
    run_js('window.location.href="/batchautonomousexperiments";')

@app.route('/batchautonomousexperiments', methods=['GET', 'POST'])
def _showBatchAutonomousExperiments():
    def pywebio_show():

        def show_batch_experiment_setup():
            put_markdown("## Batch Autonomous Experimentation Setup")

            # Make a form with the following fields:
            # Checkbox for discourage generating ideas similar to existing ideas
            # Text box for idea topic to condition on

            # Make a bright blue text
            put_html("<span style='color: red;'>This section is for large (and expensive!) runs that autonomously generate ideas, operationalize those ideas, then run those experiments.</span>")


            user_input = input_group("Batch Autonomous Experimentation", [
                # add a selection box for the model to use
                input("Give this batch run a short name (no spaces -- e.g. my-batch-123):", name='batch_name_short', value="my-batch"),
                select("Code Generation/Debugging Model to Use:", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "gpt-4o-2024-11-20", "o1-2024-12-17", "o1-mini", "gpt-4o-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"]),
                #checkbox("Codeblocks to use:", name='codeblock_names_to_use', options=knownCodeblockNames, value=experiment_codeblocks),
                select("Maximum number of papers to generate each idea from:", name='max_papers_per_idea', options=[1, 2, 3], value=2),
                # Checkbox to reduce duplicate ideas.
                checkbox("Discourage generating ideas similar to existing ideas in this batch:", name='discourage_similar_ideas', options=["Enable Deduplication"], value=True),
                # Additional text to condition ideation on:
                textarea("Any additional text to condition the ideation on (e.g. `evaluate in terms of CookingWorld from TextWorldExpress`):", name='condition_idea_text', rows=2, value=""),
                # What's the maximum time each iteration of the experiment should run for? (default 10 minutes)
                textarea("What additional text do you want to append to the experiment operationalization prompt:", name='experiment_additional_operationalization_instructions', rows=12, value="All experiments/calls to a language model should use the `gpt-4o-mini` model, because it's fast and inexpensive."),
                select("Maximum runtime per iteration for mini-pilot experiments (minutes):", name='max_time_per_iteration_pilot_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60], value=10),
                select("Maximum runtime per iteration for full pilots/experiments(minutes):", name='max_time_per_iteration_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180], value=10),
                select("Maximum (hard-limit) runtime for the entire series of experiments (hours):", name='hard_runtime_cutoff_hours', options=[0.05, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], value=6),
                # Maxium number of debug iterations (default 10)
                select("Maximum number of debug iterations:", name='max_debug_iterations', options=[5, 10, 15, 20, 25, 30], value=10),
                # Maximum cost of any LLM calls the experiment makes
                select("Maximum cost of LLM calls within the experiment container, per iteration (USD):", name='max_llm_cost_container', options=[0.10, 0.25, 0.50, 1.0, 2.0, 5.0], value=0.10),
                select("Maximum TOTAL COST of each experiment (hard limit) (USD):", name='max_experiment_cost', options=[0.10, 1.0, 5.0, 10.0, 15.0, 20.0, 25.0], value=0.10),
                # Total number of experiments to run in this batch
                select("Total number of autonomous experiments to run in this batch:", name='num_experiments', options=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100], value=10),
            ])

            # Let's convert the batch name (e.g. my-name) to a name with a date (e.g. my-name-2024-11-20-12-34-56)
            batch_name_short = user_input['batch_name_short']
            batch_name_short = batch_name_short.replace(" ", "-")
            batch_name_short = batch_name_short + "-" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

            hard_runtime_cutoff_seconds = int(user_input['hard_runtime_cutoff_hours'] * 3600)

            # Prepare JSON payload
            payload = {
                'model_str': user_input['model_str'],
                'batch_name_short': batch_name_short,
                'condition_idea_text': user_input['condition_idea_text'],
                'experiment_additional_operationalization_instructions': user_input['experiment_additional_operationalization_instructions'],
                'max_papers_per_idea': user_input['max_papers_per_idea'],
                'discourage_similar_ideas': user_input['discourage_similar_ideas'],
                'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
                'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
                'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
                'max_debug_iterations': user_input['max_debug_iterations'],
                'max_llm_cost_container': user_input['max_llm_cost_container'],
                'max_experiment_cost': user_input['max_experiment_cost'],
                'num_experiments': user_input['num_experiments'],
            }

            # Send POST request to the server
            try:
                put_markdown("## Submitting Autonomous Batch...")
                put_markdown("This may take a moment...")
                response = requests.post('http://localhost:5001/startautonomousbatch', json=payload)
                if response.status_code == 202:
                    response_data = response.json()
                    # Print an 'experiment confirmed' message in green
                    put_markdown("## Autonomous Batch Submitted")
                    put_html("<span style='color: green;'>The autonomous batch has been submitted.  New ideas and experiments will be added to the appropriate lists as they execute.</span>")
                    put_markdown("## Server Response")
                    put_text(json.dumps(response_data, indent=2))

                else:
                    put_text(f"Server returned an error: {response.status_code}")
            except Exception as e:
                put_text(f"Error communicating with the server: {str(e)}")


        # Clear the output
        clear()

        # Header
        showHeader()

        # Show the form
        show_batch_experiment_setup()


    return webio_view(pywebio_show)()


# This function reads a list of available benchmarks from disk
def getBenchmarkList():
    BENCHMARK_FOLDER = "data/"
    benchmark_list = []
    for filename in os.listdir(BENCHMARK_FOLDER):
        # Look for files that start with "benchmark" and end with ".json" and contain the word "operationalized"
        if filename.startswith("benchmark") and filename.endswith(".json") and "operationalized" in filename:
            benchmark_list.append(filename)

    # Try to read each one, to see how many records it has
    benchmark_list_with_counts = []
    for benchmark_filename in benchmark_list:
        try:
            with open(os.path.join(BENCHMARK_FOLDER, benchmark_filename), 'r') as f:
                benchmark_data = json.load(f)
                num_records = len(benchmark_data)
                benchmark_list_with_counts.append({
                    'filename': benchmark_filename,
                    'num_records': num_records
                })
        except Exception as e:
            print(f"Error reading {benchmark_filename}: {str(e)}")

    return benchmark_list_with_counts



def showRunBenchmark():
    # This function just redirects to an endpoint
    run_js('window.location.href="/runbenchmark";')

@app.route('/runbenchmark', methods=['GET', 'POST'])
def _showRunBenchmark():
    def pywebio_show():

        def show_benchmark_setup():
            put_markdown("## Benchmark Run Setup")
            put_html("<span style='color: red;'>This section is for large (and expensive!) runs of benchmarks.  The benchmarks contain previously generated ideas (and operationalizations of those ideas) whose experiments are then built and executed by a given experiment building agent.</span>")

            # Get a list of available benchmarks
            available_benchmark_list = getBenchmarkList()
            available_benchmark_list = sorted(available_benchmark_list, key=lambda x: x['filename'])
            print("List of available benchmarks:")
            print(available_benchmark_list)
            # The label for the select box should be '(num_records) filename', while the value is just the filename

            # Default name for this batch run should be 'my-benchmark-run-' plus the date (the date will be added on later)
            batch_name_short_default = "my-benchmark-run-"

            # Get the names of possible experiment building agents
            # TODO: Should get this from the server
            experment_building_agents = ["simple1", "simple1-with-faithfulness-reflection", "planner1"]

            user_input = input_group("Benchmark Run Submission", [
                # add a selection box for the model to use
                input("Give this batch run a short name (no spaces -- e.g. my-batch-123):", name='batch_name_short', value=batch_name_short_default),
                select("Experiment Building Agent to Use:", name='experiment_building_agent_name', options=experment_building_agents),
                select("Code Generation/Debugging Model to Use:", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "gpt-4o-2024-11-20", "o1-2024-12-17", "o1-mini", "gpt-4o-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"]),
                # Select box for the benchmark to run
                select("Select the benchmark to run:", name='benchmark_to_run', options=[(f"({x['num_records']}) {x['filename']}", x['filename']) for x in available_benchmark_list]),
                select("Maximum runtime per iteration for mini-pilot experiments (minutes):", name='max_time_per_iteration_pilot_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60], value=20),
                select("Maximum runtime per iteration for full pilots/experiments(minutes):", name='max_time_per_iteration_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180], value=90),
                select("Maximum (hard-limit) runtime for the entire series of experiments (hours):", name='hard_runtime_cutoff_hours', options=[0.05, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], value=6),
                # Maxium number of debug iterations (default 10)
                select("Maximum number of debug iterations:", name='max_debug_iterations', options=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50], value=25),
                # Maximum cost of any LLM calls the experiment makes
                select("Maximum cost of LLM calls within the experiment container, per iteration (USD):", name='max_llm_cost_container', options=[0.10, 0.25, 0.50, 1.0, 2.0, 5.0], value=0.10),
                select("Maximum TOTAL COST of each experiment (hard limit) (USD):", name='max_experiment_cost', options=[0.10, 1.0, 5.0, 10.0, 15.0, 20.0, 25.0], value=0.10),
                # Independent copies
                select("Total independent copies of each experiment to run:", name='num_copies_to_run', options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25], value=1),
                # Run notes
                textarea("Run notes (optional):", name='run_notes', rows=3, value=""),
            ])

            # Let's convert the batch name (e.g. my-name) to a name with a date (e.g. my-name-2024-11-20-12-34-56)
            batch_name_short = user_input['batch_name_short']
            batch_name_short = batch_name_short.replace(" ", "-")
            batch_name_short = batch_name_short + "-" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

            hard_runtime_cutoff_seconds = int(user_input['hard_runtime_cutoff_hours'] * 3600)

            # Prepare JSON payload
            payload = {
                'model_str': user_input['model_str'],
                'batch_name_short': batch_name_short,
                'experiment_building_agent_name': user_input['experiment_building_agent_name'],
                'benchmark_to_run': user_input['benchmark_to_run'],
                'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
                'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
                'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
                'max_debug_iterations': user_input['max_debug_iterations'],
                'max_llm_cost_container': user_input['max_llm_cost_container'],
                'max_experiment_cost': user_input['max_experiment_cost'],
                'run_notes': user_input['run_notes'],
                'num_copies_to_run': user_input['num_copies_to_run']
            }

            # Send POST request to the server
            try:
                put_markdown("## Submitting Benchmark Run...")
                put_markdown("This may take a moment...")
                response = requests.post('http://localhost:5001/startbenchmarkrun', json=payload)
                if response.status_code == 202:
                    response_data = response.json()
                    # Print an 'experiment confirmed' message in green
                    put_markdown("## Benchmark Run Submitted")
                    put_html("<span style='color: green;'>The benchmark run has been submitted.  New experiments will be added to the appropriate lists as they execute.</span>")
                    put_markdown("## Server Response")
                    put_text(json.dumps(response_data, indent=2))

                else:
                    put_text(f"Server returned an error: {response.status_code}")
            except Exception as e:
                put_text(f"Error communicating with the server: {str(e)}")


        # Clear the output
        clear()

        # Header
        showHeader()

        # Show the form
        show_benchmark_setup()


    return webio_view(pywebio_show)()


#
#   Meta-Analysis
#
def showMetaAnalysis():
    # This function just redirects to an endpoint
    run_js('window.location.href="/metaanalysis";')

@app.route('/metaanalysis', methods=['GET', 'POST'])
def _showMetaAnalysis():
    def pywebio_show():

        # Get the list of meta-analysis batch prefixes
        def get_metaanalysis_batch_prefixes():
            # endpoint: metaanalysis-batchruns-list
            batch_names = []
            multi_run_experiments = []
            try:
                response = requests.get('http://localhost:5001/metaanalysis-batchruns-list')
                if response.status_code == 200:
                    response_data = response.json()
                    print(response_data)
                    batch_names = response_data['batches']
                    multi_run_experiments = response_data['multi_run_experiments']
                else:
                    print(f"Server returned an error: {response.status_code}")
            except Exception as e:
                print(f"Error communicating with the server: {str(e)}")
            return batch_names, multi_run_experiments


        def load_metaanalysis_list():
            # Get the list of meta-analyses from the `metaanalysis-list` endpoint
            metaanalysis_list = []
            try:
                response = requests.get('http://localhost:5001/metaanalysis-list')
                if response.status_code == 200:
                    response_data = response.json()
                    metaanalysis_list = response_data['metaanalysis_list']
                else:
                    print(f"Server returned an error: {response.status_code}")
            except Exception as e:
                print(f"Error communicating with the server: {str(e)}")
            return metaanalysis_list


        def show_metaanalysis_setup():
            # Get a list of all previous meta-analysis files in this directory. Make a table that shows them all, with a link to download each.
            # The meta-analysis files all start with the prefix "metaanalysis-" and end with ".tsv"

            print("Here1")
            #existing_metaanalysis_files = []
            # list all files in the metaanalysis subdirectory

            # for filename in os.listdir("metaanalysis/"):
            #     if filename.startswith("meta-analysis-bulk-results.") and filename.endswith(".tsv"):
            #         existing_metaanalysis_files.append(filename)
            # print("Existing Meta-Analysis Files: " + str(existing_metaanalysis_files))
            existing_metaanalysis_records = load_metaanalysis_list()
            print("Existing Meta-Analysis Records: ")
            print(json.dumps(existing_metaanalysis_records, indent=4))

            put_markdown("## Existing Meta-Analysis Files")

            # Show a table of existing meta-analysis files
            tableData = []

            if len(existing_metaanalysis_records) > 0:
                #for idx, filename in enumerate(existing_metaanalysis_records):
                # Do it in reverse order
                for idx in range(len(existing_metaanalysis_records)-1, -1, -1):
                    print("Processing record: " + str(idx))
                    print("Record: " + str(existing_metaanalysis_records[idx]))

                    #filename_report = existing_metaanalysis_records[idx]["filename_report"]
                    #filename_report = filename_report.split("/")[-1]

            # "filename_bulk_report": filename_bulk_report,
            # "filename_metaanaysis_report": filename_metaanalysis_report,
                    filename_bulk_report = existing_metaanalysis_records[idx]["filename_bulk_report"]
                    filename_bulk_report = filename_bulk_report.split("/")[-1]
                    filename_metaanalysis_report = existing_metaanalysis_records[idx]["filename_metaanalysis_report"]
                    filename_metaanalysis_report = filename_metaanalysis_report.split("/")[-1]
                    filename_metaanalysis_report_json = existing_metaanalysis_records[idx]["filename_metaanalysis_report_json"]
                    filename_metaanalysis_report_json = filename_metaanalysis_report_json.split("/")[-1]

                    batch_run = existing_metaanalysis_records[idx]["batch_run"]
                    bulk_experiment_run = existing_metaanalysis_records[idx]["bulk_experiment_run"]
                    bulk_experiment_run_files = existing_metaanalysis_records[idx]["bulk_experiment_run_files"]
                    timestamp = existing_metaanalysis_records[idx]["timestamp"]
                    notes = existing_metaanalysis_records[idx]["notes"]
                    download_link_bulk = f"http://localhost:5001/metaanalysis-download/{filename_bulk_report}"
                    download_link_meta = f"http://localhost:5001/metaanalysis-download/{filename_metaanalysis_report}"
                    download_link_meta_json = f"http://localhost:5001/metaanalysis-download/{filename_metaanalysis_report_json}"
                    #button_bulk = put_button("Bulk Report", onclick=lambda url=download_link_bulk: run_js(f'window.open("{url}", "_blank");'))
                    #button_metaanalysis = put_button("Meta-Analysis", onclick=lambda url=download_link_meta: run_js(f'window.open("{url}", "_blank");'))
                    #buttons = put_buttons(['Bulk Report', 'Meta-Analysis'], onclick=[lambda url=download_link_bulk: run_js(f'window.open("{url}", "_blank");'), lambda url=download_link_meta: run_js(f'window.open("{url}", "_blank");')])
                    buttons = put_buttons(['Bulk Report', 'Meta-Analysis', 'Meta-Analysis (JSON)'], onclick=[lambda url=download_link_bulk: run_js(f'window.open("{url}", "_blank");'), lambda url=download_link_meta: run_js(f'window.open("{url}", "_blank");'), lambda url=download_link_meta_json: run_js(f'window.open("{url}", "_blank");')])

                    print("batch_run:", batch_run)
                    print("bulk_experiment_run:", bulk_experiment_run)

                    htmlStr = ""
                    if (batch_run is not None):
                        htmlStr += "<b>Batch Run:</b> " + str(batch_run) + "<br>"
                    if (bulk_experiment_run is not None):
                        htmlStr += "<b>Bulk Experiment Run:</b> " + str(bulk_experiment_run) + "<br>"
                        htmlStr += "<b>Files:</b> " + str(len(bulk_experiment_run_files)) + "<br>"

                    htmlStr += "<b>Report Timestamp:</b> " + str(timestamp) + "<br>"
                    htmlStr += "<b>Notes:</b> " + str(notes) + "<br>"

                    tableData.append([str(idx+1), put_html(htmlStr), style(buttons, "text-align: center;")])
                    #tableData.append([str(idx+1), put_html(filename_report), style(button_bulk, "text-align: center;")])
                    #tableData.append([str(idx+1), put_html(filename_report), style(button_bulk, "text-align: center;")])

                #put_table([["Filename", "Download Link"]] + [[x, f"[Download](/pdf/{x})"] for x in existing_metaanalysis_files])
                # Download access point: @app.route('/metaanalysis-download/<filename>', methods=['GET'])  (use a button)


            else:
                put_text("No existing meta-analysis files found.")

            print("Here1")

            put_table([["#", "Report Details", "Links"]] + tableData)

            print("Here2")


            put_markdown("## Meta-Analysis / Bulk Results Export")
            put_html("<span style='color: blue;'>This section is intended to perform bulk exports of high-level results from sets of (e.g.) benchmark experiment runs. Note, there is a (generally small) LLM cost incurred for each experiment in the meta-analysis.</span>")

            print("Here3")

            # TODO: Fetch a list of previous batch runs and bulk experiment runs
            batch_names = ["", "No Previous Batches Found"]
            multi_run_experiments = ["", "No Previous Multi-Copy Experiments Found"]

            # Get the list of prefixes
            batch_names, multi_run_experiments = get_metaanalysis_batch_prefixes()
            print("Batch Names: " + str(batch_names))
            #print("Multi-Run Experiments: " + str(multi_run_experiments))

            # Convert the dictionary (multi-run-experiments) into a list of strings
            multi_run_experiment_keys = list(multi_run_experiments.keys())
            #print("Multi-Run Experiment Keys: " + str(multi_run_experiment_keys))

            # Make the first option "[No Batch Selected -- Export Everything]"
            #batch_names.insert(0, "[No Batch Selected -- export every experiment]")
            batch_names.insert(0, "")
            multi_run_experiment_keys.insert(0, "")

            user_input = input_group("Meta-Analysis / Bulk Results Export", [
                # Add two selection boxes -- available batch runs, or available bulk experiment runs
                select("Select a previous batch run to analyze:", name='batch_run_to_analyze', options=batch_names),
                select("OR, Select a previous bulk experiment run to analyze:", name='bulk_experiment_run_to_analyze', options=multi_run_experiment_keys),
                # Add comments so the user remembers why they ran this report
                input("Notes/Comments for this report:", name='user_notes', value="Helpful reminder notes for this report here."),
            ])

            # As above, but with validation function that makes sure one (and only one) of the two fields is filled in
            # Validate that one (and only one) of the two fields is filled in
            print("User Input: " + str(user_input))
            if (user_input['batch_run_to_analyze'] == "") and (user_input['bulk_experiment_run_to_analyze'] == ""):
                put_html("<span style='color: red;'><br>Please select either a batch run or a bulk experiment run to analyze (and not both).</span>")
                return
            if (user_input['batch_run_to_analyze'] != "") and (user_input['bulk_experiment_run_to_analyze'] != ""):
                put_html("<span style='color: red;'><br>Please select either a batch run or a bulk experiment run to analyze (and not both).</span>")
                return

            print("Here4")

            # Extract the user input
            bulk_experiment_files = []
            batch_run_to_analyze = user_input['batch_run_to_analyze']
            if (batch_run_to_analyze == ""):
                batch_run_to_analyze = None
            bulk_experiment_run_to_analyze = user_input['bulk_experiment_run_to_analyze']
            if (bulk_experiment_run_to_analyze in multi_run_experiments.keys()):
                # Get the list of experiments associated with this key
                bulk_experiment_files = multi_run_experiments[bulk_experiment_run_to_analyze]
            else:
                bulk_experiment_run_to_analyze = None
            user_notes = user_input['user_notes']

            # Payload
            payload = {
                'batch_run_to_analyze': batch_run_to_analyze,
                'bulk_experiment_run_to_analyze': bulk_experiment_run_to_analyze,
                'bulk_experiment_files': bulk_experiment_files,
                'user_notes': user_notes
            }
            print("Payload: " + str(payload))

            # Send POST request to the server
            try:
                put_markdown("## Submitting Meta-Analysis / Bulk Export...")
                put_markdown("This may take a moment...")

                response = requests.post('http://localhost:5001/metaanalysis-bulkreport', json=payload)
                if response.status_code == 202:
                    response_data = response.json()
                    # Print an 'experiment confirmed' message in green
                    put_markdown("## Meta-Analysis / Bulk Export Submitted")
                    put_html("<span style='color: green;'>The meta-analysis / bulk export has been submitted.  The export will be available for download shortly.</span>")
                    put_markdown("## Server Response")
                    put_text(json.dumps(response_data, indent=2))

                else:
                    put_text(f"Server returned an error: {response.status_code}")
            except Exception as e:
                put_text(f"Error communicating with the server: {str(e)}")


        # Clear the output
        clear()

        # Header
        showHeader()

        # Show the form
        show_metaanalysis_setup()


    return webio_view(pywebio_show)()



#
#   List all the experiments (running or completed)
#

def showExperimentList():
    # This function just redirects to an endpoint
    run_js('window.location.href="/experimentlist";')

@app.route('/experimentlist', methods=['GET', 'POST'])
def _showExperimentList():
    experimentList = []
    def pywebio_show():
        # Inject JavaScript to reload the page when navigating back (otherwise table doesn't populate)
        run_js(""" window.onpageshow = function(event) { if (event.persisted) { window.location.reload() } }; """)

        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Experiment List")

        # Fetch the list of experiments
        experimentList = getExperimentList()
        if (experimentList is None):
            put_text("Error fetching experiment list.  Is the back-end server running?")
            return

        # Show task queue
        showQueueStatus()

        def show_experiment_table(experimentList):
            # TODO: Re-enable the sort-by
            sortBy = pin.sort_by

            # By default, just show them in reverse order of when they were created (which is the order they were added to the list)
            experimentList = reversed(experimentList)

            # Perform any sorting
            experimentListSorted = experimentList
            if (sortBy == "id_desc"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["id"], reverse=True)
            elif (sortBy == "id_asc"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["id"], reverse=False)
            elif (sortBy == "newest_first"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["timestamp_created"], reverse=True)
            elif (sortBy == "oldest_first"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["timestamp_created"], reverse=False)
            elif (sortBy == "recently_modified"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["timestamp_finished"], reverse=True)
            elif (sortBy == "rating_desc"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["rating"], reverse=True)
            elif (sortBy == "rating_asc"):
                experimentListSorted = sorted(experimentList, key=lambda x: x["rating"], reverse=False)
            experimentList = experimentListSorted

            # Show the list of experiments in a table -- one row per experiment.  A button should exist for each experiment to view the details.
            tableData = [
                ["#", "Experiment", "Details"]
            ]

                # Example format
                # example1 = {
                #     'id': '1',
                #     'model_str': 'claude-3-5-sonnet-20241022',
                #     'experiment_name_short': 'Example 1',
                #     'experiment_description': 'This is a test experiment.',
                #     'codeblock_names_to_use': ['Logger/Debugging', 'OpenAI/Anthropic LLM Example', 'Together.ai LLM Example', 'Non-parametric Bootstrap Resampling'],
                #     'max_time_per_iteration_mins': 10,
                #     'max_debug_iterations': 5,
                #     'max_llm_cost_container': 1.00,
                #     'status': 'running',
                #     'num_iterations_run': 3,
                #     'cost_so_far': 0.50
                # }

            for idx in range(len(experimentList)):
                experiment = experimentList[idx]
                uuid = experiment["id"]
                name = experiment["experiment_name_short"]
                description = experiment["experiment_description"]
                status = experiment["status"]
                num_iterations_run = experiment["num_iterations_run"]
                cost_so_far = experiment["cost_so_far"]
                if (cost_so_far is not None):
                    cost_so_far = round(cost_so_far, 2)
                cost_build_debug = experiment.get("total_cost_build_debug", None)
                cost_llm_proxy = experiment.get("total_cost_llm_proxy", None)
                #results_summary = experiment.get("results_summary_short", "No results yet.")
                results_summary = experiment.get("results_summary", "No results yet.")
                timestamp_created = experiment.get("timestamp_created", None)
                timestamp_finished = experiment.get("timestamp_finished", None)
                experiment_path = experiment.get("experiment_path", None)
                runtime_seconds = experiment.get("runtime_seconds", None)
                runtime_minutes = None
                if (runtime_seconds is not None):
                    runtime_minutes = round(runtime_seconds / 60.0, 1)
                interesting_results = experiment.get("interesting_results", None)

                # Experiment path
                experiment_path = experiment.get("experiment_path", None)

                # Check to see if the idea was automatically generated, or whether the idea was manually input.
                ideaAutomaticOrManual = "Manually entered by human"
                if (experiment.get("idea_id", None) != None):
                    ideaAutomaticOrManual = "Automatically generated by ideator"

                # Follow-on experiment?
                follow_on_experiment = experiment.get("follow_on_experiment", False)
                follow_on_experiment_original_id = experiment.get("follow_on_to_experiment_id", None)
                follow_on_experiment_original_name = experiment.get("follow_on_to_experiment_name", None)
                followOnExperimentStr = ""
                if (follow_on_experiment):
                    followOnExperimentStr = f"<b>Follow-on:</b> Follow-on to `{follow_on_experiment_original_name}` (ID: {follow_on_experiment_original_id})<br>"

                # Only show the first 80 charaters of the description
                description_trimmed = description
                if (len(description) > 160):
                    description_trimmed = description[0:160] + " ... (trimmed)"

                # Additional metadata
                experiment_building_agent_name = experiment.get("experiment_building_agent_name", "")
                experiment_building_model = experiment.get("model_str", "")
                benchmark_name = experiment.get("benchmark", None)

                # Add color coding for the agent name
                if (experiment_building_agent_name == "simple1"):
                    experiment_building_agent_name = f"<span style=\"color: blue;\">{experiment_building_agent_name}</span>"
                elif (experiment_building_agent_name == "simple1-with-faithfulness-reflection"):
                    experiment_building_agent_name = f"<span style=\"color: purple;\">{experiment_building_agent_name}</span>"
                elif (experiment_building_agent_name == "planner1"):
                    experiment_building_agent_name = f"<span style=\"color: orange;\">{experiment_building_agent_name}</span>"


                # Add color coding for the models
                if (experiment_building_model == "claude-3-5-sonnet-20241022"):
                    experiment_building_model = f"<span style=\"color: darkblue;\">{experiment_building_model}</span>"
                elif (experiment_building_model == "o1-mini"):
                    experiment_building_model = f"<span style=\"color: SlateBlue;\">{experiment_building_model}</span>"
                elif (experiment_building_model == "deepseek/deepseek-reasoner"):
                    experiment_building_model = f"<span style=\"color: darkred;\">{experiment_building_model}</span>"

                # For the info, show the title, details, and template on separate lines with bold headers
                infoHtml = f"<b>Name:</b> {name}<br>"
                if (follow_on_experiment):
                    infoHtml += followOnExperimentStr
                if ("batch_name" in experiment):
                    infoHtml += f"<b>Batch Name:</b> {experiment['batch_name']}<br>"
                infoHtml += f"<b>Experiment Building Agent:</b> {experiment_building_agent_name}<br>"
                infoHtml += f"<b>Experiment Building Model:</b> {experiment_building_model}<br>"
                if (benchmark_name is not None):
                    infoHtml += f"<b>Benchmark:</b> {benchmark_name}<br>"
                else:
                    infoHtml += f"<b>Idea Type:</b> {ideaAutomaticOrManual}<br>"
                infoHtml += f"<b>Description:</b> {description_trimmed}<br>"
                # If the status includes the word "failed" in it, then color it red
                if ("failed" in status):
                    infoHtml += f"<b>Status:</b> <span style=\"color: red;\"> {status} </span><br>"
                else:
                    infoHtml += f"<b>Status:</b> {status}<br>"
                infoHtml += f"<b>Iterations Run:</b> {num_iterations_run}<br>"
                costExtendedStr = ""
                if (cost_build_debug is not None) or (cost_llm_proxy is not None):
                    costExtendedStr = "($" + str(round(cost_build_debug, 2)) + " Build/Debug + $" + str(round(cost_llm_proxy, 2)) + " LLM Proxy)"
                infoHtml += f"<b>Cost So Far:</b> ${cost_so_far} {costExtendedStr}<br>"
                infoHtml += f"<b>Time Created:</b> {timestamp_created}<br>"
                infoHtml += f"<b>Time Finished:</b> {timestamp_finished}<br>"
                if (runtime_minutes is not None):
                    infoHtml += f"<b>Runtime:</b> {runtime_minutes} minutes<br>"
                else:
                    infoHtml += f"<b>Runtime:</b> Unknown<br>"
                infoHtml += f"<b>Results Summary:</b> {results_summary}<br>"
                if (interesting_results is not None):
                    # If it's true, highlight it in green
                    if (interesting_results == True):
                        infoHtml += f"<b>Interesting Results:</b> <span style=\"color: green;\"> {interesting_results} </span><br>"
                    else:
                        infoHtml += f"<b>Interesting Results:</b> {interesting_results}<br>"

                # Experiment path (if it exists)
                experiment_path = experiment.get("experiment_path", None)
                if (experiment_path is not None):
                    infoHtml += f"<b>Experiment Path:</b> {experiment_path}<br>"

                # Determine what buttons are available
                showDetails = False
                showZIP = False
                showCodeAndResults = False
                showPDF = False
                pdfLink = ""
                showFollowOnExperimentButton = False

                # Check whether a ZIP file is likely available
                if (experiment_path is not None):
                    showZIP = True
                if (status == "completed"):
                    showCodeAndResults = True
                if (status == "completed") and (experiment_path is not None):
                    showPDF = True
                    #pdfLink = f"/pdfreport/{uuid}" # needs to be on the server
                    pdfLink = f"localhost:5001/pdfreport/{uuid}"
                if (status.startswith("completed") or status.startswith("failed") or status.startswith("interrupted")):
                    showFollowOnExperimentButton = True


                # Add the buttons
                buttons = []
                if (showDetails):
                    buttons.append(put_button("Details", onclick=lambda id=uuid: showExperimentDetails(id)))
                if (showZIP):
                    buttons.append(put_button("ZIP", onclick=lambda id=uuid: getExperimentZIP(id)))
                if (showCodeAndResults):
                    buttons.append(put_button("Code & Results", onclick=lambda id=uuid: showExperimentCodeAndResults(id)))
                if (showPDF):
                    buttons.append(put_button("PDF", onclick=lambda url=pdfLink: run_js(f'window.open("{url}", "_blank");')))
                if (showFollowOnExperimentButton):
                    buttons.append(put_button("Follow-On Exp.", onclick=lambda id=uuid: showFollowOnExperiment(id)))

                tableData.append([
                    str(uuid),
                    put_html(infoHtml),
                    style(put_column(buttons), "text-align: center;")
                ])

            # Show the table
            # Update the table content
            clear('experiment_table_container')
            with use_scope('experiment_table_container'):
                put_table(tableData)


        put_markdown ("## Experiment List")

        # Add sorting options
        put_row([
            put_text("Sort By: "),
            put_select('sort_by', options=[('ID (Ascending)', 'id_asc'),
                                           ('ID (Descending)', 'id_desc'),
                                           ("Recency (newest first)", 'newest_first'),
                                           ("Recency (oldest first)", 'oldest_first'),
                                           ("Recently Modified", 'recently_modified'),
                                           ("Rating (highest rated first)", 'rating_desc'),
                                           ("Rating (lowest rated first)", 'rating_asc')
                                           ], value='newest_first')
        ])

        pin_on_change("sort_by", onchange=lambda _:show_experiment_table(experimentList))

        # Show the default table
        show_experiment_table(experimentList)

    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


#
#   Show the details of a single experiment
#

def getExperimentZIP(uuid):
    run_js(f'window.location.href="/experimentzip/{uuid}";')

@app.route('/experimentzip/<uuid>', methods=['GET', 'POST'])
def _showExperimentZIP(uuid):
    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Experiment ZIP (" + str(uuid) + ")")

        put_markdown("Compressing experiment -- this may take a moment...")

        # Send a request to the server to get the ZIP file
        zip_file_path = None
        zip_file_size_mb = 0
        try:
            response = requests.post('http://localhost:5001/zipexperiment', json={"experiment_id": uuid})
            if response.status_code == 200:
                response_data = response.json()
                #put_markdown("## Server Response")
                #put_text(json.dumps(response_data, indent=2))
                zip_file_path = response_data.get("zip_file", None)
                zip_file_size_mb = response_data.get("zip_file_size_mb", None)
            else:
                put_text(f"Server returned an error: {response.status_code}")
                return
        except Exception as e:
            put_text(f"Error communicating with the server: {str(e)}")
            return

        if (zip_file_path is None):
            put_text("Error fetching ZIP file.  Is the back-end server running?")
            return

        zip_file_just_name = os.path.basename(zip_file_path)

        # Download the file
        content = open(zip_file_path, 'rb').read()
        put_file(zip_file_just_name, content, "Download `" + str(zip_file_just_name) + "`   (" + str(round(zip_file_size_mb, 2)) + " MB)")



    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


#
#   Show experiment code and results
#
def showExperimentCodeAndResults(uuid):
    run_js(f'window.location.href="/showexperimentcodeandresults/{uuid}";')

@app.route('/showexperimentcodeandresults/<uuid>', methods=['GET', 'POST'])
def _showExperimentCodeAndResults(uuid):
    # import config from pywebio
    from pywebio import config
    @config(js_file="https://cdn.jsdelivr.net/npm/prismjs@1.23.0/components/prism-diff.min.js")
    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Experiment Code and Results (" + str(uuid) + ")")

        put_markdown("Retrieving experiment -- this may take a moment...")
        experiment_details = None
        try:
            response = requests.post('http://localhost:5001/showexperimentcodeandresults', json={"experiment_id": uuid})
            if response.status_code == 200:
                response_data = response.json()
                experiment_details = response_data
            else:
                put_text(f"Server returned an error: {response.status_code}")
                return
        except Exception as e:
            put_text(f"Error communicating with the server: {str(e)}")
            return

        if (experiment_details is None):
            put_text("Error fetching experiment details.  Is the back-end server running?")
            return

        # Show the experiment details
    # response_data = {
    #     'instruction_str': instruction_str,
    #     'requirements': requirements,
    #     'code': code,
    #     'results': results,
    #     'llm_proxy_usage': llm_proxy_usage,
    #     'log': log
    # }

        # First, the experiment name (short)
        experiment_name_short = experiment_details.get("experiment_name_short", "No name provided.")
        put_markdown("## Experiment Name")
        put_text(experiment_name_short)

        # Instruction string
        instruction_str = experiment_details.get("instruction_str", "No instructions provided.")
        put_markdown("## Instructions")
        put_markdown(instruction_str)

        # Codeblock Names
        codeblock_names = experiment_details.get("codeblock_names", "No codeblocks provided.")
        put_markdown("## Codeblocks Included")
        if (type(codeblock_names) == list):
            codeblock_names = "\n".join(codeblock_names)
            put_code(codeblock_names)
        else:
            put_code(codeblock_names)

        # Requirements
        requirements = experiment_details.get("requirements", "No requirements provided.")
        put_markdown("## Requirements")
        put_code(requirements)

        # Code
        code = experiment_details.get("code", "No code provided.")
        put_markdown("## Code")
        put_code(code, language="python")

        # Results
        results = experiment_details.get("results", "No results provided.")
        if (type(results) != str):
            results = json.dumps(results, indent=4)
        put_markdown("## Results")
        put_code(results, language="json")

        # LLM Proxy Usage
        llm_proxy_usage = experiment_details.get("llm_proxy_usage", "No LLM Proxy usage provided.")
        if (type(llm_proxy_usage) != str):
            llm_proxy_usage = json.dumps(llm_proxy_usage, indent=4)
        put_markdown("## LLM Proxy Usage")
        put_code(llm_proxy_usage, language="json")

        # Log
        log = experiment_details.get("log", "No log provided.")
        if (type(log) != str):
            log = json.dumps(log, indent=4)
        put_markdown("## Log")
        put_code(log, language="json")

        # Change log
        change_log = experiment_details.get("change_log", "No change log provided.")
        if (type(change_log) != str):
            change_log = json.dumps(change_log, indent=4)
        put_markdown("## Change Log")
        put_code(change_log, language="json")

        # Costs
        # "cost_total": experimentTotalCost,
        # "cost_build_debug": experimentCostBuildDebug,
        # "cost_llm_proxy": experimentCostLLMProxy
        experimentTotalCost = experiment_details.get("cost_total", None)
        experimentCostBuildDebug = experiment_details.get("cost_build_debug", None)
        experimentCostLLMProxy = experiment_details.get("cost_llm_proxy", None)
        put_markdown("## Costs")
        if (experimentTotalCost is not None):
            experimentTotalCost = str(round(experimentTotalCost, 2))
            put_text(f"The total cost to run this experiment is estimated at: ${experimentTotalCost}")
        else:
            put_text("The total cost to run this experiment is not available.")
        if (experimentCostBuildDebug is not None):
            experimentCostBuildDebug = str(round(experimentCostBuildDebug, 2))
            put_text(f"The cost of building and debugging this experiment code is estimated at: ${experimentCostBuildDebug}")
        else:
            put_text("The cost of building and debugging this experiment code is not available.")
        if (experimentCostLLMProxy is not None):
            experimentCostLLMProxy = str(round(experimentCostLLMProxy, 2))
            put_text(f"If the experiment itself makes LLM calls, these are estimated to be at: ${experimentCostLLMProxy}")
        else:
            put_text("If the experiment itself makes LLM calls, these costs are not available.")

        # Runtime
        experimentRuntimeSeconds = experiment_details.get("runtime_seconds", None)
        put_markdown("## Runtime")
        if (experimentRuntimeSeconds is not None):
            experimentRuntimeMinutes = round(experimentRuntimeSeconds / 60.0, 1)
            experimentRuntimeSeconds = round(experimentRuntimeSeconds, 0)
            put_text(f"The experiment ran for approximately {experimentRuntimeMinutes} minutes ({experimentRuntimeSeconds} seconds).")
        else:
            put_text("The runtime of the experiment is not available.")

        # RAW: Show the whole response
        #put_markdown("## Server Response")
        #put_text(json.dumps(experiment_details, indent=2))



    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


def showExperimentDetails(uuid):
    # This function just redirects to the "/ideation" endpoint
    # Redirect to the /ideation endpoint
    run_js(f'window.location.href="/experiment/{uuid}";')

@app.route('/experiment/<uuid>', methods=['GET', 'POST'])
def _showExperimentDetails(uuid):
    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Experiment Details (" + str(uuid) + ")")

        put_markdown("This is a placeholder.")

    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


#
#   Paper List
#
def get_paper_list_from_server():
    # Request the list using the `getpaperlist` endpoint
    endpoint = "http://localhost:5001/getpaperlist"
    paper_list = []
    try:
        payload = {}         # Empty payload
        response = requests.get(endpoint, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            paper_list = response_data["paper_list"]
            return True, paper_list
        else:
            return False, paper_list
    except Exception as e:
        print("Exception occurred when trying to retrieve paper list (" + str(e) + ")")
        return False, paper_list


# Route: Show the ideation hub
def showPaperList():
    # This function just redirects to the "/ideation" endpoint
    # Redirect to the /ideation endpoint
    run_js('window.location.href="/paperlist";')

# Route: Show the papers available in the system
@app.route('/paperlist', methods=['GET', 'POST'])
def _showPaperList():
    MAX_TOTAL_PAPER_TOKEN_COUNT = 150000
    MAX_TOTAL_PAPER_TOKEN_COUNT_STR = str(int(round(MAX_TOTAL_PAPER_TOKEN_COUNT / 1000, 0))) + "k"

    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        # Papers
        put_markdown("# Paper List")
        put_text("Loading papers, this may take a moment...")
        put_loading('grow')  # Show loading spinner in the center

        time.sleep(0.5)
        success, paper_list = get_paper_list_from_server()
        if (not success):
            put_text("Error loading papers. Is the server running?")
            return


        # Sort, first by year, then by title
        paper_list.sort(key=lambda x: (x["year"], x["title"]), reverse=True)

        # Dynamically make table
        table = [
            ["#", "Sel.", "Paper ID", "Year", "Title", "Tokens", "Topic", "ArXiv Link"],
        ]

        pin_lut = {}
        for idx, paperRecord in enumerate(paper_list):
            # Arxiv URL
            arxiv_url = "https://arxiv.org/abs/" + paperRecord["arxiv_id"]
            # First author
            authorsStr = "(unknown authors)"
            if ("authors" in paperRecord) and (len(paperRecord["authors"]) > 0):
                authors_list = paperRecord["authors"]
                authorsStr = authors_list[0]
                if (len(authors_list) > 1):
                    authorsStr += " et al."
                authorsStr = "(" + authorsStr + ")"


            # Token Count
            token_count = "unknown"
            if ("source_token_count_estimate" in paperRecord) and (paperRecord["source_token_count_estimate"] is not None):
                token_count = str(int(round(paperRecord["source_token_count_estimate"] / 1000, 0))) + "k"
            # Selection box ID
            pin_id = "sel-" + str(paperRecord["arxiv_id"])
            # Remove any non-alphanumeric characters (including periods and spaces)
            pin_id = re.sub(r'\W+', '', pin_id)
            pin_lut[pin_id] = paperRecord

            # Generate table row
            topic = ", ".join(paperRecord.get("topics", ["unknown"]))
            table.append([
                str(idx),
                put_checkbox(label="", value=False, options=" ", name=pin_id),
                paperRecord["arxiv_id"],
                paperRecord["year"],
                paperRecord["title"] + "\n" + authorsStr,
                token_count,
                topic,
                #paperRecord["publication_date"],
                #put_html('<i class="fas fa-check-circle" style="color: #90EE90;"></i>') if paperRecord["graph_available"] else put_html('<i class="fas fa-times" style="color: grey;"></i>'),
                put_button("Arxiv", onclick=lambda url=arxiv_url: run_js(f'window.open("{url}", "_blank");'))

            ])

        # Loading complete, redraw the window
        clear()
        showHeader()

        put_markdown("# Paper List")

        def add_paper_dialog():
            # Clear()
            clear()
            showHeader()
            put_markdown("## Add Paper")
            put_markdown("Use this option if you want to add a new paper (from Arxiv) into the ideation system.")

            # Input box for the Arxiv ID
            put_markdown("### Arxiv ID")
            put_markdown("Enter the Arxiv ID of the paper you'd like to add (e.g. `2101.00001`).")
            put_markdown("(Note that URLs of the form `https://arxiv.org/abs/2101.00001` can also be used)")
            #arxiv_id = input("Arxiv ID", placeholder="2101.00001", required=True)
            # NOTE: Should be a form with 3 boxes: Arxiv ID (as above), a *selection box* for 'topic', and a text box for 'new topic'.
            possible_topics = ["agents", "theory-of-mind", "unknown"]
            form_values = input_group("Add Paper", [
                input("Arxiv ID", name='arxiv_id', placeholder="2101.00001", required=True),
                #input("Topic", name='topic', placeholder="Machine Learning", required=True),
                select("Topic", name='topic', options=possible_topics, value=possible_topics[-1]),
            ])


            def submit_add_paper(arxiv_id, topic):
                put_markdown("Recieved: `" + str(arxiv_id) + "`")
                sanitized_arxiv_id = arxiv_id.strip()
                # Check if this is a URL (i.e. contains 'arxiv.org')
                if ("arxiv.org" in sanitized_arxiv_id):
                    # Remove any trailing slashes
                    sanitized_arxiv_id = sanitized_arxiv_id.rstrip("/")
                    # Extract the Arxiv ID from the URL
                    url_parts = sanitized_arxiv_id.split("/")
                    # Get the last part
                    sanitized_arxiv_id = url_parts[-1]
                # Check if the Arxiv ID is valid
                if (not re.match(r'^\d{4}\.\d{4,5}$', sanitized_arxiv_id)):
                    put_markdown("The extracted ID (`" + str(sanitized_arxiv_id) + "`) does not appear to be a valid Arxiv ID (####.#### or ####.#####).  Please try again")
                    return

                put_markdown("User has requested to add paper with Arxiv ID: `" + str(sanitized_arxiv_id) + "`.")
                put_markdown("Processing request... (this may take a minute)")

                # Send request to server
                endpoint = "http://localhost:5001/addpaper"
                try:
                    payload = {"arxiv_paper_id": sanitized_arxiv_id, "topic": topic}
                    response = requests.post(endpoint, json=payload)
                    if response.status_code == 200:
                        response_data = response.json()
                        put_markdown("## Server Response")
                        #put_text(json.dumps(response_data, indent=2))
                        if ("success" in response_data) and (response_data["success"] == True):
                            put_html("<span style='color: green;'>Paper added successfully.</span>")

                            title = response_data.get("title", "Unknown Title")
                            put_markdown(f"**Title:** {title}")
                            year = response_data.get("year", "Unknown Year")
                            put_markdown(f"**Year:** {year}")
                            authors = response_data.get("authors", "Unknown Authors")
                            if (type(authors) == list):
                                put_markdown(f"**Authors:** {', '.join(authors)}")
                            else:
                                put_markdown(f"**Authors:** {authors}")

                            # Put raw response
                            put_markdown("### Raw Response")
                            put_text(json.dumps(response_data, indent=2))

                        else:
                            put_text("Error encountered when attempting to add paper.")
                            put_text(json.dumps(response_data, indent=2))

                    else:
                        put_text(f"Server returned an error: {response.status_code}")
                        # Print the raw response
                        put_text(json.dumps(response.json(), indent=2))
                except Exception as e:
                    put_text(f"Error communicating with the server: {str(e)}.  Is the back-end server running?")

                return
                # TODO: Submit request to server

            # Submit arxiv_id
            # Get the form values
            arxiv_id = form_values['arxiv_id']
            topic = form_values['topic']
            submit_add_paper(arxiv_id, topic)

            # # Submit button
            # put_buttons(['Add Paper'], onclick=lambda _: submit_add_paper(arxiv_id))


        put_markdown("## Add paper")
        put_markdown("Use this option if you want to add a new paper (from Arxiv) into the ideation system.")
        # Button
        put_buttons(['Add Paper'], onclick=lambda _: add_paper_dialog())



        def batch_ideation():
            # Add 3 fields: Model to use, number of ideas, and condition text.  Plus a button to start.
            batch_user_input = input_group("Idea Generation Parameters", [
                # add a selection box for the model to use
                select("Model to Use", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "claude-3-5-sonnet-20240620", "o1-2024-12-17", "o1-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"], value="claude-3-5-sonnet-20241022"),
                input("How many total ideas should be generated? (Max = 100)", name='num_ideas', type=NUMBER, placeholder="50", required=True, min_value=1, max_value=100),
                input("Maximum number of papers to use per idea?", name='num_papers_per_idea', type=NUMBER, placeholder="3", required=True, min_value=1, max_value=5),
                checkbox("Discourage generating ideas similar to existing ideas (i.e. reduce duplicates)", name='discourage_similar', options=['Enable Deduplication']),
                input("Condition ideation on a particular topic (optional, leave blank to not use)", name='condition_idea')
            ])

            # Get the form responses
            model_str = batch_user_input['model_str']
            num_ideas = batch_user_input['num_ideas']
            num_papers_per_idea = batch_user_input['num_papers_per_idea']
            discourage_similar = False
            if ("Enable Deduplication" in batch_user_input['discourage_similar']):
                discourage_similar = True
            condition_idea = batch_user_input['condition_idea']

            # Start generating ideas
            clear()
            showHeader()
            put_markdown("## Batch Ideation with Random Papers...")
            put_markdown("**Model to use:** " + model_str)
            put_markdown("**Number of ideas to generate:** " + str(num_ideas))
            put_markdown("**Maximum number of papers per idea:** " + str(num_papers_per_idea))
            put_markdown("**Discourage similar ideas:** " + str(discourage_similar))
            put_markdown("**Conditioning text:** " + str(condition_idea))

            put_markdown("## Starting Batch Ideation...")
            put_text("This process may take a few minutes...")
            IDEAS_PER_BATCH = 3
            MAX_TOTAL_PAPER_TOKENS = 150000
            import math
            num_batches_to_run = math.ceil(num_ideas / IDEAS_PER_BATCH)
            put_text(f"**Running {num_batches_to_run} batches of {IDEAS_PER_BATCH} ideas each...**")

            # Make a look-up table of paper IDs to token counts
            paper_ids = [paper["arxiv_id"] for paper in paper_list]
            paper_id_to_token_count = {}
            for paper in paper_list:
                paper_id_to_token_count[paper["arxiv_id"]] = paper["source_token_count_estimate"]

            # Initialize the random seed based off the current time
            random.seed(time.time())
            for i in range(num_batches_to_run):
                put_text(f"Batch {i+1} of {num_batches_to_run}...")
                time.sleep(1)
                # Randomly pick a starting paper
                iterations = 0
                while (iterations < 100):
                    starting_paper_id = random.choice(paper_ids)
                    starting_paper_token_count = paper_id_to_token_count[starting_paper_id]
                    if (starting_paper_token_count != None) and (starting_paper_token_count < MAX_TOTAL_PAPER_TOKENS):
                        break

                # If we couldn't find a paper with a low enough token count, continue the loop
                if (starting_paper_token_count >= MAX_TOTAL_PAPER_TOKENS):
                    put_text("Error: Could not find a starting paper with a low enough token count.")
                    continue

                # Now that we have a starting paper, try to add N-1 more papers to the list
                paper_ids_to_use = [starting_paper_id]
                total_token_count = starting_paper_token_count
                for j in range(num_papers_per_idea - 1):
                    iterations = 0
                    while (iterations < 100):
                        new_paper_id = random.choice(paper_ids)
                        new_paper_token_count = paper_id_to_token_count[new_paper_id]
                        if (new_paper_id not in paper_ids_to_use) and (new_paper_token_count != None) and (total_token_count + new_paper_token_count < MAX_TOTAL_PAPER_TOKENS):
                            paper_ids_to_use.append(new_paper_id)
                            total_token_count += new_paper_token_count
                            break
                        iterations += 1

                # If we reach here, we should have a list that contains between 1 and `num_papers_per_idea` papers.  We'll use this to generate ideas (it's OK if there are fewer than `num_papers_per_idea` papers)
                # Pack the payload
                payload = {
                    'selected_paper_ids': paper_ids_to_use,
                    'model_str': model_str,
                    'discourage_similar': discourage_similar,
                    'condition_idea_text': condition_idea,
                    'batch': True
                }

                # Send it to the server
                # Send POST request to the server
                try:
                    response = requests.post('http://localhost:5001/startideation', json=payload)
                    if response.status_code == 202:
                        response_data = response.json()
                        put_text(f"Submitted Batch {i+1} of {num_batches_to_run}...")
                    else:
                        put_text(f"Server returned an error when submitting batch: {response.status_code}")
                except Exception as e:
                    put_text(f"Error communicating with the server: {str(e)}")

            put_markdown("**Batch submission complete.**")


        put_markdown("## Batch Ideation with Random Papers")
        put_markdown("Use this option if you want to create a large number of ideas from randomly selected papers.")
        # Show a button for the batch ideator
        put_buttons(['Start Batch Ideation'], onclick=lambda _: batch_ideation())


        put_markdown("## Ideation from Existing Papers")
        put_markdown("Use this option if you want to create ideas based on specific papers (or combinations of papers).")
        put_markdown("**Instructions:** Please pick 1-5 papers to help condition the ideation process.  The total token count of the selected papers must be less than **" + str(MAX_TOTAL_PAPER_TOKEN_COUNT_STR) + "** tokens.  When complete, click the **Next** button at the bottom to continue.  You can also skip this step and use random papers by selecting the **Random** button.")

        # Show the table of papers
        put_table(table)

        # Get a list of all the selected papers
        def submitPaperSelection(pin_lut):
            ok_to_continue = False      #   A Flag marking whether the paper selection process is OK, and the user can continue onto the next step.

            # List all the pins and their values
            for key in pin_lut.keys():
                print(key + " = " + str(pin[key]))

            selected_papers = []
            for pin_id, paperRecord in pin_lut.items():
                if (pin[pin_id]):
                    selected_papers.append(paperRecord)

            #print("Selected papers:")
            put_markdown("## Selected Papers")
            total_token_count = 0
            num_selected_papers = len(selected_papers)

            if (num_selected_papers == 0):
                put_text("No papers selected.  You must select 1-5 papers to condition the ideation on.")

            else:
                for paper in selected_papers:
                    print(paper["arxiv_id"] + " - " + paper["title"])
                    #put_text(paper["arxiv_id"] + " - " + paper["title"])
                    token_count = paper["source_token_count_estimate"]
                    token_count_paper_str = "unknown"
                    if (token_count is not None):
                        total_token_count += token_count
                        token_count_paper_str = str(int(round(token_count / 1000, 0))) + "k"

                    # Add to a markdown list
                    put_markdown(f"- {paper['arxiv_id']} - {paper['title']} ({token_count_paper_str} tokens)")

                total_token_count_str = str(int(round(total_token_count / 1000, 0))) + "k"

                put_markdown("*Total token count:* " + str(total_token_count_str))
                if (total_token_count > MAX_TOTAL_PAPER_TOKEN_COUNT):
                    #put_markdown("Warning: The total token count of the selected papers is over the maximum of " + str(MAX_TOTAL_PAPER_TOKEN_COUNT) + " tokens.  Please select a different set of papers that sum to less than this amount.")
                    # Must use red text
                    put_html('<p style="color:red;"><b>Warning:</b> The total token count of the selected papers is over the maximum of <b>' + str(MAX_TOTAL_PAPER_TOKEN_COUNT_STR) + '</b> tokens.  Please select a different set of papers that sum to less than this amount.</p>')

                else:
                    ok_to_continue = True


            def handle_stage2_buttons(button_label):
                if button_label == 'Continue':
                    # Continue to the next stage
                    #showIdeation()
                    #put_markdown("TODO: Do the ideation")
                    # This is no longer used -- the input group below is used instead
                    pass
                elif button_label == 'Reset':
                    # Reset the selection
                    showPaperList()
                elif button_label == 'Take me to the ideation list':
                    #showIdeationList()
                    # TODO
                    put_markdown("TODO")

                elif button_label == 'Submit another ideation request':
                    showPaperList()

            # Add up to two buttons: "Continue" and "Reset"
            if (ok_to_continue):

                # Add the select box for model, and the text box for conditioning the ideation
                put_markdown("## Automatically Generate Ideas")


                # Use pin mode, so the widgets are non-blocking
                user_input = input_group("Idea Generation Parameters", [
                    # add a selection box for the model to use
                    select("Model to Use", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "claude-3-5-sonnet-20240620", "o1-2024-12-17", "o1-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"], value="claude-3-5-sonnet-20241022"),
                    checkbox("Discourage generating ideas similar to existing ideas (i.e. reduce duplicates)", name='discourage_similar', options=['Enable Deduplication']),
                    input("Condition ideation on a particular topic (optional, leave blank to not use)", name='condition_idea')
                ])

                # Get the form responses
                selected_paper_ids = []
                for paper in selected_papers:
                    if ("arxiv_id" in paper):
                        selected_paper_ids.append(paper["arxiv_id"])

                # Pack the payload
                payload = {
                    'selected_paper_ids': selected_paper_ids,
                    'model_str': user_input['model_str'],
                    'discourage_similar': user_input['discourage_similar'],
                    'condition_idea_text': user_input['condition_idea']
                }

                # Send it to the server
                # Send POST request to the server
                try:
                    response = requests.post('http://localhost:5001/startideation', json=payload)
                    if response.status_code == 202:
                        response_data = response.json()
                        put_markdown("## Server Response")
                        put_text(json.dumps(response_data, indent=2))
                        put_text("The ideation request has been added to the queue.  These usually take a few minutes to process.  Once completed, the new ideas will appear in the ideation list.")
                        #put_buttons(["Take me to the ideation list", "Submit another ideation request"], onclick=handle_stage2_buttons)
                        put_buttons(["Submit another ideation request"], onclick=handle_stage2_buttons)
                    else:
                        put_text(f"Server returned an error: {response.status_code}")
                except Exception as e:
                    put_text(f"Error communicating with the server: {str(e)}")


                #put_buttons(['Continue', 'Reset'], onclick=handle_stage2_buttons)
            else:
                put_buttons(['Reset'], onclick=handle_stage2_buttons)





        # Add a 'submit' button
        #put_buttons(['Next'], onclick=lambda _: submitPaperSelection(pin_lut))
        #put_buttons(["Randomly Pick Papers For Me"], onclick=lambda _: run_js('alert("TODO")'))
        def handle_click(button_label):
            if button_label == 'Next':
                put_markdown("Processing selections (this may take a moment...)")
                submitPaperSelection(pin_lut)
            elif button_label == 'Randomly Pick Papers For Me':
                # Put the loader in a scope, that can be cleared
                put_markdown("Randomly selecting papers (this may take a moment...)")

                # Randomly pick a number of papers from 4-5
                num_papers = random.randint(4, 5)
                max_iterations = 100
                cur_iteration = 0
                selected_papers = []
                done = False
                # First, set all the pins to False, in case the user has already selected some papers
                for pin_id in pin_lut.keys():
                    pin[pin_id] = []    # Set to an empty list to clear the checkbox

                # Try to randomly pick 3-5 papers that, together, sum to less than the token count.
                while (cur_iteration < max_iterations) and (not done):
                    cur_iteration += 1
                    selected_papers = []
                    total_token_count = 0

                    # Randomly pick `num_papers` paper indices
                    random_paper_indices = []
                    iterations = 0
                    while (len(random_paper_indices) < num_papers):
                        random_index = random.randint(0, len(paper_list) - 1)
                        if (random_index not in random_paper_indices):
                            random_paper_indices.append(random_index)

                        iterations += 1
                        if (iterations > 1000):
                            # Something terrible has happened -- exit the loop so we don't get stuck
                            put_markdown("ERROR: Random paper selection loop exceeded 1000 iterations.  This should never happen. Exiting.")
                            return

                    # If we reach here, we should have a set of unique paper indices. Now, see if, when combined, their token count is less than the maximum
                    failure = False
                    for random_index in random_paper_indices:
                        paper = paper_list[random_index]
                        token_count = paper["source_token_count_estimate"]
                        if (token_count is None):
                            # We shouldn't add papers with an unknown token count -- restart the loop
                            failure = True
                        else:
                            total_token_count += token_count

                    # If the total token count is less than the maximum, we're done
                    if (total_token_count <= MAX_TOTAL_PAPER_TOKEN_COUNT) and (not failure):
                        # Set the pins for the selected papers
                        for random_index in random_paper_indices:
                            pin_id = "sel-" + paper_list[random_index]["arxiv_id"]
                            # Sanitize the pin id
                            pin_id = re.sub(r'\W+', '', pin_id)
                            pin[pin_id] = [' ']   # Set to a list with a single space to check the checkbox
                            #put_markdown("Setting " + pin_id + " to True")
                            done = True

                # If we reach here, we've either found a set of papers that work, or we've exceeded the maximum number of iterations
                if (not done):
                    put_markdown("ERROR: Unable to find a set of papers that sum to less than the maximum token count after " + str(max_iterations) + " iterations.  Please try again.")

                # Now, submit the selection
                submitPaperSelection(pin_lut)


        # Add the buttons to submit the selection
        put_buttons(['Next', 'Randomly Pick Papers For Me'], onclick=handle_click)



    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


#
#   A Follow-on Experiment
#
# Route: Show the ideation hub
def showFollowOnExperiment(experiment_id):
    # This function just redirects to the "/ideation" endpoint
    # Redirect to the /ideation endpoint
    run_js('window.location.href="/followonexperiment/' + experiment_id + '";')

# Route: Show the papers available in the system
#@app.route('/follow', methods=['GET', 'POST'])
@app.route('/followonexperiment/<experiment_id>', methods=['GET', 'POST'])
def _showFollowOnExperiment(experiment_id):
    MAX_TOTAL_PAPER_TOKEN_COUNT = 150000
    MAX_TOTAL_PAPER_TOKEN_COUNT_STR = str(int(round(MAX_TOTAL_PAPER_TOKEN_COUNT / 1000, 0))) + "k"

    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        # Follow-on Experiment (Loading the experiment list)
        put_markdown("# Follow-On Experiment (" + str(experiment_id) + ")")
        put_text("Loading experiment list, this may take a moment...")
        put_loading('grow')  # Show loading spinner in the center

        # Get the experiments list from the server
        time.sleep(0.5)
        experiment_list = getExperimentList()
        if (experiment_list is None):
            put_text("Error loading experiment list. Is the server running?")
            return

        # Get a list of known codeblock names from the server
        knownCodeblockNames = getKnownCodeblockNames()
        if (knownCodeblockNames is None):
            put_text("Error fetching known codeblock names.  Is the back-end server running?")
            return
        # Sort the codeblock names alphabetically
        knownCodeblockNames = sorted(knownCodeblockNames)


        clear()
        # Header
        showHeader()

        put_markdown("# Follow-On Experiment (" + str(experiment_id) + ")")

        # Try to find the experiment in the list
        experiment = None
        for exp in experiment_list:
            if (exp["id"] == experiment_id):
                experiment = exp
                break

        if (experiment is None):
            #put_text("Error: Experiment with that ID (" + str(experiment_id) + ") not found.  This should never happen.")
            # Render in red text
            put_html('<p style="color:red;"><b>Error:</b> Experiment with that ID (' + str(experiment_id) + ') not found.  This should never happen.</p>')
            return


        def show_follow_on_experiment_form(existing_experiment_record, new_experiment_short_name):
            clear()
            #show_idea_details()
            put_markdown("## Follow-on Experiment Building Form")

            original_experiment_name_short = existing_experiment_record["experiment_name_short"]
            experiment_short_name = new_experiment_short_name
            experiment_prompt_str = existing_experiment_record["experiment_description"]
            experiment_codeblocks = existing_experiment_record["codeblock_names_to_use"]
            # Remove any codeblocks that are not in the known codeblocks list
            experiment_codeblocks = [x for x in experiment_codeblocks if x in knownCodeblockNames]

            # Get the parameters that were used when the original experiment was created
            model_str = existing_experiment_record["model_str"]
            max_time_per_iteration_mins = existing_experiment_record["max_time_per_iteration_mins"]
            max_time_per_iteration_pilot_mins = existing_experiment_record.get("max_time_per_iteration_pilot_mins", 10)
            #'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
            hard_runtime_cutoff_seconds = existing_experiment_record.get("hard_runtime_cutoff_seconds", 60*60*2)
            max_debug_iterations = existing_experiment_record["max_debug_iterations"]
            max_llm_cost_container = existing_experiment_record["max_llm_cost_container"]
            max_experiment_cost = existing_experiment_record.get("max_experiment_cost", 0.10)

            # TODO: Set the experiment_prompt_str to the experiment_prompt["prompt"]
            # TODO: Set the codeblock checks to the experiment_prompt["codeblocks"]

            # Make a form with the following fields:
            # Checkbox for discourage generating ideas similar to existing ideas
            # Text box for idea topic to condition on

            # Make a bright blue text
            put_html("<span style='color: pink;'>Please review the experiment prompt below, and make any desired edits.  Press 'Submit' to begin the experiment.</span>")

            user_input = input_group("Follow-on Experiment Parameters", [
                # add a selection box for the model to use
                select("Code Generation/Debugging Model to Use:", name='model_str', options=["claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219",  "gpt-4o-2024-11-20", "o1-2024-12-17", "o1-mini", "gpt-4o-mini", "deepseek/deepseek-reasoner", "openai/o3-mini-2025-01-31"], value=model_str),
                input("Give the experiment a short name (no spaces -- e.g. my-experiment-123):", name='experiment_name_short', value=experiment_short_name),
                input("This is a follow-on experiment to (static):", name='follow_on_to_experiment', value=original_experiment_name_short, disabled=True),
                textarea("Describe the original experiment in detail:", name='experiment_description', rows=12, value=experiment_prompt_str),
                textarea("Describe the changes in this follow-on experiment:", name='experiment_description_follow_on', rows=6, value=""),
                checkbox("Codeblocks to use:", name='codeblock_names_to_use', options=knownCodeblockNames, value=experiment_codeblocks),
                # What's the maximum time each iteration of the experiment should run for? (default 10 minutes)
                select("Maximum runtime per iteration for the PILOT (minutes):", name='max_time_per_iteration_pilot_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180, 60*4, 60*5, 60*6], value=max_time_per_iteration_pilot_mins),
                select("Maximum runtime per iteration in the normal case (minutes):", name='max_time_per_iteration_mins', options=[1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 120, 180, 60*4, 60*5, 60*6], value=max_time_per_iteration_mins),
                            #"max_time_per_iteration_pilot_mins": 15,
                select("Maximum (hard-limit) runtime for the entire series of experiments (hours):", name='hard_runtime_cutoff_hours', options=[0.05, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], value=6),
                # Maxium number of debug iterations (default 10)
                select("Maximum number of debug iterations:", name='max_debug_iterations', options=[5, 10, 15, 20, 25, 30], value=max_debug_iterations),
                # Maximum cost of any LLM calls the experiment makes
                select("Maximum cost of LLM calls within the experiment container, per iteration (USD):", name='max_llm_cost_container', options=[0.10, 0.25, 0.50, 1.0, 2.0, 5.0, 10.0], value=max_llm_cost_container),
                select("Maximum TOTAL COST of this experiment (hard limit) (USD):", name='max_experiment_cost', options=[0.10, 1.0, 5.0, 10.0, 15.0, 20.0, 25.0], value=max_experiment_cost),
                # Number of independent threads to try to build and run the experiment on
                select("Number of independent attempts to build and debug this experiment (spawns one thread per attempt; multiplies the cost linearly, but increases diversity/chance of success):", name='num_copies', options=[1, 2, 3, 4, 5], value=1)
            ])

            hard_runtime_cutoff_seconds = int(user_input['hard_runtime_cutoff_hours'] * 3600)

            # TODO: Handle submission
            # Prepare JSON payload
            payload = {
                'model_str': user_input['model_str'],
                'experiment_name_short': user_input['experiment_name_short'],
                'experiment_description': user_input['experiment_description'],
                'experiment_description_follow_on': user_input['experiment_description_follow_on'],
                'codeblock_names_to_use': user_input['codeblock_names_to_use'],
                'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
                'max_time_per_iteration_minipilot_mins': user_input['max_time_per_iteration_pilot_mins'],
                'hard_runtime_cutoff_seconds': hard_runtime_cutoff_seconds,
                'max_debug_iterations': user_input['max_debug_iterations'],
                'max_llm_cost_container': user_input['max_llm_cost_container'],
                'max_experiment_cost': user_input['max_experiment_cost'],
                'num_copies': user_input['num_copies'],
                'submission_mode': 'automatic',
                'follow_on_to_experiment_id': existing_experiment_record["id"],
                'follow_on_to_experiment_name': existing_experiment_record["experiment_name_short"]                ,
                'idea_id': existing_experiment_record.get("idea_id", None),
                'original_idea': existing_experiment_record.get("original_idea", None),
                'automatically_generated_experiment_prompt': existing_experiment_record.get("automatically_generated_experiment_prompt", None),
                'follow_on_experiment': True
            }

            # Send POST request to the server
            try:
                response = requests.post('http://localhost:5001/startfollowonexperiment1', json=payload)
                if response.status_code == 202:
                    response_data = response.json()
                    # Print an 'experiment confirmed' message in green
                    put_markdown("## Experiment Submitted")
                    put_html("<span style='color: green;'>Experiment submitted.  The experiment has been added to the queue.  You can the experiment in the experiment list.</span>")

                    put_markdown("## Server Response")
                    put_text(json.dumps(response_data, indent=2))

                else:
                    put_text(f"Server returned an error: {response.status_code}")
            except Exception as e:
                put_text(f"Error communicating with the server: {str(e)}")



        # Find a unique name for this follow-on experiment
        current_experiment_name = experiment['experiment_name_short']
        follow_on_experiment_name = None
        # Get a list of existing experiment names
        existing_experiment_names = []
        for exp in experiment_list:
            existing_experiment_names.append(exp["experiment_name_short"])
        # Add 'followon<index>' to the current experiment name
        for i in range(1, 10000):
            follow_on_experiment_name = current_experiment_name + "-followon" + str(i)
            if (follow_on_experiment_name not in existing_experiment_names):
                break
            # TODO: add check for exceeding range

        # Show the follow-on experiment form
        show_follow_on_experiment_form(existing_experiment_record=experiment, new_experiment_short_name=follow_on_experiment_name)

        return


    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response




#
#   Ideation List
#

# Get a list of ideas from the server
def get_ideas_list_from_server():
    # Request the list using the `getidealist` endpoint
    endpoint = "http://localhost:5001/getidealist"
    idea_list = []
    try:
        payload = {}         # Empty payload
        response = requests.get(endpoint, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            idea_list = response_data["idea_list"]
            return True, idea_list
        else:
            return False, idea_list
    except Exception as e:
        print("Exception occurred when trying to retrieve ideation list (" + str(e) + ")")
        return False, idea_list

def get_idea_by_id_from_server(id:str):
    # Request a single idea using the `getidea` endpoint
    endpoint = "http://localhost:5001/getidea/" + str(id)
    idea = None
    try:
        payload = {}         # Empty payload
        response = requests.get(endpoint, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            idea = response_data["idea"]
            return True, idea
        else:
            return False, idea
    except Exception as e:
        print("Exception occurred when trying to retrieve ideation list (" + str(e) + ")")
        return False, idea


#Use this endpoint: @app.route('/convertideatoexperimentprompt/<id>', methods=['GET'])
def convert_idea_to_experiment_prompt_server(id:str):
    # Request the server to convert an idea to an experiment prompt
    endpoint = "http://localhost:5001/convertideatoexperimentprompt/" + str(id)
    experiment_prompt = None
    try:
        payload = {}         # Empty payload
        response = requests.get(endpoint, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            success = response_data["success"]
            if (success):
                experiment_prompt = response_data
                return True, experiment_prompt
            else:
                return False, None
        else:
            return False, None
    except Exception as e:
        print("Exception occurred when trying to convert idea to experimet prompt (" + str(e))
        return False, None





def showIdeationList():
    # This function just redirects to the "/ideation" endpoint
    # Redirect to the /ideation endpoint
    run_js(f'window.location.href="/ideationlist";')

@app.route('/ideationlist', methods=['GET', 'POST'])
def _showIdeation():
    def pywebio_show():
        # Inject JavaScript to reload the page when navigating back (otherwise table doesn't populate)
        run_js(""" window.onpageshow = function(event) { if (event.persisted) { window.location.reload() } }; """)

        # Clear the output
        clear()

        # Header
        showHeader()

        # Ideation
        put_markdown("# Ideation List")

        # Loading the ideation data
        put_markdown("Loading ideation data, this may take a moment...")
        put_loading('grow')  # Show loading spinner in the center

        # Retrieve a list of ideas from the server
        success, idea_list = get_ideas_list_from_server()

        if (not success):
            put_text("Error loading ideation data. Is the server running?")
            return

        # Sort the list by timestamp
        idea_list.sort(key=lambda x: x["date_generated"], reverse=True)

        # Clear the output
        clear()

        # # Make a table with two buttons/two options: Automatic and Manual
        # put_table([
        #     ["", "Option"],
        #     #[put_button("Automatic", onclick=generateIdeasAutomatically), "Generate new ideas automatically."],
        #     [put_button("Automatic", onclick=showIdeationAutomaticGeneration), "Generate new ideas automatically."],
        #     [put_button("Manual", onclick=makeNewIdeaManually), "Manually enter an idea."]
        # ])
        showHeader()

        put_markdown("# Ideation List")

        # Show task queue
        showQueueStatus()


        def show_idea_table():
            # def show_rating_popup(id):
            #     # TODO
            #     put_text("TODO: Show rating popup for idea " + str(id))


            sortBy = pin.sort_by

            tableData = [
                ["#", "Idea", "Actions"]
            ]

            # Main keys:
            # id
            # research_idea_name
            # research_idea_long_description
            # research_idea_short_description
            # research_idea_hypothesis
            # research_idea_variables
            # research_idea_metric
            # research_idea_pilot
            # research_idea_design_prompt
            # research_idea_codeblocks
            # date_generated
            # inspiring_paper_ids
            # generated_using_model


            # Perform any sorting
            idea_list_sorted = idea_list
            # Go through and add a numerical ID
            for idx, idea in enumerate(idea_list_sorted):
                numerical_id = 0
                try:
                    #numerical_id = int(idea["id"].replace("idea-", "").replace("-", ""))
                    # Get everything after first dash
                    numerical_id = int(idea["id"].split("-", 1)[1])
                except:
                    pass
                idea["numerical_id"] = numerical_id

            if (sortBy == "id_desc"):
                idea_list_sorted = sorted(idea_list, key=lambda x: x["numerical_id"], reverse=True)
            elif (sortBy == "id_asc"):
                idea_list_sorted = sorted(idea_list, key=lambda x: x["numerical_id"], reverse=False)
            elif (sortBy == "newest_first"):
                idea_list_sorted = sorted(idea_list, key=lambda x: x["date_generated"], reverse=True)
            elif (sortBy == "oldest_first"):
                idea_list_sorted = sorted(idea_list, key=lambda x: x["date_generated"], reverse=False)
            elif (sortBy == "recently_modified"):
                idea_list_sorted = sorted(idea_list, key=lambda x: x["date_generated"], reverse=True)
            # TODO: Currently no rating
            # elif (sortBy == "rating_desc"):
            #     idea_list_sorted = sorted(idea_list, key=lambda x: x["rating"], reverse=True)
            # elif (sortBy == "rating_asc"):
            #     idea_list_sorted = sorted(idea_list, key=lambda x: x["rating"], reverse=False)


            # For each idea, show the title, details, and template
            for idea in idea_list_sorted:
                id = idea["id"]
                name = idea["research_idea_name"]
                description = idea["research_idea_long_description"]
                prompt_example = idea["research_idea_design_prompt"]
                date_generated = idea["date_generated"]

                #link = ""
                # Details button should link to this endpoint: @app.route('/ideationspecific/<uuid>')
                link_for_creating_experiment = f"/newexperimentfromidea/{id}"      # TODO

                # For the info, show the title, details, and template on separate lines with bold headers
                infoHtml = f"<b>Name:</b> {name}<br>"
                infoHtml += f"<b>Description:</b> {description}<br>"
                infoHtml += f"<b>Prompt Example:</b> {prompt_example}<br>"

                # The rating is an integer between -2 and 5.
                # Make a string of dots to represent the rating.
                # Number = # of dots
                # Value = more green.  Negative = more red.
                idea["rating"] = 0      ## TODO: Replace this with the actual rating

                dotStr = ""
                for i in range(0, abs(idea['rating'])):
                    if (idea['rating'] > 0):
                        dotStr += '<span style="color: green;">&#9679;</span>'
                    elif (idea['rating'] < 0):
                        dotStr += '<span style="color: red;">&#9679;</span>'

                if (idea['rating'] > 0):
                    infoHtml += f"<b>Rating:</b> {idea['rating']} {dotStr} <br>"
                elif (idea['rating'] < 0):
                    infoHtml += f"<b>Rating:</b> {idea['rating']} {dotStr} <br>"
                else:
                    # Add a neutral arrow
                    #infoHtml += f"<b>Rating:</b> {idea['rating']} <i class='fas fa-arrow-right' style='color: grey;'></i><br>"
                    # Add a question mark instead
                    infoHtml += f"<b>Rating:</b> {idea['rating']} <i class='fas fa-question' style='color: grey;'></i><br>"

                # Batch
                if ("batch_name" in idea) and (idea["batch_name"] is not None):
                    infoHtml += f"<b>Batch:</b> {idea['batch_name']}<br>"

                # Last modified timestamp
                infoHtml += f"<b>Date Generated:</b> {date_generated}<br>"



                tableData.append([
                    str(id),
                    put_html(infoHtml),
                    #put_button("Details", onclick=None)
                    style(put_column([
                        put_button("Run Experiment", onclick=lambda url=link_for_creating_experiment: run_js(f'window.open("{url}", "_blank");')),
                        #put_button("Rate", onclick=lambda id=id: show_rating_popup(id))
                    ]), "text-align: center;")
                ])


            # Show the table
            # Update the table content
            clear('idea_table_container')
            with use_scope('idea_table_container'):
                put_table(tableData)


        #put_markdown ("## Previously Generated Ideas")

        # Add sorting options
        put_row([
            put_text("Sort By: "),
            put_select('sort_by', options=[('ID (Ascending)', 'id_asc'),
                                           ('ID (Descending)', 'id_desc'),
                                           ("Recency (newest first)", 'newest_first'),
                                           ("Recency (oldest first)", 'oldest_first'),
                                           ("Recently Modified", 'recently_modified'),
                                           ("Rating (highest rated first)", 'rating_desc'),
                                           ("Rating (lowest rated first)", 'rating_asc')
                                           ], value='id_desc')
        ])

        pin_on_change("sort_by", onchange=lambda _:show_idea_table())

        # Show the default table
        show_idea_table()



    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response









#
#   Web server main
#
@app.route('/', methods=['GET', 'POST'])
def pywebio_app():
    def pywebio_show():
        # Clear the output
        clear()

        # Header
        showHeader()

        put_markdown("# Main Menu")

        # Show the main dashboard functions
        put_table([
            #["", "Function"],
            ["", ""],
            [put_button("Create New Ideas (From Papers)", onclick=showPaperList), "Create new experiment ideas from existing papers."],
            [put_button("Create New Experiment (Manual)", onclick=showCreateExperimentManual), "Manually Creating a New Experiment"],
            [put_button("Ideation List", onclick=showIdeationList), "A list of experiment ideas that have been generated."],
            [put_button("Experiment Monitor", onclick=showExperimentList), "Show all current and past experiments."],
            [put_button("Batch Autonomous Experiments", onclick=showBatchAutonomousExperiments), "Run batch autonomous experiments."],
            [put_button("Run Benchmark", onclick=showRunBenchmark), "Run pre-defined benchmark."],
            [put_button("Meta-Analysis", onclick=showMetaAnalysis), "Meta-Analysis/Bulk Results Export (to TSV)"],
            [put_button("Status", onclick=showStatus), "Show the status of the system."]
        ])

    # Show the app, no caching so the back button works
    # Get the response from webio_view
    response = webio_view(pywebio_show)()

    # The code below forces the page to not cache, and to reload the page every time, so that the back button in the browser works correctly.
    # Check if the response is a Flask Response object
    if not isinstance(response, Response):
        response = make_response(response)

    # Set cache control headers to prevent caching
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


# Parse arguments
def parse_args():
    desc = "Launch a webserver to interact with CodeScientist from your browser."
    parser = argparse.ArgumentParser(desc)
    parser.add_argument("--port", type=int, default=8080,
                        help="Port to use for the webserver.")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Host to bind the webserver to. 0.0.0.0 for all interfaces.")
#    parser.add_argument("--debug", action="store_true",
#                        help="Run webserver in debug mode.")

    return parser.parse_args()



app.add_url_rule('/', 'webio_view', webio_view(pywebio_app), methods=['GET', 'POST', 'OPTIONS'])

if __name__ == '__main__':
    args = parse_args()
    #pywebio.start_server(app, port=args.port)
    app.run(port=args.port, host=args.host, debug=False)
