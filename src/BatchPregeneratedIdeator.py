# BatchPregeneratedIdeator.py
# This script is used to pre-generate a very large number of ideas from papers, and store them in a file.
# The idea being that these ideas would later be filtered (to the most promising ideas), then run as experiments.

import os
import json
import threading
import random
import queue
import time
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

# Utility for querying LLMs
from ExtractionUtils import *

# Codeblock Store
from CodeBlockStore import *
# PaperStore
from PaperStore import *
# IdeaStore
from IdeaStore import *


#
#   Ideator
#

def ideator_basicv1_create_new_ideas(paper_ids_to_use:list, model_str:str, extra_payload:dict=None, ideaStore:IdeaStore=None):
    from datetime import datetime

    print("Creating new ideas...")
    startTime = datetime.now()

    # Load the paper store
    paperStore = PaperStore()
    # Get the latex source for the papers
    paperText = {}
    for paperID in paper_ids_to_use:
        success, paper_latex = paperStore.get_paper_latex(paperID)
        if (success == True):
            paperText[paperID] = paper_latex
        else:
            print("ERROR: Could not retrieve source for paper with ID: " + str(paperID))
            return {"success": False, "error": "Could not retrieve source for paper with ID: " + str(paperID)}

    if (len(paperText) == 0):
        print("ERROR: No papers were successfully loaded.")
        return {"success": False, "error": "No papers were successfully loaded."}

    conditionalGenerationStr = extra_payload.get("conditioning_text", "")
    deduplicationEnabled = False
    conditionOnCodeblocks = True
    num_ideas_to_generate = 5

    result = ideaStore.generate_new_ideas(paperText=paperText, additional_conditioning_text=conditionalGenerationStr, discourage_similar_to_existing_ideas=deduplicationEnabled, condition_on_codeblocks=conditionOnCodeblocks, model_str=model_str, num_ideas=num_ideas_to_generate, add_to_idea_store=False, mark_as_batch_idea=False, batch_name=None, metadata_in_separate_key=True)
    # Expected return
    # {
    #         "success": success,
    #         "idea_ids": idea_ids,
    #         "ideas": list_of_ideas,
    #         "cost": cost,
    #         "time_seconds": deltaTime
    # }

    # The ideas are stored into the IdeaStore automatically -- so here, just extract metadata (e.g. success, time, cost)
    success = result.get("success", False)
    time_seconds = result.get("time_seconds", 0)
    total_cost = result.get("cost", 0)
    ideas = result.get("ideas", [])

    # Add the cost to each idea
    if (len(ideas) > 0):
        idea_cost_per_idea = total_cost / len(ideas)
        time_sec_per_idea = time_seconds / len(ideas)
        # Round the idea and time cost to 4 decimal places
        idea_cost_per_idea = round(idea_cost_per_idea, 4)
        time_sec_per_idea = round(time_sec_per_idea, 4)
        for idea in ideas:
            if ("metadata" not in idea):
                idea["metadata"] = {}
            idea["metadata"]["cost_for_this_idea"] = idea_cost_per_idea
            idea["metadata"]["time_seconds_for_this_idea"] = time_sec_per_idea

    # Keep track of how long the request took to process
    deltaTime = datetime.now() - startTime
    print("Generated " + str(len(ideas)) + " ideas.")
    print("Task completed in " + str(deltaTime.total_seconds()) + " seconds.")

    result = {
        "success": success,
        "time_seconds": deltaTime.total_seconds(),
        "total_cost": total_cost,
        "ideas": ideas
    }
    return result


def ideator_targetedv1_create_new_ideas(paper_ids_to_use:list, model_str:str, extra_payload:dict=None, ideaStore:IdeaStore=None):
    from datetime import datetime

    print("Creating new ideas...")
    startTime = datetime.now()

    # Load the paper store
    paperStore = PaperStore()
    # Get the latex source for the papers
    paperText = {}
    for paperID in paper_ids_to_use:
        success, paper_latex = paperStore.get_paper_latex(paperID)
        if (success == True):
            paperText[paperID] = paper_latex
        else:
            print("ERROR: Could not retrieve source for paper with ID: " + str(paperID))
            return {"success": False, "error": "Could not retrieve source for paper with ID: " + str(paperID)}

    if (len(paperText) == 0):
        print("ERROR: No papers were successfully loaded.")
        return {"success": False, "error": "No papers were successfully loaded."}

    # Generate some new ideas
    conditionalGenerationStr = conditionalGenerationStr = extra_payload.get("conditioning_text", "")
    deduplicationEnabled = True     # Deduplication enabled for this ideator
    conditionOnCodeblocks = True
    num_ideas_to_generate = 5
    temperature = extra_payload.get("temperature", 0.0)
    batch_name = extra_payload.get("batch_name", None)

    result = ideaStore.generate_new_ideas(paperText=paperText, additional_conditioning_text=conditionalGenerationStr, discourage_similar_to_existing_ideas=deduplicationEnabled, condition_on_codeblocks=conditionOnCodeblocks, model_str=model_str, num_ideas=num_ideas_to_generate, add_to_idea_store=False, mark_as_batch_idea=True, batch_name=batch_name, metadata_in_separate_key=True, temperature=temperature)
    # Expected return
    # {
    #         "success": success,
    #         "idea_ids": idea_ids,
    #         "ideas": list_of_ideas,
    #         "cost": cost,
    #         "time_seconds": deltaTime
    # }

    # The ideas are stored into the IdeaStore automatically -- so here, just extract metadata (e.g. success, time, cost)
    success = result.get("success", False)
    time_seconds = result.get("time_seconds", 0)
    total_cost = result.get("cost", 0)
    ideas = result.get("ideas", [])

    # Add the cost to each idea
    if (len(ideas) > 0):
        idea_cost_per_idea = total_cost / len(ideas)
        time_sec_per_idea = time_seconds / len(ideas)
        # Round the idea and time cost to 4 decimal places
        idea_cost_per_idea = round(idea_cost_per_idea, 4)
        time_sec_per_idea = round(time_sec_per_idea, 4)
        for idea in ideas:
            if ("metadata" not in idea):
                idea["metadata"] = {}
            idea["metadata"]["cost_for_this_idea"] = idea_cost_per_idea
            idea["metadata"]["time_seconds_for_this_idea"] = time_sec_per_idea

    # Keep track of how long the request took to process
    deltaTime = datetime.now() - startTime
    print("Task completed in " + str(deltaTime.total_seconds()) + " seconds.")

    result = {
        "success": success,
        "time_seconds": deltaTime.total_seconds(),
        "total_cost": total_cost,
        "ideas": ideas
    }
    return result



#
#   Logic
#

def create_new_ideas(paper_ids_to_use:list, model_str:str, ideator_to_use:str, extra_payload:dict=None, ideaStore:IdeaStore=None):
    if (ideator_to_use == "basicv1"):
        return ideator_basicv1_create_new_ideas(paper_ids_to_use, model_str, extra_payload=extra_payload, ideaStore=ideaStore)

    elif (ideator_to_use == "targetedv1"):
        return ideator_targetedv1_create_new_ideas(paper_ids_to_use, model_str, extra_payload=extra_payload, ideaStore=ideaStore)


    else:
        print("ERROR: Unknown ideator: " + str(ideator_to_use))
        return {"success": False, "error": "Unknown ideator: " + str(ideator_to_use)}

    return {"success": False, "error": "Unknown error."}


# Generate the possible combinations of the paper list
def generate_paper_combinations(paper_ids:list, max_papers_per_idea:int=2):
    # Generate the 1..n combinations of papers ideas
    import itertools
    paper_combinations = []
    # Sort the paper IDs
    paper_ids_sorted = sorted(paper_ids)
    for num_papers_to_combine in range(1, max_papers_per_idea+1):
        print("Generating combinations of " + str(num_papers_to_combine) + " paper(s).")
        combinations_of_length = itertools.combinations(paper_ids_sorted, num_papers_to_combine)
        combinations_of_length = list(combinations_of_length)   # make the list
        # Sort each one
        #for idx, combination in enumerate(combinations_of_length):
        #    combinations_of_length[idx] = sorted(combination)
        print("  Found " + str(len(combinations_of_length)) + " combinations with " + str(num_papers_to_combine) + " paper(s).")
        paper_combinations.extend(combinations_of_length)
    print("Generated a total of " + str(len(paper_combinations)) + " combinations of papers.")

    return paper_combinations


# Hash a list of paper IDs into a single string
def hash_paper_id_list(paper_ids:list):
    # Sort the list
    paper_ids_sorted = sorted(paper_ids)
    # Convert to a string
    hashed_paper_ids = "---".join(paper_ids_sorted)
    return hashed_paper_ids


#
#   Main
#
def main(filename_ideastore_benchmark:str, conditioning_text:str, batch_name:str, model_str:str, DEBUG_MAX_IDEAS_TO_RUN:int=10):
    # Step 0: Load the API keys
    loadAPIKeys()

    # Step 1: Load the list of papers
    paperStore = PaperStore()

    # Get a list of paper topics, and choose only one topic
    paper_topics = paperStore.get_topic_list()
    print("Paper topics: " + str(paper_topics))

    # Ask the user what topic they want to use
    # Show a list (numbered) of the paper topics
    invalid_attempts = 0
    topic_number = -1
    for attempt_idx in range(0, 3):
        try:
            print("-"*40)
            print(" Paper topics")
            print("-"*40)
            for idx, topic in enumerate(paper_topics):
                print(str(idx) + ": " + topic)
            print("")
            print("Enter the number of the topic you want to use: ")
            topic_number = input()
            topic_number = int(topic_number)
            if (topic_number >= 0) and (topic_number < len(paper_topics)):
                break
            else:
                print("Invalid input.  Please enter a number between 0 and " + str(len(paper_topics) - 1) + ".")
                print("")
                invalid_attempts += 1
        except:
            print("Invalid input.  Please enter a number between 0 and " + str(len(paper_topics) - 1) + ".")
            print("")
            invalid_attempts += 1

    if (invalid_attempts >= 3):
        print("Too many invalid attempts. Exiting.")
        return

    selected_topic = paper_topics[topic_number]
    print("Selected topic: " + selected_topic)

    selected_topic_list = []
    if (isinstance(selected_topic, str)):
        selected_topic_list.append(selected_topic)
    elif (isinstance(selected_topic, list)):
        selected_topic_list = selected_topic


    # Step 2: Create the sets of papers (i.e. cross-product of papers -- single papers, and pairs of papers) to generate ideas from.
    # Get a list of papers for the selected topic(s)
    paper_ids = paperStore.get_paper_ids(topic_filter=selected_topic_list)
    print("Found " + str(len(paper_ids)) + " papers for the selected topic(s).")

    possible_paper_combinations = generate_paper_combinations(paper_ids, max_papers_per_idea=2)
    print("Generated " + str(len(possible_paper_combinations)) + " possible paper combinations.")


    # Step 3: Load the existing idea store
    ideaStore = IdeaStore(ideastore_filename=filename_ideastore_benchmark)
    all_existing_ideas = ideaStore.get_all_ideas()
    print("Found " + str(len(all_existing_ideas)) + " existing ideas in the idea store.")

    # Step 4: Filter out any sets of papers that already exist in the idea store (in case this script is run multiple times, or was interrupted, or if new papers were added to the paper list)
    # Assemble a list of existing paper combinations
    existing_paper_combinations = []
    for existing_idea in all_existing_ideas:
        existing_paper_ids = existing_idea.get("inspiring_paper_ids", None)
        #print("Existing paper IDs: " + str(existing_paper_ids))
        if (existing_paper_ids is None):
            continue
        hashed_paper_ids_str = hash_paper_id_list(existing_paper_ids)
        #print("Hashed paper IDs: " + hashed_paper_ids_str)
        existing_paper_combinations.append(hashed_paper_ids_str)

    # Turn it into a set to remove duplicates
    print("Found that existing ideas were generated from " + str(len(existing_paper_combinations)) + " unique paper combinations.")


    filtered_paper_ids = []
    for candidate_paper_ids in possible_paper_combinations:
        # Check whether the sets of papers in the `candidate_paper_ids` list are the same as any of the sets of papers in the `existing_paper_combinations` list
        candidate_paper_ids_hashed_str = hash_paper_id_list(candidate_paper_ids)
        if (candidate_paper_ids_hashed_str not in existing_paper_combinations):
            filtered_paper_ids.append(candidate_paper_ids)

    print("Filtered down from " + str(len(possible_paper_combinations)) + " possible paper sets to " + str(len(filtered_paper_ids)) + " paper sets that do not have existing ideas.")


    # Step 5: Generate ideas from the (remaining) sets of papers.
    #DEBUG_MAX_IDEAS_TO_RUN = -1  # Disabled -- run them all
    #DEBUG_MAX_IDEAS_TO_RUN = 5
    #DEBUG_MAX_IDEAS_TO_RUN = 50
    #DEBUG_MAX_IDEAS_TO_RUN = 100

    #FILTERING_ENABLED = True               # If enabled, at least one of the papers below must be in every combination of papers for it to be selected for ideation.
    FILTERING_ENABLED = False
    particularly_interesting_papers = [
        "2402.03244",
        "2401.16467",
        "2406.06769",
        "2406.06485",
        "2311.01468",
        "2310.05746",
        "2305.05091",
        "2305.17390",
        "2308.10144",
        "2304.02868",
        "2305.14879",
        "2311.05772",
        "2106.09578",
        "2007.09185",
        "2002.09127",
        "2005.00811",
    ]

    # Further filter the paper sets to only include those that contain particularly interesting papers
    if (FILTERING_ENABLED == True):
        filtered_interesting_paper_sets = []
        for candidate_paper_ids in filtered_paper_ids:
            # Check if at least one interesting paper is in this set of paper IDs
            found_interesting_paper = False
            for interesting_paper_id in particularly_interesting_papers:
                if interesting_paper_id in candidate_paper_ids:
                    found_interesting_paper = True
                    break
            if (found_interesting_paper == True):
                filtered_interesting_paper_sets.append(candidate_paper_ids)

        print("Filtered down to " + str(len(filtered_interesting_paper_sets)) + " paper sets that contain particularly interesting papers.")
        filtered_paper_ids = filtered_interesting_paper_sets
        time.sleep(5)

    # Set the random seed to the time
    random.seed(time.time())

    # Randomize the order of the paper sets to run
    randomized_paper_sets = filtered_paper_ids
    random.shuffle(randomized_paper_sets)

    #DEBUG: Limit the number of paper sets to run
    if (DEBUG_MAX_IDEAS_TO_RUN > 0):
        randomized_paper_sets = randomized_paper_sets[0:DEBUG_MAX_IDEAS_TO_RUN]

    # Run the ideas
    ideator_to_use = "basicv1"

    print("Running ideas from " + str(len(randomized_paper_sets)) + " paper sets.")
    time.sleep(2)


    def process_paper_set(paper_set_to_run, model_str, ideator_to_use, ideaStore, lock):
        """
        Function to process a single paper set, including adding the resulting ideas
        to the ideaStore (within a lock).
        """
        print(f"Running ideas from paper set: {paper_set_to_run}")
        try:
            # Assemble the extra payload
            extra_payload = {
                "conditioning_text": conditioning_text,
                "existing_ideas": ideaStore.get_all_ideas(),
                "temperature": 0.2,
                "batch_name": batch_name
            }

            result = create_new_ideas(paper_set_to_run, model_str, ideator_to_use, extra_payload=extra_payload, ideaStore=ideaStore)
            print(json.dumps(result, indent=4))
            print("")

            # Try to add to the idea store
            if result.get("success", False) == True:
                ideas = result.get("ideas", [])
                for idx, idea in enumerate(ideas):
                    print(f"Adding idea to the IdeaStore. ({idx+1} of {len(ideas)})")
                    with lock:
                        # Lock around add_idea to ensure thread safety
                        ideaStore.add_idea(idea)
        except Exception as e:
            print(f"ERROR: Could not run ideas for paper set: {paper_set_to_run}")
            print(e)
            traceback.print_exc()

        # Sleep for a bit (optional, if you still want that delay)
        time.sleep(1)


    MAX_WORKERS = 5    # Number of threads to run concurrently
    def run_in_threads(randomized_paper_sets, model_str, ideator_to_use, ideaStore):
        # Create a lock for the ideaStore
        lock = threading.Lock()
        from tqdm import tqdm
        # You can wrap the logic in a ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit a future for each paper set
            futures = [
                executor.submit(
                    process_paper_set,
                    paper_set_to_run,
                    model_str,
                    ideator_to_use,
                    ideaStore,
                    lock
                )
                for paper_set_to_run in randomized_paper_sets
            ]

            # If you want a progress bar that updates as each future completes:
            for future in tqdm(as_completed(futures), total=len(futures)):
                # Gather the results (or catch exceptions) if needed
                try:
                    future.result()  # This will re-raise any exception that occurred
                except Exception as e:
                    print("Exception in thread:", e)

    run_in_threads(randomized_paper_sets, model_str, ideator_to_use, ideaStore)



#
#   Batch Ideation
#
if __name__ == "__main__":
    print("Initializing...")

    # Model to use for ideation
    model_str = "claude-3-5-sonnet-20241022"

    # Filename of an ideastore to save these ideas to
    filename_ideastore_benchmark = "batch-generation-example-output.json"

    # Name for this batch of ideas
    batch_name = "my-test-batch-2024-03-01"

    # Add any special conditioning text for this batch of ideas
    conditioning_text = "RESEARCH METHODS: Important things to remember regarding research methods in this domain:\n"
    conditioning_text += "1. Agent performance on most text games is low, because these tasks tend to be hard for them.  Instead of expecting success (which is very rare, and infrequently happens on some environments, if ever), you should measure task progress in terms of the partial progress scores that most environments provide.\n"
    conditioning_text += "2. Similarly, remember that if an agent has separate training and evaluation periods, that (during evaluation) the memory of the agent should be reset to what it was at the end of training.  That way, it won't be using knowledge obtained in one evaluation episode for another evaluation episode. (Note that it can still record memories /during/ the evaluation episodes, but memories from one evaluation episode shouldn't be retained to another; only from training episodes -- unless there is some 'continual learning' framing to the research question).\n"
    conditioning_text += "3. There are separate train, development, and test sets for most environments.  The train set is used to train the agent, and the development set is used to evaluate it's performance at all times except during the final experiment.  No knowledge of the test set can leak into the design or tuning of the agent.\n"
    conditioning_text += "4. Generally mini-pilot experiments can run on only 2-3 episodes for fast debugging, up to 10 or 20 steps.  Pilot and full experiments should run on ~50 episodes, to the same number of steps (e.g. 25 or 50 steps).\n"
    conditioning_text += "5. Most environments provide a set of seeds for training, development, and testing.  If you randomly shuffle these lists of seeds (with a static seed, like 42, so this shuffle is repeatable across runs), then you will get a more representative cross-section of the environment's problems.  Environments are often parametrically generated, and just taking incremental seeds (i.e. 1, 2, 3, ...) rather than randomly ordered seeds (e.g. 103, 40, 97, ...) may generate very similar problems, and not be representative.\n"
    conditioning_text += "6. Remember to include appropriate baselines.  For example, an appropriate baseline for `Model A augmented with change X` is almost always `Model A without change X`, not a different model (like a random baseline).\n"
    conditioning_text += "DETAILS: Remember to be very explicit about including details in your experiment descriptions, particularly if your ideas are based off the input papers. The input papers are NOT available to follow-on stages, so your idea must be *SELF-CONTAINED*, and describe everything that is needed to implement it faithfully.\n"
    conditioning_text += "SCOPE: While you should use the provided codeblock templates, you should not feel entirely constrained by them -- anything that a language model can reasonably implement is fair game.  However, remember that the codeblocks are designed to be easy to implement, and that the more complex the code that a language model has to implement from scratch, the more likely it is to have bugs, or not work -- especially if it requires downloading external code.\n"
    conditioning_text += "AUTOMATED: The experiments that you create should be experiments that can be run in a fully-automated fashion, and not require human input.\n"

    # Maximum number of paper combinations to try.
    # i.e. 100 means try 100 combinations of papers. (Each paper combination typically generates 5 ideas)
    max_paper_combinations_to_run = 3       # Intentionally set to a very low number here

    main(filename_ideastore_benchmark=filename_ideastore_benchmark, conditioning_text=conditioning_text, batch_name=batch_name, model_str=model_str, DEBUG_MAX_IDEAS_TO_RUN=max_paper_combinations_to_run)