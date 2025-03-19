# ExperimentWebServer.py
# Copy/pasted from the DiscoveryKnowledgeGraph -- needs adapting.

import json
from flask import Flask, request, jsonify
import threading
import random
import queue
import time
import sys

from concurrent.futures import ThreadPoolExecutor, as_completed

from datetime import datetime
from tqdm import tqdm

from ExtractionUtils import *

# CodeblockStore
from CodeBlockStore import *
from ExperimentMaker import *

# PaperStore
from PaperStore import *
# IdeaStore
from IdeaStore import *
# MetaAnalysis
from MetaAnalysis import *

# Critical stop thread event
EVENT_CRITICAL_STOP = threading.Event()

# Flash app
app = Flask(__name__)

# Global task queue
taskQueue = queue.Queue()

# Lock for shared resources (if needed)
resource_lock = threading.Lock()
CURRENT_TASK_BEING_PROCESSED = None     # Reference to the current task being processed

# Codeblock store path
PATH_CODEBLOCKS = "codeblocks/"

# Filenames (NEW)
FILENAME_PROCESSED_TASKS = "data/processedTasks.json"         # The list of processed tasks (with time/cost information)
FILENAME_EXPERIMENTS = "data/all-experiments.json"
FILENAME_METAANALYSIS_LIST = "data/metaanalysis-list.json"    # List of meta-analyses

# Thread locks
THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON = threading.Lock()
THREAD_LOCK_FILE_METAANALYSIS_JSON = threading.Lock()


# Experiment Threads
DEFAULT_MAX_EXPERIMENT_THREADS = 5
MAX_EXPERIMENT_THREADS = DEFAULT_MAX_EXPERIMENT_THREADS     # Now dynamically controllable from a file (`config_threads.json`)
THREAD_LOCK_EXPERIMENT_WORKERS = threading.Lock()
worker_thread_count = {"experiment_threads": 0}


# Constants (experiment statuses)
STATUS_CREATED      = "created"
STATUS_RUNNING      = "running"
STATUS_COMPLETED    = "completed"
STATUS_FAILED       = "failed (generic)"
STATUS_FAILED_TO_CREATE             = "failed to create"
STATUS_FAILED_TO_CREATE_UNKNOWN_BUILDER = "failed to create (unknown experiment building agent)"
STATUS_FAILED_TO_CREATE_FOLLOW_ON   = "failed to create (follow-on experiment)"
STATUS_INTERRUPTED                  = "interrupted"
STATUS_FAILED_TOO_MANY_ITERATIONS   = "failed (too many debug iterations)"
STATUS_FAILED_COST_LIMIT            = "failed (cost limit exceeded)"
STATUS_FAILED_CONTAINER_ERROR       = "failed (container error)"
STATUS_FAILED_FILEIO                = "failed (file I/O error)"
STATUS_FAILED_WORKER_EXCEPTION      = "failed (generic error in worker thread)"
STATUS_FAILED_AFTER_RUNNING         = "failed (after running)"
STATUS_CODE_COMPLETE_CRITICAL_ERROR = "failed (partial code generated)"
STATUS_CODE_PARSING_ISSUE           = "failed (code parsing issue)"
STATUS_HARD_RUNTIME_LIMIT_REACHED   = "failed (hard experiment runtime limit reached)"


#
#   Tasks
#


# Randomly select up to N papers from the paper list (whose total token count is less than MAX_TOTAL_PAPER_TOKENS)
def randomly_select_n_papers(max_paper_count:int, MAX_TOTAL_PAPER_TOKENS:int=100000):
    # Step 1: Get a list of papers and their token counts
    paper_list = get_papers_local()

    # Make a look-up table of paper IDs to token counts
    paper_ids = [paper["arxiv_id"] for paper in paper_list]
    paper_id_to_token_count = {}
    for paper in paper_list:
        paper_id_to_token_count[paper["arxiv_id"]] = paper["source_token_count_estimate"]

    # Initialize the random seed based off the current time
    random.seed(time.time())

    # Randomly pick a starting paper
    iterations = 0
    while (iterations < 1000):
        starting_paper_id = random.choice(paper_ids)
        starting_paper_token_count = paper_id_to_token_count[starting_paper_id]
        if (starting_paper_token_count != None) and (starting_paper_token_count < MAX_TOTAL_PAPER_TOKENS):
            break

    # If we couldn't find a paper with a low enough token count, continue the loop
    if (starting_paper_token_count >= MAX_TOTAL_PAPER_TOKENS):
        print("ERROR: randomly_select_n_papers(): Could not find a starting paper with a low enough token count.")
        return None

    # Now that we have a starting paper, try to add N-1 more papers to the list
    num_papers_per_idea = random.randint(1, max_paper_count)
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

    # If we reach here, we should have a list that contains between 1 and `max_paper_count` papers.
    return paper_ids_to_use


def task_do_autonomous_experiment_minibatch(payload:dict):
    # TODO
    from datetime import datetime       # No idea why it's not importing from the top correctly
    startTime = datetime.now()
    totalCost = 0

    print("#######")
    print("Starting one mini-batch of autonomous experimentation.")
    print("#######")

    # Parse the payload
            # From the code that originally packed it:
            # payload = {
            #     'model_str': user_input['model_str'],
            #     'batch_name_short': batch_name_short,
            #     'condition_idea_text': user_input['condition_idea_text'],
            #     'experiment_additional_operationalization_instructions': user_input['experiment_additional_operationalization_instructions'],
            #     'max_papers_per_idea': user_input['max_papers_per_idea'],
            #     'discourage_similar_ideas': user_input['discourage_similar_ideas'],
            #     'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
            #     'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
            #     'max_debug_iterations': user_input['max_debug_iterations'],
            #     'max_llm_cost_container': user_input['max_llm_cost_container'],
            #     'max_experiment_cost': user_input['max_experiment_cost'],
            #     'num_experiments': user_input['num_experiments'],
            # }

    # TODO: Unpack
    max_papers_per_idea = payload.get("max_papers_per_idea", 3)
    experiment_additional_operationalization_instructions = payload.get("experiment_additional_operationalization_instructions", "")
    if (len(experiment_additional_operationalization_instructions) <= 2):
        experimexperiment_additional_operationalization_instructions = None


    # Step 1: Generate 3 ideas from randomly selected papers
    ideation_payload = {}
                # From the code that originally packs it:
                # payload = {
                #     'selected_paper_ids': paper_ids_to_use,
                #     'model_str': model_str,
                #     'discourage_similar': discourage_similar,
                #     'condition_idea_text': condition_idea,
                #     'batch': True
                # }
    ideation_payload["model_str"] = payload.get("model_str", None)
    ideation_payload["discourage_similar"] = payload.get("discourage_similar_ideas", [])            # TODO: Need to enable this JUST FOR IDEAS WITHIN THIS SAME BATCH NAME
    ideation_payload["condition_idea_text"] = payload.get("condition_idea_text", "")                # TODO: Need to test this.
    ideation_payload["batch"] = True
    ideation_payload["batch_name"] = payload.get("batch_name_short", None)

    # Some models have reduced input token limits
    max_tokens_papers = 100000
    ideation_model_str = ideation_payload.get("model_str", None)
    if (ideation_model_str.lower().startswith("deepseek/deepseek-reasoner")):
        max_tokens_papers = 50000

    randomly_selected_papers = randomly_select_n_papers(max_paper_count=max_papers_per_idea, MAX_TOTAL_PAPER_TOKENS=max_tokens_papers)
    if (randomly_selected_papers is None):
        print("ERROR: Autonomous Experiment Minibatch: Could not randomly select papers.")
        return {"success": False, "error": "Could not randomly select papers.", "time_seconds": datetime.now() - startTime, "total_cost": totalCost}
    ideation_payload["selected_paper_ids"] = randomly_selected_papers

    ideation_result = task_create_new_ideas(ideation_payload)       # Actually create the new ideas

    totalCost += ideation_result.get("total_cost", 0)
    if (ideation_result.get("success", False) == False):
        # Failed to generate ideas
        print("ERROR: Autonomous Experiment Minibatch: Failed to generate ideas.  Exiting early.")
        return {"success": False, "error": "Failed to generate ideas.", "time_seconds": datetime.now() - startTime, "total_cost": totalCost}

    idea_ids = ideation_result.get("idea_ids", [])
    if (len(idea_ids) == 0):
        print("ERROR: Autonomous Experiment Minibatch: No ideas were generated.  Exiting early.")
        return {"success": False, "error": "No ideas were generated.", "time_seconds": datetime.now() - startTime, "total_cost": totalCost}

    print("Generated ideas: " + str(idea_ids))


    # Step 2: Operationalize the ideas/turn them into experiment prompts with the experiment maker.  (This needs to be conditioned on the `experiment_additional_operationalization_instructions`)
    # Get the IdeaStore
    ideaStore = IdeaStore()

    experiments_to_submit = []
    for idx, idea_id in enumerate(idea_ids):
        # Get the list of ideas
        idea_conversion_model_str = "claude-3-5-sonnet-20241022"
        idea = ideaStore.get_idea_by_id(idea_id)
        if (idea is None):
            print("ERROR: Autonomous Experiment Minibatch: Could not find idea with ID: " + str(idea_id) + ".  Skipping.")
            continue

        # Convert the idea to an experiment prompt
        experiment_prompt = ideaStore.convert_idea_to_experiment_prompt(idea, idea_conversion_model_str, extra_conditioning_text=experiment_additional_operationalization_instructions)
        totalCost += experiment_prompt.get("cost", 0)
        success = False
        if (experiment_prompt is not None) and ("success" in experiment_prompt) and (experiment_prompt["success"] == True):
            success = True
        else:
            print("ERROR: Autonomous Experiment Minibatch: Could not convert idea to experiment prompt.  Skipping.")
            continue

        # Extract experiment prompt, and list of codeblocks
        experiment_builder_prompt = experiment_prompt.get("prompt", None)
        codeblocks = experiment_prompt.get("codeblocks", [])

        # ALWAYS enable the debugger/logger, if it's not already enabled.
        if ("Logger/Debugging" not in codeblocks):
            codeblocks.append("Logger/Debugging")

        # Make sure the experiment prompt is not None, and that the codeblocks are not empty
        if (experiment_builder_prompt is None) or (len(codeblocks) == 0):
            print("ERROR: Autonomous Experiment Minibatch: The experiment builder prompt was empty, or the codeblocks were empty.  Skipping.")
            continue

        # Add this experiment to the list of experiments to submit
        packed = {
            "idea_id": idea_id,
            "idea": idea,
            "experiment_prompt": experiment_builder_prompt,
            "codeblocks": codeblocks,
        }
        experiments_to_submit.append(packed)

    # DEBUG: Save file with the experiment prompts
    print("Writing `debug.experiments_to_submit.json` with the experiments to submit...")
    with open("debug.experiments_to_submit.json", "w") as f:
        json.dump(experiments_to_submit, f, indent=4)

    # Step 3: Submit the 3 experiments to run.
            # Original payload for `startnewexperiment1`:
            # payload = {
            #     'model_str': user_input['model_str'],
            #     'experiment_name_short': user_input['experiment_name_short'],
            #     'experiment_description': user_input['experiment_description'],
            #     'codeblock_names_to_use': user_input['codeblock_names_to_use'],
            #     'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
            #     'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
            #     'max_debug_iterations': user_input['max_debug_iterations'],
            #     'max_llm_cost_container': user_input['max_llm_cost_container'],
            #     'num_copies': user_input['num_copies'],
            #     'submission_mode': 'automatic',
            #     'idea_id': idea_id,
            #     'original_idea': idea,
            #     'automatically_generated_experiment_prompt': experiment_prompt
            # }

    # Submit the experiments
    numSubmittedExperiments = 0
    for idx in range(0, len(experiments_to_submit)):
        idea_id = experiments_to_submit[idx]["idea_id"]
        idea = experiments_to_submit[idx]["idea"]
        experiment_prompt = experiments_to_submit[idx]["experiment_prompt"]
        codeblock_names_to_use = experiments_to_submit[idx]["codeblocks"]

        # Create the experiment description
        experiment_description = experiment_prompt

        # Get the maximum experiment cost from the payload
        max_experiment_cost = payload.get("max_experiment_cost", 0.00)      # If not found, default to zero (so it will at least exit quickly)

        experiment_submission_packed = {
            "model_str": payload.get("model_str", None),
            "experiment_name_short": idea.get("research_idea_name", "Unknown"),
            "experiment_description": experiment_description,
            "codeblock_names_to_use": codeblock_names_to_use,
            "max_time_per_iteration_mins": payload.get("max_time_per_iteration_mins", 1),
            "max_time_per_iteration_pilot_mins": payload.get("max_time_per_iteration_pilot_mins", 1),
            "max_debug_iterations": payload.get("max_debug_iterations", 1),
            "max_llm_cost_container": payload.get("max_llm_cost_container", 0.00),
            "num_copies": payload.get("num_experiments", 1),
            "submission_mode": "automatic",
            "idea_id": idea_id,
            "original_idea": idea,
            "automatically_generated_experiment_prompt": experiment_prompt,
            "max_experiment_cost": max_experiment_cost,
            "batch_name": payload.get("batch_name_short", None)
        }

        # Submit the experiment
        experiment_submission_result = task_start_new_experiment(experiment_submission_packed)
        if (experiment_submission_result.get("success", False) == False):
            print("ERROR: Autonomous Experiment Minibatch: Failed to submit experiment for idea ID: " + str(idea_id))
            continue
        else:
            numSubmittedExperiments += 1

    print("Submitted " + str(numSubmittedExperiments) + " experiments.")

    # Return
    deltaTime = datetime.now() - startTime
    result = {
        "success": True,
        "time_seconds": deltaTime.total_seconds(),
        "total_cost": totalCost
    }
    return result


def get_unique_experiment_id(experiments_data:dict):
    import random
    new_experiment_id = str(random.randint(1000, 999999999999))
    print("get_unique_experiment_id(): Started generating unique ID... ")
    existing_experiment_ids = set()

    # Add the new experiment to the list of experiments
    if ("experiment_list" not in experiments_data):
        # Error
        print("get_unique_experiment_id(): ERROR: Could not find 'experiment_list' in experiments data.")
        #return {"success": False, "error": "Could not find 'experiment_list' in experiments data."}
    else:
        for experiment in experiments_data["experiment_list"]:
            if ("id" in experiment):
                existing_experiment_ids.add(experiment["id"])

        # Keep generating a new experiment ID until it's unique
        while (new_experiment_id in existing_experiment_ids):
            new_experiment_id = str(random.randint(1000, 999999999999))

    print("get_unique_experiment_id(): Generated unique ID: " + str(new_experiment_id) + " (" + str(len(existing_experiment_ids)) + " existing experiments)")
    return new_experiment_id

# A check function to ensure that the experiment ID is unique
def is_experiment_id_unique(experiment_id:str, experiments_data:dict):
    existing_experiment_ids = []
    count = 0

    # Add the new experiment to the list of experiments
    if ("experiment_list" not in experiments_data):
        # Error
        print("ensure_experiment_id_unique(): ERROR: Could not find 'experiment_list' in experiments data.")
        return False
    else:
        for experiment in experiments_data["experiment_list"]:
            if ("id" in experiment):
                existing_experiment_ids.append(experiment["id"])

    # Check if the experiment ID is in the list of existing experiment IDs
    # Count how many times we see the experiment ID
    for existing_id in existing_experiment_ids:
        if (existing_id == experiment_id):
            count += 1

    if (count > 1):
        print("ensure_experiment_id_unique(): ERROR: Experiment ID is not unique: " + str(experiment_id))
        return False

    # If we reach here, the experiment ID is unique
    print("ensure_experiment_id_unique(): Experiment ID is unique: " + str(experiment_id))
    return True


# A check to ensure all experiment IDs are unique
# Should likely only be run once, at the start (since it hits the THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON)
def ensure_all_experiment_ids_unique():
    print("ensure_all_experiment_ids_unique(): Checking all experiment IDs are unique...")
    # Use a counter
    id_counter = {}
    non_unique_ids = set()

    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        existing_experiment_ids = []
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ensure_all_experiment_ids_unique(): ERROR: Could not load experiments file: " + str(e))
            return False

        # Add the new experiment to the list of experiments
        if ("experiment_list" not in experiments_data):
            # Error
            print("ensure_all_experiment_ids_unique(): ERROR: Could not find 'experiment_list' in experiments data.")
            return False
        else:
            for experiment in experiments_data["experiment_list"]:
                if ("id" in experiment):
                    existing_experiment_ids.append(experiment["id"])

        print("ensure_all_experiment_ids_unique(): Found " + str(len(existing_experiment_ids)) + " existing experiments.")

        # Check if the experiment ID is in the list of existing experiment IDs
        for experiment_id in existing_experiment_ids:
            if (experiment_id in id_counter):
                id_counter[experiment_id] += 1
                non_unique_ids.add(experiment_id)
            else:
                id_counter[experiment_id] = 1

    print("ensure_all_experiment_ids_unique(): Found " + str(len(non_unique_ids)) + " non-unique experiment IDs.")

    if (len(non_unique_ids) > 0):
        print("ensure_all_experiment_ids_unique(): ERROR: Found non-unique experiment IDs: " + str(non_unique_ids))
        return False
    else:
        print("ensure_all_experiment_ids_unique(): All experiment IDs are unique.")
        return True


# Task: Design/Create a new experiment with the experiment builder
## TODO: MAKE THIS THREAD SAFE, SO THAT ONLY ONE FUNCTION CAN HAVE WRITE ACCESS AT A TIME
def task_start_new_experiment(payload:dict):
    from datetime import datetime       # No idea why it's not importing from the top correctly
    startTime = datetime.now()

    # Load the experiments file
    experiments_data = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return {"success": False, "error": "Could not load experiments file: " + str(e)}

        # Add the new experiment to the list of experiments
        if ("experiment_list" not in experiments_data):
            # Error
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return {"success": False, "error": "Could not find 'experiment_list' in experiments data."}

        # Add the experiment
        payload["id"] = get_unique_experiment_id(experiments_data=experiments_data)

        payload["timestamp_created"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload["timestamp_finished"] = ""
        payload["status"] = "created"
        payload["num_iterations_run"] = 0
        payload["cost_so_far"] = 0.00
        payload["results_summary"] = ""
        payload["experiment_path"] = None
        payload["results_summary"] = None
        payload["results_summary_short"] = None
        payload["runtime_seconds"] = 0
        if ("max_experiment_cost" not in payload):
            payload["max_experiment_cost"] = 0.00       # Default to zero cost, so it will exit quickly if not set

        experiments_data["experiment_list"].append(payload)

        # Save the experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "w") as f:
                json.dump(experiments_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save experiments file: " + str(e))
            return {"success": False, "error": "Could not save experiments file: " + str(e)}

    # Return
    deltaTime = datetime.now() - startTime
    result = {
        "success": True,
        "time_seconds": deltaTime.total_seconds(),
        "total_cost": 0
    }
    return result




#   Create new ideas task
def task_create_new_ideas(payload:dict):
    from datetime import datetime
    # Parse the payload

    # Payload: Check for a list of papers to condition the ideation from
    papersToConditionFrom = []
    if ("selected_paper_ids" in payload) and (type(payload["selected_paper_ids"]) == list):
        papersToConditionFrom = payload["selected_paper_ids"]

    if (len(papersToConditionFrom) == 0):
        print("ERROR: Missing selected paper IDs in payload.")
        return {"success": False, "error": "Missing `selected_paper_ids` in payload: No papers have been provided to condition the ideation process on."}


    # Payload: Model string
    modelStr = ""
    if ("model_str" in payload) and (type(payload["model_str"]) == str):
        modelStr = payload["model_str"]

    # If the model string is missing, stop
    if (modelStr == ""):
        print("ERROR: Missing model string in payload.")
        return {"success": False, "error": "Missing model string in payload."}


    # Payload: Deduplication
    deduplicationEnabled = False
    if ("discourage_similar" in payload) and (type(payload["discourage_similar"]) == list):
        if ("Enable Deduplication" in payload["discourage_similar"]):
            deduplicationEnabled = True

    # Payload: Condition on existing codeblocks in experiment builder
    conditionOnCodeblocks = True        # Just do this by default

    # Payload: Conditional idea generation
    conditionalGenerationStr = ""
    if ("condition_idea_text" in payload) and (type(payload["condition_idea_text"]) == str):
        conditionalGenerationStr = payload["condition_idea_text"]

    # Payload: Is this is a batch job?
    isBatchJob = False
    batch_name = None
    if ("batch" in payload) and (type(payload["batch"]) == bool) and (payload["batch"] == True):
        isBatchJob = True
    if ("batch_name" in payload) and (type(payload["batch_name"]) == str):
        batch_name = payload["batch_name"]
        isBatchJob = True


    print("Creating new ideas...")
    startTime = datetime.now()

    # Load the paper store
    paperStore = PaperStore()
    # Get the latex source for the papers
    paperText = {}
    for paperID in papersToConditionFrom:
        success, paper_latex = paperStore.get_paper_latex(paperID)
        if (success == True):
            paperText[paperID] = paper_latex
        else:
            print("ERROR: Could not retrieve source for paper with ID: " + str(paperID))

    if (len(paperText) == 0):
        print("ERROR: No papers were successfully loaded.")
        return {"success": False, "error": "No papers were successfully loaded."}

    # Load the Idea Store
    ideaStore = IdeaStore()

    # Generate some new ideas
    result = ideaStore.generate_new_ideas(paperText=paperText, additional_conditioning_text=conditionalGenerationStr, discourage_similar_to_existing_ideas=deduplicationEnabled, condition_on_codeblocks=conditionOnCodeblocks, model_str=modelStr, num_ideas=5, add_to_idea_store=True, mark_as_batch_idea=isBatchJob, batch_name=batch_name)

    # The ideas are stored into the IdeaStore automatically -- so here, just extract metadata (e.g. success, time, cost)
    success = result.get("success", False)
    #time_seconds = result.get("time_seconds", 0)
    total_cost = result.get("cost", 0)
    idea_ids = result.get("idea_ids", [])

    # Keep track of how long the request took to process
    deltaTime = datetime.now() - startTime
    print("Task completed in " + str(deltaTime.total_seconds()) + " seconds.")

    result = {
        "success": success,
        "time_seconds": deltaTime.total_seconds(),
        "total_cost": total_cost,
        "idea_ids": idea_ids
    }
    return result




TASK_IDEATION_CREATE_NEW_IDEAS = "ideation_create_new_ideas"
TASK_START_NEW_EXPERIMENT = "start_new_experiment"
TASK_START_FOLLOWON_EXPERIMENT = "start_followon_experiment"
TASK_START_NEW_AUTONOMOUS_BATCH_EXPERIMENT = "start_new_autonomous_batch_experiment"

#
#   Creating task packets
#   These packets are intended to be added to the queue
#
def create_task_ideation(payload):
    task = {
        "task_type": TASK_IDEATION_CREATE_NEW_IDEAS,
        "payload": payload
    }

    return task

def run_start_new_experiment(payload):
    task = {
        "task_type": TASK_START_NEW_EXPERIMENT,
        "payload": payload
    }

    return task

def run_start_followon_experiment(payload):
    task = {
        "task_type": TASK_START_FOLLOWON_EXPERIMENT,
        "payload": payload
    }

    return task

def run_start_autonomous_batch_experiment(payload):
    task = {
        "task_type": TASK_START_NEW_AUTONOMOUS_BATCH_EXPERIMENT,
        "payload": payload
    }

    return task


#
#   Server/Worker Functions
#

processedTaskResults = []

# Function to process tasks
def task_worker():
    global EVENT_CRITICAL_STOP
    print("Task worker: Started!")

    # Load the processed task information
    loadProcessedTasks()

    # Load the API keys
    loadAPIKeys()

    # Sleep for 5 seconds to allow the system checks to start up (and EVENT_CRITICAL_STOP to fire if something happened during the initialization)
    time.sleep(5)

    #while (True):
    while not EVENT_CRITICAL_STOP.is_set():
        # Start up to 5 experiments per cycle
        for i in range(5):
            result = check_for_experiments_to_spawn()
            if (result == False):   # Result will be true if it found an experiment to spawn.  If False, then there are no more experiments to spawn, and we can end early.
                break

        # Print the queue size (optional)
        print("Task Queue Size: " + str(taskQueue.qsize()))

        # Get a task from the queue
        task = None
        try:
            task = taskQueue.get(timeout=1)
        except queue.Empty:
            pass

        print("Task: " + str(task))

        if (task is None):
            # The queue is empty -- sleep briefly
            print("Task worker: Queue is empty. Sleeping...")
            time.sleep(1)
            continue

        print("Task worker: Processing task...")
        # Perform the task
        result = process_task(task)
        processedTaskResults.append(result)

        # Mark the task as done (optional if you're tracking task completion)
        taskQueue.task_done()

        # Save the processed task information
        saveProcessedTasks()

    print("Task worker: Stopped!")


def saveProcessedTasks():
    global processedTaskResults

    # Save the processed tasks
    with open(FILENAME_PROCESSED_TASKS, "w") as f:
        json.dump(processedTaskResults, f, indent=4)

    print("Saved processed tasks to " + str(FILENAME_PROCESSED_TASKS))


def loadProcessedTasks():
    global processedTaskResults

    # Load the processed tasks
    try:
        with open(FILENAME_PROCESSED_TASKS, "r") as f:
            processedTaskResults = json.load(f)
    except Exception as e:
        print("ERROR: Could not load processed tasks from file: " + str(e))
        return False

    print("Loaded processed tasks from " + str(FILENAME_PROCESSED_TASKS))
    return True


# The main functin that parses a given task in the worker queue
def process_task(task):
    from datetime import datetime
    global CURRENT_TASK_BEING_PROCESSED

    # Access shared resources safely if needed
    with resource_lock:
        startTime = datetime.now()

        submissionTime = "unknown"
        if ("submission_time" in task):
            submissionTime = task["submission_time"]
        result = {
            "task_type": task.get("task_type", None),
            "submission_time": submissionTime,
            "start_time": startTime.isoformat(),
            "success": False,
            "error": None
        }

        # Update the current task being processed
        CURRENT_TASK_BEING_PROCESSED = task

        # Process which task to run
        task_type = task.get("task_type", None)

        # TASK: Ideation/Create new ideas
        if (task_type == TASK_IDEATION_CREATE_NEW_IDEAS):
            payload = task.get("payload", None)
            result_ = task_create_new_ideas(payload)
            result.update(result_)
            # Reset the current task being processed
            CURRENT_TASK_BEING_PROCESSED = None

        # TASK: Design a new experiment
        elif (task_type == TASK_START_NEW_EXPERIMENT):
            payload = task.get("payload", None)
            result_ = task_start_new_experiment(payload)
            result.update(result_)
            # Reset the current task being processed
            CURRENT_TASK_BEING_PROCESSED = None

        # TASK: Run a follow-on experiment
        elif (task_type == TASK_START_FOLLOWON_EXPERIMENT):
            payload = task.get("payload", None)
            result_ = task_start_new_experiment(payload)         # NOTE: Handled in the same way -- the experiment executer checks to see whether it's a follow-on or not
            result.update(result_)
            # Reset the current task being processed
            CURRENT_TASK_BEING_PROCESSED = None

        # TASK: Run an autonomous batch experiment
        elif (task_type == TASK_START_NEW_AUTONOMOUS_BATCH_EXPERIMENT):
            payload = task.get("payload", None)
            result_ = task_do_autonomous_experiment_minibatch(payload)
            result.update(result_)
            # Reset the current task being processed
            CURRENT_TASK_BEING_PROCESSED = None

        # Unknown task type
        else:
            print("ERROR: Unknown task type: " + str(task_type))
            result["success"] = False
            result["error"] = "Unknown task type"
            # Reset the current task being processed
            CURRENT_TASK_BEING_PROCESSED = None

        # Add end time
        endTime = datetime.now()
        deltaTimeSeconds = (endTime - startTime).total_seconds()
        result["end_time"] = endTime.isoformat()
        result["runtime_seconds"] = round(deltaTimeSeconds, 2)

    # Return
    return result



#
#   Experiment execution threading
#

# Check to see if there are experiments waiting to be run.  If there are, and there are available threads, start one.
def check_for_experiments_to_spawn():
    global MAX_EXPERIMENT_THREADS
    print("check_for_experiment_to_spawn: started...")
    # First, check to see if the maximum number of experiment threads are already running
    with THREAD_LOCK_EXPERIMENT_WORKERS:
        # Try to load the maximum number of experiment threads from the 'config_threads.json" file
        FILENAME_CONFIG_THREADS = "config_threads.json"
        try:
            MAX_EXPERIMENT_THREADS = DEFAULT_MAX_EXPERIMENT_THREADS
            with open(FILENAME_CONFIG_THREADS, "r") as f:
                config_data = json.load(f)
                MAX_EXPERIMENT_THREADS = config_data.get("max_experiment_threads", DEFAULT_MAX_EXPERIMENT_THREADS)
        except Exception as e:
            print("ERROR: Could not load 'config_threads.json' file.  Using default maximum experimental threads (" + str(MAX_EXPERIMENT_THREADS) + "): " + str(e))


        num_running_experiment_threads = worker_thread_count["experiment_threads"]
        print("Experiment Worker Threads (Running: " + str(num_running_experiment_threads) + " / Max: " + str(MAX_EXPERIMENT_THREADS) + ")")
        if (worker_thread_count["experiment_threads"] >= MAX_EXPERIMENT_THREADS):
            # Maximum number of threads are already running -- return
            return

    # Next, check to see if there are any experiments that need to be spawned
    next_experiment_id_to_start = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Load the experiments file
        experiments_data = None
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return

        if ("experiment_list" not in experiments_data):
            # Error
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return


        # Count how many experiments are currently waiting for processing (i.e. have the "created" status)
        num_experiments_waiting = 0
        experiment_ids_waiting = []
        for experiment in experiments_data["experiment_list"]:
            if (experiment["status"] == "created"):
                num_experiments_waiting += 1
                experiment_ids_waiting.append(experiment["id"])

        print("Experiments waiting in queue: " + str(num_experiments_waiting))

        # If there are no experiments waiting to run, return
        if (num_experiments_waiting == 0):
            print("No experiments waiting to run.  Returning...")
            return False

        # If there are experiments waiting, and there are available threads, start one
        next_experiment_id_to_start = experiment_ids_waiting[0]
        # Extra check (just to make sure) -- check if the experiment ID is unique.
        # NOTE: If we run a non-unique ID, then it essentially spawns the same experiment over and over, pausing the queue, and spending money/resources until the hard limits are reached.
        print("check_for_experiments_to_spawn: Checking if experiment ID is unique: " + str(next_experiment_id_to_start))
        while (is_experiment_id_unique(next_experiment_id_to_start, experiments_data=experiments_data) == False):
            print("CRITICAL ERROR: Experiment ID is not unique: " + str(next_experiment_id_to_start))
            # Remove the experiment from the list of experiments waiting
            experiment_ids_waiting.pop(0)
            if (len(experiment_ids_waiting) == 0):
                print("ERROR: No more experiments to run.")
                return False
            next_experiment_id_to_start = experiment_ids_waiting[0]
            print("check_for_experiments_to_spawn: Checking if experiment ID is unique: " + str(next_experiment_id_to_start))


    # Start the experiment worker thread
    # NOTE: Slightly wonky that we're starting a new thread from outside the thread lock (that's exited above after we confirm one is available), but this function should only be running a single time anyway -- so should be okay.
    # Can always wrap this function around another thread lock, to be extra sure.
    if (next_experiment_id_to_start is not None):
        print("Starting new experiment worker thread (Experiment ID: " + str(next_experiment_id_to_start) + ")")
        #experiment_worker_thread = threading.Thread(target=start_new_experiment_thread(next_experiment_id_to_start), daemon=True)
        experiment_worker_thread = threading.Thread(target=start_new_experiment_thread, args=(next_experiment_id_to_start,), daemon=True)
        experiment_worker_thread.start()
        print("Thread started...")
        # Sleep for 2 seconds between experiment spawns
        time.sleep(2)
        return True



# A thread wrapper for running one experiment, while keeping track of the number of experiment worker threads
def start_new_experiment_thread(id:str):
    import traceback
    with THREAD_LOCK_EXPERIMENT_WORKERS:
        # Increment the number of experiment threads running
        worker_thread_count["experiment_threads"] += 1
        print("Starting new experiment worker thread (Experiment ID: " + str(id) + ")")
        sys.stdout.flush()  # Flush output to ensure it appears

    # Set the status of the experiment to 'running'
    change_experiment_status(id, STATUS_RUNNING)

    # Keys from the 'benchmark' submission packet
        # experiment_submission_packed = {
        #     "experiment_name_short": original_idea_sanitized.get("research_idea_name", "Unknown"),
        #     "model_str": data.get("model_str", None),
        #     "experiment_building_agent_name": data.get("experiment_building_agent_name", None),
        #     "run_notes": data.get("run_notes", None),
        #     "experiment_description": experiment_builder_prompt,
        #     "codeblock_names_to_use": experiment_builder_codeblocks,
        #     "max_time_per_iteration_mins": data.get("max_time_per_iteration_mins", 1),
        #     "max_time_per_iteration_pilot_mins": data.get("max_time_per_iteration_pilot_mins", 1),
        #     "max_debug_iterations": data.get("max_debug_iterations", 1),
        #     "max_llm_cost_container": data.get("max_llm_cost_container", 0.00),
        #     "num_copies": data.get("num_experiments", 1),
        #     "submission_mode": "benchmark",
        #     "idea_id": benchmark_idea_id,
        #     "original_idea": original_idea_sanitized,
        #     "automatically_generated_experiment_prompt": experiment_builder_prompt,
        #     "max_experiment_cost": data.get("max_experiment_cost", 0.0),
        #     "batch_name": data.get("batch_name_short", None),
        #     "benchmark": benchmark_to_run,
        #     "operationalization": operationalization,                   # Full copy of the operationalization
        #     "full_original_benchmark_problem": benchmark_problem        # Full copy of the benchmark problem
        # }

    # Try to get which agent we should be using to execute this experiment
    experiment_record = get_experiment_info(id)
    if (experiment_record is None):
        print("ERROR: Could not find experiment with ID: " + str(id))
        new_status = STATUS_FAILED_TO_CREATE
        change_experiment_status(id, new_status)
        return

    experiment_building_agent_name = experiment_record.get("experiment_building_agent_name", None)
    print("Experiment (id: " + str(id) + ") requests Experiment Building Agent Name: " + str(experiment_building_agent_name))

    try:
        # Run the experiment
        # TODO: These agent names should come from a list/defines.
        # We can keep these in for examples of how to add new agents to the system.
        if (experiment_building_agent_name == "simple1") or (experiment_building_agent_name is None):
            new_status = run_experiment(id, use_faithfulness_reflection=False)                    # Original experiment agent

        elif (experiment_building_agent_name == "simple1-with-faithfulness-reflection"):
            new_status = run_experiment(id, use_faithfulness_reflection=True)                     # Original experiment agent with faithfulness reflection

        else:
            print("ERROR: Unknown Experiment Building Agent Name: " + str(experiment_building_agent_name))
            new_status = STATUS_FAILED_TO_CREATE_UNKNOWN_BUILDER

        # Set the run to 'completed'
        change_experiment_status(id, new_status)

    except Exception as e:
        traceback.print_exc()
        print("ERROR: Exception in experiment worker thread: " + str(e) + " (Experiment ID: " + str(id) + ")\n" + traceback.format_exc())
        new_status = STATUS_FAILED_WORKER_EXCEPTION
        change_experiment_status(id, new_status)

    finally:
        with THREAD_LOCK_EXPERIMENT_WORKERS:
            # Decrement the number of experiment threads running
            worker_thread_count["experiment_threads"] -= 1
            print("Experiment worker thread finished (Experiment ID: " + str(id) + ")")


# Update an experiment's status string in the experiments JSON file
def change_experiment_status(id:str, new_status:str):
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Open the experiments JSON file
        experiments_data = None
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == id):
                experiment["status"] = new_status
                break

        # Save the updated experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "w") as f:
                json.dump(experiments_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save experiments file: " + str(e))
            return


# This function essentially tries to recreate the `createExperiment` function, but with the final code from the previous experiment, mixed with the parameters from the new (follow-on) experiment.
def follow_on_experiment_get_previous_experiment_info(previous_experiment_id, new_experiment):
    # Load the experiments file
    previous_experiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        experiments_data = None
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return None

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == previous_experiment_id):
                previous_experiment = experiment
                break

        # If the experiment was not found, return
        if (previous_experiment is None):
            print("ERROR: Follow-on experiment lookup: could not find previous experiment with ID: " + str(previous_experiment_id))
            return None

    # Look through the previous experiment file to find some relevant information.
    # First, get the output directory
    previous_experiment_path = previous_experiment.get("experiment_path", None)
    if (previous_experiment_path is None):
        print("ERROR: Follow-on experiment lookup: Could not find previous experiment path.")
        return None

    # Load the history from the last run
    historyPacked = None
    filenameIn = previous_experiment_path + "/history.json"
    try:
        with open(filenameIn, "r") as f:
            historyPacked = json.load(f)
    except Exception as e:
        print("ERROR: Follow-on experiment lookup: Could not load history file (" + str(filenameIn) + "): " + str(e))
        return None

    if (historyPacked is None):
        print("ERROR: Follow-on experiment lookup: Could not load history file (" + str(filenameIn) + ")")
        return None
    if ("history" not in historyPacked):
        print("ERROR: Follow-on experiment lookup: Could not find 'history' key in history file (" + str(filenameIn) + ")")
        return None
    history = historyPacked["history"]
    if (len(history) == 0):
        print("ERROR: Follow-on experiment lookup: No history entries found in history file (" + str(filenameIn) + ")")
        return None


    # Now generate the starting code, which will be the final code from the previous experiment

    # This is what needs to be returned, as if it was returning from the createExperiment function.
        #     # Return the response
        # packedOut = {
        #     "success": True,
        #     "instruction_str": instructionStr,        # From new experiment
        #     "codeblock_names": codeblockNames,        # From new experiment
        #     "requirements": requirements,             # From last experiment
        #     "code": code,                             # From last experiment
        #     "codeblock_code": retrievedCodeblockDict, # From new experiment
        #     "model": modelStr,                        # From last experiment
        #     "max_tokens": max_tokens,                 # From last experiment
        #     "temperature": temperature,               # From last experiment
        #     "responseJSON": responseJSON,             # Set to None?
        #     "responseText": responseText,             # Set to None?
        #     "cost": cost,                             # Set to 0.0001
        #     "errors": errors                          # Set to []
        # }

    # Get the last history entry
    lastHistoryEntry = history[-1]

    # Get the codeblocks (the new ones, that were selected for the follow-on experiment)
    codeblock_names = new_experiment.get("codeblock_names_to_use", [])
    codeblock_code = {}
    codeblockStore = CodeBlockStore(PATH_CODEBLOCKS)
    for codeblock_name in codeblock_names:
        codeblock = codeblockStore.getCodeblockByName(codeblock_name)
        if (codeblock is None):
            print("ERROR: Could not find codeblock with name: " + str(codeblock_name))
        else:
            codeblock_code[codeblock_name] = codeblock
    print("Retrieved codeblocks: " + str(codeblock_code.keys()))

    # Repackage the last history entry into the format expected by the createExperiment function
    packed = {
        "success": True,
        "instruction_str": new_experiment.get("experiment_description", None),    # New
        "codeblock_names": new_experiment.get("codeblock_names_to_use", []),      # New
        "requirements": lastHistoryEntry.get("requirements", ""),                 # Last
        "code": lastHistoryEntry.get("code", ""),                                 # Last
        "codeblock_code": codeblock_code,                                         # New
        "model": lastHistoryEntry.get("model", ""),                               # Last
        "max_tokens": lastHistoryEntry.get("max_tokens", 0),                      # Last
        "temperature": lastHistoryEntry.get("temperature", 0.0),                  # Last
        "responseJSON": None,                                                     # Blank out
        "responseText": "",                                                       # Blank out
        "cost": 0.0000001,                                                        # Set to a small value (effectively blanking it out, but making it non-zero in case that causes some issues)
        "errors": []                                                              # Blank out
    }

    return packed



# Get the record for one experiment
def get_experiment_info(id:str):
    # Load the experiment data
    experiments_data = None
    targetExperiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return None

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == id):
                targetExperiment = experiment
                return targetExperiment

        # If the experiment was not found, return
        if (targetExperiment is None):
            print("ERROR: Could not find experiment with ID: " + str(id))
            return None


# Run one experiment
# This is the main function for the agent that essentially takes the idea/plan, and runs a single complete experiment
# (from code generation, debugging, through report generation)
def run_experiment(id:str, use_faithfulness_reflection:bool=False):
    exit_status = STATUS_FAILED
    import datetime

    print("run_experiment(): Running experiment (ID: " + str(id) + ")")

    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Load the experiment data
    experiments_data = None
    targetExperiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return STATUS_FAILED_FILEIO

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == id):
                targetExperiment = experiment
                break

        # If the experiment was not found, return
        if (targetExperiment is None):
            print("ERROR: Could not find experiment with ID: " + str(id))
            return STATUS_FAILED_FILEIO

    # Experiment parameters
    # Examples:
    #experimentName = "react-causal-memory-persistent"
    #instructionStr = "Please investigate whether adding a causal memory to a ReAct agent helps improve its performance over a baseline ReAct agent.  The causal memory should be *abstractive*, abstracting how single actions (or sequences of actions) helped achieve subgoals or larger goals.  The memory should be persistent, saved across episodes (and framed as `lessons` in the prompt, that may or may not be from the current episode, so it doesn't get confused). The memory should be displayed in the log file, so you can inspect it to make sure it's behaving correctly. Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    #additionalInstructionStr = "Please use the Python programming language."
    #codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #max_container_llm_cost = 5.00
    #max_runtime_seconds = 60 * 30   # 30 minutes

    experimentName = targetExperiment.get("experiment_name_short")
    instructionStr = targetExperiment.get("experiment_description")
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = targetExperiment.get("codeblock_names_to_use")
    modelStr = targetExperiment.get("model_str")
    max_container_llm_cost = targetExperiment.get("max_llm_cost_container")
    max_runtime_seconds = targetExperiment.get("max_time_per_iteration_mins") * 60
    max_runtime_seconds_pilot = targetExperiment.get("max_time_per_iteration_pilot_mins", 10) * 60            # Default to 10 minutes if not set.
    max_reflections = targetExperiment.get("max_debug_iterations")
    max_experiment_cost = targetExperiment.get("max_experiment_cost", 0.00)     # Note: This is not enforced until the debugging/reflection steps.  So a really expensive initial generation may exceed this.
    hard_runtime_cutoff_seconds = targetExperiment.get("hard_runtime_cutoff_seconds", (60*60*6))  # 6 hours (if not otherwise specified)

    temperature = targetExperiment.get("temperature", 0.1)
    max_tokens = 8192
    if (modelStr.startswith("o1-mini")):
        max_tokens = 32000  # Technically larger, but limiting here
    elif (modelStr.startswith("o3-mini")):
        max_tokens = 32000  # Technically larger, but limiting here


    # Check to see if no cost limit was set
    if (max_experiment_cost <= 0.01):
        print("ERROR: No cost limit set, or cost limit was very low (" + str(max_experiment_cost) + ") for experiment with ID: " + str(id) + ".  Exiting.")
        return STATUS_FAILED_COST_LIMIT


    # Check to see if this is a follow-on experiment (and if so, set a few variables)
    is_follow_on_experiment = False
    follow_on_experiment_previous_experiment_id = None
    if ("follow_on_experiment" in targetExperiment) and (targetExperiment["follow_on_experiment"] == True):
        is_follow_on_experiment = True
        follow_on_experiment_previous_experiment_id = targetExperiment.get("follow_on_to_experiment_id", None)

    # Re-sanitize the experiment name, since it's being used in the path
    experimentNameForPath = experimentName
    # Use a regex to remove all non-alphanumeric characters.  Convert spaces to dashes.
    experimentNameForPath = re.sub(r'\W+', '', experimentNameForPath)
    experimentNameForPath = experimentNameForPath.replace(" ", "-")

    # Create the experiment output directory
    experimentNameWithDate = experimentNameForPath + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pathExperimentOutput = "generated-experiments/" + experimentNameWithDate + "/"
    if (not os.path.exists(pathExperimentOutput)):
        os.makedirs(pathExperimentOutput)

    print("run_experiment(): Running experiment (ID: " + str(id) + "): Output folder is: " + str(pathExperimentOutput))

    # Save the experiment output path to the experiment data
    targetExperiment["experiment_path"] = pathExperimentOutput
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Re-load the experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return STATUS_FAILED_FILEIO

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == id):
                experiment.update(targetExperiment)
                break

        # Save the updated experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "w") as f:
                json.dump(experiments_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save experiments file: " + str(e))
            return STATUS_FAILED_FILEIO

    startTime = datetime.datetime.now()

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker(PATH_CODEBLOCKS)

    # Create the experiment
    # First: Check if this is a new experiment, or a follow-on experiment
    combinedCodeblock = None
    follow_on_description = None
    if (is_follow_on_experiment == False):
        # New experiment
        # NOTE: I'm not sure initial code generation is currently included in the total experiment cost calculation.
        print("New Experiment")
        combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

        # Make sure the codeblock contains code -- if not, retry one time.
        if (combinedCodeblock is None) or ("success" in combinedCodeblock and combinedCodeblock["success"] == False) or ("code" not in combinedCodeblock) or (combinedCodeblock["code"] == None):
            # Something went wrong -- retry once
            print("Retrying experiment creation...")
            combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    else:
        # Follow-on experiment
        print("Follow-on Experiment")
        combinedCodeblock = follow_on_experiment_get_previous_experiment_info(follow_on_experiment_previous_experiment_id, targetExperiment)

        # Get the follow-on description
        follow_on_description = targetExperiment.get("experiment_description_follow_on", None)
        print("Follow-on description: " + str(follow_on_description))

        if (combinedCodeblock is None):
            print("ERROR: Could not create follow-on experiment.")


    # If the codeblock is still None, return
    # This suggests that -- for whatever reason -- we were unable to generate the initial code for the experiment.
    continue_experiment = True
    if (combinedCodeblock is None) or ("success" in combinedCodeblock and combinedCodeblock["success"] == False) or ("code" not in combinedCodeblock) or (combinedCodeblock["code"] == None):
        print("ERROR: Could not create experiment.")
        continue_experiment = False
        if (is_follow_on_experiment == True):
            exit_status = STATUS_FAILED_TO_CREATE_FOLLOW_ON
        else:
            exit_status = STATUS_FAILED_TO_CREATE

    # Main experiment cycle: Run the experiment, reflect on the output, and continue until a stop condition is reached.
    # The main stop conditions are: (1) The experiment appears to be complete/work, or (2) some kind of limit is reached (e.g. cost, time, etc.)
    history = None
    historyPacked = None
    if (continue_experiment == True):
        history, historyPacked = experimentMaker.runAndReflectExperimentWithPackedHistory(combinedCodeblock, modelStr, MAX_REFLECTIONS=max_reflections, max_tokens=max_tokens, pathLogOutput=pathExperimentOutput, max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds, max_runtime_seconds_pilot=max_runtime_seconds_pilot, max_experiment_cost=max_experiment_cost, follow_on_description=follow_on_description, use_faithfulness_reflection=use_faithfulness_reflection, hard_runtime_cutoff_seconds=hard_runtime_cutoff_seconds, temperature=temperature)

    # Record how long it took to run the experiment
    totalTimeSeconds = (datetime.datetime.now() - startTime).total_seconds()

    # If the experiment failed, and returned a generic error, then change the error status to mark that the experiment failed AFTER running/reflection, for some reason (i.e. 'we got this far')
    if (exit_status == STATUS_FAILED):
        exit_status = STATUS_FAILED_AFTER_RUNNING

    # Check the last step of the history to see if the experiment was successful (`is_ok` should be True)
    if (history is not None) and (len(history) > 0):
        lastStep = history[-1]
        if ("is_ok" in lastStep) and (lastStep["is_ok"] == True):
            exit_status = STATUS_COMPLETED

        # Get (and save) the number of iterations run from the history
        numIterationsRun = len(history)
        targetExperiment["num_iterations_run"] = numIterationsRun
        # Also look for the 'summary' and 'summary_short' keys in the history metadata
        summary = None
        summaryShort = None
        interestingResults = None
        if (historyPacked is not None) and ("summary" in historyPacked["metadata"]):
            summary = historyPacked["metadata"]["summary"]
        if (historyPacked is not None) and ("summary_short" in historyPacked["metadata"]):
            summaryShort = historyPacked["metadata"]["summary_short"]
        if (historyPacked is not None) and ("interesting_results" in historyPacked["metadata"]):
            interestingResults = historyPacked["metadata"]["interesting_results"]
        targetExperiment["results_summary"] = summary
        targetExperiment["results_summary_short"] = summaryShort
        targetExperiment["interesting_results"] = interestingResults

        # Update the cost
        cost_so_far = 0
        cost_build_debug = 0
        cost_llm_proxy = 0
        if (historyPacked is not None) and ("total_cost" in historyPacked["metadata"]):
            cost_so_far = historyPacked["metadata"]["total_cost"]
            cost_build_debug = historyPacked["metadata"]["total_cost_build_debug"]
            cost_llm_proxy = historyPacked["metadata"]["total_cost_llm_proxy"]

        targetExperiment["cost_so_far"] = cost_so_far
        targetExperiment["total_cost_build_debug"] = cost_build_debug
        targetExperiment["total_cost_llm_proxy"] = cost_llm_proxy

    # Update timestamp_finished
    targetExperiment["timestamp_finished"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update time
    targetExperiment["runtime_seconds"] = totalTimeSeconds

    # Check to see if the experiment had any number of errors, and if so, update the status to reflect which kind of error.
    if (history is not None) and (len(history) > 0):
        lastStep = history[-1]
        if ("is_ok" in lastStep) and (lastStep["is_ok"] == False):
            # TODO: Check for max iterations
            history_length = len(historyPacked["history"])
            if (history_length >= max_reflections):
                exit_status = STATUS_FAILED_TOO_MANY_ITERATIONS

        # Check for cost limit exceeded
        if (historyPacked["metadata"]["cost_limit_exceeded"] == True):
            exit_status = STATUS_FAILED_COST_LIMIT

        # Check for a container error
        if (historyPacked["metadata"]["container_failure"] == True):
            exit_status = STATUS_FAILED_CONTAINER_ERROR

        # Check for code_complete_critical_error
        if (historyPacked["metadata"]["code_complete_critical_error"] == True):
            exit_status = STATUS_CODE_COMPLETE_CRITICAL_ERROR

        # Check for error_code_parsing_issue
        if (historyPacked["metadata"]["error_code_parsing_issue"] == True):
            exit_status = STATUS_CODE_PARSING_ISSUE

        # Check for hitting the hard runtime limit (hard_time_limit_reached)
        if (historyPacked["metadata"]["hard_time_limit_reached"] == True):
            exit_status = STATUS_HARD_RUNTIME_LIMIT_REACHED

        # Add the experiment model to the metadata
        historyPacked["metadata"]["experiment_building_agent_name"] = targetExperiment.get("experiment_building_agent_name", None)


    # Save the experiment status/information back to the experiments JSON file
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Re-load the experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return STATUS_FAILED_FILEIO

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == id):
                experiment.update(targetExperiment)
                break

        # Save the updated experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "w") as f:
                json.dump(experiments_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save experiments file: " + str(e))
            return STATUS_FAILED_FILEIO

    # Print the exit status
    print("run_experiment(): Experiment (ID: " + str(id) + ") finished.  Exit status: " + str(exit_status))

    # Return
    return exit_status



#
#   Endpoints
#


@app.route('/startideation', methods=['POST'])
def process_request():
    from datetime import datetime
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Print the data
    print("Received data: " + str(data))

    # Assemble the task
    task = create_task_ideation(payload = data)

    # Always add the time the task was added to the queue
    task["added_time"] = datetime.now().isoformat()

    # Add the task to the queue
    taskQueue.put(task)

    # Return a response indicating the task has been queued
    response_data = {
        'status': 'queued',
        'message': 'Your task has been added to the queue and will be processed shortly.'
    }

    return jsonify(response_data), 202  # 202 Accepted indicates the request has been accepted for processing


# Create an endpoint that provides high-level statistics on the task queue
@app.route('/queuestatus', methods=['GET', 'POST'])
def get_task_stats():

    # Get the number of currently active experiment workers
    num_running_experiment_threads = 0
    with THREAD_LOCK_EXPERIMENT_WORKERS:
        num_running_experiment_threads = worker_thread_count["experiment_threads"]

    # Make a histogram of the different task types currently waiting in the queue
    taskTypeHist = {}
    for task in list(taskQueue.queue):
        taskType = task.get("task_type", "unknown")
        if (taskType not in taskTypeHist):
            taskTypeHist[taskType] = 0
        taskTypeHist[taskType] += 1

    currentTaskTypeBeingProcessed = None
    if (CURRENT_TASK_BEING_PROCESSED is not None):
        currentTaskTypeBeingProcessed = CURRENT_TASK_BEING_PROCESSED.get("task_type", "unknown")

    # Pack a response
    response_data = {
        'queue_size': taskQueue.qsize(),
        'processed_tasks': len(processedTaskResults),
        'queued_task_type_histogram': taskTypeHist,
        'current_task_being_processed': currentTaskTypeBeingProcessed,
        "num_running_experiment_threads": num_running_experiment_threads,
        "max_experiment_threads": MAX_EXPERIMENT_THREADS
    }

    return jsonify(response_data), 200


# Create an endpoint that provides high-level statistics on the task queue
@app.route('/queuedetails', methods=['GET', 'POST'])
def get_task_stats_details():
    # This returns two pieces of information: (1) a breakdown of the number of tasks completed, and their costs, (2) a list of the current tasks in the queue, and when they were added.
    response = {}

    # Part 1: Breakdown of costs
    processedTaskCosts = {}

    for task in processedTaskResults:
        taskType = task.get("task_type", "unknown")
        taskCost = task.get("total_cost", 0)
        taskTimeSec = task.get("time_seconds", 0)
        success = task.get("success", False)

        if (taskType not in processedTaskCosts):
            processedTaskCosts[taskType] = {"total_cost": 0, "min_cost": 0, "max_cost": 0, "avg_cost": 0,
                                            "total_time_sec": 0, "min_time_sec": 0, "max_time_sec": 0, "avg_time_sec": 0,
                                            "num_success": 0, "num_fail": 0, "total_jobs": 0}


        processedTaskCosts[taskType]["total_cost"] += taskCost
        if (taskCost < processedTaskCosts[taskType]["min_cost"]) or (processedTaskCosts[taskType]["min_cost"] == 0):
            processedTaskCosts[taskType]["min_cost"] = taskCost
        if (taskCost > processedTaskCosts[taskType]["max_cost"]):
            processedTaskCosts[taskType]["max_cost"] = taskCost

        processedTaskCosts[taskType]["total_time_sec"] += taskTimeSec
        if (taskTimeSec < processedTaskCosts[taskType]["min_time_sec"]):
            processedTaskCosts[taskType]["min_time_sec"] = taskTimeSec
        if (taskTimeSec > processedTaskCosts[taskType]["max_time_sec"]):
            processedTaskCosts[taskType]["max_time_sec"] = taskTimeSec

        processedTaskCosts[taskType]["total_jobs"] += 1
        if (success == True):
            processedTaskCosts[taskType]["num_success"] += 1
        else:
            processedTaskCosts[taskType]["num_fail"] += 1

    # Calculate averages
    for taskType in processedTaskCosts:
        totalCost = processedTaskCosts[taskType]["total_cost"]
        totalJobs = processedTaskCosts[taskType]["total_jobs"]
        totalSec = processedTaskCosts[taskType]["total_time_sec"]

        if (totalJobs > 0):
            processedTaskCosts[taskType]["avg_cost"] = totalCost / totalJobs
            processedTaskCosts[taskType]["avg_time_sec"] = totalSec / totalJobs

    # Store
    response["processed_task_summary"] = processedTaskCosts

    # Part 2: List queued tasks
    numQueuedTasks = taskQueue.qsize()
    response["num_queued_tasks"] = numQueuedTasks

    MAX_TASKS_TO_INCLUDE = 100
    queuedTasks = []
    # Add the task and added time for the 100 tasks at the front of the queue
    for i, task in enumerate(list(taskQueue.queue)):
        if (i >= MAX_TASKS_TO_INCLUDE):
            break

        taskType = task.get("task_type", "unknown")
        taskAddedTime = task.get("added_time", None)
        queuedTasks.append({"task_type": taskType, "added_time": taskAddedTime})
    response["queued_task_details"] = queuedTasks


    # Also add task currently being processed:
    currentTaskTypeBeingProcessed = None
    if (CURRENT_TASK_BEING_PROCESSED is not None):
        currentTaskTypeBeingProcessed = CURRENT_TASK_BEING_PROCESSED.get("task_type", "unknown")
    response['current_task_being_processed'] = currentTaskTypeBeingProcessed


    # Show the last 10 tasks completed
    lastTasksCompleted = []
    MAX_PREV_TASKS_TO_INCLUDE = 10
    for i in range(1, min(MAX_PREV_TASKS_TO_INCLUDE, len(processedTaskResults)+1)):
        lastTask = processedTaskResults[-i]
        lastTasksCompleted.append(lastTask)
    response["last_tasks_completed"] = lastTasksCompleted


    # Return
    return jsonify(response), 200


# Server-side function to get a list of available codeblocks
@app.route('/knowncodeblocknames', methods=['GET'])
def get_known_codeblock_names():
    import traceback
    try:
        # Load the codeblock store
        codeblockStore = CodeBlockStore(PATH_CODEBLOCKS)
        # Get a list of all the codeblock names
        codeblockNames = codeblockStore.listCodeblocks()
        # Return
        response_data = {
            'codeblock_names': codeblockNames
        }
        return jsonify(response_data), 200
    except Exception as e:
        traceback.print_exc()
        print ("ERROR: " + str(e) + "\n")
        return jsonify({'error': str(e)}), 500


#
#   Starting batch autonomous experiments
#
@app.route('/startautonomousbatch', methods=['POST'])
def process_request_startautonomousbatch():
    from datetime import datetime
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Print the data
    print("Received data: " + str(data))

    total_num_experiments = data.get("num_experiments", 0)
    if (total_num_experiments <= 0):
        return jsonify({'error': 'Invalid number of experiments provided'}), 400
    if (total_num_experiments > 100):
        return jsonify({'error': 'Number of experiments exceeds maximum limit of 100'}), 400

    num_experiments_per_minibatch = 5
    num_minibatches_to_add = total_num_experiments // num_experiments_per_minibatch

    for i in range(num_minibatches_to_add):
        print("Adding autonomous experimentation minibatch " + str(i+1) + " of " + str(num_minibatches_to_add))

        # Assemble the task
        task = run_start_autonomous_batch_experiment(payload = data)

        # Always add the time the task was added to the queue
        task["added_time"] = datetime.now().isoformat()

        # Add the task to the queue
        taskQueue.put(task)

        time.sleep(2)   # Sleep for 2 seconds between adding minibatches


    # Return a response indicating the task has been queued
    response_data = {
        'status': 'queued',
        'message': 'Your task has been added to the queue and will be processed shortly.',
        'payload': data
    }

    return jsonify(response_data), 202


#
#   Starting benchmark runs
#
# startbenchmarkrun
@app.route('/startbenchmarkrun', methods=['POST'])
def process_request_startbenchmarkrun():
    from datetime import datetime
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Print the data
    print("Received data: " + str(data))

            # payload = {
            #     'model_str': user_input['model_str'],
            #     'batch_name_short': batch_name_short,
            #     'experiment_building_agent_name': user_input['experiment_building_agent_name'],
            #     'benchmark_to_run': user_input['benchmark_to_run'],
            #     'max_time_per_iteration_mins': user_input['max_time_per_iteration_mins'],
            #     'max_time_per_iteration_pilot_mins': user_input['max_time_per_iteration_pilot_mins'],
            #     'max_debug_iterations': user_input['max_debug_iterations'],
            #     'max_llm_cost_container': user_input['max_llm_cost_container'],
            #     'max_experiment_cost': user_input['max_experiment_cost'],
            #     'run_notes': user_input['run_notes']
            # }

    # Load the benchmark
    benchmark_to_run = data.get("benchmark_to_run", None)
    if (benchmark_to_run is None):
        return jsonify({'error': 'No benchmark provided'}), 400

    # Try to load the benchmark
    benchmark_problems = []
    BENCHMARK_FOLDER = "data/"
    try:
        with open(BENCHMARK_FOLDER + benchmark_to_run, "r") as f:
            benchmark_problems = json.load(f)
    except Exception as e:
        return jsonify({'error': 'Could not load benchmark: ' + str(e)}), 400

    # Check the benchmark
    if (not isinstance(benchmark_problems, list)) or (len(benchmark_problems) == 0):
        return jsonify({'error': 'Invalid benchmark format'}), 400

    # Try to submit each of the benchmark problems
    for i, benchmark_problem in enumerate(benchmark_problems):
        print("Adding benchmark problem " + str(i+1) + " of " + str(len(benchmark_problems)))

        # Copy all the data from the benchmark problem
        from copy import deepcopy
        benchmark_problem_copy = deepcopy(benchmark_problem)
        # Add all the keys from the payload
        for key in data:
            benchmark_problem_copy[key] = data[key]

        operationalization = benchmark_problem.get("operationalization", None)
        if (operationalization is None):
            # Continue
            print("ERROR: No operationalization provided for benchmark problem " + str(i+1) + ". Skipping.")
            continue
        experiment_builder_prompt = operationalization.get("operationalization_description", None)
        experiment_builder_codeblocks = operationalization.get("operationalization_codeblocks", None)
        benchmark_idea_id = benchmark_problem.get("id", None)
        original_idea_sanitized = {}
        original_idea_sanitized["research_idea_name"] = benchmark_problem.get("research_idea_name", None)   # Name to use for the experiment
        original_idea_sanitized["research_idea_long_description"] = benchmark_problem.get("research_idea_long_description", None)
        original_idea_sanitized["research_idea_short_description"] = benchmark_problem.get("research_idea_short_description", None)
        original_idea_sanitized["research_idea_hypothesis"] = benchmark_problem.get("research_idea_hypothesis", None)
        original_idea_sanitized["research_idea_variables"] = benchmark_problem.get("research_idea_variables", None)
        original_idea_sanitized["research_idea_metric"] = benchmark_problem.get("research_idea_metric", None)
        original_idea_sanitized["research_idea_baselines"] = benchmark_problem.get("research_idea_baselines", None)
        original_idea_sanitized["research_idea_pilot"] = benchmark_problem.get("research_idea_pilot", None)
        original_idea_sanitized["research_idea_design_prompt"] = benchmark_problem.get("research_idea_design_prompt", None)
        original_idea_sanitized["research_idea_codeblocks"] = benchmark_problem.get("research_idea_codeblocks", [])
        original_idea_sanitized["research_idea_required_code_and_resources"] = benchmark_problem.get("research_idea_required_code_and_resources", [])
        original_idea_sanitized["research_idea_external_requirements"] = benchmark_problem.get("research_idea_external_requirements", [])

        experiment_submission_packed = {
            "experiment_name_short": original_idea_sanitized.get("research_idea_name", "Unknown"),
            "batch_name": data.get("batch_name_short", None),
            "model_str": data.get("model_str", None),
            "experiment_building_agent_name": data.get("experiment_building_agent_name", None),
            "run_notes": data.get("run_notes", None),
            "experiment_description": experiment_builder_prompt,
            "codeblock_names_to_use": experiment_builder_codeblocks,
            "max_time_per_iteration_mins": data.get("max_time_per_iteration_mins", 1),
            "max_time_per_iteration_pilot_mins": data.get("max_time_per_iteration_pilot_mins", 1),
            "max_debug_iterations": data.get("max_debug_iterations", 1),
            "max_llm_cost_container": data.get("max_llm_cost_container", 0.00),
            "num_copies": data.get("num_experiments", 1),
            "submission_mode": "benchmark",
            "idea_id": benchmark_idea_id,
            "original_idea": original_idea_sanitized,
            "automatically_generated_experiment_prompt": experiment_builder_prompt,
            "max_experiment_cost": data.get("max_experiment_cost", 0.0),
            "benchmark": benchmark_to_run,
            "operationalization": operationalization,                   # Full copy of the operationalization
            "full_original_benchmark_problem": benchmark_problem        # Full copy of the benchmark problem
        }

        # Check how many copies are to be submitted
        num_copies_to_run = 1
        if ("num_copies_to_run" in data):
            num_copies_to_run = data["num_copies_to_run"]
        if (num_copies_to_run <= 0):
            num_copies_to_run = 1
        if (num_copies_to_run > 25):        # This is an arbitrary hard-coded limit -- can be increased if needed.
            num_copies_to_run = 25
            print("WARNING: Number of copies to run (" + str(num_copies_to_run) + ") exceeds maximum limit of 25. Setting to 25.")
        if (not isinstance(num_copies_to_run, int)):
            num_copies_to_run = 1

        if (num_copies_to_run == 1):
            task = run_start_new_experiment(payload = experiment_submission_packed)     # Assemble the task
            task["added_time"] = datetime.now().isoformat()                             # Always add the time the task was added to the queue
            # Add the task to the queue
            taskQueue.put(task)
            time.sleep(2)
        else:
            for i in range(num_copies_to_run):
                print("\tSubmitting copy " + str(i+1) + " of " + str(num_copies_to_run))
                # Make a deep copy of the experiment submission packed
                experiment_submission_packed_copy = deepcopy(experiment_submission_packed)
                # Change the experiment short name to add "-copyN" to the end
                experiment_submission_packed_copy["experiment_name_short"] = experiment_submission_packed_copy["experiment_name_short"] + "-copy" + str(i+1)
                # Assemble the task
                task = run_start_new_experiment(payload = experiment_submission_packed_copy)
                task["added_time"] = datetime.now().isoformat()                             # Always add the time the task was added to the queue
                # Add the task to the queue
                taskQueue.put(task)
                time.sleep(2)


    # Return a response indicating the task has been queued
    response_data = {
        'status': 'queued',
        'message': 'Your task has been added to the queue and will be processed shortly.',
        'payload': data
    }

    return jsonify(response_data), 202

#
#   Starting new experiments
#
@app.route('/startnewexperiment1', methods=['POST'])
def process_request_startnewexperiment1():
    from datetime import datetime
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Print the data
    print("Received data: " + str(data))

    # Multiple copy aware
    # Check how many copies are to be submitted
    num_copies_to_run = 1
    if ("num_copies" in data):
        num_copies_to_run = data["num_copies"]
    if (num_copies_to_run <= 0):
        num_copies_to_run = 1
    if (num_copies_to_run > 10):        # This is an arbitrary hard-coded limit -- can be increased if needed.
        num_copies_to_run = 10
        print("WARNING: Number of copies to run (" + str(num_copies_to_run) + ") exceeds maximum limit of 10. Setting to 10.")
    if (not isinstance(num_copies_to_run, int)):
        num_copies_to_run = 1

    if (num_copies_to_run == 1):
        task = run_start_new_experiment(payload = data)     # Assemble the task
        task["added_time"] = datetime.now().isoformat()                             # Always add the time the task was added to the queue
        # Add the task to the queue
        taskQueue.put(task)
        time.sleep(2)
    else:
        for i in range(num_copies_to_run):
            print("\tSubmitting copy " + str(i+1) + " of " + str(num_copies_to_run))
            # Make a deep copy of the experiment submission packed
            experiment_submission_packed_copy = deepcopy(data)
            # Change the experiment short name to add "-copyN" to the end
            experiment_submission_packed_copy["experiment_name_short"] = experiment_submission_packed_copy["experiment_name_short"] + "-copy" + str(i+1)
            # Assemble the task
            task = run_start_new_experiment(payload = experiment_submission_packed_copy)
            task["added_time"] = datetime.now().isoformat()                             # Always add the time the task was added to the queue
            # Add the task to the queue
            taskQueue.put(task)
            time.sleep(2)   # Add a short delay between submitting each copy to the server

    # Return a response indicating the task has been queued
    response_data = {
        'status': 'queued',
        'message': 'Your task has been added to the queue and will be processed shortly.',
        'payload': data
    }

    return jsonify(response_data), 202

#
#   Starting follow-on experiments
#
@app.route('/startfollowonexperiment1', methods=['POST'])
def process_request_startfollowonexperiment1():
    from datetime import datetime
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    # Print the data
    print("Received data: " + str(data))

    # Assemble the task
    ## TODO: CHANGE THIS
    task = run_start_followon_experiment(payload = data)

    # Always add the time the task was added to the queue
    task["added_time"] = datetime.now().isoformat()

    # Add the task to the queue
    taskQueue.put(task)

    # Return a response indicating the task has been queued
    response_data = {
        'status': 'queued',
        'message': 'Your task has been added to the queue and will be processed shortly.',
        'payload': data
    }

    return jsonify(response_data), 202


#
#   Getting the experiment list
#
@app.route('/getexperimentlist', methods=['GET'])
def process_request_get_experiment_list():
    # Get a list of all current/past experiments
    allExperiments = []
    experiments_data = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Actually, load the experiments from the file
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return jsonify({'error': 'Could not load experiments file: ' + str(e)}), 500

    # Check for the experiment list
    if ("experiment_list" not in experiments_data):
        print("ERROR: Could not find 'experiment_list' in experiments data.")
        return jsonify({'error': 'Could not find "experiment_list" in experiments data.'}), 500

    # Add the experiments to the list
    allExperiments = experiments_data["experiment_list"]


    # Return the response
    response_data = {
        'experiment_list': allExperiments
    }
    return jsonify(response_data), 200


# Endpoint to request that a specific experiment (by ID) is ZIPPED, with a link returned.
@app.route('/zipexperiment', methods=['GET', 'POST'])
def process_request_zip_experiment():
    # Get the ID for the experiment to ZIP
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    experiment_id = data.get("experiment_id", None)
    print("ZIP requested (Experiment ID: " + str(experiment_id) + ")")

    # Check for the experiment ID
    if (experiment_id is None):
        return jsonify({'error': 'No experiment ID provided'}), 400

    # Check for the experiment ID
    if (not isinstance(experiment_id, str)):
        experiment_id = str(experiment_id)

    # Load the experiment file, and get the path to the experiment
    experiments_data = None
    targetExperiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Load the experiments from the file
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return jsonify({'error': 'Could not load experiments file: ' + str(e)}), 500

        # Check for the experiment list
        if ("experiment_list" not in experiments_data):
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return jsonify({'error': 'Could not find "experiment_list" in experiments data.'}), 500

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == experiment_id):
                targetExperiment = experiment
                break

    # Check if the experiment was found
    if (targetExperiment is None):
        return jsonify({'error': 'Could not find experiment with ID: ' + str(experiment_id)}), 404

    # Get the path to the experiment
    experimentPath = targetExperiment.get("experiment_path", None)
    experimentId = targetExperiment.get("id", None)

    # Check if the experiment path was found
    if (experimentPath is None):
        return jsonify({'error': 'Could not find path for experiment with ID: ' + str(experiment_id)}), 404

    # Check if the experiment path exists
    if (not os.path.exists(experimentPath)):
        return jsonify({'error': 'The path for an experiment does not appear to exist on disk (ID: ' + str(experiment_id)} + ")"), 404

    # Zip the experiment folder
    # First, make a folder to store zipped experiments, if it doesn't already exist
    FOLDER_ZIPPED_EXPERIMENTS = "zipped-experiments/"
    if (not os.path.exists(FOLDER_ZIPPED_EXPERIMENTS)):
        os.makedirs(FOLDER_ZIPPED_EXPERIMENTS)

    # Create a zip file
    # The ZIP file name should be the last part of the experiment path (after the last slash)
    # Remove any trailing slash from the experiment path
    experimentPath = experimentPath.rstrip("/")
    experimentPathParts = experimentPath.split("/")
    experimentFolderName = experimentPathParts[-1]
    # Check for length
    if (len(experimentFolderName) == 0):
        experimentFolderName = "experiment-id-" + str(experimentId)

    # Create the zip file
    zipFilenamePrefix = FOLDER_ZIPPED_EXPERIMENTS + experimentFolderName # ".zip"
    zipFilename = zipFilenamePrefix + ".zip"
    zipFileSizeMB = 0
    # ZIP everything in the folder, recursively
    import shutil
    try:
        print("Creating ZIP file (" + zipFilename + ") for experiment path: " + experimentPath)
        shutil.make_archive(zipFilenamePrefix, 'zip', experimentPath)
        # Get the file size
        zipFileSizeMB = os.path.getsize(zipFilename) / (1024 * 1024)
    except Exception as e:
        print("ERROR: Could not create ZIP file: " + str(e))
        return jsonify({'error': 'Could not create ZIP file: ' + str(e)}), 500

    # Return the link to the ZIP file
    response_data = {
        'zip_file': zipFilename,
        'zip_file_size_mb': zipFileSizeMB
    }

    return jsonify(response_data), 200


# Endpoint to request the experiment code
@app.route('/showexperimentcodeandresults', methods=['GET', 'POST'])
def process_request_get_experiment_code():
    print("STARTED")
    # Get the ID for the experiment
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    experiment_id = data.get("experiment_id", None)
    print("Code requested (Experiment ID: " + str(experiment_id) + ")")

    # Check for the experiment ID
    if (experiment_id is None):
        return jsonify({'error': 'No experiment ID provided'}), 400

    # Check for the experiment ID
    if (not isinstance(experiment_id, str)):
        experiment_id = str(experiment_id)

    # Load the experiment file, and get the path to the experiment
    experiments_data = None
    targetExperiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Load the experiments from the file
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return jsonify({'error': 'Could not load experiments file: ' + str(e)}), 500

        # Check for the experiment list
        if ("experiment_list" not in experiments_data):
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return jsonify({'error': 'Could not find "experiment_list" in experiments data.'}), 500

        # Find the experiment with the given ID
        for experiment in experiments_data["experiment_list"]:
            if (experiment["id"] == experiment_id):
                targetExperiment = experiment
                break

    # Check if the experiment was found
    if (targetExperiment is None):
        return jsonify({'error': 'Could not find experiment with ID: ' + str(experiment_id)}), 404

    # Get the path to the experiment
    experimentPath = targetExperiment.get("experiment_path", None)
    experimentId = targetExperiment.get("id", None)
    experimentNameShort = targetExperiment.get("experiment_name_short", None)
    experimentTotalCost = targetExperiment.get("cost_so_far", None)
    experimentCostBuildDebug = targetExperiment.get("total_cost_build_debug", None)
    experimentCostLLMProxy = targetExperiment.get("total_cost_llm_proxy", None)
    experimentRuntimeSeconds = targetExperiment.get("runtime_seconds", None)

    # Check if the experiment path was found
    if (experimentPath is None):
        return jsonify({'error': 'Could not find path for experiment with ID: ' + str(experiment_id)}), 404

    # Check if the experiment path exists
    if (not os.path.exists(experimentPath)):
        return jsonify({'error': 'The path for an experiment does not appear to exist on disk (ID: ' + str(experiment_id)} + ")"), 404

    # Load the 'history.json' file from the experiment path
    historyFilename = os.path.join(experimentPath, "history.json")
    historyData = None
    try:
        with open(historyFilename, "r") as f:
            historyData = json.load(f)
    except Exception as e:
        print("ERROR: Could not load history file: " + str(e))
        return jsonify({'error': 'Could not load history file: ' + str(e)}), 500

    # Get the changelog in the metadata
    metadata = historyData.get("metadata", None)
    change_log = None
    if (metadata is not None):
        change_log = metadata.get("change_log", None)

    # Get the 'history' key (a list)
    history = historyData.get("history", None)
    if (history is None) or (not isinstance(history, list)) or (len(history) == 0):
        return jsonify({'error': 'Could not find "history" key in history file.'}), 500

    # Get the last element in the history list
    lastStep = history[-1]
    instruction_str = lastStep.get("instruction_str", None)
    requirements = lastStep.get("requirements", None)
    code = lastStep.get("code", None)
    exec_result = lastStep.get("exec_result", None)
    if (exec_result is not None) and (type(exec_result) == list):
        # Get the last element
        exec_result = exec_result[-1]
    results = None
    log = None
    llm_proxy_usage = None
    if (exec_result is not None) and ("results_json" in exec_result):
        results = exec_result["results_json"]
    if (exec_result is not None) and ("log" in exec_result):
        log = exec_result["log"]
    if (exec_result is not None) and ("llm_proxy_usage" in exec_result):
        llm_proxy_usage = exec_result["llm_proxy_usage"]

    codeblock_names = lastStep.get("codeblock_names", None)

    # Pack
    response_data = {
        'experiment_id': experimentId,
        'experiment_name_short': experimentNameShort,
        'instruction_str': instruction_str,
        'codeblock_names': codeblock_names,
        'requirements': requirements,
        'code': code,
        'results': results,
        'llm_proxy_usage': llm_proxy_usage,
        'log': log,
        "cost_total": experimentTotalCost,
        "cost_build_debug": experimentCostBuildDebug,
        "cost_llm_proxy": experimentCostLLMProxy,
        "runtime_seconds": experimentRuntimeSeconds,
        "change_log": change_log
    }

    return jsonify(response_data), 200


# PDF Report serving
# When getting a url request of the kind /pdfreport/<experiment_id>, this function will serve the PDF report for the experiment with the given ID.
@app.route('/pdfreport/<experiment_id>', methods=['GET'])
def serve_pdf_report(experiment_id):
    print("SERVING PDF REPORT (" + str(experiment_id) + ")")
    # Open the experiment list, to find the path for this experiment
    experiment_data = None
    targetExperiment = None
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        # Load the experiments from the file
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiment_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return jsonify({'error': 'Could not load experiments file: ' + str(e)}), 500

        # Check for the experiment list
        if ("experiment_list" not in experiment_data):
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return jsonify({'error': 'Could not find "experiment_list" in experiments data.'}), 500

        # Find the experiment with the given ID
        for experiment in experiment_data["experiment_list"]:
            if (experiment["id"] == experiment_id):
                targetExperiment = experiment
                break

    # Check if the experiment was found
    if (targetExperiment is None):
        return jsonify({'error': 'Could not find experiment with ID: ' + str(experiment_id)}), 404

    # Get the path to the experiment
    experimentPath = targetExperiment.get("experiment_path", None)
    experimentId = targetExperiment.get("id", None)

    # Check if the experiment path was found
    if (experimentPath is None):
        return jsonify({'error': 'Could not find path for experiment with ID: ' + str(experiment_id)}), 404

    # Check if the experiment path exists
    if (not os.path.exists(experimentPath)):
        return jsonify({'error': 'The path for an experiment does not appear to exist on disk (ID: ' + str(experiment_id)} + ")"), 404

    # Check if the PDF report exists
    pdfReportFilename = os.path.join(experimentPath, "report.pdf")
    if (not os.path.exists(pdfReportFilename)):
        # Try the back-off filename
        pdfReportFilename = os.path.join(experimentPath + "/report/", "report.pdf")
        if (not os.path.exists(pdfReportFilename)):
            return jsonify({'error': 'The PDF report for the experiment does not appear to exist on disk (ID: ' + str(experiment_id)} + ")"), 404

    # Load the file (in binary)
    pdfReportData = None
    with open(pdfReportFilename, "rb") as f:
        pdfReportData = f.read()

    # Send the file
    from flask import Response
    return Response(pdfReportData, mimetype='application/pdf')


# Get a list of all the papers in the PaperStore
@app.route('/getpaperlist', methods=['GET'])
def get_papers():
    # Get the PaperStore
    paper_list = get_papers_local()

    # Return
    response_data = {
        'paper_list': paper_list
    }
    return jsonify(response_data), 200

def get_papers_local():
    # Get the PaperStore
    paperStore = PaperStore()
    # Get the list of papers
    paper_index = paperStore.get_paper_index()
    # Filter to include only highly relevent metadata
    paper_list = []
    for paper_id, paper_metadata in paper_index.items():
        packed = {
            "arxiv_id": paper_metadata.get("arxiv_id", ""),
            "title": paper_metadata.get("title", ""),
            "authors": paper_metadata.get("authors", ""),
            "year": paper_metadata.get("year", ""),
            "date_added": paper_metadata.get("date_added", ""),
            "source_token_count_estimate": paper_metadata.get("source_token_count_estimate", 0),
            "topics": paper_metadata.get("topics", [])
        }

        paper_list.append(packed)

    return paper_list


# App route: Add a new paper to the PaperStore.  This is a POST request.
@app.route('/addpaper', methods=['POST'])
def add_paper():
    # Get the JSON data (which should include `arxiv_paper_id`)
    data = request.get_json()
    if (not data):
        return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

    # Get the arXiv paper ID
    arxiv_paper_id = data.get("arxiv_paper_id", None)
    if (arxiv_paper_id is None):
        return jsonify({'success': False, 'error': 'No arXiv paper ID provided'}), 400

    # If it's a URL, try to extract the arXiv ID
    if ("arxiv.org" in arxiv_paper_id):
        # Split the URL, extract everything after the last slash
        arxiv_paper_id = arxiv_paper_id.split("/")[-1]
        # Remove .pdf, if it exists
        if (".pdf" in arxiv_paper_id):
            arxiv_paper_id = arxiv_paper_id.replace(".pdf", "")

    topics = []
    if ("topic" in data):
        topics.append(data["topic"])

    # Try to add the paper to the paper store
    success = None
    errorStr = ""
    try:
        paperStore = PaperStore()
        success, errorStr, paper_metadata = paperStore.add_arxiv_paper(arxiv_paper_id, topics=topics)
    except Exception as e:
        return jsonify({'success': False, 'error': 'Could not add paper: ' + str(e)}), 500

    # Return
    if (success):
        paper_title = paper_metadata.get("title", "Unknown Title")
        paper_authors = paper_metadata.get("authors", "Unknown Authors")
        paper_year = paper_metadata.get("year", "Unknown Year")
        response = {
            "success": True,
            "arxiv_id": arxiv_paper_id,
            "title": paper_title,
            "authors": paper_authors,
            "year": paper_year,
            "topics": topics
        }
        return jsonify(response), 200
    else:
        return jsonify({'success': False, 'error': 'There was an error when adding this paper. ' + str(errorStr)}), 500


#
#   Ideation
#
# Get a list of all the papers in the PaperStore
@app.route('/getidealist', methods=['GET'])
def get_idea_list():
    # Get the IdeaStore
    ideaStore = IdeaStore()
    # Get the list of ideas
    all_ideas = ideaStore.get_all_ideas()

    # TODO: Include some filtering?

    # Return
    response_data = {
        'idea_list': all_ideas
    }
    return jsonify(response_data), 200

# Get a specific idea
@app.route('/getidea/<id>', methods=['GET'])
def get_idea_single(id):
    # Get the IdeaStore
    ideaStore = IdeaStore()
    # Get the list of ideas
    all_ideas = ideaStore.get_all_ideas()
    query_idea = None
    for idea in all_ideas:
        if (idea["id"] == id):
            query_idea = idea
            break

    # Return
    response_data = {
        'id': id,
        'idea': query_idea
    }
    return jsonify(response_data), 200


# Convert an idea into an experiment prompt
@app.route('/convertideatoexperimentprompt/<id>', methods=['GET'])
def convert_idea_to_experiment(id):
    # Get the IdeaStore
    ideaStore = IdeaStore()

    # Get the list of ideas
    model_str = "claude-3-5-sonnet-20241022"
    idea = ideaStore.get_idea_by_id(id)
    if (idea is None):
        return jsonify({'success': False, 'error': 'Could not find idea with ID: ' + str(id)}), 404

    experiment_prompt = ideaStore.convert_idea_to_experiment_prompt(idea, model_str)
    success = False
    if (experiment_prompt is not None) and ("success" in experiment_prompt) and (experiment_prompt["success"] == True):
        success = True
    experiment_prompt["success"] = success

    response_data = {}
    if (success):
        response_data = experiment_prompt

    else:
        response_data = {
            "success": False,
            "error": "Could not convert idea to experiment prompt."
        }

    return jsonify(response_data), 200


#
#   Meta-Analysis / Bulk Data Export
#

# Load the meta-analysis data from file
def get_metaanalysis_list():
    # Load the meta-analysis data
    metaanalysis_data = None
    max_attempts = 4
    for i in range(0, max_attempts):
        try:
            # Thread lock
            with THREAD_LOCK_FILE_METAANALYSIS_JSON:
                with open(FILENAME_METAANALYSIS_LIST, "r") as f:
                    metaanalysis_data = json.load(f)
            return metaanalysis_data
        except Exception as e:
            print("ERROR: Could not load meta-analysis data: " + str(e))
            time.sleep(0.5)

    return []

def add_metaanalysis_entry(metaanalysis_entry):
    # Load the meta-analysis data
    metaanalysis_data = get_metaanalysis_list()

    # Thread lock
    with THREAD_LOCK_FILE_METAANALYSIS_JSON:
        # Add the new entry
        metaanalysis_data.append(metaanalysis_entry)

        # Save the new data
        try:
            print("Saving meta-analysis entry...")
            with open(FILENAME_METAANALYSIS_LIST, "w") as f:
                json.dump(metaanalysis_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save meta-analysis data: " + str(e))
            return False

    return

# App Route: Just get all the previously saved meta-analysis entries from the file
@app.route('/metaanalysis-list', methods=['GET'])
def metaanalysis_list():
    # Load the meta-analysis data
    metaanalysis_data = get_metaanalysis_list()

    # Return
    response_data = {
        'metaanalysis_list': metaanalysis_data
    }
    return jsonify(response_data), 200


# App route: Get a list of all possible valid batch runs for the meta-analysis
@app.route('/metaanalysis-batchruns-list', methods=['GET'])
def metaanalysis_batchruns_list():
    # Get the list of all batch runs
    batch_prefixes_result = find_experiment_prefixes_for_metaanalysis(FILENAME_EXPERIMENTS)
    batches = []
    multi_run_experiments = {}
    if (batch_prefixes_result != None) and (batch_prefixes_result["success"] == True):
        batches = batch_prefixes_result["batches"]
        multi_run_experiments = batch_prefixes_result["multi_run_experiments"]

    # Return
    response_data = {
        'batches': batches,
        'multi_run_experiments': multi_run_experiments
    }
    return jsonify(response_data), 200


# App route: Download a specific meta-analysis file
@app.route('/metaanalysis-download/<filename>', methods=['GET'])
def metaanalysis_download(filename):
    filenameSanitized = "metaanalysis/" + filename

    # Check if the file exists
    if (not os.path.exists(filenameSanitized)):
        return jsonify({'error': 'File does not exist: ' + str(filename)}), 404

    # Load the file
    with open(filenameSanitized, "rb") as f:
        file_data = f.read()

    # Send the file
    from flask import Response
    return Response(file_data, mimetype='text/tab-separated-values')


# Wrapper for `perform-metaanalysis` that also saves the results to a file
#def perform_metaanalysis(filenameOut:str, experiment_filename_in:str, experiment_prefix_to_extract:str, specific_experiments_to_analyze:list=None, path_for_secondary_experiment_verification:str=None):
def perform_metaanalysis_wrapper(user_notes:str, bulk_experiment_run_to_analyze, filenameOutPrefix:str, experiment_filename_in:str, experiment_prefix_to_extract:str, specific_experiments_to_analyze:list=None, path_for_secondary_experiment_verification:str=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Perform the meta-analysis
    result = perform_metaanalysis(filenameOutPrefix, experiment_filename_in, experiment_prefix_to_extract, specific_experiments_to_analyze, path_for_secondary_experiment_verification)

    # Save the result to a file
    if (result is not None) and (result["success"] == True):
        filename_bulk_report = result["filename_bulk_report"]
        filename_metaanalysis_report = result["filename_metaanalysis_report"]
        filename_metaanalysis_report_json = result["filename_metaanalysis_report_json"]

        # Add the meta-analysis entry
        metaanalysis_entry = {
            "filename_bulk_report": filename_bulk_report,
            "filename_metaanalysis_report": filename_metaanalysis_report,
            "filename_metaanalysis_report_json": filename_metaanalysis_report_json,
            "batch_run": experiment_prefix_to_extract,
            "bulk_experiment_run": bulk_experiment_run_to_analyze,
            "bulk_experiment_run_files": specific_experiments_to_analyze,
            "timestamp": timestamp,
            "notes": user_notes,
        }
        add_metaanalysis_entry(metaanalysis_entry)

    return result


# App route: Perform a new meta-analysis/bulk data report
@app.route('/metaanalysis-bulkreport', methods=['POST'])
def metaanalysis():
    import time
            # payload = {
            #     'batch_run_to_analyze': batch_run_to_analyze,
            #     'bulk_experiment_run_to_analyze': bulk_experiment_run_to_analyze,
            #     'export_filename': export_filename
            # }

    # Get the JSON data
    data = request.get_json()
    if (not data):
        return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

    # # Get the arXiv paper ID
    # arxiv_paper_id = data.get("arxiv_paper_id", None)
    # if (arxiv_paper_id is None):
    #     return jsonify({'success': False, 'error': 'No arXiv paper ID provided'}), 400

    # Unpack
    batch_run_to_analyze = data.get("batch_run_to_analyze", None)
    bulk_experiment_run_to_analyze = data.get("bulk_experiment_run_to_analyze", None)
    bulk_experiment_filenames = data.get("bulk_experiment_files", [])
    user_notes = data.get("user_notes", "")

    # Try to run the analysis and generate the export
    success = None
    errorStr = ""
    metaanalysis = None
    try:
        # Make the metaanalysis/ directory if it doesn't exist
        if (not os.path.exists("metaanalysis/")):
            os.makedirs("metaanalysis/")

        # Check which case (batch run or bulk experiment run) we are dealing with
        if (batch_run_to_analyze is not None):
            # Perform the batch meta-analysis

            # Filename to export
            filenameOutPrefix = "metaanalysis/report." + batch_run_to_analyze + ".report" + time.strftime("%Y-%m-%d-%H-%M-%S")

            print("Performing meta-analysis for batch run: " + str(batch_run_to_analyze))


            #result = perform_metaanalysis(filenameOut, FILENAME_EXPERIMENTS, batch_run_to_analyze, path_for_secondary_experiment_verification=None)
            # Spawn meta-analysis in separate thread
            #metaanalysis_thread = threading.Thread(target=perform_metaanalysis, args=(filenameOut, FILENAME_EXPERIMENTS, batch_run_to_analyze, None, None))
            #metaanalysis_thread = threading.Thread(target=perform_metaanalysis_wrapper, args=(user_notes, filenameOut, FILENAME_EXPERIMENTS, batch_run_to_analyze, None, None))
            metaanalysis_thread = threading.Thread(target=perform_metaanalysis_wrapper, args=(user_notes, None, filenameOutPrefix, FILENAME_EXPERIMENTS, batch_run_to_analyze, None, None))
            metaanalysis_thread.start()

            # This will take a while -- let the user know
            metaanalysis_result = {
                "message": "Performing meta-analysis for batch run: " + str(batch_run_to_analyze) + " -- this may take a few minutes.  Meta-analysis file will be available when completed.",
                "filename_prefix": filenameOutPrefix
            }
            return jsonify(metaanalysis_result), 202

        elif (bulk_experiment_run_to_analyze is not None):
            # Perform the bulk experiment meta-analysis

            #def perform_metaanalysis(filenameOut:str, experiment_filename_in:str, experiment_prefix_to_extract:str, specific_experiments_to_analyze:list=None, path_for_secondary_experiment_verification:str=None):
            filenameOutPrefix = "metaanalysis/report." + bulk_experiment_run_to_analyze + ".report" + time.strftime("%Y-%m-%d-%H-%M-%S")

            print("Performing meta-analysis for bulk experiment run: " + str(bulk_experiment_run_to_analyze))

            # Spawn meta-analysis in separate thread
            #metaanalysis_thread = threading.Thread(target=perform_metaanalysis, args=(filenameOut, FILENAME_EXPERIMENTS, None, bulk_experiment_filenames, None))
            #metaanalysis_thread = threading.Thread(target=perform_metaanalysis_wrapper, args=(user_notes, filenameOut, FILENAME_EXPERIMENTS, None, bulk_experiment_filenames, None))
            metaanalysis_thread = threading.Thread(target=perform_metaanalysis_wrapper, args=(user_notes, bulk_experiment_run_to_analyze, filenameOutPrefix, FILENAME_EXPERIMENTS, None, bulk_experiment_filenames, None))
            metaanalysis_thread.start()

            # This will take a while -- let the user know
            metaanalysis_result = {
                "message": "Performing meta-analysis for bulk experiment run: " + str(bulk_experiment_run_to_analyze) + " -- this may take a few minutes.  Meta-analysis file will be available when completed.",
                "filename_prefix": filenameOutPrefix
            }
            return jsonify(metaanalysis_result), 202



    except Exception as e:
        print("ERROR: Could not perform meta-analysis: " + str(e))
        return jsonify({'success': False, 'error': 'Could not add paper: ' + str(e)}), 500

    # Return
    if (success):
        response = {
            "success": True,
            "metaanalysis": metaanalysis
        }
        return jsonify(response), 200
    else:
        return jsonify({'success': False, 'error': 'There was an error when performing this meta-analysis. ' + str(errorStr)}), 500


#
#   Helpers
#

# Create a blank experiments filename
def initialize_blank_experiment_list():
    # Check for existing file
    if (os.path.exists(FILENAME_EXPERIMENTS)):
        print("Experiments file already exists.")
        return

    # Create a blank experiments file
    experiments_data = {
        "metadata": {},
        "experiment_list": []
    }

    # Save the experiments data
    try:
        with open(FILENAME_EXPERIMENTS, "w") as f:
            json.dump(experiments_data, f, indent=4)
    except Exception as e:
        print("ERROR: Could not save experiments file: " + str(e))
        return {"success": False, "error": "Could not save experiments file: " + str(e)}

    print("Created blank experiments file: " + str(FILENAME_EXPERIMENTS))


# Check experiment list
# This runs once, right when the program starts -- any experiments that were marked as 'running' will be marked as 'interrupted' if the server was restarted.
def mark_running_experiments_as_interrupted():
    # Thread lock
    print("Fresh start: Checking experiments file for experiments listed as 'running', which should be set to 'interrupted'...")
    with THREAD_LOCK_FILE_ALL_EXPERIMENTS_JSON:
        count = 0

        # Load all the experiments
        experiment_data = None
        try:
            with open(FILENAME_EXPERIMENTS, "r") as f:
                experiments_data = json.load(f)
        except Exception as e:
            print("ERROR: Could not load experiments file: " + str(e))
            return {"success": False, "error": "Could not load experiments file: " + str(e)}

        # Check for the experiment list
        if ("experiment_list" not in experiments_data):
            print("ERROR: Could not find 'experiment_list' in experiments data.")
            return {"success": False, "error": "Could not find 'experiment_list' in experiments data."}

        # Go through every experiment -- if it's status is 'running', change it to 'interrupted'
        for experiment in experiments_data["experiment_list"]:
            if (experiment["status"] == STATUS_RUNNING):
                experiment["status"] = STATUS_INTERRUPTED
                count += 1

        # Save the updated experiments data
        try:
            with open(FILENAME_EXPERIMENTS, "w") as f:
                json.dump(experiments_data, f, indent=4)
        except Exception as e:
            print("ERROR: Could not save experiments file: " + str(e))
            return {"success": False, "error": "Could not save experiments file: " + str(e)}

        print("Marked " + str(count) + " 'running' experiments as 'interrupted'.")




#
#   Main Server Entry-Point
#

# Start the background worker thread
worker_thread = threading.Thread(target=task_worker, daemon=True)
worker_thread.start()

if __name__ == '__main__':
    # Check/validate the experiment list file
    initialize_blank_experiment_list()
    # If the server was interrupted with experiments running, mark those running experiments as 'interrupted'
    mark_running_experiments_as_interrupted()

    # Critical error check -- make sure all the experiment IDs are unique (if not, stop the server -- otherwise the worker thread will get stuck spawning the same experiment, and cost a lot of money)
    all_unique_result = ensure_all_experiment_ids_unique()
    if (all_unique_result == False):
        print("ERROR: Could not ensure all experiment IDs are unique. Stopping.")
        # Signal to the worker thread to stop
        EVENT_CRITICAL_STOP.set()
        worker_thread.join()
        # Exit
        sys.exit(1)

    # Run the server on port 5001
    app.run(port=5001, debug=False)
