# MetaAnalysis.py
# A postprocessing script to extract a set of experiments (starting with a given prefix) to a TSV file


import os
import json
import time
import re

import concurrent.futures

from ExtractionUtils import *


def do_metaanalysis_prompt(experiment_results:list, idea, operationalization, model_str:str="claude-3-7-sonnet-20250219", max_tokens:int=8000, temperature=0.0):

    def mkPrompt(experiment_results:list, idea, operationalization):
        prompt = "You are ScientistGPT, the most capable automated scientific reasoning system ever created.  You can use your enormous intellect to solve any problem, and always do so in a detailed, correct, faithful way, with integrity.\n"
        prompt += "Previously, you designed and ran a series of experiments centered around a particular idea/topic, though (in an effort to increase success), each implementation of that experiment was slightly different.\n"
        prompt += "This is a meta-analysis step: I'll show you the results of the experiments that were run, and your job is to analyze them and draw larger-scale conclusions.\n"
        prompt += "\n"
        prompt += "# Output\n"
        prompt += "You will be asked to analyze all the experiments below, which were run based on the same original idea/topic, and provide a meta-analysis.  The components of the meta-analysis are:\n"
        prompt += "1. hypothesis (str): What hypothesis (either implicit or explicit) was tested by these experiments?\n"
        prompt += "2. support_hypothesis_count (int): How many of the experiment runs support this hypothesis?\n"
        prompt += "3. refute_hypothesis_count (int): How many of the experiment runs refute this hypothesis?\n"
        prompt += "4. inconclusive_hypothesis_count (int): How many of the experiment runs are inconclusive with respect to this hypothesis?\n"
        prompt += "5. detailed_summary (str): Provide a detailed natural language summary/meta-analysis of the overall results and conclusions that can be drawn from this suite of experiments.\n"
        prompt += "\n"

        prompt += "# Idea and Operationalization/Plan\n"
        prompt += "For reference, the original idea and operationalization/plan are below:\n"
        prompt += "Idea:\n"
        prompt += "```\n"
        prompt += json.dumps(idea, indent=4) + "\n"
        prompt += "```\n"
        prompt += "Operationalization/Plan:\n"
        prompt += "```\n"
        prompt += json.dumps(operationalization, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "# Experiments\n"
        prompt += "Here are the experiments that were run:\n"
        prompt += "```\n"
        prompt += json.dumps(experiment_results, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "# Output format\n"
        prompt += "Please provide the following information in JSON format:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "    \"experiment_name\": \"...\",\n"
        prompt += "    \"hypothesis\": \"...\",\n"
        prompt += "    \"support_refute_inconclusive_judgements\": [\n"
        prompt += "        {\n"
        prompt += "            \"specific_experiment_name\": \"...\",\n"
        prompt += "            \"brief_reasoning_for_judgement\": \"...\"\n"
        prompt += "            \"judgement\": \"support\"  # or \"refute\" or \"inconclusive\"\n"
        prompt += "        },\n"
        prompt += "        {\n"
        prompt += "            \"specific_experiment_name\": \"...\",\n"
        prompt += "            \"brief_reasoning_for_judgement\": \"...\"\n"
        prompt += "            \"judgement\": \"support\"  # or \"refute\" or \"inconclusive\"\n"
        prompt += "        }, ...\n"
        prompt += "    \"support_hypothesis_count\": 0,\n"
        prompt += "    \"refute_hypothesis_count\": 0,\n"
        prompt += "    \"inconclusive_hypothesis_count\": 0,\n"
        prompt += "    \"detailed_summary\": \"...\"\n"
        prompt += "}\n"
        prompt += "```\n"
        prompt += "NOTE: `experiment_name` should be the base name of the experiments.  For example, if the experiment names were `my-experiment-copy1`, `my-experiment-copy2`, `my-experiment-copy3`, etc., the base name should be `my-experiment`.\n"
        prompt += "SPECIAL NOTE: The 'support_refute_inconclusive_judgements' field is a list of dictionaries, intended for you to make accurate, reasoned judgements about each experiment in relation to the hypothesis.  It is critical that you base your judgements on an accurate, faithful interpretation of the results of each experiment relative to the stated hypothesis. Errors are very consequential.\n"
        prompt += "Do not hallucinate.\n"
        prompt += "Your JSON must be between code blocks (```), and must be correct, as it will be automatically extracted without human intervention.  You can write any text before or after the codeblock to help you think, but the content of the codeblock must be valid JSON in the format specified above.\n"

        return prompt


    # Make the prompt
    prompt = mkPrompt(experiment_results, idea, operationalization)
    responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=model_str, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

    # Try to run `determine_metaanalysis_classification`
    try:
        count_support = 0
        count_refute = 0
        count_inconclusive = 0
        if ("support_hypothesis_count" in responseJSON):
            count_support = responseJSON["support_hypothesis_count"]
        if ("refute_hypothesis_count" in responseJSON):
            count_refute = responseJSON["refute_hypothesis_count"]
        if ("inconclusive_hypothesis_count" in responseJSON):
            count_inconclusive = responseJSON["inconclusive_hypothesis_count"]

        classification = determine_metaanalysis_classification(count_support, count_refute, count_inconclusive)
        responseJSON["categorization"] = classification
    except Exception as e:
        print("Error determining meta-analysis classification: " + str(e))


    packed = {
        "meta-analysis": responseJSON,
        "cost": cost
    }
    return packed



def find_experiments_with_multiple_runs(experiments:list):
    # Look through the experiment data and find lists of experiments of the form "my-experiment-name-copy1", "my-experiment-name-copy2", etc.
    # Return a dictionary with the experiment name as the key, and a list of the copies as the value.
    multi_run_experiments = {}

    for experiment in experiments:
        # If the experiment name ends with "-copy" and a number (e.g. "-copy1", "-copy2", "-copy3", ..., "-copy25"), then it's a copy
        experiment_name = experiment["experiment_name_short"]
        fields = experiment_name.split("-")
        if (len(fields) < 2):
            continue
        if (fields[-1].startswith("copy")):
            # It's likely a copy -- extract everything after the "copy" string, and see if it's a number
            copy_number = fields[-1][4:]
            try:
                copy_number_int = int(copy_number)
                # It's a number -- add it to the dictionary
                experiment_name_base = "-".join(fields[:-1])
                if (experiment_name_base not in multi_run_experiments):
                    multi_run_experiments[experiment_name_base] = []
                multi_run_experiments[experiment_name_base].append(experiment_name)
            except:
                # Not a number -- don't add it
                pass

    return multi_run_experiments


def find_experiment_prefixes_for_metaanalysis(experiment_filename_in:str):
    errors = []

    # Read the experiments JSON file
    experimentData = {}
    load_attempts = 0
    try:
        with open(experiment_filename_in, "r") as f:
            experimentData = json.load(f)
    except Exception as e:
        load_attempts += 1
        if (load_attempts > 4):
            errors.append("ERROR: Unable to load the experiments JSON file after " + str(load_attempts) + " attempts.")
            errors.append("Error message: " + str(e))
            print("Errors:" + str(errors))
            return {"success": False, "prefixes": [], "errors": errors}
        else:
            print("Error loading experiments JSON file. Retrying in 2 seconds.")
            time.sleep(2)

    # Extract the experiments
    metadata = experimentData["metadata"]   # Currently empty
    experiments = experimentData["experiment_list"]

    # Extract the experiment batch names
    batches = []
    for experiment in experiments:
        if ("batch_name" not in experiment):
            continue

        batchName = experiment["batch_name"]
        # Extract the prefix
        if (batchName not in batches):        # Keeps them in order, compared to using a set
            batches.append(batchName)

    # Extract the experiments with multiple copies
    multi_run_experiments = find_experiments_with_multiple_runs(experiments)

    # Return
    packet = {
        "success": True,
        "batches": batches,
        "multi_run_experiments": multi_run_experiments,
        "errors": errors
    }
    return packet


def determine_metaanalysis_classification(count_support:int, count_refute:int, count_inconclusive:int):
    sum = count_support + count_refute + count_inconclusive
    if (sum <= 0):
        return "no information"

    # Criteria 1: If 2 or fewer 'support' or 'refute' experiments, then classify as "limited information"
    sum_support_refute = count_support + count_refute
    if (sum_support_refute <= 2):
        return "limited information"

    # Criteria 2: If 80%+ of experiments go to 'support' or 'refute', then classify as 'consistent (support)' or 'consistent (refute)'

    if (count_support / sum >= 0.8):
        return "consistent (support)"
    if (count_refute / sum >= 0.8):
        return "consistent (refute)"

    # Otherwise, classify as "mixed information"
    return "mixed information"


# NOTE: If the 'path_for_secondary_experiment_verification' is not None, then the script will copy the entire experiment directory to the specified path if the 'hypothesis_category' is not empty.
def perform_metaanalysis(filenameOutPrefix:str, experiment_filename_in:str, experiment_prefix_to_extract:str, specific_experiments_to_analyze:list=None, path_for_secondary_experiment_verification:str=None):
    errors = []
    summaries_for_metaanalysis = []

    # Check if the path exists -- if it does, stop
    ENABLE_COPYING = False
    if (path_for_secondary_experiment_verification != None):
        ENABLE_COPYING = True
        if (os.path.exists(path_for_secondary_experiment_verification)):
            # Check how many files are in it
            numFiles = len([name for name in os.listdir(path_for_secondary_experiment_verification)])
            if (numFiles > 0):
                errors.append("Path " + path_for_secondary_experiment_verification + " already exists and is not empty. Exiting.")
                errors.append("You should choose a different experiment output path.")
                print("Errors:" + str(errors))
                return {"success": False, "errors": errors}
        else:
            # Create the path
            print("Creating path " + path_for_secondary_experiment_verification)
            os.makedirs(path_for_secondary_experiment_verification)

    # Read the experiments JSON file
    experimentData = {}
    load_attempts = 0
    try:
        with open(experiment_filename_in, "r") as f:
            experimentData = json.load(f)
    except Exception as e:
        load_attempts += 1
        if (load_attempts > 4):
            errors.append("ERROR: Unable to load the experiments JSON file after " + str(load_attempts) + " attempts.")
            errors.append("Error message: " + str(e))
            print("Errors:" + str(errors))
            return {"success": False, "errors": errors}
        else:
            print("Error loading experiments JSON file. Retrying in 2 seconds.")
            time.sleep(2)


    # Extract the experiments
    metadata = experimentData["metadata"]   # Currently empty
    experiments = experimentData["experiment_list"]

    # Extract the experiments with a given prefix
    extracted = []
    if (specific_experiments_to_analyze == None):
        # Mode: Batch name
        for experiment in experiments:
            if ("batch_name" not in experiment):
                continue

            batchName = experiment["batch_name"]
            if batchName.startswith(experiment_prefix_to_extract):
                extracted.append(experiment)
        print("Found " + str(len(extracted)) + " experiments with prefix `" + experiment_prefix_to_extract + "`")

    else:
        # Mode: Specific experiments
        if (isinstance(specific_experiments_to_analyze, list)):
            for experiment in experiments:
                experimentName = experiment["experiment_name_short"]
                if (experimentName in specific_experiments_to_analyze):
                    extracted.append(experiment)
        else:
            errors.append("ERROR: specific_experiments_to_analyze should be a list of experiment names.")
            print("Errors:" + str(errors))
            return {"success": False, "errors": errors}

        print("Found " + str(len(extracted)) + " specific experiments to analyze.")



    # Now we'll extract just a few fields to a TSV file
    extractedFiltered = []
    #for experiment in extracted:
    from tqdm import tqdm
    for experiment in tqdm(extracted):
        id = experiment.get("id", "")
        batchName = experiment.get("batch_name", "")
        experimentName = experiment.get("experiment_name_short", "")
        originalIdeaDict = experiment.get("original_idea", None)
        originalIdea = ""
        if (originalIdeaDict is not None):
            originalIdea = originalIdeaDict.get("research_idea_short_description", "")
        original_idea_full = experiment.get("original_idea", "")
        operationalization = experiment.get("operationalization", "")
        runtimeMinutes = experiment.get("runtime_seconds", 0) / 60.0
        totalCost = experiment.get("cost_so_far", 0.0)
        numIterationsRun = experiment.get("num_iterations_run", 0)

        interestingResults = experiment.get("interesting_results", False)
        if (interestingResults == True):
            interestingResults = "1"
        else:
            interestingResults = "0"

        resultsSummary = experiment.get("results_summary_short", "")

        status = experiment.get("status", "")
        statusNumerical = 0
        if (status.startswith("completed")):
            statusNumerical = 1

        # Try to get more information from the completed experiment
        experimentPath = experiment.get("experiment_path", "")
        summary_full = ""
        summaryMedium = ""
        faithfullness_category = ""
        hypothesis_category = ""
        hypothesis = ""
        code = ""
        code_num_lines = ""
        code_num_tokens = ""
        if (len(experimentPath) > 0):
            # Try to read the more detailed summary of the results in the history
            detailed_results_summary = {}
            history = []
            filenameHistory = os.path.join(experimentPath, "history.json")
            try:
                if (os.path.exists(filenameHistory)):
                    with open(filenameHistory, "r") as f:
                        historyData = json.load(f)
                        if ("metadata" in historyData):
                            if ("summary_results" in historyData["metadata"]):
                                detailed_results_summary = historyData["metadata"]["summary_results"]
                                history = historyData["history"]
            except Exception as e:
                print("Error reading history file: " + str(e))
            if ("summary" in detailed_results_summary):
                summary_full = detailed_results_summary["summary"]
            if ("summary_medium" in detailed_results_summary):
                summaryMedium = detailed_results_summary["summary_medium"]
            if ("faithfullness_category" in detailed_results_summary):
                faithfullness_category = detailed_results_summary["faithfullness_category"]
            if ("hypothesis_category" in detailed_results_summary):
                hypothesis_category = detailed_results_summary["hypothesis_category"]
            if ("hypothesis" in detailed_results_summary):
                hypothesis = detailed_results_summary["hypothesis"]

            if (len(history) > 0):
                #print("History steps: " + str(len(history)))
                if (len(history) > 0):
                    # Try to get the most recent version of the code
                    for entry in history:
                        #print("Keys: " + str(entry.keys()))
                        if ("code" in entry):
                            candidateCode = entry["code"]
                            if (len(candidateCode) < 200):
                                # If the code is short, then something was likely wrong with the parsing -- so skip
                                pass
                            else:
                                code = candidateCode

        # Measure the length of the code (in lines, and in tokens)
        if (len(code) > 0):
            code_num_lines = str(len(code.split("\n")))
            code_num_tokens = str(countTokens(code))
            print("Code: " + str(code_num_tokens) + " tokens, " + str(code_num_lines) + " lines")
        else:
            print("No code parsed.")

        # Pack all this into a dictionary
        packed = {
            "id": id,
            "batch_name": batchName,
            "experiment_name": experimentName,
            "original_idea": originalIdea,
            "runtime_minutes": runtimeMinutes,
            "total_cost": totalCost,
            "num_iterations_run": numIterationsRun,
            "code_num_lines": code_num_lines,
            "code_num_tokens": code_num_tokens,
            "status": status,
            "status_numerical": statusNumerical,
            "interesting_results": interestingResults,
            "faithfullness_category": faithfullness_category,
            "hypothesis_category": hypothesis_category,
            "results_summary": resultsSummary,
            "summary_medium": summaryMedium,
            "hypothesis": hypothesis
        }

        extractedFiltered.append(packed)

        # Also pack one for the meta-analysis
        packed_for_metaanalysis = {
            "id": id,
            "batch_name": batchName,
            "experiment_name": experimentName,
            "original_idea_full": original_idea_full,
            "operationalization": operationalization,
            "results_summary": summary_full,
        }
        summaries_for_metaanalysis.append(packed_for_metaanalysis)


        # If the experiment 'hypothesis_category' is not empty, then also copy the entire experiment directory to the experiment output path for verification.
        if (ENABLE_COPYING == True):
            if (len(hypothesis_category) > 0):
                # Copy the entire experiment directory
                import shutil
                # For the name, extract everything after the last slash in the original experiment path
                #experimentOutputPath = os.path.join(path_for_secondary_experiment_verification, experimentPath.split("/")[-1])
                # Remove any trailing slashes from original path
                experimentPath1 = experimentPath.rstrip("/")
                # Also make subdirectories for the hypothesis categorory
                hypothesis_category_directory = hypothesis_category.replace(" ", "_")
                # Try to create the intermediate directory
                os.makedirs(path_for_secondary_experiment_verification + "/" + hypothesis_category_directory, exist_ok=True)
                experimentOutputPath = path_for_secondary_experiment_verification + "/" + hypothesis_category_directory + "/" + experimentPath1.split("/")[-1]
                # Create the output path
                #os.makedirs(experimentOutputPath, exist_ok=True)

                #experimentOutputPath = path_for_secondary_experiment_verification + "/" + experimentPath1.split("/")[-1]
                # Copy everything in the original path to the new path
                print("Copying " + experimentPath + " to " + experimentOutputPath)
                shutil.copytree(experimentPath, experimentOutputPath)

            else:
                print("Skipping " + experimentPath + " because hypothesis_category is empty")


    # Write to a TSV file
    header = ["id", "batch_name", "experiment_name", "original_idea", "runtime_minutes", "total_cost", "num_iterations_run", "code_num_lines", "code_num_tokens", "status", "status_numerical", "interesting_results", "faithfullness_category", "hypothesis_category", "results_summary", "summary_medium", "hypothesis"]
    filenameOutBulk = filenameOutPrefix + ".bulk.tsv"
    with open(filenameOutBulk, "w") as f:
        f.write("\t".join(header) + "\n")
        for experiment in extractedFiltered:
            line = [str(experiment[field]) for field in header]
            f.write("\t".join(line) + "\n")
    print("Wrote extracted experiments to " + filenameOutBulk)


    # Do the meta-analysis parts
    filenameOutMetaAnalysisJSON = filenameOutPrefix + ".meta-analysis.json"
    filenameOutMetaAnalysisTSV = filenameOutPrefix + ".meta-analysis.tsv"

    meta_analysis_groups = {}
    for experiment in summaries_for_metaanalysis:
        operationalization_str = ""
        if ("operationalization" in experiment):
            # Convert the operationalization JSON to a hashable string
            operationalization_str = json.dumps(experiment["operationalization"], sort_keys=True)

        if (len(operationalization_str) == 0):
            continue

        if (operationalization_str not in meta_analysis_groups):
            meta_analysis_groups[operationalization_str] = []

        meta_analysis_groups[operationalization_str].append(experiment)

    print("Grouped " + str(len(summaries_for_metaanalysis)) + " experiments into " + str(len(meta_analysis_groups)) + " groups for meta-analysis.")

    # Now, for each group, prompt for a meta-analysis
    meta_analysis_out = []
    meta_analysis_groups_sanitized = []
    for meta_analysis_group in meta_analysis_groups:
        print("Group: " + str(meta_analysis_group))
        experiments_in_group = meta_analysis_groups[meta_analysis_group]

        if (len(experiments_in_group) == 0):
            print("No experiments -- skipping.")
            continue

        # Get the idea and the operationalization (from just the first one)
        idea = experiments_in_group[0]["original_idea_full"]
        operationalization = experiments_in_group[0]["operationalization"]

        # Now, remake a version of the list, that doesn't include the 'original_idea_full' and 'operationalization' in each of the experiment results
        experiments_sanitized = []
        for experiment in experiments_in_group:
            repacked = {
                "id": experiment["id"],
                "batch_name": experiment["batch_name"],
                "experiment_name": experiment["experiment_name"],
                "results_summary": experiment["results_summary"]
            }
            # Only add if the 'results_summary' is not empty
            if (len(repacked["results_summary"]) > 5):
                experiments_sanitized.append(repacked)

        group_sanitized = {
            "idea": idea,
            "operationalization": operationalization,
            "experiments": experiments_sanitized
        }

        meta_analysis_groups_sanitized.append(group_sanitized)


    # As above, but thread it
    def process_one_metaanalysis(metaanalysis_group_sanitized):
        experiments_in_group = metaanalysis_group_sanitized["experiments"]
        idea = metaanalysis_group_sanitized["idea"]
        operationalization = metaanalysis_group_sanitized["operationalization"]
        try:
            packed = do_metaanalysis_prompt(experiments_in_group, idea, operationalization)
            return metaanalysis_group_sanitized, packed
        except Exception as e:
            print("Error in meta-analysis: " + str(e))
            return None, None

    num_errors = 0
    total_cost = 0.0
    #max_threads = 4        # For testing (or low-throughput keys)
    max_threads = 10
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        # Submit all tasks concurrently.
        futures = [
            executor.submit(process_one_metaanalysis, sanitized_metaanalysis_group)
            for sanitized_metaanalysis_group in meta_analysis_groups_sanitized
        ]

        # Process tasks as they complete.
        for future in concurrent.futures.as_completed(futures):
            sanitized_metaanalysis_group, packed = future.result()
            if (packed is None):
                num_errors += 1
            else:
                cost = packed.get("cost", 0.0)
                total_cost += cost
                meta_analysis = packed.get("meta-analysis", {})

                # Add the meta-analysis to this group
                experiments_in_group = sanitized_metaanalysis_group["experiments"]
                all_ids = [experiment["id"] for experiment in experiments_in_group]
                all_batch_names = [experiment["batch_name"] for experiment in experiments_in_group]
                all_experiment_names = [experiment["experiment_name"] for experiment in experiments_in_group]
                idea = sanitized_metaanalysis_group["idea"]
                operationalization = sanitized_metaanalysis_group["operationalization"]

                meta_packed = {
                    "idea": idea,
                    "operationalization": operationalization,
                    "experiments": experiments_in_group,
                    "meta-analysis": meta_analysis,
                    "cost": cost,
                    "all_ids": all_ids,
                    "all_batch_names": all_batch_names,
                    "all_experiment_names": all_experiment_names
                }
                meta_analysis_out.append(meta_packed)

                # Write the meta-analysis to the file
                print("Writing meta-analysis to " + filenameOutMetaAnalysisJSON)
                with open(filenameOutMetaAnalysisJSON, "w") as f:
                    f.write(json.dumps(meta_analysis_out, indent=4) + "\n")


    # Write the meta-analysis to the file
    print("Writing meta-analysis to " + filenameOutMetaAnalysisJSON)
    with open(filenameOutMetaAnalysisJSON, "w") as f:
        f.write(json.dumps(meta_analysis_out, indent=4) + "\n")


    # Write the meta-analysis to a TSV file
    # Re-sort the meta-analysis by [`meta-analysis`][`experiment_name`] (if it exists)
    meta_analysis_out = sorted(meta_analysis_out, key=lambda x: x["meta-analysis"].get("experiment_name", ""))

    print("Writing meta-analysis to " + filenameOutMetaAnalysisTSV)
    with open(filenameOutMetaAnalysisTSV, "w") as f:
        f.write("experiment_name\tbatch_names\thypothesis\tsupport_hypothesis_count\trefute_hypothesis_count\tinconclusive_hypothesis_count\tcategorization\tdetailed_summary\texperiment_ids\n")
        for meta_analysis in meta_analysis_out:
            try:
                meta_analysis_results = meta_analysis.get("meta-analysis", "")
                experiment_name = meta_analysis_results.get("experiment_name", "")
                batch_names = set(meta_analysis.get("all_batch_names", []))
                batch_names = ", ".join(batch_names)
                hypothesis = meta_analysis_results.get("hypothesis", "")
                support_hypothesis_count = meta_analysis_results.get("support_hypothesis_count", -1)
                refute_hypothesis_count = meta_analysis_results.get("refute_hypothesis_count", -1)
                inconclusive_hypothesis_count = meta_analysis_results.get("inconclusive_hypothesis_count", -1)
                categorization = meta_analysis_results.get("categorization", "")
                detailed_summary = meta_analysis_results.get("detailed_summary", "")
                experiment_ids = ", ".join(meta_analysis.get("all_ids", []))

                one_line = str(experiment_name) + "\t" + str(batch_names) + "\t" + str(hypothesis) + "\t" + str(support_hypothesis_count) + "\t" + str(refute_hypothesis_count) + "\t" + str(inconclusive_hypothesis_count) + "\t" + str(categorization) + "\t" + str(detailed_summary) + "\t" + str(experiment_ids)
                # Sanitize for TSV -- remove newlines
                one_line = one_line.replace("\n", " ")
                f.write(one_line + "\n")
            except Exception as e:
                print("Error writing meta-analysis line: " + str(e))
                # Try to get at least the experiment name
                experiment_name = meta_analysis.get("experiment_name", "unknown")
                f.write("Error processing line (experiment: " + experiment_name + ", error: " + str(e) + ")\n")
    print("Wrote meta-analysis to " + filenameOutMetaAnalysisTSV)


    # Return
    packet = {
        "success": True,
        "filename_bulk_report": filenameOutBulk,
        "filename_metaanalysis_report": filenameOutMetaAnalysisTSV,
        "filename_metaanalysis_report_json": filenameOutMetaAnalysisJSON,
        "errors": errors
    }
    return packet



# Main
if __name__ == "__main__":
    pass
