# ExperimentMaker.py


import os
import re
import tqdm
import difflib
from copy import deepcopy

from ExtractionUtils import *

from CodeBlockStore import *

LLM_PROXY_BASE_PATH = "llm-proxy/"

class ExperimentMaker():
    # Constructor
    def __init__(self, PATH_CODEBLOCKS):
        self.PATH_CODEBLOCKS = PATH_CODEBLOCKS

        # Instantiate the CodeBlockStore
        self.codeBlockStore = CodeBlockStore(PATH_CODEBLOCKS)

        pass

    # Create the initial code for an experiment.
    # Examples:
    # modelStr = "o1-mini"
    # codeblocksToCombine = ["Logger/Debugging", "OpenAI/Anthropic LLM Example", "Together.ai LLM Example", "Non-parametric Bootstrap Resampling"]
    # instructionStr = "Please create a program that creates a dataset of 20 2-digit multiplication problems, and tests two different LLM models on this dataset.  Show the average performance of each model (in terms of correctness), and whether the better model is statistically significantly better than the other."
    # combinedCodeblock = codeblockStore.combineCodeblocks(instructionStr, codeblocksToCombine, modelStr=modelStr, max_tokens=16384, temperature=0.0)
    def createExperiment(self, instructionStr:str, additionalInstructionStr:str, codeblocksToCombine:list, modelStr:str, max_tokens:int, temperature:float):
        # Create the combined codeblock
        combinedCodeblock = self.codeBlockStore.combineCodeblocks(instructionStr, codeblocksToCombine, modelStr=modelStr, max_tokens=max_tokens, temperature=temperature, additionalInstructionStr=additionalInstructionStr)
        return combinedCodeblock


    # Execute an experiment in a container
    def executeExperiment(self, codeStruct, basePath:str=None, max_runtime_seconds:int=600, apt_packages = ["git", "wget", "curl", "openjdk-17-jre"]):
        print("MODAL DEBUG: executeExperiment() started.... (basePath = " + str(basePath) + ")")
        # Get the code
        code = codeStruct["code"]
        # Get the requirements
        requirements = codeStruct["requirements"]
        # Get the supporting files
        supportingFiles = codeStruct["supporting_files"]

        # Run the code in a Modal container
        from modules.ModuleRunPythonInModal import ModuleRunPythonInModal
        moduleModal = ModuleRunPythonInModal()

        # Assemble the packet
        # Faux payload
        payload = {
            "input": {
                "python_version": "3.12",
                "requirements.txt": requirements,
                "code": code,
                "supporting_files": supportingFiles,
                "base_path": basePath,
                "max_runtime_seconds": max_runtime_seconds,
                "apt_packages": apt_packages
            }
        }

        # Run the action
        #result = moduleDocker.runAction(moduleDocker.ACTION_RUN_PROGRAM["name"], payload)
        result = moduleModal.runAction(moduleModal.ACTION_RUN_PROGRAM["name"], payload)

        # Print result
        print("Result:")
        print(json.dumps(result, indent=4))

        # Add the result to the codeStruct
        if ("exec_result" not in codeStruct):
            codeStruct["exec_result"] = []
        if ("output" in result):
            packedOutput = result["output"]
            # Also copy over 'errors'
            if ("errors" in result):
                packedOutput["execution_errors"] = result["errors"]
            # Store the output
            codeStruct["exec_result"].append(packedOutput)

        # Return
        print("MODAL DEBUG: executeExperiment() finished (basePath = " + str(basePath) + ")")
        return codeStruct


    # Run/Reflect An Experiment
    # This is the main function that runs an experiment, reflects on the results of the experiment, and generates new code to fix any issues.
    # max_container_llm_cost_usd: The maximum cost of the container that is allowed to be used for the LLM proxy server.  If the cost exceeds this amount, the code will receive an error.
    # NOTE: The experiment cost currently does not include the Modal container cost, since this is typically small.
    def runAndReflectExperiment(self, codeStructIn_:dict, modelStr:str, MAX_REFLECTIONS = 5, pathLogOutput:str="generated/", max_tokens:int=32000, max_container_llm_cost_usd:float=0.25, max_runtime_seconds=600, max_experiment_cost:float=0.00, follow_on_description=None, use_faithfulness_reflection:bool=False, hard_runtime_cutoff_seconds:float=60*60*6, temperature=0.0):
        history, historyPacked = self.runAndReflectExperimentWithPackedHistory(codeStructIn_, modelStr, MAX_REFLECTIONS, pathLogOutput, max_tokens, max_container_llm_cost_usd, max_runtime_seconds, max_experiment_cost=max_experiment_cost, follow_on_description=follow_on_description, use_faithfulness_reflection=use_faithfulness_reflection, hard_runtime_cutoff_seconds=hard_runtime_cutoff_seconds, temperature=temperature)
        return history

    def runAndReflectExperimentWithPackedHistory(self, codeStructIn_:dict, modelStr:str, MAX_REFLECTIONS = 5, pathLogOutput:str="generated/", max_tokens:int=32000, max_container_llm_cost_usd:float=0.25, max_runtime_seconds=600, max_runtime_seconds_pilot=600, max_experiment_cost:float=0.00, follow_on_description=None, use_faithfulness_reflection:bool=False, hard_runtime_cutoff_seconds:float=60*60*6, temperature=0.0):
        startTime = time.time()

        # Make sure the codeStructIn_ contains code
        if ("code" not in codeStructIn_):
            print("ERROR: The `codeStructIn_` dictionary must contain a `code` key.")
            return None, None

        # Step 3: Try to execute that experiment
        codeStructIn = {}
        codeStructIn["supporting_files"] = []
        # Copy all the rest of the keys over
        for key in codeStructIn_:
            codeStructIn[key] = codeStructIn_[key]

        # Add the `api_keys.donotcommit.json` file
        supportingFileAPIKeys = {"filename": "llm-proxy/api_keys.donotcommit.json", "contents": None}
        with open("api_keys.donotcommit.json", 'r') as file:
            supportingFileAPIKeys["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileAPIKeys)

        # Add the LLM proxy files
        # Proxy file 1: `llm-proxy-server.py`
        supportingFileLLMProxy = {"filename": "llm-proxy/llm-proxy-server.py", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "llm-proxy-server.py", 'r') as file:
            supportingFileLLMProxy["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxy)

        # Proxy file 2: `experiment-llm-cost.json`
        supportingFileLLMProxyCost = {"filename": "llm-proxy/experiment-llm-cost.json", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "experiment-llm-cost.json", 'r') as file:
            supportingFileLLMProxyCost["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxyCost)

        # Proxy file 3: `experiment-setup.json`
        supportingFileLLMProxySetup = {"filename": "llm-proxy/experiment-setup.json", "contents": None}
        # Automatically generate the experiment cost/setup file for the LLM proxy.
        # NOTE: This file can also be used to allow/disallow certain LLM models.
        experiment_llm_setup_json = {
            "notes": "This is an automatically-generated file that sets the maximum allowable cost to go through the LLM proxy server.",
            "max_cost_usd": max_container_llm_cost_usd
        }
        supportingFileLLMProxySetup["contents"] = json.dumps(experiment_llm_setup_json, indent=4)
        codeStructIn["supporting_files"].append(supportingFileLLMProxySetup)

        # Proxy file 4: The LLM library
        supportingFileLLMProxyLib = {"filename": "llm_proxy_usage.py", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "llm_proxy_usage.py", 'r') as file:
            supportingFileLLMProxyLib["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxyLib)

        # Add the common library of experimental functions
        supportingFileCommonLib = {"filename": "experiment_common_library.py", "contents": None}
        supportingFileCommonLib["contents"] = self.codeBlockStore.getCommonLibrary()
        codeStructIn["supporting_files"].append(supportingFileCommonLib)


        # Keep track of whether the cost limit has been exceeded
        cost_limit_exceeded = False

        # Keep a history
        history = []
        history.append(codeStructIn)
        historyPacked = {}

        # Keep track of the number of consecutive container errors.
        consecutive_container_errors = 0        # Keep track of consecutive container errors.  Exit if this exceeds a certain number.
        MAX_CONSECUTIVE_CONTAINER_ERRORS = 3     # The maximum number of consecutive container errors before exiting.
        container_failure = False
        hard_time_limit_reached = False
        # Run the code, and reflect on it's output.  Repeat until the model believes the execution is correct, and that it's fixed any issues.
        for i in range(MAX_REFLECTIONS):
            deltaTimeSeconds = time.time() - startTime
            print("-" * 80)
            print("Reflection " + str(i+1) + " of " + str(MAX_REFLECTIONS))
            print("Elapsed experiment time: " + str(round(deltaTimeSeconds, 2)) + " seconds (hard time limit: " + str(int(hard_runtime_cutoff_seconds)) + " seconds)")
            print("-" * 80)

            # Check the hard time limit
            if (deltaTimeSeconds >= hard_runtime_cutoff_seconds):
                print("ERROR: Exceeded the hard runtime cutoff of " + str(hard_runtime_cutoff_seconds) + " seconds (Current runtime: " + str(deltaTimeSeconds) + " seconds). Exiting.")
                hard_time_limit_reached = True
                break

            # Check what mode we're in -- MINI_PILOT, or something else.  If we're in MINI_PILOT mode, we'll use a shorter runtime.
            currentMode = "MINI_PILOT"
            if (len(history) > 1):
                lastHistoryStep = history[-1]
                if ("next_pilot_mode" in lastHistoryStep):
                    currentMode = lastHistoryStep["next_pilot_mode"]
            currentMaxRuntime = max_runtime_seconds
            if (currentMode == "MINI_PILOT"):
                currentMaxRuntime = max_runtime_seconds_pilot
            print("Current mode: " + currentMode)
            print("Current max runtime for this mode: " + str(currentMaxRuntime) + " seconds")

            # Collect all `retained_files` from the history, and add them to the supporting files.  `retained_files` are in the `exec_result` of each history step.
            retained_files = {}
            for histStep in history:
                if ("exec_result" in histStep):
                    for execResultStep in histStep["exec_result"]:
                        if ("retain_files" in execResultStep):
                            try:
                                for retained_filename in execResultStep["retain_files"].keys():
                                    retained_files[retained_filename] = execResultStep["retain_files"][retained_filename]
                            except Exception as e:
                                print("ERROR: Could not retain file from this step in history: " + str(e))

            print("Found " + str(len(retained_files)) + " retained files from the history.")

            # Remove any past `retained_files` from the supporting files
            supporting_files_before = len(codeStructIn["supporting_files"])
            codeStructIn["supporting_files"] = [x for x in codeStructIn["supporting_files"] if x["filename"] not in retained_files]
            print("Removed " + str(supporting_files_before - len(codeStructIn["supporting_files"])) + " retained files from the supporting files, that should be overwritten with new copies.")

            # Add the retained files to the supporting files
            print("Adding retained files to supporting files... (total files: " + str(len(retained_files)) + ")")
            for retained_filename in retained_files:
                print("Adding retained file to supporting files: " + retained_filename)
                contents = retained_files[retained_filename]
                if (not isinstance(contents, str)):
                    try:
                        contents = json.dumps(retained_files[retained_filename], indent=4)
                    except:
                        contents = str(retained_files[retained_filename])
                supportingFileRetained = {"filename": retained_filename, "contents": contents}
                codeStructIn["supporting_files"].append(supportingFileRetained)


            # Execute the experiment
            codeStructOut = self.executeExperiment(codeStructIn, basePath=pathLogOutput, max_runtime_seconds=currentMaxRuntime)

            # Early stopping -- look for consecutive container errors
            if ("exec_result" in codeStructOut):
                execResult = codeStructOut["exec_result"]
                if ("modal_container_completed" in execResult):
                    if (execResult["modal_container_completed"] == False):
                        print("ERROR: The Modal container did not complete successfully.")
                        consecutive_container_errors += 1
                    else:
                        consecutive_container_errors = 0
                else:
                    consecutive_container_errors = 0
            else:
                consecutive_container_errors = 0

            if (consecutive_container_errors >= MAX_CONSECUTIVE_CONTAINER_ERRORS):
                container_failure = True
                print("ERROR: Exceeded the maximum number of consecutive container errors (" + str(MAX_CONSECUTIVE_CONTAINER_ERRORS) + ").  Exiting.")
                break


            # Step 4: Reflect
            # Reflect on the code execution
            codeblockStore = CodeBlockStore(self.PATH_CODEBLOCKS)
            # Assemble a changelog for the debugger
            change_log = []
            for histStep1 in history:
                    # Deep copy
                histStep = deepcopy(histStep1)
                packedStep = {}
                packedStep["issues"] = []
                packedStep["summary_of_changes"] = []
                if ("issues" in histStep):
                    packedStep["issues"] = histStep["issues"]
                if ("summary_of_changes" in histStep):
                    packedStep["summary_of_changes"] = histStep["summary_of_changes"]
                if ("additional_simulated_code_issues" in histStep):
                    packedStep["additional_simulated_code_issues"] = histStep["additional_simulated_code_issues"]
                change_log.append(packedStep)

            reflectionCodeblock = codeblockStore.reflectCodeblocks(codeStructOut, modelStr=modelStr, max_tokens=max_tokens, temperature=temperature, follow_on_description=follow_on_description, max_runtime_seconds=currentMaxRuntime, change_log=change_log, use_faithfulness_reflection=use_faithfulness_reflection)
            history.append(reflectionCodeblock)

            # Make the reflection the new codeStructIn
            codeStructIn = reflectionCodeblock

            # Save
            # Check that the output directory exists exists
            if (pathLogOutput[-1] != "/"):
                pathLogOutput += "/"
            if (not os.path.exists(pathLogOutput)):
                os.makedirs(pathLogOutput)

            print(json.dumps(reflectionCodeblock, indent=4))
            print("Saving `" + str(pathLogOutput) + "/" + "reflectionCodeblock.json`...")

            with open(pathLogOutput + "reflectionCodeblock.json", 'w') as file:
                reflectedCodeblock1 = deepcopy(reflectionCodeblock)
                # Delete the 'supporting files' key
                if ("supporting_files" in reflectedCodeblock1):
                    del reflectedCodeblock1["supporting_files"]

                json.dump(reflectedCodeblock1, file, indent=4)

            # Save the history
            print("Saving `" + str(pathLogOutput) + "/" + "history.json`...")
            with open(pathLogOutput + "history.json", 'w') as file:
                sanitizedHistory = []
                for histStep1 in history:
                    # Deep copy
                    histStep = deepcopy(histStep1)

                    if ("supporting_files" in histStep1):
                        del histStep["supporting_files"]
                    sanitizedHistory.append(histStep)

                # Pack the history with some metadata
                # Metadata 1: Cost
                totalCost = 0
                for histStep in sanitizedHistory:
                    if ("cost" in histStep) and (type(histStep["cost"]) == float):
                        totalCost += histStep["cost"]
                # Metadata 2: Is the final reflection OK?
                isOk = False
                if ("is_ok" in reflectionCodeblock) and (reflectionCodeblock["is_ok"] == True):
                    isOk = True
                current_pilot_mode = None
                next_pilot_mode = None
                if ("current_pilot_mode" in reflectionCodeblock):
                    current_pilot_mode = reflectionCodeblock["current_pilot_mode"]
                if ("next_pilot_mode" in reflectionCodeblock):
                    next_pilot_mode = reflectionCodeblock["next_pilot_mode"]

                # Metadata 3: Total number of reflections
                numReflections = len(sanitizedHistory)
                # Metadata 4: The issues/changelog
                changeLog = []
                for histStep in sanitizedHistory:
                    packedStep = {}
                    packedStep["issues"] = []
                    packedStep["summary_of_changes"] = []
                    if ("issues" in histStep):
                        packedStep["issues"] = histStep["issues"]
                    if ("summary_of_changes" in histStep):
                        packedStep["summary_of_changes"] = histStep["summary_of_changes"]

                    changeLog.append(packedStep)
                # Metadata 5: Reflection time
                deltaTime = time.time() - startTime

                # Metadata 6: LLM Proxy cost
                # Get the 'exec_result' of the last history step
                lastHistoryStep = sanitizedHistory[-1]
                llm_proxy_total_cost = 0
                if ("exec_result" in lastHistoryStep):
                    for execResult in lastHistoryStep["exec_result"]:
                        if ("llm_proxy_usage" in execResult):
                            llm_proxy_usage_this_step = execResult["llm_proxy_usage"]
                            try:
                                llm_proxy_cost_this_step = llm_proxy_usage_this_step["metadata"]["total_cost_usd"]
                                llm_proxy_total_cost += llm_proxy_cost_this_step
                            except:
                                pass

                # Check for a specific error: Code parsing issues
                error_code_parsing_issue = False
                if ("error_code_parsing_issue" in reflectionCodeblock) and (reflectionCodeblock["error_code_parsing_issue"] == True):
                    print("ERROR: Code parsing issue detected.  Signaling to exit early at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    error_code_parsing_issue = True



                # Check whether the current stage is finished / check for an 'is_ok' key
                done = False
                if ("is_ok" in reflectionCodeblock) and (reflectionCodeblock["is_ok"] == True):
                    #print("*** Reflection has marked the code and execution as OK.  Exiting at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    # If we're in MINI_PILOT mode, and the reflection is OK, then move to PILOT mode.
                    # if (currentMode == "MINI_PILOT"):
                    #     # Here, we currently just have to trust that the LLM call successfully changes the mode from MINI_PILOT to PILOT.   # TODO: Add a manual check here.
                    #     done = False
                    # # If we're in PILOT mode, and the relfection is OK, do not move on to FULL_EXPERIMENT mode (we can stop here).
                    # if (currentMode == "PILOT"):
                    #     # Here, we currently just have to trust that the LLM call successfully changes the mode from MINI_PILOT to PILOT.   # TODO: Add a manual check here.
                    #     done = True # Temporary, to let the user manually start the full (expensive) experiments.
                    done = True # Added this check into the prompt -- so `is_ok` should only be True if the entire experiment is true. `is_ok_stage` should be true if just the stage is true.

                # Check if the cost limit has been exceeded
                if (totalCost >= max_experiment_cost):
                    cost_limit_exceeded = True

                # Pack the history with the metadata
                historyPacked = {}
                #metadata["experiment_building_agent_name"] = targetExperiment.get("experiment_building_agent_name", None)
                experiment_building_agent_name = "simple1"
                if (use_faithfulness_reflection == True):
                    experiment_building_agent_name += "simple1-with_faithfulness-reflection"

                historyPacked["metadata"] = {
                    "experiment_building_agent_name": experiment_building_agent_name,
                    "model_str": modelStr,
                    "temperature": temperature,
                    "max_reflections": MAX_REFLECTIONS,
                    "max_tokens": max_tokens,
                    "total_cost_build_debug": totalCost,
                    "total_cost_llm_proxy": llm_proxy_total_cost,
                    "total_cost": totalCost + llm_proxy_total_cost,
                    "max_experiment_cost": max_experiment_cost,
                    "cost_limit_exceeded": cost_limit_exceeded,
                    "reflection_time_seconds": deltaTime,
                    "is_ok": isOk,
                    "current_pilot_mode": current_pilot_mode,
                    "next_pilot_mode": next_pilot_mode,
                    "num_reflections": numReflections,
                    "error_code_parsing_issue": error_code_parsing_issue,
                    "hard_runtime_cutoff_seconds": hard_runtime_cutoff_seconds,
                    "change_log": changeLog
                }
                historyPacked["history"] = sanitizedHistory
                json.dump(historyPacked, file, indent=4)


                # Check if we're done
                if (done == True):
                    print("*** Reflection has marked the code and execution as OK.  Exiting at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    break

                if (cost_limit_exceeded == True):
                    print("*** Cost limit exceeded.  Exiting at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    break

                # Check whether there's been a critical code error
                if ("code_complete_critical_error" in reflectionCodeblock) and (reflectionCodeblock["code_complete_critical_error"] == True):
                    print("*** Critical code error detected.  Exiting at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    break

                # Check if there's been a code parsing issue
                if (error_code_parsing_issue == True):
                    print("*** Code parsing issue detected.  Exiting at step " + str(i+1) + " of " + str(MAX_REFLECTIONS) + " reflections.")
                    break

        # Learn lessons: Reflect on the reflection, to see if there are any lessons that can be learned from any mistakes that occurred, that we can store to improve future code generation.
        print("-" * 80)
        print("Generating Summary of Results")
        print("-" * 80)

        # First, check to make sure that the last reflection was successful
        lastReflection = history[-1]
        summary = None
        summary_short = None
        interesting_results = None
        latex_filename = None
        latex_success = None

        summary_results = {}
        if ("is_ok" in lastReflection) and (lastReflection["is_ok"] == True) and (cost_limit_exceeded == False):
            # Generate a summary
            for summary_retry_idx in range(0, 3):
                print("Generating Summary of Results (Attempt " + str(summary_retry_idx+1) + " of 3)")
                summary_results = codeblockStore.generateResultsSummaryFromSuccessfulReflection(history, modelStr=modelStr, max_tokens=max_tokens, temperature=0.0)
                if ("summary" in summary_results) and (summary_results["summary"] != None):
                    break
                print ("WARNING: Summary generation failed.")

            if ("summary" in summary_results):
                summary = summary_results["summary"]
            if ("summary_short" in summary_results):
                summary_short = summary_results["summary_short"]
            if ("interesting_results" in summary_results):
                interesting_results = summary_results["interesting_results"]

            # Also generate a latex summary report
            # NOTE: The Latex report generation can be buggy/quit with errors, so we'll try it up to a few times.
            MAX_LATEX_REPORT_RETRIES = 5
            for latexIter in range(MAX_LATEX_REPORT_RETRIES):
                latex_success = False
                latex_filename = None
                print("Generating Latex Report (Attempt " + str(latexIter+1) + " of " + str(MAX_LATEX_REPORT_RETRIES) + ")")
                additional_instruction_str = None
                latex_temperature = 0.0
                if (latexIter > 0) and (latexIter < 3):
                    latex_temperature = 0.1
                elif (latexIter >= 3):
                    additional_instruction_str = "**IMPORTANT NOTE:** FOR SOME REASON THE LAST 3 REPORTS YOU HAVE ATTEMPTED TO GENERATE HAVE FAILED. THIS IS LIKELY DUE TO A LATEX ERROR FOR SOMETHING FANCY YOU'RE TRYING TO RENDER, OR AN ERROR WITH AN IMAGE, OR SOMETHING SIMILAR.  FOR THIS REPORT, JUST TRY TO GENERATE SOMETHING PLAIN/NOT FANCY, SO THAT IT STILL CONVEYS THE CRITICAL INFORMATION, BUT COMPILES SUCCESSFULLY."
                    latex_temperature = 0.2
                latex_results = codeblockStore.generateLatexReport(history, modelStr=modelStr, max_tokens=max_tokens, temperature=latex_temperature, export_path=pathLogOutput, additional_instruction_str=additional_instruction_str)
                if (latex_results != None):
                    if ("latex_report_filename" in latex_results):
                        latex_filename = latex_results["latex_report_filename"]
                    if ("success" in latex_results):
                        latex_success = latex_results["success"]

                # If the latex report was successful, break out of the loop
                if (latex_success == True):
                    print("LATEX Report was successfully generated -- breaking")
                    break

        else:
            print("ERROR: Last reflection not marked OK.  Not interpreting results.")

        # Add the summary results to the metadata
        historyPacked["metadata"]["summary_results"] = summary_results
        historyPacked["metadata"]["summary"] = summary
        historyPacked["metadata"]["summary_short"] = summary_short
        historyPacked["metadata"]["interesting_results"] = interesting_results
        # Add the latex report (if it exists) to the metadata
        historyPacked["metadata"]["latex_report_filename"] = latex_filename
        historyPacked["metadata"]["latex_report_success"] = latex_success
        # Note whether the exit was due to a container failure
        historyPacked["metadata"]["container_failure"] = container_failure
        # Note whether the hard time limit was reached
        historyPacked["metadata"]["hard_runtime_cutoff_seconds"] = hard_runtime_cutoff_seconds
        historyPacked["metadata"]["hard_time_limit_reached"] = hard_time_limit_reached


        # Add whether there's a critical code error to the metadata
        if ("code_complete_critical_error" in lastReflection) and (lastReflection["code_complete_critical_error"] == True):
            historyPacked["metadata"]["code_complete_critical_error"] = True
        else:
            historyPacked["metadata"]["code_complete_critical_error"] = False

        # Add whether there's been a code parsing issue
        if (error_code_parsing_issue == True):
            historyPacked["metadata"]["error_code_parsing_issue"] = True
        else:
            historyPacked["metadata"]["error_code_parsing_issue"] = False


        # Save the history
        print("Saving `" + str(pathLogOutput) + "/" + "history.json`...")
        with open(pathLogOutput + "history.json", 'w') as file:
            json.dump(historyPacked, file, indent=4)

        print("Done.")

        # Return
        # TODO
        return history, historyPacked


#
#   Second pass: A plan-based approach to generating and debugging experiments.
#

    def runPlanBasedExpermentMaker(self, instructionStr:str, additionalInstructionStr:str, codeblocksToCombine:list, modelStr:str, max_tokens:int, temperature:float):
        codeStruct = self.codeBlockStore.generateExperimentPlan(instructionStr, codeblocksToCombine, modelStr=modelStr, max_tokens=max_tokens, temperature=temperature, additionalInstructionStr=additionalInstructionStr)
        return codeStruct

    # def codebuildingWithPlanOneStep(self, lastCodeStruct:dict, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, follow_on_description=None, max_runtime_seconds=None):
    def codebuildingWithPlanOneStep(self, lastCodeStruct:dict, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, follow_on_description=None, max_runtime_seconds=None):
        # Reflect on the code execution
        #codeStruct = self.codeBlockStore.codebuildingWithPlanOneStep(lastCodeStruct, modelStr=modelStr, max_tokens=max_tokens, temperature=temperature, follow_on_description=follow_on_description, max_runtime_seconds=max_runtime_seconds)
        #return codeStruct
        return None

    def checkForStuckExperiment(self, lastCodeStruct:dict, history:list, modelStr="gpt-4o-mini", min_stuck_iterations=4, debugLogOutPath:str=None):
        newCodeStruct = self.codeBlockStore.checkForStuckExperiment_(lastCodeStruct, history, model_str=modelStr, min_stuck_iterations=min_stuck_iterations, debugLogOutPath=debugLogOutPath)
        return newCodeStruct

    # Execute the most recent code, and save the output
    def executeCurrentCode(self, lastCodeStruct:dict, pathLogOutput:str="generated/", max_container_llm_cost_usd:float=0.25, max_runtime_seconds=600, max_runtime_seconds_pilot=600, apt_packages = ["git", "wget", "curl", "openjdk-17-jre"]):
        startTime = time.time()

        # Make sure the codeStructIn_ contains code
        if ("code" not in lastCodeStruct) or (lastCodeStruct["code"] == None):
            print("ERROR: executeCurrentCode(): No code was provided in the input. Exiting.")
            return None

        # Step 3: Try to execute that experiment
        # The executor uses it's own code structure -- here we'll copy over the code and requirements, and add the supporting files.
        codeStructIn = {}
        if ("requirements" in lastCodeStruct) and (lastCodeStruct["requirements"] != None):
            codeStructIn["requirements"] = lastCodeStruct["requirements"]
        else:
            codeStructIn["requirements"] = ""

        codeStructIn["code"] = lastCodeStruct["code"]

        # Add supporting files
        codeStructIn["supporting_files"] = []

        # Add the `api_keys.donotcommit.json` file
        supportingFileAPIKeys = {"filename": "llm-proxy/api_keys.donotcommit.json", "contents": None}
        with open("api_keys.donotcommit.json", 'r') as file:
            supportingFileAPIKeys["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileAPIKeys)

        # Add the LLM proxy files
        # Proxy file 1: `llm-proxy-server.py`
        supportingFileLLMProxy = {"filename": "llm-proxy/llm-proxy-server.py", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "llm-proxy-server.py", 'r') as file:
            supportingFileLLMProxy["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxy)

        # Proxy file 2: `experiment-llm-cost.json`
        supportingFileLLMProxyCost = {"filename": "llm-proxy/experiment-llm-cost.json", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "experiment-llm-cost.json", 'r') as file:
            supportingFileLLMProxyCost["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxyCost)

        # Proxy file 3: `experiment-setup.json`
        supportingFileLLMProxySetup = {"filename": "llm-proxy/experiment-setup.json", "contents": None}

        # Automatically generate the experiment cost/setup file for the LLM proxy.
        # NOTE: This file can also be used to allow/disallow certain LLM models.
        experiment_llm_setup_json = {
            "notes": "This is an automatically-generated file that sets the maximum allowable cost to go through the LLM proxy server.",
            "max_cost_usd": max_container_llm_cost_usd
        }
        supportingFileLLMProxySetup["contents"] = json.dumps(experiment_llm_setup_json, indent=4)
        codeStructIn["supporting_files"].append(supportingFileLLMProxySetup)

        # Proxy file 4: The LLM library
        supportingFileLLMProxyLib = {"filename": "llm_proxy_usage.py", "contents": None}
        with open(LLM_PROXY_BASE_PATH + "llm_proxy_usage.py", 'r') as file:
            supportingFileLLMProxyLib["contents"] = file.read()
        codeStructIn["supporting_files"].append(supportingFileLLMProxyLib)

        # Add the common library of experimental functions
        supportingFileCommonLib = {"filename": "experiment_common_library.py", "contents": None}
        supportingFileCommonLib["contents"] = self.codeBlockStore.getCommonLibrary()
        codeStructIn["supporting_files"].append(supportingFileCommonLib)

        # TODO: Fix this to use the current pilot mode
        currentMaxRuntime = max_runtime_seconds

        # Execute the experiment
        codeStructOut = self.executeExperiment(codeStructIn, basePath=pathLogOutput, max_runtime_seconds=currentMaxRuntime, apt_packages=apt_packages)

        # Clear the execution output
        lastCodeStruct["pip.stdout"] = None
        lastCodeStruct["pip.stderr"] = None
        lastCodeStruct["python.stdout"] = None
        lastCodeStruct["python.stderr"] = None
        lastCodeStruct["log"] = None
        lastCodeStruct["results_json"] = None
        lastCodeStruct["llm_proxy_usage"] = None
        lastCodeStruct["files_downloaded"] = None
        lastCodeStruct["files_errors"] = None
        lastCodeStruct["files_and_sizes"] = None
        lastCodeStruct["files_too_big"] = None
        lastCodeStruct["return_code"] = None
        lastCodeStruct["runtime_seconds"] = None

        lastCodeStruct["critical_error"] = False


        # Parse the result
        if ("errors" not in lastCodeStruct):
            lastCodeStruct["errors"] = {}

        # Look for the execution result
        execResult = None
        if ("exec_result" in codeStructOut):
            execResult = codeStructOut["exec_result"]
            # Check if it's a list and not a dictionary
            if (type(execResult) == list):
                execResult = execResult[-1]

            # Save it, just for debugging
            print("Saving `execResult.json`...")
            with open(pathLogOutput + "execResult.json", 'w') as file:
                json.dump(execResult, file, indent=4)

            # Check if there was a container failure
            lastCodeStruct["errors"]["container_failure"] = True
            if ("modal_container_completed" in execResult) and (execResult["modal_container_completed"] == True):
                lastCodeStruct["errors"]["container_failure"] = False

        else:
            lastCodeStruct["errors"]["container_failure"] = True
            lastCodeStruct["critical_error"] = True

        # output = {
        #     "pip.stdout": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stdout.pip.txt"),
        #     "pip.stderr": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stderr.pip.txt"),
        #     "python.stdout": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stdout.python.txt"),
        #     "python.stderr": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stderr.python.txt"),
        #     "log": log,
        #     "results_json": resultsJson,
        #     "llm_proxy_usage": llm_proxy_usage,
        #     "files_downloaded": files_downloaded,
        #     "files_errors": files_errors,
        #     "files_and_sizes": files_and_sizes,
        #     "file_path": folderOut + "/" + MODAL_OUTPUT_SUBFOLDER,
        #     "return_code": return_code,
        #     "other_errors": other_errors,
        #     "sandbox_errors": sandbox_errors,
        #     "modal_container_completed": modal_container_completed,
        #     "statistics": {
        #         "runtime_seconds": deltaTimeSeconds
        #     }

        # Extract the results
        if ("pip.stdout" in execResult):
            lastCodeStruct["pip.stdout"] = execResult["pip.stdout"]
        if ("pip.stderr" in execResult):
            lastCodeStruct["pip.stderr"] = execResult["pip.stderr"]
        if ("python.stdout" in execResult):
            lastCodeStruct["python.stdout"] = execResult["python.stdout"]
        if ("python.stderr" in execResult):
            lastCodeStruct["python.stderr"] = execResult["python.stderr"]
        if ("log" in execResult):
            lastCodeStruct["log"] = execResult["log"]
        if ("results_json" in execResult):
            lastCodeStruct["results_json"] = execResult["results_json"]
        if ("llm_proxy_usage" in execResult):
            lastCodeStruct["llm_proxy_usage"] = execResult["llm_proxy_usage"]
        if ("files_downloaded" in execResult):
            lastCodeStruct["files_downloaded"] = execResult["files_downloaded"]
        if ("files_errors" in execResult):
            lastCodeStruct["files_errors"] = execResult["files_errors"]
        if ("files_and_sizes" in execResult):
            lastCodeStruct["files_and_sizes"] = execResult["files_and_sizes"]
        if ("files_too_big" in execResult):
            lastCodeStruct["files_too_big"] = execResult["files_too_big"]
        if ("return_code" in execResult):
            lastCodeStruct["return_code"] = execResult["return_code"]
        if ("other_errors" in execResult):
            lastCodeStruct["other_errors"] = execResult["other_errors"]
        if ("statistics" in execResult) and ("runtime_seconds" in execResult["statistics"]):
            lastCodeStruct["runtime_seconds"] = execResult["statistics"]["runtime_seconds"]

        # Return
        return lastCodeStruct


#
#   ExperimentMaker example tests
#

# A quick test for the Experment Maker
def experimentMakerTest():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' experiment
    instructionStr = "Please create a program that prints 'Hello, World!' to the console."
    additionalInstructionStr = "Please use the Python programming language."
    #codeblocksToCombine = ["Logger/Debugging", "OpenAI/Anthropic LLM Example", "Together.ai LLM Example", "Non-parametric Bootstrap Resampling"]
    codeblocksToCombine = ["Logger/Debugging"]
    modelStr = "o1-mini"
    max_tokens = 16384
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=2, pathLogOutput="generated-temp/")

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest2():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please create a program that asks an LLM to answer the question 'What is 10 * 5?`"
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server"]
    modelStr = "o1-mini"
    max_tokens = 16384
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=2, pathLogOutput="generated-temp/")

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest3():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please create a ReAct agent for CookingWorld using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 20. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=30, max_tokens=max_tokens, pathLogOutput="generated-temp/")

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest4():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please create a ReAct agent for CookingWorld using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  After it's working, do NOT set `is_ok` to be true -- keep trying to modify the agent to make it better, so that it's capable of solving this task in a faster, more accurate, and more general way."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=30, max_tokens=max_tokens, pathLogOutput="generated-temp/")

    # Print the history
    print(json.dumps(history, indent=4))



def experimentMakerTest5():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please investigate the effect of implementing a ReAct agent with and without a small difference.  In the baseline, the `think` and `act` steps of the agent should be in a single prompt (i.e. a single LLM call).  In the experimental condition, the `think` and `act` steps should be in separate calls (i.e. it thinks, then it acts based on the thought).  Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 1.00
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput="generated-temp/", max_container_llm_cost_usd=max_container_llm_cost)

    # Print the history
    print(json.dumps(history, indent=4))



def experimentMakerTest6():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please investigate whether adding a causal memory to a ReAct agent helps improve its performance over a baseline ReAct agent.  Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 5.00
    max_runtime_seconds = 60 * 30   # 30 minutes
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput="generated-temp/", max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds)

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest7():
    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.
    instructionStr = "Please investigate whether adding a causal memory to a ReAct agent helps improve its performance over a baseline ReAct agent.  The causal memory should be *abstractive*, abstracting specifically how single actions (or sequences of actions) helped achieve subgoals or larger goals.  Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0

    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 5.00
    max_runtime_seconds = 60 * 30   # 30 minutes
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput="generated-temp/", max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds)

    # Print the history
    print(json.dumps(history, indent=4))



def experimentMakerTest8():
    import datetime

    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.

    # Experiment parameters
    experimentName = "react-causal-memory-persistent"
    instructionStr = "Please investigate whether adding a causal memory to a ReAct agent helps improve its performance over a baseline ReAct agent.  The causal memory should be *abstractive*, abstracting specifically how single actions (or sequences of actions) helped achieve subgoals or larger goals.  The memory should be persistent, saved across episodes (and framed as `lessons` in the prompt, that may or may not be from the current episode, so it doesn't get confused).   The memory should be reported in the log file, for debugging.  Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  After the code is successfully working at 5 episodes, please scale it to running 20 episodes. The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0


    # Create the experiment output directory
    experimentNameWithDate = experimentName + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pathExperimentOutput = "generated-experiments/" + experimentNameWithDate + "/"
    if (not os.path.exists(pathExperimentOutput)):
        os.makedirs(pathExperimentOutput)


    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 5.00
    max_runtime_seconds = 60 * 30   # 30 minutes
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput=pathExperimentOutput, max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds)

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest9():
    import datetime

    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.

    # Experiment parameters
    experimentName = "react-causal-memory-persistent"
    instructionStr = "Please investigate whether adding a causal memory to a ReAct agent helps improve its performance over a baseline ReAct agent.  The causal memory should be *abstractive*, abstracting how single actions (or sequences of actions) helped achieve subgoals or larger goals.  The memory should be persistent, saved across episodes (and framed as `lessons` in the prompt, that may or may not be from the current episode, so it doesn't get confused). The memory should be displayed in the log file, so you can inspect it to make sure it's behaving correctly. Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score.  The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this.  Report whether the baseline and experimental condition are significantly different."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "LLM example through proxy server", "ReAct Agent Example", "TextWorldExpress API Example", "Non-parametric Bootstrap Resampling"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0


    # Create the experiment output directory
    experimentNameWithDate = experimentName + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pathExperimentOutput = "generated-experiments/" + experimentNameWithDate + "/"
    if (not os.path.exists(pathExperimentOutput)):
        os.makedirs(pathExperimentOutput)


    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 5.00
    max_runtime_seconds = 60 * 30   # 30 minutes
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput=pathExperimentOutput, max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds)

    # Print the history
    print(json.dumps(history, indent=4))


def experimentMakerTest10():
    import datetime

    # Load the API keys
    from ExtractionUtils import loadAPIKeys
    loadAPIKeys()

    # Make a simple 'hello world' LLM program.

    # Experiment parameters
    experimentName = "save-test1"
    instructionStr = "Please create 3 sample plots: a sin, a cosine, and a sin*sqrt(x) plot."
    additionalInstructionStr = "Please use the Python programming language."
    codeblocksToCombine = ["Logger/Debugging", "MatPlotLib Line Plot"]
    #modelStr = "o1-mini"
    #max_tokens = 16384
    modelStr = "claude-3-5-sonnet-20241022"
    max_tokens = 8192
    temperature = 0.0


    # Create the experiment output directory
    experimentNameWithDate = experimentName + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pathExperimentOutput = "generated-experiments/" + experimentNameWithDate + "/"
    if (not os.path.exists(pathExperimentOutput)):
        os.makedirs(pathExperimentOutput)


    # Instantiate the ExperimentMaker
    experimentMaker = ExperimentMaker("codeblocks/")
    combinedCodeblock = experimentMaker.createExperiment(instructionStr, additionalInstructionStr, codeblocksToCombine, modelStr, max_tokens, temperature)

    # Print the combined codeblock
    print(json.dumps(combinedCodeblock, indent=4))

    # Run/Reflect on the experiment
    max_container_llm_cost = 5.00
    max_runtime_seconds = 60 * 30   # 30 minutes
    history = experimentMaker.runAndReflectExperiment(combinedCodeblock, modelStr, MAX_REFLECTIONS=10, max_tokens=max_tokens, pathLogOutput=pathExperimentOutput, max_container_llm_cost_usd=max_container_llm_cost, max_runtime_seconds=max_runtime_seconds)

    # Print the history
    print(json.dumps(history, indent=4))


# Test just the log trimmer
def testLogTrimmer():
    # Load the codeblock store to get access to the trimming function
    codeblockStore = CodeBlockStore("codeblocks/")
    # Load the log file
    logFile = "log_in.json"
    print("Loading log file (" + logFile + ")")
    with open(logFile, 'r') as file:
        log = json.load(file)

    # Try to trim the log with the trim function (as a test of the trim function)
    # def trimPromptComponentLog(self, logIn:list, maxTokens:int=10000):
    trimmedLog = codeblockStore.trimPromptComponentLog(log, maxTokens=20000)

    #print("Trimmed log:")
    #print(json.dumps(trimmedLog, indent=4))
    filenameOut = "debug.json"
    with open(filenameOut, 'w') as file:
        file.write(trimmedLog)




# Test
if __name__ == "__main__":
    #experimentMakerTest()
    #experimentMakerTest2()
    #experimentMakerTest3()
    #experimentMakerTest4()
    #experimentMakerTest5()
    #experimentMakerTest6()
    #experimentMakerTest7()
    #experimentMakerTest8()
    #experimentMakerTest10()
    pass
