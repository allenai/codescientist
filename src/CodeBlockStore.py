# CodeBlockStore.py

import os
import re
import tqdm
import difflib
from copy import deepcopy

from ExtractionUtils import *


PATH_CODEBLOCKS = "codeblocks/"
FILENAME_CODEBLOCK_SUMMARIES = "codeblock_summaries.json"
FILENAME_COMMON_LIBRARY = "experiment_common_library.py"

# Class to load/store the codeblocks
class CodeBlockStore():
    # Constructor
    def __init__(self, path_codeblocks):
        self.path_codeblocks = path_codeblocks
        self.codeblocks = []

        # Load the codeblocks
        self.loadCodeblocks()

        # Load the codeblock summaries
        self.codeblockSummaries = self.loadCodeblockSummaries(PATH_CODEBLOCKS + "/" + FILENAME_CODEBLOCK_SUMMARIES)

        # Summarize any codeblocks without summaries
        self.summarizeAllCodeblocks(justUpdate=True)
        #self.summarizeAllCodeblocks(justUpdate=False)       # Force a complete update

    # Get a (string listing of) the common library
    def getCommonLibrary(self):
        commonLibraryPath = os.path.join(self.path_codeblocks, FILENAME_COMMON_LIBRARY)
        try:
            with open(commonLibraryPath, 'r') as file:
                commonLibrary = file.read()
            return commonLibrary
        except Exception as e:
            print("ERROR: Could not load common library from: " + commonLibraryPath)
            print("ERROR: " + str(e))
            return ""


    # List the codeblocks
    def listCodeblocks(self):
        names = []
        for codeblock in self.codeblocks:
            if ("name" in codeblock) and (codeblock["name"] is not None):
                names.append(codeblock["name"])
        return names

    # Get a codeblock by name
    def getCodeblockByName(self, name):
        for codeblock in self.codeblocks:
            if ("name" in codeblock) and (codeblock["name"] is not None) and (codeblock["name"] == name):
                return codeblock
        return None

    # Load the codeblocks
    def loadCodeblocks(self):
        # Recursively find all .py files in the codeblocks directory
        print("* Loading codeblocks from: " + self.path_codeblocks)
        numCodeblocksAdded = 0
        for root, dirs, files in os.walk(self.path_codeblocks):
            for file in files:
                if file.endswith(".py"):
                    # Load the codeblock
                    parsedCodeblock = self.loadCodeblock(os.path.join(root, file))
                    if (parsedCodeblock is not None):
                        self.codeblocks.append(parsedCodeblock)
                        numCodeblocksAdded += 1

        print("* Added " + str(numCodeblocksAdded) + " codeblocks from: " + self.path_codeblocks)



    # Load a single codeblock file
    def loadCodeblock(self, filename):
        out = None

        # Make sure the filename does not contain the common library (FILENAME_COMMON_LIBRARY)
        if (filename.endswith(FILENAME_COMMON_LIBRARY)):
            return None

        # Load the file
        with open(filename, 'r') as file:
            codeblock = file.read()

        # Check what language the codeblock is in
        if (filename.endswith(".py")):
            # Check to see if the codeblock is "disabled".
            lines = codeblock.split('\n')
            if (lines[0].strip().lower().startswith("# disabled")):
                print("Skipping codeblock marked disabled: " + filename)
                return None

            # Python codeblock
            out = self.parseCodeblockPython(codeblock)


        else:
            # Unknown language
            pass


        return out


    #
    #   Parsers for specific kinds of codeblocks
    #
    def parseCodeblockPython(self, codeblockIn):
        out = {}
        out["codeblock_raw"] = codeblockIn
        out["warnings"] = []
        out["errors"] = []

        lines = codeblockIn.split('\n')

        # First, extract all the lines that begin with a comment
        commentLines = []           # With the comment block removed
        for line in lines:
            lineSanitized = line.strip()
            if (lineSanitized.startswith("#")):
                # Remove any leading comment characters
                lineSanitized = re.sub(r'^#+', '', lineSanitized).strip()
                commentLines.append(lineSanitized)


        # Next, look for specific fields in the comments.  The format is (field name: value)
        # Fields ending with a * will allow multiple values (on separate lines), and be stored as a list
        fields = ["name", "description", "inclusion_criteria", "exclusion_criteria", "python_version", "pip_requirement*"]

        # Initialize the fields to None
        for field in fields:
            if (field.endswith("*")):
                out[field[:-1]] = []
            else:
                out[field] = None

        # Attempt to find the fields
        for field in fields:
            # Check whether the field is a list or not
            isFieldList = False
            if (field.endswith("*")):
                isFieldList = True
                field = field[:-1]

            # Search each line for the field
            for line in commentLines:
                lineLowerCase = line.lower()
                # Check if the field is in the line
                if (lineLowerCase.startswith(field + ":")):
                    # Extract the value
                    value = line[len(field)+1:].strip()
                    if (not isFieldList):
                        out[field] = value
                    else:
                        # If the field is a list, then append to the list
                        if (out[field] is None):
                            out[field] = []
                        out[field].append(value)

                    # If the field is NOT a list, then break out of the loop.  Otherwise, allow it to be populated multiple times
                    if (not isFieldList):
                        break


        # Check that all the fields are filled
        for field in fields:
            if (field.endswith("*")):
                field = field[:-1]

            if (out[field] is None):
                out["errors"].append("Field '" + field + "' is missing from the codeblock")

        # Return
        return out


    #
    #   Attempt to create automatic summaries of the codeblocks
    #

    # Load codeblock summaries
    def loadCodeblockSummaries(self, filename):
        summaries = None
        try:
            with open(filename, 'r') as file:
                summaries = json.load(file)
            return summaries
        except:
            print("Could not load existing codeblock summaries from: " + filename)
            return {}


    def summarizeAllCodeblocks(self, justUpdate=True):
        # Loop through all the codeblocks
        num_updated = 0
        for codeblock in tqdm.tqdm(self.codeblocks):
            codeblockName = codeblock["name"]
            if (justUpdate and (codeblockName in self.codeblockSummaries)):
                # Skip codeblocks that already have summaries
                print("Found existing summary for: " + codeblockName + ". Skipping.")
                continue

            summaryResponse = self.summarizeCodeblock(codeblock)
            summary = summaryResponse["summary"]
            if (summary is not None):
                self.codeblockSummaries[codeblockName] = summary
                num_updated += 1

        # Save the summaries to disk
        if (num_updated > 0):
            print("Writing " + str(len(self.codeblockSummaries)) + " codeblock summaries to disk.")
            filenameOut = PATH_CODEBLOCKS + "/" + FILENAME_CODEBLOCK_SUMMARIES
            # Check that the full path exists
            if not os.path.exists(PATH_CODEBLOCKS):
                os.makedirs(PATH_CODEBLOCKS)
            with open(filenameOut, 'w') as fileOut:
                json.dump(self.codeblockSummaries, fileOut, indent=4)

        return self.codeblockSummaries


    # Get a (raw version) of the codeblock summaries, which can be included in prompts.
    def get_codeblock_summaries_raw(self):
        # Load the codeblock summaries
        summaries = self.loadCodeblockSummaries(PATH_CODEBLOCKS + "/" + FILENAME_CODEBLOCK_SUMMARIES)
        if (summaries is None) or (len(summaries) == 0):
            print("ERROR: No codeblock summaries found.  Retrying...")
            # This is an error that should generally not happen -- if it does, pause for 5 seconds, then retry.
            time.sleep(5)
            summaries = self.loadCodeblockSummaries(PATH_CODEBLOCKS + "/" + FILENAME_CODEBLOCK_SUMMARIES)

        if (summaries is None) or (len(summaries) == 0):
            print("ERROR: Still no codeblock summaries found.  Exiting.")
            return None

        return summaries


    def summarizeCodeblock(self, codeblockIn):
        print("Generating summary for codeblock: " + codeblockIn["name"])

        prompt = ""
        prompt = "You are ScientistGPT, the most capable automated scientific reasoning system ever created.  You can use your enormous intellect to solve any problem.\n"
        prompt += "Together we are creating an automated scientific discovery system, that is capable of building scientific experiments.  Those scientific experiments are generally almost always fully implemented in code.\n"
        prompt += "To build these experiments, we have a large number of 'code templates', that can be combined like LEGO-blocks to build experiments (though the analogy isn't perfect, because the code templates do need to be modified/adapted to be used for a given experiment/purpose).\n"
        prompt += "The first step of that process is searching through the corpus of code templates to find those that are highly relevant/need to be used for a given type of experiment.  This looks similar to a conventional search task, where the query is a description of the experiment, and the corpus that's being searched has documents that take the form of short but highly informative summaries of the function and utility of a given code template, so it can be quickly, easily, and accurately discovered.\n"
        prompt += "Your task is to write that short, but highly informative summary, that would be extremely useful for an automated search system that's using the experiment description as a search query to find this code template, if it's useful.\n"
        prompt += "The summary is not intended for humans -- it shouldn't have fluff, be overly verbose, or serve as a kind of advertisement -- it should be highly informative, and serve as the vehicle for finding this code template if it's relevant to the experiment.  Failure to find the correct code templates will mean failure to build the experiment (or, failure to build a correct experiment), which is a strongly negative outcome.\n"
        prompt += "The code template you're summarizing is the following:\n"
        prompt += "```\n"
        prompt += codeblockIn["codeblock_raw"] + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "Please provide your short, highly informative summary below. The output format is a JSON dictionary, containing a single key ('summary'), with the value being another dictionary with the following keys:\n"
        prompt += "1. 'name': The name of the code template.\n"
        prompt += "2. 'description': A highly informative description of the code template, that would be useful for an automated search system to find this code template if it's relevant to the experiment.\n"
        prompt += "3. 'libraries': What libaries does this code template use?"
        prompt += "4. 'when_to_use': When should this code template be used?  What kind of experiments, systems, or purposes is it useful for? Be both general and specific.\n"
        prompt += "5. 'examples': A brief description of any examples that are included in the code template, and what they demonstrate.\n"
        prompt += "6. 'kinds_of_ideas': What kinds of ideas, concepts, or experiments might be particularly well-suited to this code template?\n"
        prompt += "\n"
        prompt += "Remember, your summary must be:\n"
        prompt += "A. Highly informative, and useful for an automated search system to find this code template if it's relevant to the experiment.\n"
        prompt += "B. Not intended for humans -- it should not have fluff, be overly verbose, or serve as a kind of advertisement.\n"
        prompt += "C. Accurate, and not hallucinated or otherwise misleading.\n"
        prompt += "D. Correctly formatted as a JSON dictionary, with a single key ('summary'), and a dictionary value with the keys above.\n"

        # Now, get the response from the LLM
        modelStr = "gpt-4o"
        max_tokens = 4096
        temperature = 0.0
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

        summary = None
        if ("summary" in responseJSON):
            summary = responseJSON["summary"]

            # Try to add "inclusion_criteria" and "exclusion_criteria" to the summary
            if ("inclusion_criteria" in codeblockIn):
                summary["inclusion_criteria"] = codeblockIn["inclusion_criteria"]
            if ("exclusion_criteria" in codeblockIn):
                summary["exclusion_criteria"] = codeblockIn["exclusion_criteria"]

        errors = []
        if (summary is None):
            errors.append("ERROR: 'summary' key not found in the response JSON")

        # Return the response
        packedOut = {
            "codeblock": codeblockIn,
            "summary": summary,
            "model": modelStr,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "responseJSON": responseJSON,
            "responseText": responseText,
            "cost": cost,
            "errors": errors
        }
        return packedOut

    #
    #   Attempt to combine/adapt the codeblock(s) for a particular purpose.
    #

    # Combine the codeblocks for a particular purpose
    def combineCodeblocks(self, instructionStr:str, codeblockNames:list, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, additionalInstructionStr:str=""):
        # First, try to retrieve all the codeblocks mentioned
        retrievedCodeblocks = []
        retrievedCodeblockDict = {}
        retrievalErrors = []
        for name in codeblockNames:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                retrievedCodeblocks.append(codeblock)
                retrievedCodeblockDict[name] = codeblock
            else:
                retrievalErrors.append("ERROR: Could not find codeblock with name: " + str(name))

        # Check if any codeblocks were not found
        if (len(retrievalErrors) > 0):
            print("ERROR: Could not find all requested codeblocks." + "\n".join(retrievalErrors))
            return {
                "success": False,
                "errors": retrievalErrors
            }

        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        prompt += "Your task is the following:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"
        if (additionalInstructionStr != ""):
            prompt += "\n"
            prompt += "You have been provided with the following additional instructions:\n"
            prompt += "```\n"
            prompt += additionalInstructionStr + "\n"
            prompt += "```\n"
        prompt += "\n"
        prompt += "RESULTS: You should save any results (both final results, and intermediate results for further processing) in a file called `results.json`. It must be called this, or the results file will not automatically be found, and the experiment will not be useful.\n"

        # Code library / code blocks
        prompt += "\n"
        prompt += "*SECTION: Common code library, and code examples (called `codeblocks`)*\n"
        prompt += "- You have access to a common library (`experiment_common_library`) that contains useful functions, and you can directly import them into your code.  The common library is provided below.\n"
        prompt += "- In addition, you have a number of `codeblock tempates`, which are vetted code examples that (often) reference the common library.  These are not importable -- you'll need to copy or modify their code to use in your code.\n"
        prompt += "\n"
        prompt += "*SUBSECTION: Common code library\n"
        prompt += "The common library is provided below.  You can directly import these functions into your code.\n"
        prompt += "```\n"
        prompt += self.getCommonLibrary() + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Add the codeblocks
        prompt += "*SUBSECTION: Codeblocks (vetted code templates you should base your code on, if possible)\n"
        numCodeblocks = len(retrievedCodeblocks)
        prompt += "You have been provided with " + str(numCodeblocks) + " template codeblocks to assist you.  They are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        prompt += "You should base your code AS MUCH AS POSSIBLE on these codeblocks, as (though they may look a little different than examples on the internet), they are VETTED, KNOWN-GOOD examples that you should DIRECTLY COPY as much as possible.  Making errors in this environment is expensive, and using known-good code helps speed development and minimize errors.  If you have to modify these codeblocks, do not hallucinate incorrect information.\n"
        prompt += "The code in the codeblocks is NOT IMPORTABLE -- it is meant to be COPY AND PASTED (with whatever modifications are required) into your code.\n"
        for idx, codeblock in enumerate(retrievedCodeblocks):
            prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
            prompt += "```\n"
            prompt += codeblock["codeblock_raw"] + "\n"
            prompt += "```\n"
            prompt += "\n"

        # Now, get the response from the LLM
        prompt += "\n"
        prompt += "*SECTION*: Writing your code\n"
        prompt += "Please provide your code below.  The output format is as follows: Your output should be between two (and exactly two) codeblocks (```).  The first codeblock will be the contents of the `requirements.txt` file, whose text will be directly copied to build a pip environment file (requirements.txt).  The second codeblock will be the contents of the `main.py` file, which is the code that will be run.  All requirements and code must be correct and ready to run, as these will be automatically run, and not examined by humans or other processes before being automatically run.\n"
        # Added section about writing debuggable/testable code
        prompt += "\n"
        prompt += "*SUBSECTION: Writing debuggable/testable experiment code*\n"
        prompt += "Here are some additional considerations when writing your experiment code:\n"
        prompt += "(a) The code you're writing is scientific code to perform an experiment to test a specific hypothesis.  It should be written in a scientific, systematic, and rigorous manner, with integrity.\n"
        prompt += "(b) It's very easy to make mistakes, and very hard to find them.  Your code should include *THOROUGH* checks for errors, or assumptions that may not be true.\n"
        prompt += "(c) During the MINI_PILOT phase of the experiment, you should be very verbosely outputting information about the internal workings of your code to the log file, and do so in a way that is easy to understand, interpret, and spot errors in logic or assumptions. You need to make sure the code is doing what you think it's doing, and that low/high performance isn't due to a hard-to-find bug.\n"
        prompt += "(d) Testing Example 1: You're sending a prompt to an LLM and expecting a response back in a certain format that's easy to parse.  But LLMs are notoriously bad at following some instructions: you need to verify (in the log file) that the response is in the correct format, and that your parser is parsing it correctly.  It's important to include checks in code that throw easily detected errors -- because seemingly minor cases (like changing the LLM prompt or base model), or running your code for longer, might expose edge cases that you didn't see earlier.\n"
        prompt += "(e) Testing Example 2: You've made an agent that switches back-and-forth between different modes of operation based on some trigger.  What if that trigger never happens?  Or what if it gets stuck in one mode under certain conditions?  Or always repeats the same action?  Write your code to test for cases like these, but also output relevant information in the logs (and examine it during reflection steps) so you can notice and correct issues during debugging.\n"
        prompt += "\n"

        # Added section about writing pilot experiments
        prompt += "*SUBSECTION: Writing pilot experiments*\n"
        prompt += " - There should be a global variable in your code (PILOT_MODE:str) with three possible settings: `MINI_PILOT`, `PILOT`, or `FULL EXPERIMENT`.  Most code should start off in the `MINI_PILOT` mode.\n"
        prompt += " - The `MINI_PILOT` setting should run on a very small subset of the data, and should be able to run in a few minutes.  The purpose is for fast debugging and verification of the code. For example, for question answering tasks, this might be 10 questions.  For agent tasks, this might be 2-3 episodes at 10-20 steps each.  The questions/episodes should come from the training set.\n"
        prompt += " - The `PILOT` setting should be a moderate subset of the data, ideally running in less than 1-2 hours. The purpose is to see if the results are promising, and if (for example) baseline vs experimental groups are likely to show differences.  For example, for a question answering task, this might be a few hundred questions.  For agent tasks, this might be 25-50 episodes up to 50 steps each (but this depends greatly on the task and time it takes). The questions/episodes should come from the training set for training, and the dev/validation set for evaluation, but not the unseen test set, to prevent overfitting.\n"
        prompt += " - The `FULL EXPERIMENT` setting should be the full experiment, with all data, all steps, etc.  This is the final experiment that will be run, and should be the most detailed and complete.  Training data should come from the training set.  Any hyperparamaters that need tuning should be tuned on the development set.  The experiment should be evaluated on the test set.\n"
        prompt += " - In all cases, appropriate inferrential and summary statistics should be reported, as well as any follow-on analyses. The difference between pilot levels is simply of scale, not of quality.\n"
        prompt += "\n"

        # General reminders
        prompt += "*SUBSECTION: Specific reminders for this task*\n"
        prompt += "Remember, your code must be:\n"
        prompt += "1. Correct and accurate, or it will produce wrong answers.\n"
        prompt += "2. Adhere to the correct API usage, as provided in the examples, and not hallucinate or otherwise extrapolate/guess function names, or it is unlikely to work\n"
        prompt += "3. Strive to run perfectly, without error (syntactic or logical), the first time.\n"
        prompt += "4. Run correctly without human intervention, as your code will be run automatically immediately after it is generated without human review or modification.\n"
        prompt += "5. Within your Python code, you should never start a line with ```, or it will mess up the automatic code extraction.\n"
        prompt += "6. Never use triple-quoted strings (e.g. \"\"\") in your Python code -- they will mess up the automatic code extraction.\n"
        prompt += "7. The code will be run in a container. Aside from the log files (log.json, results.json), no other files will be saved.  Any files that are NOT log.json or results.json (e.g. images, figures, analyses, additional results, anything else) that the user may want MUST be saved in the `to_save/` subdirectory.  Any files in `to_save` will automatically be downloaded.  This should ideally not include large files.\n"
        prompt += "8. You MUST always include exactly two (```) blocks.  The first MUST be the requirements, even if it's empty.  The second MUST be the Python code.  If this isn't the case, the automatic parser will break. The codeblocks markers (```) MUST be on a newline, alone.\n"
        prompt += "\n"
        prompt += "Example output: \n"
        prompt += "The first codeblock is always `requirements.txt`, even if empty."
        prompt += "```\n"
        prompt += "numpy==1.21.2\n"
        prompt += "```\n"
        prompt += "The second codeblock is always `main.py`."
        prompt += "```\n"
        prompt += "import numpy as np\n"
        prompt += "print(np.random.rand(5))\n"
        prompt += "```\n"



        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)

        # Parse the codeblocks
        requirements = None
        code = None
        success, requirements, code = self.parseRequirementsAndCodeFromLLM(responseText)

        # Check if `responseJSON` is None -- if it is, there was some kind of error.  Try again once more
        if (success is False):
            print("ERROR: Could not extract codeblocks from response.  Trying again once more.")
            responseJSON, responseText, cost_ = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)
            cost += cost_
            success, requirements, code = self.parseRequirementsAndCodeFromLLM(responseText)


        # If the response is still None, then exit.
        if (success is False):
            print("ERROR: Could not extract codeblocks from response on second try.  Exiting.")
            return {
                "success": False,
                "errors": ["ERROR: Response does not appear to include code blocks.  It's possible the code is too long to parse."],
                "cost": cost
            }

        errors = []
        if (requirements is None):
            errors.append("ERROR: 'requirements' key not found in the response JSON")
        if (code is None):
            errors.append("ERROR: 'code' key not found in the response JSON")

        # Return the response
        packedOut = {
            "success": True,
            "instruction_str": instructionStr,
            "codeblock_names": codeblockNames,
            "requirements": requirements,
            "code": code,
            "codeblock_code": retrievedCodeblockDict,
            "model": modelStr,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "responseJSON": responseJSON,
            "responseText": responseText,
            "cost": cost,
            "errors": errors
        }

        return packedOut


    # This helper function reads the text of the LLM, and tries to find the first two codeblocks in it.
    def parseRequirementsAndCodeFromLLM(self, responseStr, numCodeblocks=2):
        metadata = {}
        requirements = []
        code = []

        # Split the response into lines
        lines = responseStr.split('\n')

        # Find the line indices of codeblocks
        codeblockIndices = []
        startIdx = None
        for idx, line in enumerate(lines):
            if (line.strip().startswith("```")):
                if (startIdx is None):
                    startIdx = idx
                else:
                    codeblockIndices.append((startIdx, idx))
                    startIdx = None

        if (numCodeblocks == 2):
            if (len(codeblockIndices) < 2):
                return False, None, None

            if (len(codeblockIndices) > 2):
                print("WARNING: More than 2 codeblocks found in the response.  Only the first two will be used.")
                codeblockIndices = codeblockIndices[:2]

            # Extract the codeblocks.  Note, the extracted codeblocks should NOT include the ``` lines.
            for idx, (startIdx, endIdx) in enumerate(codeblockIndices):
                codeblock = lines[startIdx+1:endIdx]
                codeblock = "\n".join(codeblock)
                if (idx == 0):
                    requirements = codeblock
                elif (idx == 1):
                    code = codeblock

            return True, requirements, code

        if (numCodeblocks == 3):
            if (len(codeblockIndices) < 3):
                return False, None, None, None

            if (len(codeblockIndices) > 3):
                print("WARNING: More than 3 codeblocks found in the response.  Only the first three will be used.")
                codeblockIndices = codeblockIndices[:3]

            # Extract the codeblocks.  Note, the extracted codeblocks should NOT include the ``` lines.
            for idx, (startIdx, endIdx) in enumerate(codeblockIndices):
                codeblock = lines[startIdx+1:endIdx]
                codeblock = "\n".join(codeblock)
                if (idx == 0):
                    metadata = None
                    # Try to parse as JSON
                    try:
                        metadata = json.loads(codeblock)
                        # It should have 3 keys: 'requirements', 'code', and 'metadata'
                        if ("requirements" not in metadata) or ("code" not in metadata) or ("metadata" not in metadata):
                            # Check if the dictionary has a single key, with the value being a dictionary with those keys.  Some LLMs do this.
                            if (type(metadata) == dict) and (len(metadata) == 1):
                                # Check if the single key's value is a dictionary with those keys
                                key = list(metadata.keys())[0]
                                value = metadata[key]
                                if (type(value) == dict) and ("requirements" in value) and ("code" in value) and ("metadata" in value):
                                    metadata = value

                    except:
                        metadata = {}
                elif (idx == 1):
                    requirements = codeblock
                elif (idx == 2):
                    code = codeblock

            return True, metadata, requirements, code


    def parseRequirementsAndCodeFromLLMMetadataLast(self, responseStr, numCodeblocks=2):
        metadata = {}
        requirements = []
        code = []

        # Split the response into lines
        lines = responseStr.split('\n')

        # Find the line indices of codeblocks
        codeblockIndices = []
        startIdx = None
        for idx, line in enumerate(lines):
            if (line.strip().startswith("```")):
                if (startIdx is None):
                    startIdx = idx
                else:
                    codeblockIndices.append((startIdx, idx))
                    startIdx = None

        if (numCodeblocks == 2):
            if (len(codeblockIndices) < 2):
                return False, None, None

            if (len(codeblockIndices) > 2):
                print("WARNING: More than 2 codeblocks found in the response.  Only the first two will be used.")
                codeblockIndices = codeblockIndices[:2]

            # Extract the codeblocks.  Note, the extracted codeblocks should NOT include the ``` lines.
            for idx, (startIdx, endIdx) in enumerate(codeblockIndices):
                codeblock = lines[startIdx+1:endIdx]
                codeblock = "\n".join(codeblock)
                if (idx == 0):
                    requirements = codeblock
                elif (idx == 1):
                    code = codeblock

            return True, requirements, code

        if (numCodeblocks == 3):
            if (len(codeblockIndices) < 3):
                return False, None, None, None

            if (len(codeblockIndices) > 3):
                print("WARNING: More than 3 codeblocks found in the response.  This likely indicates an error. Not attempting to extract codeblocks.")
                return False, None, None, None

            # Extract the codeblocks.  Note, the extracted codeblocks should NOT include the ``` lines.
            for idx, (startIdx, endIdx) in enumerate(codeblockIndices):
                codeblock = lines[startIdx+1:endIdx]
                codeblock = "\n".join(codeblock)
                if (idx == 0):
                    requirements = codeblock
                elif (idx == 1):
                    code = codeblock
                elif (idx == 2):
                    metadata = None
                    # Try to parse as JSON
                    try:
                        metadata = json.loads(codeblock)
                        # # It should have 3 keys: 'requirements', 'code', and 'metadata'
                        # if ("requirements" not in metadata) or ("code" not in metadata) or ("metadata" not in metadata):
                        #     # Check if the dictionary has a single key, with the value being a dictionary with those keys.  Some LLMs do this.
                        #     if (type(metadata) == dict) and (len(metadata) == 1):
                        #         # Check if the single key's value is a dictionary with those keys
                        #         key = list(metadata.keys())[0]
                        #         value = metadata[key]
                        #         if (type(value) == dict) and ("requirements" in value) and ("code" in value) and ("metadata" in value):
                        #             metadata = value

                    except Exception as e:
                        print("ERROR: parseRequirementsAndCodeFromLLMMetadataLast(): Could not parse JSON codeblock:" + str(e))
                        print("------")
                        print(codeblock)
                        print("------")
                        metadata = {}

            return True, metadata, requirements, code


    # This is a general function for trimming -- use the logging-specific one for logs.
    def trimPromptComponent(self, componentIn:str, maxTokens:int=10000):
        lines = componentIn.split('\n')
        # If it's below the max tokens, return it
        token_count = countTokens(componentIn)
        if (token_count <= maxTokens):
            return componentIn

        # If it's above the max tokens, try to trim it
        # Try to trim the lines from the middle out
        windowSize = 1
        trimmedComponent = ""
        while (token_count > maxTokens) and (windowSize < len(lines)):
            # Trim out the middle lines, +/- windowSize
            trimmedLines = []
            middleIdx = len(lines) // 2
            trimStartIdx = max(0, middleIdx - windowSize)
            trimEndIdx = min(len(lines), middleIdx + windowSize)
            trimmedLines = lines[:trimStartIdx] + ["# (Up to " + str(windowSize) + " lines trimmed for space)"] + lines[trimEndIdx:]
            trimmedComponent = "\n".join(trimmedLines)
            token_count = countTokens(trimmedComponent)

            # Increase the window size
            windowSize += 1

        if (token_count > maxTokens):
            print("WARNING: Could not trim the component to fit within the token limit.")
            return "# WARNING: Could not trim the component to fit within the token limit.  This may mean single lines exceed the token limit.\n" + componentIn
        # Return the trimmed component
        return trimmedComponent

    # This is a function for trimming the log file, that (tries to) keeps all things marked as 'error', since those are likely high-importance.
    def trimPromptComponentLog(self, logIn:list, maxTokens:int=10000):
        print("Trimming log with " + str(len(logIn)) + " lines to fit within " + str(maxTokens) + " tokens.")
        # Each element in the log is a dictionary with two keys: `type` and `message`.  We want to, at a minimum, keep all `error` types.
        # First, check if the log is already below the token limit

        # Ensure that 'logIn' is a list
        if (type(logIn) != list):
            print("##########################################")
            print("ERROR: 'logIn' is not a list.  Returning.")
            print("##########################################")
            return ["ERROR: component provided to `trimPromptComponentLog` is not a list (type is " + str(type(logIn)) + ")"]

        token_count = countTokens(json.dumps(logIn, indent=4))
        if (token_count <= maxTokens):
            return json.dumps(logIn, indent=4)
        initial_token_count = token_count

        # Pre-compute the token counts for each line -- this is a slow step, so if we pre-compute it, it speeds everything up.
        #tokenCountsPerLine = []
        tokenCountsPerLine = [0] * len(logIn)
        for idx in range(len(logIn)):
            tokenCountsPerLine[idx] = countTokens(json.dumps(logIn[idx], indent=4))

        messageJSON = [{"type": "meta", "message": "# (Up to " + str(1234567890) + " lines trimmed for space, but messages with type `error` retained)"}]
        token_count_message = countTokens(json.dumps(messageJSON, indent=4))

        # If it's above the max tokens, try to trim it
        # Try to trim the lines from the middle out
        windowSize = 1
        trimmedLog = []
        iterations = 0
        windowSizeStep = 1
        if (len(logIn) > 10000):
            windowSizeStep = len(logIn) // 1000

        while (token_count > maxTokens) and (windowSize < len(logIn)):
            iterations += 1
            #print("Iteration: " + str(iterations))

            # Trim out the middle lines, +/- windowSize
            trimmedLog = []

            # Find the boundaries of the part of the middle that we'll trim out
            middleIdx = len(logIn) // 2
            trimStartIdx = max(0, middleIdx - windowSize)
            trimEndIdx = min(len(logIn), middleIdx + windowSize)

            # But, we have to keep the errors
            middleErrors = []
            middleErrorTokenCounts = []
            token_count_middle_errors = 0
            for middleIdx1 in range(trimStartIdx, trimEndIdx):
                logEntry = logIn[middleIdx1]
                try:
                    if (logEntry["type"].lower() == "error"):
                        middleErrors.append(logEntry)
                        middleErrorTokenCounts.append(tokenCountsPerLine[middleIdx1])
                        token_count_middle_errors += tokenCountsPerLine[middleIdx1]
                except:
                    pass
            # If the number of tokens in the middle errors ends up being more than 25% of the message, then start subsampling the middle errors (just include the ones at the start and end)
            if (token_count_middle_errors > 0.25 * maxTokens):
                #print("*** Token count of middle errors is more than 25% of the message.  Subsampling the middle errors.")

                # Try to ratchet it up a bit
                middleWindowSize = 1
                found = False
                for middleWindowSize in range(1, len(middleErrors)//2):
                    candidateMiddleErrors = middleErrors[:middleWindowSize] + middleErrors[-middleWindowSize:]
                    # Use middleErrorTokenCounts
                    token_count_candidate_middle_errors = sum(middleErrorTokenCounts[:middleWindowSize]) + sum(middleErrorTokenCounts[-middleWindowSize:])
                    if (token_count_candidate_middle_errors > 0.25 * maxTokens):
                        found = True
                        break

                #print("Window size: " + str(middleWindowSize))

                # If we still can't get it down, then just take the first and last 5
                if (found == True):
                    middleErrors = middleErrors[:middleWindowSize] + middleErrors[-middleWindowSize:]
                    token_count_candidate_middle_errors = sum(middleErrorTokenCounts[:middleWindowSize]) + sum(middleErrorTokenCounts[-middleWindowSize:])

                else:
                    min_middle_errors = 5
                    if (len(middleErrors) < 2 * min_middle_errors):
                        min_middle_errors = len(middleErrors) // 2

                    middleErrors = middleErrors[:min_middle_errors] + middleErrors[-min_middle_errors:]
                    token_count_candidate_middle_errors = sum(middleErrorTokenCounts[:middleWindowSize]) + sum(middleErrorTokenCounts[-middleWindowSize:])

                token_count_middle_errors = token_count_candidate_middle_errors

            # Add the token counts from the first half and second half, plus any that we have to keep in the middle (that are 'errors')
            token_count_first_half = sum(tokenCountsPerLine[:trimStartIdx])
            token_count_second_half = sum(tokenCountsPerLine[trimEndIdx:])

            token_count_estimate = token_count_first_half + token_count_message + token_count_middle_errors + token_count_second_half

            # Count the number of lines that are included
            numLinesIncluded = trimStartIdx + (len(logIn) - trimEndIdx)

            MINIMUM_LINES_TO_INCLUDE = 20       # If we have less than this many lines, stop trimming the log.
            if (token_count_estimate > maxTokens) and (numLinesIncluded > 20):
                # If the estimate is too high, then increase the window size
                #windowSize += 1
                windowSize += windowSizeStep        # Makes it faster for large log files
                continue

            #print("Window: 0 -> " + str(trimStartIdx) + " and " + str(trimEndIdx) + " -> " + str(len(logIn)) + " (including " + str(len(middleErrors)) + " middle errors)")
            #print("Token count estimate: " + str(token_count_estimate) + " (first_half: " + str(token_count_first_half) + ", message: " + str(token_count_message) + ", middle_errors: " + str(token_count_middle_errors) + ", second_half: " + str(token_count_second_half) + ")")

            # If we reach here, then the estimate is below the max tokens, so we can assemble the trimmed log
            trimmedLogMiddle = [{"type": "meta", "message": "# (Up to " + str(windowSize) + " lines trimmed for space, but messages with type `error` retained)"}]
            trimmedLogMiddle2 = [{"type": "meta", "message": "# (End of trimming)"}]
            trimmedLog = logIn[:trimStartIdx] + trimmedLogMiddle + middleErrors + trimmedLogMiddle2 + logIn[trimEndIdx:]

            # End here
            break

        # Check the final token count
        token_count = countTokens(json.dumps(trimmedLog, indent=4))
        print("Final token count: " + str(token_count) + " . (Max tokens: " + str(maxTokens) + ", initial_token_count = " + str(initial_token_count) + ")")

        # If it's still above the max tokens, then return an error
        TOKEN_COUNT_TOLERANCE = 1000
        if (token_count > (maxTokens + TOKEN_COUNT_TOLERANCE)):
            print("WARNING: Could not trim the log to fit within the token limit.  Trying back-off method.")
            # Use a backoff method -- just start adding in lines (alternating from the top/bottom) until we're within the token limit
            trimmedLog = []
            logTop = []
            logBottom = []
            topIdx = 0
            bottomIdx = len(logIn) - 1
            middleMessage = [{"type": "meta", "message": "# (This is only a partial log -- lines trimmed for space"}]

            cycleCount = 0
            while (token_count < (maxTokens + TOKEN_COUNT_TOLERANCE)) and (cycleCount < 1000):     # Add a hard limit of 1000 cycles here, for the backoff, just in case
                # Check to see if adding these lines will put us over the token limit
                logTop = logIn[:topIdx]
                logBottom = logIn[bottomIdx:]
                tempTrimmedLog = middleMessage + logTop + middleMessage + logBottom
                token_count = countTokens(json.dumps(tempTrimmedLog, indent=4))
                if (token_count < (maxTokens + TOKEN_COUNT_TOLERANCE)):
                    trimmedLog = tempTrimmedLog

                # Increment the top and bottom indices
                topIdx += 1
                bottomIdx -= 1

                # If the top and bottom have met, then break
                if (topIdx >= bottomIdx):
                    break

                cycleCount += 1
                print("Cycle: " + str(cycleCount) + "  Token count: " + str(token_count) + "  Max tokens: " + str(maxTokens) + " topIdx: " + str(topIdx) + " bottomIdx: " + str(bottomIdx))

            #return "# WARNING: Could not trim the log to fit within the token limit.  This may mean single lines exceed the token limit.\n" + json.dumps(logIn, indent=4)

        # Return the trimmed log
        print("Trimmed log to " + str(len(trimmedLog)) + " lines.")
        return json.dumps(trimmedLog, indent=4)


    # Sometimes a LLM will not generate a complete code listing when modifying code, but will instead write something like "# REST OF THE CODE HERE".
    # This function will attempt to detect (and fix) this with two calls:
    # First: A call to a cheap, quick LLM to detect it
    # Second: A call to a more expensive LLM to fix it
    def check_code_is_complete(self, last_code:str, last_requirements:str, current_code:str, current_requirements:str, model_detect_str:str, model_fix_str:str, max_tokens:int):
        total_cost = 0.0

        # Step 1: Detection
        prompt_detection = "You are ScientistGPT, the most advanced AI scientist and coder in the world. You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientifically, with integrity.\n\n"
        prompt_detection += "Previously you were given a coding task.  You were given input code, and had to modify the code in some way (usually to fix an issue).\n"
        prompt_detection += "The code that you generate will be directly copy and pasted into an interpreter, and run, without human intervention -- so it must be complete.\n"
        prompt_detection += "An infrequent (but serious) issue is that the code you generate will not be complete, and include things like `# REST OF THE CODE HERE`, where code from the reference is intended to be automatically copy/pasted.\n"
        prompt_detection += "Your current task is to detect whether there are any such `# REST OF THE CODE HERE` / incomplete code issues in the code you generated.\n"
        prompt_detection += "NOTE: The task here is only to DETECT whether the issue exists, NOT TO FIX IT.  If an issue exists, the fixing will be done by another separate step.\n"
        prompt_detection += "NOTE: The task is also not to otherwise reflect on the correctness of the code, or to try to fix it -- it is ONLY to detect whether this specific issue (the code not being complete/runnable due to it not being completely generated) exists.\n"
        prompt_detection += "\n"
        prompt_detection += "Below I will supply the following:\n"
        prompt_detection += "1. The code you generated in the CURRENT step (including CODE and REQUIREMENTS.TXT)\n"
        prompt_detection += "2. The code you generated in the LAST step (including CODE and REQUiREMENTS.TXT)\n"
        prompt_detection += "\n"
        prompt_detection += "Your task is to DETECT if the code you generated in the CURRENT step has any incomplete code issues that would be resolved by merging with the code from the LAST step.\n"
        prompt_detection += "Definition of incomplete code issues: The code under CURRENT CODE STEP below is not directly runnable, as-is, were it copied and pasted directly into a file and run fully automatically without modification.\n"
        prompt_detection += "Examples of incomplete code issues:\n"
        prompt_detection += "- It includes comments like '# REST OF THE CODE HERE' or '# INSERT PREVIOUS CODE HERE' or '# SAME AS PREVIOUS CODE' that indicate that the code is not complete\n"
        prompt_detection += "- It's missing code/otherwise appears that the code is cut off at the bottom.\n"
        prompt_detection += "- It says something like 'the code in the last step is runnable and does not require changes', without actually including the FULL, COMPLETE CODE from the LAST STEP into the CURRENT STEP. (i.e. so it's not runnable, or would execute nothing but comments if run)\n"
        prompt_detection += "\n"
        prompt_detection += "The output format is JSON -- you simply need to generate a dictionary that answers true/false to the incomplete code issues.  If there is an issue, the output should be {\"incomplete_code\": true}, otherwise it should be {\"incomplete_code\": false}.\n"
        prompt_detection += "\n"
        prompt_detection += "*SECTION*: CURRENT STEP CODE\n"
        prompt_detection += "REQUIREMENTS.TXT:\n"
        prompt_detection += "```\n"
        prompt_detection += str(current_requirements) + "\n"
        prompt_detection += "```\n"
        prompt_detection += "CODE:\n"
        prompt_detection += "```\n"
        prompt_detection += str(current_code) + "\n"
        prompt_detection += "```\n"
        prompt_detection += "\n"
        prompt_detection += "*SECTION*: LAST STEP CODE\n"
        prompt_detection += "REQUIREMENTS.TXT:\n"
        prompt_detection += "```\n"
        prompt_detection += str(last_requirements) + "\n"
        prompt_detection += "```\n"
        prompt_detection += "CODE:\n"
        prompt_detection += "```\n"
        prompt_detection += str(last_code) + "\n"
        prompt_detection += "```\n"
        prompt_detection += "\n"
        prompt_detection += "Your current task is to detect whether there are any such `# REST OF THE CODE HERE` / incomplete code issues in the code you generated.\n"
        prompt_detection += "NOTE: The task here is only to DETECT whether the issue exists, NOT TO FIX IT.  If an issue exists, the fixing will be done by another separate step.\n"
        prompt_detection += "NOTE: The task is also not to otherwise reflect on the correctness of the code, or to try to fix it -- it is ONLY to detect whether this specific issue (the code not being complete/runnable due to it not being completely generated) exists.\n"
        prompt_detection += "The output format is JSON -- you simply need to generate a dictionary that answers true/false to the incomplete code issues.  If there is an issue, the output should be {\"incomplete_code\": true}, otherwise it should be {\"incomplete_code\": false}.\n"
        prompt_detection += "The output must be between code blocks (```), or it will not automatically be parsed, and will not be useful.  For example, you should output the following if you detect the issue:\n"
        prompt_detection += "```\n"
        prompt_detection += "{\"incomplete_code\": true}\n"
        prompt_detection += "```\n"
        prompt_detection += "Or the following if you do not detect the issue:\n"
        prompt_detection += "```\n"
        prompt_detection += "{\"incomplete_code\": false}\n"
        prompt_detection += "```\n"
        prompt_detection += "The key must be `incomplete_code`, and the value must be boolean `true` or `false`. The dictionary must be between code blocks (```).\n"
        prompt_detection += "Please generate the output now.\n"

        # Get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt_detection, model=model_detect_str, maxTokens=400, temperature=0.0, jsonOut=True)
        total_cost += cost

        # Parse the response
        incomplete_code = False
        try:
            incomplete_code = responseJSON["incomplete_code"]
        except:
            pass

        # If the response is not a boolean, then return an error
        if (type(incomplete_code) != bool):
            return {
                "success": False,
                "errors": ["ERROR: Could not parse the response from the LLM.  The response was not a boolean value."],
                "cost": total_cost
            }

        # If the response is False, then the current code is good
        if (incomplete_code == False):
            return {
                "success": True,
                "incomplete_code": False,
                "code": current_code,
                "requirements": current_requirements,
                "cost": total_cost
            }

        # If the response is True, then we need to fix the code
        # Step 2: Fixing
        prompt_fix = "You are ScientistGPT, the most advanced AI scientist and coder in the world. You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientifically, with integrity.\n\n"
        prompt_fix += "Previously you were given a coding task.  You were given input code, and had to modify the code in some way (usually to fix an issue).\n"
        prompt_fix += "The code that you generate will be directly copy and pasted into an interpreter, and run, without human intervention -- so it must be complete.\n"
        prompt_fix += "An infrequent (but serious) issue is that the code you generate will not be complete, and include things like `# REST OF THE CODE HERE`, where code from the reference is intended to be automatically copy/pasted.\n"
        prompt_fix += "** A PREVIOUS STEP DETECTED THAT THAT ERROR HAS OCCURRED HERE **\n"
        prompt_fix += "Your current task is to fix this error, and output complete, runnable, working code.\n"
        prompt_fix += "\n"
        prompt_fix += "Below I will supply the following:\n"
        prompt_fix += "1. The code you generated in the CURRENT step (including CODE and REQUIREMENTS.TXT).  An error has been detected here where you have something like `# Paste the rest of the code here` or `# Rest of the code here` or something similar.\n"
        prompt_fix += "2. The code you generated in the LAST step (including CODE and REQUiREMENTS.TXT)\n"
        prompt_fix += "Your task is to fix the code, nominally through pasting the correct sections from the LAST STEP into the CURRENT STEP, while retaining the parts of the CURRENT STEP that were changed. \n"
        prompt_fix += "NOTE: You should not be otherwise changing the code, to fix other errors -- only fixing the incomplete code issue.  Any other errors (if there are any) are handled in separate steps, not this step.\n"
        prompt_fix += "The output format is to output the `requirements.txt` and `python code` in between code blocks -- this is described more at the end.\n"
        prompt_fix += "\n"
        prompt_fix += "*SECTION*: CURRENT STEP CODE\n"
        prompt_fix += "REQUIREMENTS.TXT:\n"
        prompt_fix += "```\n"
        prompt_fix += str(current_requirements) + "\n"
        prompt_fix += "```\n"
        prompt_fix += "CODE:\n"
        prompt_fix += "```\n"
        prompt_fix += str(current_code) + "\n"
        prompt_fix += "```\n"
        prompt_fix += "\n"
        prompt_fix += "*SECTION*: LAST STEP CODE\n"
        prompt_fix += "REQUIREMENTS.TXT:\n"
        prompt_fix += "```\n"
        prompt_fix += str(last_requirements) + "\n"
        prompt_fix += "```\n"
        prompt_fix += "CODE:\n"
        prompt_fix += "```\n"
        prompt_fix += str(last_code) + "\n"
        prompt_fix += "```\n"
        prompt_fix += "\n"
        prompt_fix += "Your current task is to fix any incomplete code error in the CURRENT STEP CODE, based on the reference code in the LAST STEP CODE.  Any changes in the CURRENT STEP CODE should be *retained*, since it's supposed to be a better, fixed version of the last step code (minus the `# put rest of code here` issue).\n"
        prompt_fix += "The code that you generate will be automatically, directly copy/pasted and run without human intervention, so the code must be complete and correct.\n"
        prompt_fix += "NOTE: You should not be otherwise changing the code, to fix other errors -- only fixing the incomplete code issue.  Any other errors (if there are any) are handled in separate steps, not this step.\n"
        prompt_fix += "*OUTPUT FORMAT*\n"
        prompt_fix += "The output format is to output the `requirements.txt` and `python code` in between separate code blocks (```).  The first code block MUST be the `requirements.txt` file.  The second code block MUST be the python file (that will be `main.py`).\n"
        prompt_fix += "There should always be exactly two sets of codeblocks, one for requirements, and one for code, even if the requirements are empty.  If the requirements are empty, just output a blank line in that codeblock.\n"
        prompt_fix += "While you can briefly output plain text to help you think before the codeblocks, the content within the codeblocks must be only the `requirements.txt` and code, as these will be automatically copy/pasted and placed into the appropriate files.\n"
        prompt_fix += "Output example:\n"
        prompt_fix += "requirements.txt:\n"
        prompt_fix += "```\n"
        prompt_fix += "numpy==1.21.2\n"
        prompt_fix += "```"
        prompt_fix += "code:\n"
        prompt_fix += "```\n"
        prompt_fix += "import numpy as np\n"
        prompt_fix += "print(np.random.rand(5))\n"
        prompt_fix += "```\n"
        prompt_fix += "Please generate the output now.\n"

        # Send the prompt
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt_fix, model=model_fix_str, maxTokens=max_tokens, temperature=0.0, jsonOut=False)

        success, requirements, code = self.parseRequirementsAndCodeFromLLM(responseText, numCodeblocks=2)
        total_cost += cost

        # Check for success
        if (success is False):
            return {
                "success": False,
                "errors": ["ERROR: Could not extract codeblocks from response."],
                "cost": total_cost
            }

        # Success -- return the requirements and code
        return {
            "success": True,
            "incomplete_code": True,
            "requirements": requirements,
            "code": code,
            "cost": total_cost
        }



    # This is one of the main experiment running prompts.
    # Reflect on the code, execution results, and codeblocks, and try to generate new code that fixes any issues.
    def reflectCodeblocks(self, lastCodeStruct:dict, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, follow_on_description=None, max_runtime_seconds=None, change_log=None, use_faithfulness_reflection:bool=False):
        # lastCodeStruct keys:
        # instructionStr: the instruction string used in the last code generation
        # codeblock_names: list of codeblock names used in the last code generation
        # requirements: requirements file
        # code: lastest version of Python code
        # supporting_files: any supporting files -- these will NOT be included in the prompt.
        # exec_result: an array of the results of the code execution, with the last result being the most recent.  Direct from the ModuleRunPythonInDocker module.

        # Get the instruction string
        instructionStr = lastCodeStruct["instruction_str"]
        # Get the codeblock names
        codeblockNames = lastCodeStruct["codeblock_names"]
        # Get the supporting files
        supportingFiles = lastCodeStruct["supporting_files"]
        # Get the current experiment mode
        currentPilotMode = "MINI_PILOT"
        if ("next_pilot_mode" in lastCodeStruct):
            currentPilotMode = lastCodeStruct["next_pilot_mode"]

        # Unpack the last execution results
        execResult = []
        lastExecResult = None
        pipStdOut = None
        pipStdErr = None
        pythonStdOut = None
        pythonStdErr = None
        dockerErrors = None
        log = None
        lastResultJson = None
        llmUsage = None

        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            execResult = lastCodeStruct["exec_result"]
            lastExecResult = lastCodeStruct["exec_result"][-1]

            pipStdOut = lastExecResult["pip.stdout"]
            pipStdErr = lastExecResult["pip.stderr"]
            pythonStdOut = lastExecResult["python.stdout"]
            pythonStdErr = lastExecResult["python.stderr"]
            dockerErrors = []
            if ("execution_errors" in lastExecResult):
                dockerErrors = lastExecResult["execution_errors"]
            if ("log" in lastExecResult):
                log = lastExecResult["log"]
            if ("results_json" in lastExecResult):
                lastResultJson = lastExecResult["results_json"]
            if ("llm_proxy_usage" in lastExecResult):
                llmUsage = lastExecResult["llm_proxy_usage"]

        # Start building the reflection prompt

        # First, try to retrieve all the codeblocks mentioned
        retrievedCodeblocks = []
        retrievedCodeblockDict = {}
        retrievalErrors = []
        for name in codeblockNames:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                retrievedCodeblocks.append(codeblock)
                retrievedCodeblockDict[name] = codeblock
            else:
                retrievalErrors.append("ERROR: Could not find codeblock with name: " + str(name))

        # Check if any codeblocks were not found
        if (len(retrievalErrors) > 0):
            print("ERROR: Could not find all requested codeblocks." + "\n".join(retrievalErrors))
            return {
                "errors": retrievalErrors
            }

        # Get a list of the summaries for the codeblocks that were NOT included
        codeblock_summaries_for_remaining_codeblocks = self.get_codeblock_summaries_raw()
        # `Codeblock_summaries` is a dictionary with the codeblock name as the key.  Remove any codeblocks (i.e. keys) that were included.
        for name in codeblockNames:
            if (name in codeblock_summaries_for_remaining_codeblocks):
                del codeblock_summaries_for_remaining_codeblocks[name]


        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Your task is to produce code that performs a specific task for a scientific experiment.  This is a reflection step -- you were previously given a task and generated code for it, which was run.  You will be shown the results, and asked to fix any errors. If everything looks good -- i.e. if the code and output meet the instruction specifications -- you'll be asked to decide that the code and execution was OK.\n"
        prompt += "To support this task, you will be provided (below):\n"
        prompt += "1. The instruction string from the previous task\n"
        prompt += "2. Example code you were provided to generate the code\n"
        prompt += "3. The code (and requirements.txt) you generated\n"
        prompt += "4. The results of running the code, including any logs\n"
        prompt += "\n"

        #prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        if (follow_on_description is None):
            prompt += "Your task description for the code was the the following:\n"
        else:
            prompt += "You are being asked to modify this experiment for a follow-on experiment.  I will show you both the original task description, and the follow-on instructions. Here is the task description for the original experiment:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"

        if (follow_on_description is not None):
            prompt += "\n"
            prompt += "VERY IMPORTANT: Here is the task description for the follow-on experiment (*this is what you should be working on right now!*):\n"
            prompt += "```\n"
            prompt += follow_on_description + "\n"
            prompt += "```\n"
            prompt += "\n"

        # Change log
        if (change_log is not None):
            prompt += "*Change Log*\n"
            prompt += "Below is the automatically generated change log, to help you know the changes that have been made along the way.  The last element is the set of most recent changes/issues.\n"
            prompt += "```\n"
            prompt += json.dumps(change_log, indent=4) + "\n"
            prompt += "```\n"
            prompt += "\n"

        # additional_simulated_code_issues
        try:
            last_additional_simulated_code_issues = None
            if ("additional_simulated_code_issues" in lastCodeStruct) and (lastCodeStruct["additional_simulated_code_issues"] is not None):
                last_additional_simulated_code_issues = lastCodeStruct["additional_simulated_code_issues"]
                if (len(last_additional_simulated_code_issues) > 0):
                    prompt += "*ADDITONAL KNOWN ISSUES*\n"
                    prompt += "The following issues were previously identified with this code (though this list may not be exhaustive).  You should include these amoungst your fixes for this experiment code:\n"
                    prompt += "```\n"
                    prompt += json.dumps(last_additional_simulated_code_issues, indent=4) + "\n"
                    prompt += "```\n"
                    prompt += "\n"

        except Exception as e:
            import traceback
            print("Error in additional_simulated_code_issues: " + str(e) + "\n" + traceback.format_exc())

        prompt += "\n"
        prompt += "*PILOT MODE*: The requested pilot mode is: `" + str(currentPilotMode) + "`.  While the code should support all 3 pilot modes through a global variable (`MINI_PILOT`, `PILOT`, and `FULL_EXPERIMENT`), the pilot mode (`" + str(currentPilotMode) + "`) should be the one that is enabled.  If it is not currently enabled in the code, please enable it. (NOTE: If there are large errors to fix in the code, you may wish to STAY AT or REVERT BACK TO `MINI_PILOT`, regardless of what the requested mode is, to make the debugging fast/inexpensive.)\n"
        prompt += "\n"

        # Code library / code blocks
        prompt += "\n"
        prompt += "*SECTION: Common code library, and code examples (called `codeblocks`)*\n"
        prompt += "- You have access to a common library (`experiment_common_library`) that contains useful functions, and you can directly import them into your code.  The common library is provided below.\n"
        prompt += "- In addition, you have a number of `codeblock tempates`, which are vetted code examples that (often) reference the common library.  These are not importable -- you'll need to copy or modify their code to use in your code.\n"
        prompt += "\n"
        prompt += "*SUBSECTION: Common code library\n"
        prompt += "The common library is provided below.  You can directly import these functions into your code.\n"
        prompt += "```\n"
        prompt += self.getCommonLibrary() + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Add the codeblocks
        prompt += "*SUBSECTION: Codeblocks (vetted code templates you should base your code on, if possible)\n"
        numCodeblocks = len(retrievedCodeblocks)
        prompt += "You have been provided with " + str(numCodeblocks) + " template codeblocks to assist you.  They are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        prompt += "You should base your code AS MUCH AS POSSIBLE on these codeblocks, as (though they may look a little different than examples on the internet), they are VETTED, KNOWN-GOOD examples that you should DIRECTLY COPY as much as possible.  Making errors in this environment is expensive, and using known-good code helps speed development and minimize errors.  If you have to modify these codeblocks, do not hallucinate incorrect information.\n"
        prompt += "The code in the codeblocks is NOT IMPORTABLE -- it is meant to be COPY AND PASTED (with whatever modifications are required) into your code.\n"
        for idx, codeblock in enumerate(retrievedCodeblocks):
            prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
            prompt += "```\n"
            prompt += codeblock["codeblock_raw"] + "\n"
            prompt += "```\n"
            prompt += "\n"


        # # Codeblocks
        # numCodeblocks = len(retrievedCodeblocks)
        # prompt += "You have been provided with " + str(numCodeblocks) + " template codeblocks to assist you.  They are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        # prompt += "You should base your code AS MUCH AS POSSIBLE on these codeblocks, as (though they may look a little different than examples on the internet), they are VETTED, KNOWN-GOOD examples that you should DIRECTLY COPY as much as possible.  Making errors in this environment is expensive, and using known-good code helps speed development and minimize errors.  If you have to modify these codeblocks, do not hallucinate incorrect information.\n"
        # prompt += "The code in the codeblocks is NOT IMPORTABLE -- it is meant to be COPY AND PASTED (with whatever modifications are required) into your code.\n"
        # for idx, codeblock in enumerate(retrievedCodeblocks):
        #     prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
        #     prompt += "```\n"
        #     prompt += codeblock["codeblock_raw"] + "\n"
        #     prompt += "```\n"
        #     prompt += "\n"

        # Codeblock summaries for codeblocks that were NOT picked
        prompt += "*SUBSECTION: Codeblock summaries for codeblocks that were NOT picked*\n"
        prompt += "Below are summaries of template codeblocks that are in the library but were NOT listed to be included in the full listings above.  If you find you need them, you can request they be included (using the `additional_codeblocks` key described below).\n"
        prompt += "```\n"
        prompt += json.dumps(codeblock_summaries_for_remaining_codeblocks, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Requirements and code
        prompt += "*SECTION: Your current code and requirements*\n"
        max_section_tokens = 8000
        prompt += "\n"
        prompt += "The requirements.txt file you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["requirements"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "The code you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["code"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "*SECTION: Results of running the code*\n"
        prompt += "The results of running the code are below.\n"
        prompt += "*SUBSECTION: stdout, stderr, container, llm usage*\n"
        prompt += "The pip stderr output is below:\n"
        prompt += "```\n"
        prompt += str(pipStdErr) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The python stdout output is below:\n"
        prompt += "```\n"
        #prompt += str(pythonStdOut) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(str(pythonStdOut), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The python stderr output is below:\n"
        prompt += "```\n"
        #prompt += str(pythonStdErr) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(str(pythonStdErr), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The Docker errors are below:\n"
        prompt += "```\n"
        #prompt += json.dumps(dockerErrors, indent=4) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(json.dumps(dockerErrors, indent=4), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        # LLM Usage
        prompt += "Any large language model (LLM) usage by the code is below:\n"
        prompt += "```\n"
        prompt += json.dumps(llmUsage, indent=4) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += "```\n"

        # Results file
        prompt += "\n"
        prompt += "*SUBSECTION: Results file, and log file*\n"
        prompt += "RESULTS: You should save any results (both final results, and intermediate results for further processing) in a file called `results.json`."
        prompt += "The results file (results.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(lastResultJson, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE
        if (lastResultJson is not None):
            prompt += self.trimPromptComponent(json.dumps(lastResultJson, indent=4), maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "# No `results.json` file found. This is a major error.\n"
        prompt += "```\n"
        # Log file
        prompt += "The log file (log.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(log, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE  (and highlighting ERRORs?)
        if (log is not None):
            prompt += self.trimPromptComponentLog(log, maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "# No `log.json` file found. This is a major error. Please see the logger codeblock example.  The log is a JSON list, with each list element containg two keys: `type` (str, usually 'info', 'debug', or 'error') and `message` (str). \n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "*SECTION: Your current task: Reflection / Code Iteration*\n"
        prompt += "You should now reflect on the code you generated, the results of running the code, and the logs.  If there are any errors, you should fix them.  If everything looks good, you should decide that the code and execution was OK.\n"
        # prompt += "Your output should be in JSON format, with the following format:\n"
        # prompt += "- If the code and execution was OK, return a JSON dictionary with a single key: `is_ok`, and a value of `true`. e.g. `{\"is_ok\": true}`\n"
        # prompt += "- If there were errors, return a JSON dictionary with 4 keys: `issues`, `requirements`, `code`, and `summary_of_changes`. `issues` should be a list of strings briefly describing any issues that were identified, and what their fixes are. `requirements` is a string whose text will be directly copied to build a pip environment file (requirements.txt). `code` is a string whose text will be directly copied to build the code to run (main.py).  `summary_of_changes` should briefly describe how the code was changed to address any issues.  All requirements and code must be correct and ready to run, as these will be automatically run, and not examined by humans or other processes before being automatically run.\n"
        # prompt += "Remember, your code must be:\n"
        # prompt += "1. Correct and accurate, or it will produce wrong answers.\n"
        # prompt += "2. Adhere to the correct API usage, as provided in the examples, and not hallucinate or otherwise extrapolate/guess function names, or it is unlikely to work\n"
        # prompt += "3. Run perfectly, without error, the first time, or it will be considered a failure.\n"
        # prompt += "4. Run correctly without human intervention, as it will be run automatically immediately after it is generated without human review or modification.\n"
        # prompt += "Remember, any errors you identify must be:\n"
        # prompt += "- Not hallucinated. Do not hallucinate errors that do not exist.\n"
        # prompt += "- Actual errors that affect the correctness of the code, data, or experiment. Do not report `errors` that are not errors, e.g., trying to make a loop more efficient, when this is not an actual error. We do not have infinite time or budget to make the code beautiful.\n"
        # prompt += "- Perceived Code/API errors that are not actually generating errorful behavior -- especially if these are adhering to the examples.  The example codeblocks provide known-good human-vetted implementations, and should be preferentially used in all cases except for when they are producing errors.\n"


        prompt += "Please provide your code below.  The output format is as follows: Your output should be between three (and exactly three) codeblocks (```).  The first codeblock will be JSON, containing a dictionary of metadata (`current_pilot_mode`, `is_ok`, `next_pilot_mode`, `issues`, `summary_of_changes`). The second codeblock will be the contents of the `requirements.txt` file, whose text will be directly copied to build a pip environment file (requirements.txt).  The third codeblock will be the contents of the `main.py` file, which is the code that will be run.  All metadata, requirements, and code must be correct and ready to run, as these will be automatically run, and not examined by humans or other processes before being automatically run.\n"
        #prompt += "Please provide your code below.  The output format is as follows: Your output should be between two (and exactly two) codeblocks (```).  The first codeblock will be the contents of the `requirements.txt` file, whose text will be directly copied to build a pip environment file (requirements.txt).  The second codeblock will be the contents of the `main.py` file, which is the code that will be run.  All requirements and code must be correct and ready to run, as these will be automatically run, and not examined by humans or other processes before being automatically run.\n"
        # Added section about writing debuggable/testable code
        prompt += "\n"
        prompt += "*SUBSECTION: Writing debuggable/testable experiment code*\n"
        prompt += "Here are some additional considerations when writing your experiment code:\n"
        prompt += "(a) The code you're writing is scientific code to perform an experiment to test a specific hypothesis.  It should be written in a scientific, systematic, and rigorous manner, with integrity.\n"
        prompt += "(b) It's very easy to make mistakes, and very hard to find them.  Your code should include *THOROUGH* checks for errors, or assumptions that may not be true.\n"
        prompt += "(c) During the MINI_PILOT phase of the experiment, you should be very verbosely outputting information about the internal workings of your code to the log file, and do so in a way that is easy to understand, interpret, and spot errors in logic or assumptions. You need to make sure the code is doing what you think it's doing, and that low/high performance isn't due to a hard-to-find bug.\n"
        prompt += "(d) Testing Example 1: You're sending a prompt to an LLM and expecting a response back in a certain format that's easy to parse.  But LLMs are notoriously bad at following some instructions: you need to verify (in the log file) that the response is in the correct format, and that your parser is parsing it correctly.  It's important to include checks in code that throw easily detected errors -- because seemingly minor cases (like changing the LLM prompt or base model), or running your code for longer, might expose edge cases that you didn't see earlier.\n"
        prompt += "(e) Testing Example 2: You've made an agent that switches back-and-forth between different modes of operation based on some trigger.  What if that trigger never happens?  Or what if it gets stuck in one mode under certain conditions?  Or always repeats the same action?  Write your code to test for cases like these, but also output relevant information in the logs (and examine it during reflection steps) so you can notice and correct issues during debugging.\n"
        prompt += "\n"

        # Added section about writing pilot experiments
        prompt += "*SUBSECTION: Writing pilot experiments*\n"
        prompt += " - There should be a global variable in your code (PILOT_MODE:str) with three possible settings: `MINI_PILOT`, `PILOT`, or `FULL EXPERIMENT`.\n"
        prompt += " - The current setting of the PILOT_MODE should be whatever setting is requested by the experiment.  If no setting was explicitly requested, default to `MINI_PILOT`.\n"
        prompt += " - The `MINI_PILOT` setting should run on a very small subset of the data, and should be able to run in a few minutes.  The purpose is for fast debugging and verification of the code. For example, for question answering tasks, this might be 10 questions.  For agent tasks, this might be 2-3 episodes at 10-20 steps each.  The questions/episodes should come from the training set.\n"
        prompt += " - The `PILOT` setting should be a moderate subset of the data, ideally running in less than 1-2 hours. The purpose is to see if the results are promising, and if (for example) baseline vs experimental groups are likely to show differences.  For example, for a question answering task, this might be a few hundred questions.  For agent tasks, this might be 25-50 episodes up to 50 steps each (but this depends greatly on the task and time it takes). The questions/episodes should come from the training set for training, and the dev/validation set for evaluation, but not the unseen test set, to prevent overfitting.\n"
        prompt += " - The `FULL EXPERIMENT` setting should be the full experiment, with all data, all steps, etc.  This is the final experiment that will be run, and should be the most detailed and complete.  Training data should come from the training set.  Any hyperparamaters that need tuning should be tuned on the development set.  The experiment should be evaluated on the test set.\n"
        prompt += " - In all cases, appropriate inferrential and summary statistics should be reported, as well as any follow-on analyses. The difference between pilot levels is simply of scale, not of quality.\n"
        prompt += "\n"

        # Maximum runtime.
        if (max_runtime_seconds is not None):
            prompt += "*SUBSECTION: Maximum experiment runtime*\n"
            prompt += " - This experiment is run in a container.\n"
            prompt += " - The container has a user-defined maximum runtime of " + str(max_runtime_seconds) + " seconds per debug iteration.  If the experiment exceeds this runtime, it will be terminated.  Whatever files exist (e.g. logs, results, etc.) will still be reported, as of their last save.\n"
            prompt += " - If you're creating experments that are hitting the runtime limit, please consider reducing the size of the experiment.  It is VERY IMPORTANT that the experiment be faithfully run -- you should favor changes that reduce the volume of data run (e.g. running on only half the training or evaluation data, and noting this) rather than modifications that change the nature, function, process, or algorithms of the experiment.\n"
            prompt += "\n"

        # Codeblock reminders
        prompt += "*SUBSECTION: Codeblock reminders*" + "\n"
        prompt += " - VERY IMPORTANT: A common kind of error you make is, if you're not confident in how to implement something, you often just 'simulate' it by making code that fakes the procedure (like a fake benchmark, LLM call, algorithm, etc.). THIS IS NOT GOOD.\n"
        prompt += " - Whenever possible, the codeblock templates should be used to implement the procedures they describe.  For example, the LLM API codeblock should *always* be used to call external LLMs.  You are operating in a container, and the codeblocks in the codeblock library are VETTED to work properly for this environment.\n"
        prompt += " - Similarly, this is a scientific experiment.  Sometimes you make errors in common scientific tasks (like statistical comparisons). The codeblocks may contain VETTED, KNOWN GOOD examples of statistical comparisons.  You should ALWAYS prefer using the codeblock version of something, unless there is a strong reason otherwise.\n"
        prompt += " - If, for whatever reason, the codeblock isn't included in your list of full examples, BUT it is included in the library, you can request it be included in the full list by adding it to the `additional_codeblocks` list in the metadata.\n"
        prompt += " - The major source of error in the experiment building and debugging process is failure to find and use the codeblocks properly.  Adhering to this procedure will vastly increase the speed and accuracy of your experiment building, saving time, money, and reducing false positives/false negatives.\n"
        prompt += " - The codeblocks often use the common library (`experiment_common_library`).  Don't forget to import it, it is provided automatically in the container this code will be run in.\n"
        prompt += "\n"

        # General reminders
        prompt += "*SUBSECTION: Specific reminders for this task*\n"
        prompt += "Remember, your code must be:\n"
        prompt += "The metadata JSON dictionary should have the following format:\n"
        prompt += "- `current_pilot_mode`: string.  One of `MINI_PILOT`, `PILOT`, or `FULL EXPERIMENT`.\n"
        if (follow_on_description is None):
            prompt += "- `is_ok_stage`: boolean.  value of `true` if you are confident the code is doing what it's supposed to do (as per the experiment instructions), and the execution is OK.  Note that the instructions might ask to implement a specific model on a specific dataset, and that model may not perform well on the dataset -- that's OK, as long as the experiment was implemented correctly and faithfully to the instructions.  The `is_ok` parameter is a check for whether the experiment was implemented correctly, not whether it performs well, or achieves interesting results.  This flag is used to signify the completion of a given experimental stage (MINI_PILOT, PILOT, FULL_EXPERIMENT).\n"
            prompt += "- `is_ok`: boolean.  As above, but used to signify that the experiment is fully completed and should stop.  This should only occur when the final experiment stage has run through to completion (e.g. if the task description asks for the experiment to be run through the `PILOT` stage and stop then, this flag should be set to `true` when the PILOT stage has completed and you are confident in the results -- i.e. not if only the MINI_PILOT has run successfully.\n"
        else:
            prompt += "- `is_ok_stage`: boolean.  value of `true` if you are confident the code is doing what it's supposed to do (as per the experiment instructions *AND FOLLOW-ON MODIFICATION INSTRUCTIONS*), and the execution is OK.  Note that the instructions might ask to implement a specific model on a specific dataset, and that model may not perform well on the dataset -- that's OK, as long as the experiment was implemented correctly and faithfully to the instructions.  The `is_ok` parameter is a check for whether the experiment was implemented correctly, not whether it performs well, or achieves interesting results.  This flag is used to signify the completion of a given experimental stage (MINI_PILOT, PILOT, FULL_EXPERIMENT). BUT, sometimes there are errors in the pilot mode -- you should only signify `is_ok` is true if the expected mode ACTUALLY ran, based on the code and output.\n"
            prompt += "- `is_ok`: boolean.  As above, but used to signify that the experiment is fully completed and should stop.  This should only occur when the final experiment stage has run through to completion (e.g. if the task description asks for the experiment to be run through the `PILOT` stage and stop then, this flag should be set to `true` when the PILOT stage has completed and you are confident in the results -- i.e. not if only the MINI_PILOT has run successfully.\n"
        prompt += "- `next_pilot_mode`: string. One of `MINI_PILOT`, `PILOT`, or `FULL EXPERIMENT`.  What pilot mode SHOULD the experiment be running in next time?  If it's finished the current mode, this should be the next mode.  If it's not finished in the current mode, this is likely the same mode.  If there's a mode error (i.e. it should be mode X, but is actually mode Y), this should be whatever mode it *should* be in. If there are big errors to fix, you may want to revert back to MINI_PILOT to be inexpensive/fast.\n"
        prompt += "- `issues`: list of strings.  Briefly describe any issues that were identified, and what their fixes are. \n" #Empty list if `is_ok` is true.\n"
        prompt += "- `summary_of_changes`: list of strings.  Briefly describe how the code was changed to address any issues. \n" #Empty list if `is_ok` is true.\n"
        prompt += "- `additional_codeblocks`: list of strings.  Normally an empty list.  If you need codeblocks from the codeblock library to assist in your experiment design/debugging that (for whatever reason) were not included in the initial prompt, list their names (exactly) here, and they will be included in the next debug iteration.\n"
        prompt += "\n"
        if (follow_on_description is not None):
            prompt += "\n"
            prompt += "SPECIAL NOTE REGARDING `is_ok` and `is_ok_stage` RELATING TO FOLLOW-ON EXPERIMENTS:\n"
            prompt += "This is a follow-on experient.  Your determination of the `is_ok` and `is_ok_stage` should be modified according to the requested modifications in the follow-on experiment. For example, if the original experiment said run 5 samples, and the follow-on says run to 10 samples, you should not mark the experiment OK if the last execution only ran 5 samples -- it MUST meet the requirements in the follow-on text to be considered OK.\n"
            prompt += "For reference, here are the follow-on experiment instructions:\n"
            prompt += "```\n"
            prompt += follow_on_description + "\n"
            prompt += "```\n"
            prompt += "\n"

        prompt += "Remember, your code must be:\n"
        prompt += "1. Correct and accurate, or it will produce wrong answers.\n"
        prompt += "2. Adhere to the correct API usage, as provided in the examples, and not hallucinate or otherwise extrapolate/guess function names, or it is unlikely to work\n"
        prompt += "3. Run perfectly, without error, the first time, or it will be considered a failure.\n"
        prompt += "4. Run correctly without human intervention, as it will be run automatically immediately after it is generated without human review or modification.\n"
        prompt += "5. Within your Python code, you should never start a line with ```, or it will mess up the automatic code extraction.\n"
        prompt += "6. Never use triple-quoted strings (e.g. \"\"\") in your Python code -- they will mess up the automatic code extraction.\n"
        prompt += "7. The code will be run in a container. Aside from the log files (log.json, results.json), no other files will be saved.  Any files that are NOT log.json or results.json (e.g. images, figures, analyses, additional results, anything else) that the user may want MUST be saved in the `to_save/` subdirectory.  Any files in `to_save` will automatically be downloaded.  This should ideally not include large files.\n"
        prompt += "8. You MUST always include exactly three (```) blocks.  The first MUST be the metadata. The second MUST be the requirements, even if it's empty.  The third MUST be the Python code.  If this isn't the case, the automatic parser will break. The codeblocks markers (```) MUST be on a newline, alone.\n"
        prompt += "\n"
        prompt += "Remember, any errors you identify must be:\n"
        prompt += "- Not hallucinated. Do not hallucinate errors that do not exist.\n"
        prompt += "- Actual errors that affect the correctness of the code, data, or experiment. Do not report `errors` that are not errors, e.g., trying to make a loop more efficient, when this is not an actual error. We do not have infinite time or budget to make the code beautiful.\n"
        prompt += "- Perceived Code/API errors that are not actually generating errorful behavior -- especially if these are adhering to the examples.  The example codeblocks provide known-good human-vetted implementations, and should be preferentially used in all cases except for when they are producing errors.\n"

        prompt += "Example output: \n"
        prompt += "The first codeblock is always metadata with the following keys: `current_pilot_mode`, `is_ok`, `is_ok_stage`, `next_pilot_mode`, `issues`, `summary_of_changes`, `additional_codeblocks`."
        prompt += "```\n"
        prompt += "{\n"
        prompt += "  \"current_pilot_mode\": \"MINI_PILOT\",   # Always a string\n"
        prompt += "  \"is_ok_stage\": false   # Always a boolean\n"
        prompt += "  \"is_ok\": false   # Always a boolean\n"
        prompt += "  \"next_pilot_mode\": \"MINI_PILOT\",   # Always a string\n"
        prompt += "  \"issues\": [\"ERROR: 'numpy' is not in the requirements file\"],  # Always a list of strings\n"
        prompt += "  \"summary_of_changes\": [\"Added 'numpy' to the requirements file\"]   # Always a list of strings\n"
        prompt += "  \"additional_codeblocks\": [\"codeblock1name\", \"codeblock2name\"]   # Always a list of strings\n"
        prompt += "}\n"
        prompt += "The second codeblock is always `requirements.txt`, even if empty."
        prompt += "```\n"
        prompt += "numpy==1.21.2\n"
        prompt += "```\n"
        prompt += "The third codeblock is always `main.py`."
        prompt += "```\n"
        prompt += "import numpy as np\n"
        prompt += "print(np.random.rand(5))\n"
        prompt += "```\n"
        ### Removing this since it just causes problems.
        ###prompt += "NOTE: If `is_ok` is true, provide empty responses for `requirements` and `code` to save time -- we'll just use the last code and requirements automatically.\n"

        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)

        metadata = None
        requirements = None
        code = None

        # Parse the codeblocks
        # parseRequirementsAndCodeFromLLM
        success, metadata, requirements, code = self.parseRequirementsAndCodeFromLLM(responseText, numCodeblocks=3)

        # Check if `responseJSON` is None -- if it is, there was some kind of error.  Try again once more
        if (success is False):
            print("ERROR: Could not successfully parse response.  Trying again once more.")
            prompt_retry = "**NOTE** THIS IS A RETRY, BECAUSE PARSING YOUR RESPONSE FAILED. THIS USUALLY HAPPENS IF THE RESPONSE WAS TOO LONG.  YOU LIKELY NEED TO CONDENSE YOUR CODE, BUT KEEP IT FUNCTIONALLY IDENTICAL.***\n"
            prompt_retry += "** ORIGINAL TASK DESCRIPTION FOLLOWS FROM HERE **\n"
            prompt_retry += prompt
            responseJSON, responseText, cost_ = getLLMResponseJSON(promptStr=prompt_retry, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)
            cost += cost_

            success, metadata, requirements, code = self.parseRequirementsAndCodeFromLLM(responseText, numCodeblocks=3)

        # A common issue (if, e.g. the prompt is generating, but the code is too long) is that the parsing will fail, but still throw 'success' for some reason.
        # This ends up being found later when the 'metadata' is empty. So, we'll check for that here, and end early if that's the case.
        error_no_metadata = False
        if (metadata is None) or (len(metadata) == 0):
            error_no_metadata = True

        # If the response is still None, then exit.
        if (success is None) or (error_no_metadata is True):
            print("ERROR: Was not able to successfully parse response during code reflection stage (after retrying).  This may indicate a JSON parsing issue, or the code may be too long. Exiting.")
            # TODO: Should this return None, so it's not stored?  Storing this might reset everything
            return {
                "instruction_str": instructionStr,
                "codeblock_names": codeblockNames,
                "requirements": lastCodeStruct["requirements"],
                "code": lastCodeStruct["code"],
                "codeblock_code": retrievedCodeblockDict,
                "supporting_files": supportingFiles,
                "model": modelStr,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "responseJSON": None,
                "responseText": None,
                "cost": cost,
                "error_code_parsing_issue": True,
                "errors": ["ERROR: Response JSON is None, even after retrying.  Likely a JSON parsing issue."]
            }

        # Check for the common issue where the LLM has sections of code like "# PASTE REST OF CODE HERE" -- this is a common error
        # def check_code_is_complete(self, last_code:str, last_requirements:str, current_code:str, current_requirements:str, model_detect_str:str, model_fix_str:str):
        # Detection model -- use something cheap (e.g. gpt-4o-mini) to detect the issue
        model_detect_str = "gpt-4o-mini"
        code_is_complete_result = self.check_code_is_complete(last_code=lastCodeStruct["code"], last_requirements=lastCodeStruct["requirements"], current_code=code, current_requirements=requirements, model_detect_str=model_detect_str, model_fix_str=modelStr, max_tokens=max_tokens)

        # Get the result
        # Check for errors
        code_complete_fixed = False
        code_complete_critical_error = False

        try:
            # Add cost to total experiment cost
            if ("cost" in code_is_complete_result):
                cost += code_is_complete_result["cost"]

            # Check result
            if (code_is_complete_result is None) or ((code_is_complete_result is not None) and (code_is_complete_result["success"] is False)):
                # Error -- should likely exit here
                print("ERROR CHECKING WHETHER CODE IS COMPLETE -- EXIT")
                code_complete_critical_error = True
            else:
                if ("fixed" in code_is_complete_result) and (code_is_complete_result["fixed"] is True):
                    code_complete_fixed = True
                    print("INFO: Code was fixed to be complete.")
                    code = code_is_complete_result["code"]
                    requirements = code_is_complete_result["requirements"]
                else:
                    print("INFO: Code was checked for issues and is complete.")

        except Exception as e:
            print("ERROR CHECKING WHETHER CODE IS COMPLETE -- EXIT")
            code_complete_critical_error = True


        # Parse any additional codeblocks that are mentioned
        additionalCodeblockNames = []
        if ("additional_codeblocks" in metadata):
            candidate_additional_codeblocks = []
            # If it's a list, add the list
            if (isinstance(metadata["additional_codeblocks"], list)):
                candidate_additional_codeblocks = metadata["additional_codeblocks"]
            # If it's a string, add the string
            elif (isinstance(metadata["additional_codeblocks"], str)):
                candidate_additional_codeblocks = [metadata["additional_codeblocks"]]

            # Now, check if the codeblock names are in the library
            for name in candidate_additional_codeblocks:
                codeblock = self.getCodeblockByName(name)
                if (codeblock is not None):
                    additionalCodeblockNames.append(name)
                else:
                    retrievalErrors.append("ERROR: Could not find additional codeblock with name: " + str(name))

            # Add the additional codeblocks to the list of codeblocks
            for name in additionalCodeblockNames:
                if (name not in codeblockNames):
                    codeblockNames.append(name)
                    print("INFO: Adding additional codeblock to specification: " + str(name))


        # Parse metadata for pilot mode, or the current stage of the experiment being completed.
        errors = []
        issues = None
        is_ok = None
        is_ok_stage = None
        summary_of_changes = None
        current_pilot_mode_extracted = None
        next_pilot_mode_extracted = None
        if ("issues" in metadata):
            issues = metadata["issues"]
        if ("summary_of_changes" in metadata):
            summary_of_changes = metadata["summary_of_changes"]
        if ("is_ok" in metadata):
            is_ok = metadata["is_ok"]
        if ("is_ok_stage" in metadata):
            is_ok_stage = metadata["is_ok_stage"]
        if ("current_pilot_mode" in metadata):
            current_pilot_mode_extracted = metadata["current_pilot_mode"]
        if ("next_pilot_mode" in metadata):
            next_pilot_mode_extracted = metadata["next_pilot_mode"]

            # If the is_ok key is present, the other keys won't be present -- but we'll bring forward the code and requirements
            # Removed this -- it has to generate the whole thing.
            # if (is_ok == True):
            #     if ("code" in lastCodeStruct):
            #         code = lastCodeStruct["code"]
            #     if ("requirements" in lastCodeStruct):
            #         requirements = lastCodeStruct["requirements"]


        #
        #   TODO: Add a secondary check to see if the code has any "simulation" components in it that should be real -- e.g. LLM calls, etc.
        #   Then, it should add these to the list of requested changes (and, make sure the `is_ok` flag is set to False, and `current_pilot_mode/next_pilot_mode` are set to the same value)
        # ERROR: THIS USES THE LAST CODE STRUCTURE -- IT SHOULD USE THE CURRENT CODE STRUCTURE.  That's what `packedOutCandidate`` is for (though it's super hacky)
        additional_simulated_code_issues = None
        packedOutCandidate = {
            "instruction_str": instructionStr,
            "codeblock_names": codeblockNames,
            "requirements": requirements,
            "code": code,
            "codeblock_code": retrievedCodeblockDict,
            "supporting_files": supportingFiles,
            "model": modelStr,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "responseJSON": responseJSON,
            "responseText": responseText,
            "cost": cost,
            "errors": errors,
            "exec_result": execResult,
            "issues": issues,
            "summary_of_changes": summary_of_changes,
            "additional_simulated_code_issues": additional_simulated_code_issues,
            "is_ok": is_ok,
            "is_ok_stage": is_ok_stage,
            "current_pilot_mode": currentPilotMode,
            "current_pilot_mode_extracted": current_pilot_mode_extracted,
            "code_complete_fixed": code_complete_fixed,
            "code_complete_critical_error": code_complete_critical_error,
            "next_pilot_mode": next_pilot_mode_extracted
        }

        additional_simulated_code_issues = None
        check_cost = 0
        if (use_faithfulness_reflection is True):
            # Check simulation for 'faithfulness' -- i.e. if the code is simulating something that should be real (or, missing codeblocks)
            additional_simulated_code_issues, check_cost = self.checkCodeForSimulationOrMissingCodeblocks(packedOutCandidate, modelStr=modelStr, max_tokens=max_tokens, temperature=temperature, follow_on_description=follow_on_description)

        cost += check_cost  # Add the cost of the check to the total cost
        candidate_additional_codeblocks = []
        # Check if there are any errors
        if (additional_simulated_code_issues is not None) and (len(additional_simulated_code_issues) > 0):
            is_ok = False
            #current_pilot_mode_extracted = currentPilotMode
            #next_pilot_mode_extracted = currentPilotMode

            # Try to parse, and add to `additional_codeblocks` if possible.
            # Check if it's a list
            if (type(additional_simulated_code_issues) is list):
                for issue in additional_simulated_code_issues:
                    if ("relevant_codeblocks" in issue):
                        # If it's a list, add each element of the list
                        if (isinstance(issue["relevant_codeblocks"], list)):
                            for name in issue["relevant_codeblocks"]:
                                candidate_additional_codeblocks.append(name)
                        # If it's a string, add the string
                        elif (isinstance(issue["relevant_codeblocks"], str)):
                            candidate_additional_codeblocks.append(issue["relevant_codeblocks"])
            # If it's a dictionary (i.e. single element generated incorrectly)
            elif (type(additional_simulated_code_issues) is dict):
                if ("relevant_codeblocks" in additional_simulated_code_issues):
                    # If it's a list, add each element of the list
                    if (isinstance(additional_simulated_code_issues["relevant_codeblocks"], list)):
                        for name in additional_simulated_code_issues["relevant_codeblocks"]:
                            candidate_additional_codeblocks.append(name)
                    # If it's a string, add the string
                    elif (isinstance(additional_simulated_code_issues["relevant_codeblocks"], str)):
                        candidate_additional_codeblocks.append(additional_simulated_code_issues["relevant_codeblocks"])

        # For any additional codeblocks that were identified, add them to the list of codeblocks
        for name in candidate_additional_codeblocks:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                if (name not in codeblockNames):
                    codeblockNames.append(name)
                    print("INFO: Adding additional codeblock to specification (from simulation errors): " + str(name))
            else:
                retrievalErrors.append("ERROR: Could not find additional codeblock with name: " + str(name))


        if (requirements is None):
            errors.append("ERROR: 'requirements' key not found in the response JSON")
        if (code is None):
            errors.append("ERROR: 'code' key not found in the response JSON")

        # Return the response
        packedOut = {
            "instruction_str": instructionStr,
            "codeblock_names": codeblockNames,
            "requirements": requirements,
            "code": code,
            "codeblock_code": retrievedCodeblockDict,
            "supporting_files": supportingFiles,
            "model": modelStr,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "responseJSON": responseJSON,
            "responseText": responseText,
            "cost": cost,
            "errors": errors,
            "exec_result": execResult,
            "issues": issues,
            "summary_of_changes": summary_of_changes,
            "additional_simulated_code_issues": additional_simulated_code_issues,
            "is_ok": is_ok,
            "is_ok_stage": is_ok_stage,
            "current_pilot_mode": currentPilotMode,
            "current_pilot_mode_extracted": current_pilot_mode_extracted,
            "code_complete_fixed": code_complete_fixed,
            "code_complete_critical_error": code_complete_critical_error,
            "next_pilot_mode": next_pilot_mode_extracted
        }

        return packedOut


    # The most common error in experiment building is that the LLM can't figure out how to do something, so it will just "simulate" it.
    # For example, it might not figure out how to do an LLM call, so it will "simulate" an LLM call, with fake/pretend output. This is a major error.
    # In some (many?) cases, there is a codeblock template that exists in the codeblock library that might address this.
    # The goal of this function is (1) to look for functions that are not implemented faithfully/that do this simulation/randomization stuff, and (2) for each function, to look for codeblock(s) that might address this.
    def checkCodeForSimulationOrMissingCodeblocks(self, lastCodeStruct:dict, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, follow_on_description=None):
        # TODO: This likely needs to be modified to include the newer common-experiment-library prompt.

        # lastCodeStruct keys:
        # instructionStr: the instruction string used in the last code generation
        # codeblock_names: list of codeblock names used in the last code generation
        # requirements: requirements file
        # code: lastest version of Python code
        # supporting_files: any supporting files -- these will NOT be included in the prompt.
        # exec_result: an array of the results of the code execution, with the last result being the most recent.  Direct from the ModuleRunPythonInDocker module.

        # Get the instruction string
        instructionStr = lastCodeStruct["instruction_str"]
        # Get the codeblock names
        codeblockNames = lastCodeStruct["codeblock_names"]
        # Get the supporting files
        supportingFiles = lastCodeStruct["supporting_files"]
        # Get the current experiment mode
        currentPilotMode = "MINI_PILOT"
        if ("next_pilot_mode" in lastCodeStruct):
            currentPilotMode = lastCodeStruct["next_pilot_mode"]

        # Unpack the last execution results
        execResult = []
        lastExecResult = None
        pipStdOut = None
        pipStdErr = None
        pythonStdOut = None
        pythonStdErr = None
        dockerErrors = None
        log = None
        lastResultJson = None
        llmUsage = None

        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            execResult = lastCodeStruct["exec_result"]
            lastExecResult = lastCodeStruct["exec_result"][-1]

            pipStdOut = lastExecResult["pip.stdout"]
            pipStdErr = lastExecResult["pip.stderr"]
            pythonStdOut = lastExecResult["python.stdout"]
            pythonStdErr = lastExecResult["python.stderr"]
            dockerErrors = []
            if ("execution_errors" in lastExecResult):
                dockerErrors = lastExecResult["execution_errors"]
            if ("log" in lastExecResult):
                log = lastExecResult["log"]
            if ("results_json" in lastExecResult):
                lastResultJson = lastExecResult["results_json"]
            if ("llm_proxy_usage" in lastExecResult):
                llmUsage = lastExecResult["llm_proxy_usage"]

        # Start building the reflection prompt

        # First, try to retrieve all the codeblocks mentioned
        retrievedCodeblocks = []
        retrievedCodeblockDict = {}
        retrievalErrors = []
        for name in codeblockNames:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                retrievedCodeblocks.append(codeblock)
                retrievedCodeblockDict[name] = codeblock
            else:
                retrievalErrors.append("ERROR: Could not find codeblock with name: " + str(name))

        # Check if any codeblocks were not found
        #if (len(retrievalErrors) > 0):
            #print("ERROR: Could not find all requested codeblocks." + "\n".join(retrievalErrors))
            #return {
            #    "errors": retrievalErrors
            #}


        # Get a list of the summaries for the codeblocks that were NOT included
        codeblock_summaries_for_remaining_codeblocks = self.get_codeblock_summaries_raw()
        # `Codeblock_summaries` is a dictionary with the codeblock name as the key.  Remove any codeblocks (i.e. keys) that were included.
        for name in codeblockNames:
            if (name in codeblock_summaries_for_remaining_codeblocks):
                del codeblock_summaries_for_remaining_codeblocks[name]


        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Your task has been to produce code that performs a specific task for a scientific experiment. \n"
        prompt += "This is a reflection step -- you were previously given a task and generated code for it, which was run. \n"
        prompt += "One of the most common kinds of errors is that the experiments are not generated *faithfully*, with some examples described below:\n"
        prompt += "1. The experiment requires a language model to be called, but the LLM output is 'simulated' or randomly generated, and the LLM never actually called, and real output never received/parsed.\n"
        prompt += "2. The experiment requires a specific dataset or benchmark to be used, but that benchmark isn't used -- instead a 'simulated' or faux version is generated in the code and used, making the evaluation inaccurate.\n"
        prompt += "3. Code that says (or suggests) it does one thing, but ends up ultimately doing another thing -- e.g. a model for adding attention to an output, that (for whatever reason) never uses the attention output, and instead picks a random output.\n"
        prompt += "4. Code (such as statistics code) that should be generated according to a vetted example from the codeblock library, but instead an in-house or hallucinated example is included that is errorful.\n"
        prompt += "5. Any other case where the code is not doing what it should be doing, and is otherwise simulating/pretending to do the task, or doing something that looks incorrect.\n"
        prompt += "The primary task for this reflection step is to identify cases such as the above, and describe them (as well as describe which codeblocks from the vetted codeblock library should have been used as references to generate this code).\n"
        prompt += "\n"

        #prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        if (follow_on_description is None):
            prompt += "Your task description for the code was the the following:\n"
        else:
            prompt += "You are being asked to modify this experiment for a follow-on experiment.  I will show you both the original task description, and the follow-on instructions. Here is the task description for the original experiment:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"

        if (follow_on_description is not None):
            prompt += "\n"
            prompt += "VERY IMPORTANT: Here is the task description for the follow-on experiment (*this is what you should be working on right now!*):\n"
            prompt += "```\n"
            prompt += follow_on_description + "\n"
            prompt += "```\n"
            prompt += "\n"

        prompt += "*PILOT MODE*: The requested pilot mode is: `" + str(currentPilotMode) + "`.  While the code should support all 3 pilot modes through a global variable (`MINI_PILOT`, `PILOT`, and `FULL_EXPERIMENT`), the pilot mode (`" + str(currentPilotMode) + "`) should be the one that is enabled.  If it is not currently enabled in the code, please enable it.\n"
        prompt += "\n"

        # Codeblocks
        numCodeblocks = len(retrievedCodeblocks)
        prompt += "You previously selected " + str(numCodeblocks) + " template codeblocks from the codeblock library to assist you (summaries of other codeblocks, that you did not select, but may wish to, may also be listed after this section).  The codeblocks you selected are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        prompt += "You should base your code AS MUCH AS POSSIBLE on these codeblocks, as (though they may look a little different than examples on the internet), they are VETTED, KNOWN-GOOD examples that you should DIRECTLY COPY as much as possible.  Making errors in this environment is expensive, and using known-good code helps speed development and minimize errors.  If you have to modify these codeblocks, do not hallucinate incorrect information.\n"
        prompt += "The code in the codeblocks is NOT IMPORTABLE -- it is meant to be COPY AND PASTED (with whatever modifications are required) into your code.\n"
        for idx, codeblock in enumerate(retrievedCodeblocks):
            prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
            prompt += "```\n"
            prompt += codeblock["codeblock_raw"] + "\n"
            prompt += "```\n"
            prompt += "\n"

        # Codeblock summaries for codeblocks that were NOT picked
        prompt += "Below are summaries of template codeblocks that are in the library but were NOT listed to be included in the full listings above.  Please reference them by name, if required.\n"
        prompt += "```\n"
        prompt += json.dumps(codeblock_summaries_for_remaining_codeblocks, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Requirements and code
        max_section_tokens = 8000
        prompt += "\n"
        prompt += "The requirements.txt file you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["requirements"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "The code you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["code"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "The results of running the code are below.\n"
        prompt += "The pip stderr output is below:\n"
        prompt += "```\n"
        prompt += str(pipStdErr) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The python stdout output is below:\n"
        prompt += "```\n"
        #prompt += str(pythonStdOut) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(str(pythonStdOut), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The python stderr output is below:\n"
        prompt += "```\n"
        #prompt += str(pythonStdErr) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(str(pythonStdErr), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The Docker errors are below:\n"
        prompt += "```\n"
        #prompt += json.dumps(dockerErrors, indent=4) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(json.dumps(dockerErrors, indent=4), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        # LLM Usage
        prompt += "Any large language model (LLM) usage by the code is below:\n"
        prompt += "```\n"
        prompt += json.dumps(llmUsage, indent=4) + "\n"                           # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += "```\n"

        # Results file
        prompt += "The results file (results.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(lastResultJson, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE
        if (lastResultJson is not None):
            prompt += self.trimPromptComponent(json.dumps(lastResultJson, indent=4), maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "# No `results.json` file found. (This is a significant issue).\n"
        prompt += "```\n"
        # Log file
        prompt += "The log file (log.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(log, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE  (and highlighting ERRORs?)
        if (log is not None):
            prompt += self.trimPromptComponentLog(log, maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "# No `log.json` file found. (This is a significant issue). Please see the logger codeblock example.  The log is a JSON list, with each list element containg two keys: `type` (str, usually 'info', 'debug', or 'error') and `message` (str). \n"
        prompt += "```\n"
        prompt += "\n"

        #prompt += "You should now reflect on the code you generated, the results of running the code, and the logs.  If there are any errors, you should fix them.  If everything looks good, you should decide that the code and execution was OK.\n"
        prompt += "You should now reflect on the code you generated, the results of running the code, and the log.  If there are cases where the code is not faithful, you should report these.  As a reminder: \n"
        prompt += "This is a reflection step -- you were previously given a task and generated code for it, which was run. \n"
        prompt += "One of the most common kinds of errors is that the experiments are not generated *faithfully*, with some examples described below:\n"
        prompt += "1. The experiment requires a language model to be called, but the LLM output is 'simulated' or randomly generated, and the LLM never actually called, and real output never received/parsed.\n"
        prompt += "2. The experiment requires a specific dataset or benchmark to be used, but that benchmark isn't used -- instead a 'simulated' or faux version is generated in the code and used, making the evaluation inaccurate.\n"
        prompt += "3. Code that says (or suggests) it does one thing, but ends up ultimately doing another thing -- e.g. a model for adding attention to an output, that (for whatever reason) never uses the attention output, and instead picks a random output. (NOTE: It's okay to have random baselines, but they should be explicitly intended/labeled as such -- not a model that says it does one thing, but actually does another.\n"
        prompt += "4. Code (such as statistics code) that should be generated according to a vetted example from the codeblock library, but instead an in-house or hallucinated example is included that is errorful.\n"
        prompt += "5. Any other case where the code is not doing what it should be doing, and is otherwise simulating/pretending to do the task, or doing something that looks incorrect.\n"
        prompt += "The primary task for this reflection step is to identify cases such as the above, and describe them (as well as describe which codeblocks from the vetted codeblock library should have been used as references to generate this code).\n"
        prompt += "\n"

        prompt += "*SECTION: Output format*\n"
        prompt += "Please provide your output below.  Your output should list any issues you found, describe what the correct behavior should be, and what codeblocks from the codeblock library (if any are relevant) should have been used to generate the code.\n"
        prompt += "The output should be a JSON array of dictionaries, with each array containing the following keys: `issue`, `fix`, `relevant_codeblocks`.\n"
        prompt += "The `issue` key is a string describing the issue you found.\n"
        prompt += "The `fix` key is a string describing what the correct behavior should be.\n"
        prompt += "The `relevant_codeblocks` key is a list of strings, each string being the EXACT name of a codeblock from the codeblock library that should have been used to generate the code. You can use codeblock names from above that were either full listings, or summary listings that should be included as full listings next time.  If there is no relevant codeblock, this should be an empty list.\n"
        prompt += "Your JSON output must be between codeblocks (```), or it will not be able to be parsed.  For example:\n"
        prompt += "```\n"
        prompt += "[\n"
        prompt += "  {\n"
        prompt += "    \"issue\": \"The code is not calling the LLM, and is instead simulating the output.\",\n"
        prompt += "    \"fix\": \"The code should call the LLM and parse the output.\",\n"
        prompt += "    \"relevant_codeblocks\": [\"llm_codeblock_name\"]\n"
        prompt += "  },\n"
        prompt += "  {\n"
        prompt += "    \"issue\": \"The code is not using the correct dataset, and is instead using a simulated dataset.\",\n"
        prompt += "    \"fix\": \"The code should use the correct dataset.\",\n"
        prompt += "    \"relevant_codeblocks\": [\"dataset_codeblock_name\"]\n"
        prompt += "  },\n"
        prompt += "  {\n"
        prompt += "    \"issue\": \"The code is not using the attention output, and is instead picking a random output.\",\n"
        prompt += "    \"fix\": \"The code should use the attention output.\",\n"
        prompt += "    \"relevant_codeblocks\": []\n  # Example of a case where the codeblock library doesn't have a relevant codeblock\n"
        prompt += "  }\n"
        prompt += "]\n"
        prompt += "```\n"
        prompt += "IMPORTANT REMINDERS:\n"
        prompt += "- Do not hallucinate issues or other information that does not exist.\n"
        prompt += "- Do not report issues that are not actual issues, or that are not relevant to the correctness of the code.\n"
        prompt += "- You can think step-by-step or include any other thoughts as plain text before the JSON codeblock (```) that help you think -- only the information from the first ``` codeblock will be parsed.\n"
        prompt += "- If there are NO issues (i.e. zero issues of the kind this prompt is asking for), you should still provide an empty JSON array ([]) to signify no issues.\n"
        prompt += "Please provide your output below.\n"

        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)

        # The response should just be the JSON output
        if (responseJSON is not None):
            return responseJSON, cost

        # If the response is None, then exit.
        return None, cost    # Parse failure



    # Generate a lesson based on a successful set of reflections
    # Combine the codeblocks for a particular purpose
    def generateLessonFromSuccessfulReflection(self, history:list, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0):
        # lastCodeStruct keys:
        # instructionStr: the instruction string used in the last code generation
        # codeblock_names: list of codeblock names used in the last code generation
        # requirements: requirements file
        # code: lastest version of Python code
        # supporting_files: any supporting files -- these will NOT be included in the prompt.
        # exec_result: an array of the results of the code execution, with the last result being the most recent.  Direct from the ModuleRunPythonInDocker module.

        # Get the last code struct
        lastCodeStruct = history[-1]

        # Get the instruction string
        instructionStr = lastCodeStruct["instruction_str"]
        # Get the codeblock names
        codeblockNames = lastCodeStruct["codeblock_names"]

        # Get the initial code, and the final code
        codeInitial = None
        codeFinal = None
        requirementsInitial = None
        requirementsFinal = None

        if (len(history) >= 0):
            codeInitial = history[0]["code"]
            codeFinal = lastCodeStruct["code"]
            requirementsInitial = history[0]["requirements"]
            requirementsFinal = lastCodeStruct["requirements"]

        # Get all the "issues" and "summary_of_changes" from the reflections
        issueHistory = []
        for step_idx, step in enumerate(history):
            if ("issues" in step) and (step["issues"] is not None):
                issues = step["issues"]
                summary_of_changes = None
                if ("summary_of_changes" in step):
                    summary_of_changes = step["summary_of_changes"]

                issueHistory.append({
                    "step": step_idx,
                    "issues": issues,
                    "summary_of_changes": summary_of_changes
                })


        # Start building the reflection prompt

        # First, try to retrieve all the codeblocks mentioned
        retrievedCodeblocks = []
        retrievedCodeblockDict = {}
        retrievalErrors = []
        for name in codeblockNames:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                retrievedCodeblocks.append(codeblock)
                retrievedCodeblockDict[name] = codeblock
            else:
                retrievalErrors.append("ERROR: Could not find codeblock with name: " + str(name))

        # Check if any codeblocks were not found
        if (len(retrievalErrors) > 0):
            print("ERROR: Could not find all requested codeblocks." + "\n".join(retrievalErrors))
            return {
                "errors": retrievalErrors
            }

        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Previously, your task was to produce code that performs a specific task for a scientific experiment.  This is a reflection step -- you were previously given a task and generated code for it, which was run, and you marked that run as successful and correct.\n"
        prompt += "Your current task is to reflect on the debugging process that you went through to get the code working, and write down any lessons you learned from that process, that you could apply to future coding tasks to (ideally) prevent these issues from happening in the first place, OR help you quickly fix them if they happena gain.\n"
        prompt += "To support this task, you will be provided (below):\n"
        prompt += "1. The instruction string from the previous task\n"
        prompt += "2. Example code you were provided to generate the code\n"
        prompt += "3. The code (and requirements.txt) you generated\n"
        prompt += "4. Your summary of what you changed at each debugging step\n"
        prompt += "5. A final `diff` of your initial code and final code\n"
        prompt += "\n"

        #prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        prompt += "Your task description for the code was the the following:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"
        numCodeblocks = len(retrievedCodeblocks)
        prompt += "You have been provided with " + str(numCodeblocks) + " template codeblocks to assist you.  They are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        for idx, codeblock in enumerate(retrievedCodeblocks):
            prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
            prompt += "```\n"
            prompt += codeblock["codeblock_raw"] + "\n"
            prompt += "```\n"
            prompt += "\n"

        prompt += "\n"
        prompt += "The requirements.txt file you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["requirements"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "The code you generated is below:\n"
        prompt += "```\n"
        prompt += lastCodeStruct["code"] + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "A summary of what you changed during each debugging step is below:\n"
        prompt += "```\n"
        prompt += json.dumps(issueHistory, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "A `diff` of your initial `requirements.txt` and final `requirements.txt` is below:\n"
        prompt += "```\n"
        diff = difflib.unified_diff(requirementsInitial.split('\n'), requirementsFinal.split('\n'), lineterm='')
        prompt += "\n".join(diff) + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "A `diff` of your initial code and final code is below:\n"
        prompt += "```\n"
        diff = difflib.unified_diff(codeInitial.split('\n'), codeFinal.split('\n'), lineterm='')
        prompt += "\n".join(diff) + "\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "You should now reflect on the debugging process, the changes between the initial and final code, and write down a list of one or more lessons. The lessons should be brief, clear, direct, and extremely useful for identifying and fixing issues such as this in the future.\n"
        prompt += "The lesson format is a JSON dictionary with (minimally) the following keys:\n"
        prompt += "- `title`: (str) a brief title for this lesson\n"
        prompt += "- `applicable_situations`: (str) when is this lesson applicable?  how would I know if I'm in or likely to encounter this issue?\n"
        prompt += "- `applicable_codeblocks`: (list) Are there specific codeblock(s) that this lesson is particularly applicable to?\n"
        prompt += "- `description`: (str) a description/summary of the lesson\n"
        prompt += "- `code_example`: a brief example of (commented) code that shows how to apply this lesson.  Should show (brief) example input and output to clearly illustrate the situation and the utility of the approach.\n"
        prompt += "\n"
        prompt += "Your output should be a JSON list of lessons (`lessons`), with each lesson being a dictionary as described above. There may be one lesson, or more than one lesson.\n"
        prompt += "Your output should be between codeblocks (```), with a single key (`lessons`).  For example:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "\"lessons\": [\n"
        prompt += "    {\n"
        prompt += "        \"title\": \"...\",\n"
        prompt += "        \"applicable_situations\": \"...\",\n"
        prompt += "        \"applicable_codeblocks\": [\"My Codeblock 1\"],\n"
        prompt += "        \"description\": \"...\",\n"
        prompt += "        \"code_example\": \"...\"\n"
        prompt += "    },\n"
        prompt += "    { # Any more lessons go here...\n"
        prompt += "    }\n"
        prompt += "]\n"
        prompt += "}\n"
        prompt += "```\n"

        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

        if (responseJSON is None):
            print("ERROR: Response JSON is None.  Exiting.")
            return {
                "lesons": [],
                "errors": ["ERROR: Response JSON is None, even after retrying.  Likely a JSON parsing issue."]
            }

        lessons = []
        errors = []
        if ("lessons" in responseJSON):
            lessons = responseJSON["lessons"]
            if (type(lessons) != list):
                lessons = [lessons]
        elif (type(responseJSON) == list):
            lessons = responseJSON
        else:
            errors.append("ERROR: 'lessons' key not found in the response JSON")

        # Return the response
        packedOut = {
            "lessons": lessons,
            "errors": errors
        }

        return packedOut


    # Given a successful experiment, and a results file, generate a natural language summary of the findings.
    def generateResultsSummaryFromSuccessfulReflection(self, history:list, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0):
        # lastCodeStruct keys:
        # instructionStr: the instruction string used in the last code generation
        # codeblock_names: list of codeblock names used in the last code generation
        # requirements: requirements file
        # code: lastest version of Python code
        # supporting_files: any supporting files -- these will NOT be included in the prompt.
        # exec_result: an array of the results of the code execution, with the last result being the most recent.  Direct from the ModuleRunPythonInDocker module.

        # Get the last code struct
        lastCodeStruct = history[-1]

        # Get the instruction string
        instructionStr = lastCodeStruct["instruction_str"]

        # Get the results file from the exec_result
        resultsFile = None
        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            lastExecResult = lastCodeStruct["exec_result"][-1]
            if ("results_json" in lastExecResult):
                resultsFile = lastExecResult["results_json"]

        # Get the log file, too, if it exists.
        logFile = None
        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            lastExecResult = lastCodeStruct["exec_result"][-1]
            if ("log" in lastExecResult):
                logFile = lastExecResult["log"]

        # Get the final code
        codeFinal = None
        if (len(history) >= 0):
            codeFinal = lastCodeStruct["code"]


        # Start building the 'results summary' prompt

        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Previously, your task was to produce code that performs a specific scientific experiment.  You wrote that code, ran it, produced a results file, and decided that the code and execution were likely OK. \n"
        prompt += "Now, your task is to reflect on the goal of the experiment and results of the experiment, and write a short summary of the findings.  What was the hypothesis (implicit or explicit?).  What did the results show?  Do they support or reject the hypothesis?  What are the limitations of this result?  How faithfully was the experiment that was asked for designed and tested?\n"
        prompt += "To support this task, you will be provided (below):\n"
        prompt += "1. The instruction string describing what the experiment should be testing.\n"
        prompt += "2. The code (and requirements.txt) you generated\n"
        prompt += "3. The results file your code generated\n"
        prompt += "4. Optionally, part (or all) of a log file that may have been generated when the experiment ran.\n"
        prompt += "\n"
        prompt += "The information that you'll be asked to provide in your summary report is below:\n"
        prompt += "```\n"
        prompt += "- `summary`: (str) A detailed summary\n"
        prompt += "- `summary_medium_detail`: (str) A medium-length summary, that is 2-3 sentences, and includes specific results (e.g. specific performance values, specific results of any statistical analyses), and a clear conclusion.\n"
        prompt += "- `summary_very_short`: (str) a very short summary (maximum of 20 words)\n"
        prompt += "- `hypothesis`: (str) What was the hypothesis (implicit or explicit) of the experiment?\n"
        prompt += "- `hypothesis_operationalized`: (str) What was the version of the hypothesis (likely a scoped down version) that was tested through this operationalization/experiment?\n"
        prompt += "- `hypothesis_inference`: (str) A clear explanation of whether the experimental results support, reject, or are inconclusive with respect to the hypothesis.\n"
        prompt += "- `hypothesis_category`: (str) A string, one of `support`, `reject`, or `inconclusive`.\n"
        prompt += "- `faithfullness_details`: (str) Was the experiment that was conducted a faithful representation of the experiment that was asked for?  Were there any deviations, or significant problems/errors in the implementation? and if so, what were they?\n"
        prompt += "- `faithfullness_category`: (str) A string, one of `faithful`, `deviations`, or `errors`.\n"
        prompt += "- `interesting_results`: (bool) Did the experiment work? And/or, were the results interesting or unexpected?  Was an experimental model significantly different than a baseline model (or, trending towards significance, in an experiment with a low number of samples)?  Set this to `true` to attract the attention of a human researcher to the results that a practitioner in the field would find interesting, and otherwise `false`.\n"
        prompt += "```\n"
        prompt += "\n"
        #prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        prompt += "Your task description for the code was the the following:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"

        prompt += "The code you generated is below:\n"
        prompt += "```\n"
        prompt += codeFinal + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Results file
        max_section_tokens = 32000
        prompt += "The results file (results.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(lastResultJson, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(json.dumps(resultsFile, indent=4), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"
        # Log file
        prompt += "The log file (log.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(log, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE  (and highlighting ERRORs?)
        if (logFile is not None):
            prompt += self.trimPromptComponentLog(logFile, maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "No log file was generated.\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "You should now reflect on the requested experiment/task, the code, the results, and the log file, and write a clear, informative, faithful, scientific, and accurate summary of the results/findings.\n"
        prompt += "What was the hypothesis (implicit or explicit?).  How was it tested? What did the results show?  Do they support or reject the hypothesis?  What are the limitations of this result?  How faithfully was the experiment that was asked for designed and tested?\n"
        prompt += "The summary format is a JSON dictionary with (minimally) the following keys:\n"
        prompt += "- `summary`: (str) A detailed summary\n"
        prompt += "- `summary_medium_detail`: (str) A medium-length summary, that is 2-3 sentences, and includes specific results (e.g. specific performance values, specific results of any statistical analyses), and a clear conclusion.\n"
        prompt += "- `summary_very_short`: (str) a very short summary (maximum of 20 words)\n"
        prompt += "- `hypothesis`: (str) What was the hypothesis (implicit or explicit) of the experiment?\n"
        prompt += "- `hypothesis_operationalized`: (str) What was the version of the hypothesis (likely a scoped down version) that was tested through this operationalization/experiment?\n"
        prompt += "- `hypothesis_inference`: (str) A clear explanation of whether the experimental results support, reject, or are inconclusive with respect to the hypothesis.\n"
        prompt += "- `hypothesis_category`: (str) A string, one of `support`, `reject`, or `inconclusive`.\n"
        prompt += "- `faithfullness_details`: (str) Was the experiment that was conducted a faithful representation of the experiment that was asked for?  Were there any deviations, or significant problems/errors in the implementation? and if so, what were they?\n"
        prompt += "- `faithfullness_category`: (str) A string, one of `faithful`, `deviations`, or `errors`.\n"
        prompt += "- `interesting_results`: (bool) Did the experiment work? And/or, were the results interesting or unexpected?  Was an experimental model significantly different than a baseline model (or, trending towards significance, in an experiment with a low number of samples)?  Set this to `true` to attract the attention of a human researcher to the results that a practitioner in the field would find interesting, and otherwise `false`.\n"
        prompt += "\n"
        prompt += "Your output should be between codeblocks (```), and contain a single dictionary that must have the following keys.  An example of the format is below:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "  \"summary\": \"Your detailed summary here...\",\n"
        prompt += "  \"summary_medium_detail\": \"Your medium-length summary here...\",\n"
        prompt += "  \"summary_very_short\": \"Your very short summary here...\"\n"
        prompt += "  \"hypothesis\": \"Your hypothesis here...\",\n"
        prompt += "  \"hypothesis_operationalized\": \"Your operationalized hypothesis here...\",\n"
        prompt += "  \"hypothesis_inference\": \"Your inference here...\",\n"
        prompt += "  \"hypothesis_category\": \"Your hypothesis category here...\",\n"
        prompt += "  \"faithfullness_details\": \"Your faithfullness details here...\",\n"
        prompt += "  \"faithfullness_category\": \"Your faithfullness category here...\",\n"
        prompt += "  \"interesting_results\": false # true or false\n"
        prompt += "}\n"
        prompt += "```\n"

        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

        summary_results = {
            "summary": None,
            "summary_short": None,
            "summary_medium": None,
            "hypothesis": None,
            "hypothesis_operationalized": None,
            "hypothesis_inference": None,
            "hypothesis_category": None,
            "faithfullness_details": None,
            "faithfullness_category": None,
            "interesting_results": None,
            "errors": []
        }

        if (responseJSON is None):
            print("ERROR: Response JSON is None.  Exiting.")
            summary_results["errors"].append("ERROR: Response JSON is None. Likely a JSON parsing issue.")
            return summary_results

        # Check to see if the values are in the response, or nested in a secondary dictionary
        if (isinstance(responseJSON, dict)):
            if (len(responseJSON.keys()) == 1):
                key = list(responseJSON.keys())[0]
                value = responseJSON[key]
                if (isinstance(value, dict)):
                    # This suggests that the response is a single key, and the value is a dictionary
                    # Check for the keys in the dictionary
                    if ("summary_very_short" in value):
                        # The whole response is nested -- pull it out
                        responseJSON = value

        # if ("summary" in responseJSON):
        #     summary = responseJSON["summary"]
        # if ("summary_very_short" in responseJSON):
        #     summary_short = responseJSON["summary_very_short"]
        # if ("summary_medium_detail" in responseJSON):
        #     summary_medium = responseJSON["summary_medium_detail"]
        # if ("interesting_results" in responseJSON):
        #     interesting_results = responseJSON["interesting_results"]

        # Get the response
        if ("summary" in responseJSON):
            summary_results["summary"] = responseJSON["summary"]
        if ("summary_very_short" in responseJSON):
            summary_results["summary_short"] = responseJSON["summary_very_short"]
        if ("summary_medium_detail" in responseJSON):
            summary_results["summary_medium"] = responseJSON["summary_medium_detail"]
        if ("hypothesis" in responseJSON):
            summary_results["hypothesis"] = responseJSON["hypothesis"]
        if ("hypothesis_operationalized" in responseJSON):
            summary_results["hypothesis_operationalized"] = responseJSON["hypothesis_operationalized"]
        if ("hypothesis_inference" in responseJSON):
            summary_results["hypothesis_inference"] = responseJSON["hypothesis_inference"]
        if ("hypothesis_category" in responseJSON):
            summary_results["hypothesis_category"] = responseJSON["hypothesis_category"]
        if ("faithfullness_details" in responseJSON):
            summary_results["faithfullness_details"] = responseJSON["faithfullness_details"]
        if ("faithfullness_category" in responseJSON):
            summary_results["faithfullness_category"] = responseJSON["faithfullness_category"]
        if ("interesting_results" in responseJSON):
            summary_results["interesting_results"] = responseJSON["interesting_results"]

        # Return the response
        return summary_results



    # Given a successful experiment, and a results file, generate a LATEX report of the findings.
    def generateLatexReport(self, history:list, modelStr="gpt-4o-mini", max_tokens=8192, temperature=0.0, export_path:str="", additional_instruction_str:str=None):
        # lastCodeStruct keys:
        # instructionStr: the instruction string used in the last code generation
        # codeblock_names: list of codeblock names used in the last code generation
        # requirements: requirements file
        # code: lastest version of Python code
        # supporting_files: any supporting files -- these will NOT be included in the prompt.
        # exec_result: an array of the results of the code execution, with the last result being the most recent.  Direct from the ModuleRunPythonInDocker module.

        # Get the last code struct
        lastCodeStruct = history[-1]

        # Get the instruction string
        instructionStr = lastCodeStruct["instruction_str"]

        # Get the results file from the exec_result
        resultsFile = None
        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            lastExecResult = lastCodeStruct["exec_result"][-1]
            if ("results_json" in lastExecResult):
                resultsFile = lastExecResult["results_json"]

        # Get the log file, too, if it exists.
        logFile = None
        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            lastExecResult = lastCodeStruct["exec_result"][-1]
            if ("log" in lastExecResult):
                logFile = lastExecResult["log"]

        # Get the final code
        codeFinal = None
        if (len(history) >= 0):
            codeFinal = lastCodeStruct["code"]

        # Get a list of the files that were downloaded (and available to the latex report)
        filesDownloaded = {}
        fileDownloadLocation = None         # The location of the files
        if ("exec_result" in lastCodeStruct) and (len(lastCodeStruct["exec_result"]) > 0):
            lastExecResult = lastCodeStruct["exec_result"][-1]
            if ("files_downloaded" in lastExecResult) and (lastExecResult["files_downloaded"] is not None):
                for filenameKey in lastExecResult["files_downloaded"].keys():
                    # Only include files in the 'to_save/' directory
                    if (filenameKey.startswith("to_save/")):
                        filesDownloaded[filenameKey] = lastExecResult["files_downloaded"][filenameKey]

            # Store the location of the files
            if ("file_path" in lastExecResult):
                fileDownloadLocation = lastExecResult["file_path"]

        # Start building the 'results summary' prompt

        # Next, create a prompt with the codeblocks.
        prompt = "You are CodeScientist, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Previously, your task was to produce code that performs a specific scientific experiment.  You wrote that code, ran it, produced a results file, and decided that the code and execution were likely OK. \n"
        prompt += "Now, your task is to reflect on the goal of the experiment and results of the experiment, and write a short description of the findings in the form of a SHORT SCIENTIFIC PAPER IN LATEX.  What was the hypothesis (implicit or explicit?).  What did the results show?  Do they support or reject the hypothesis?  What are the limitations of this result?  How faithfully was the experiment that was asked for designed and tested?\n"
        prompt += "You should generate tables, figures, and other scientific content as needed to support your findings.\n"
        prompt += "To support this task, you will be provided (below):\n"
        prompt += "1. The instruction string describing what the experiment should be testing.\n"
        prompt += "2. The code (and requirements.txt) you generated\n"
        prompt += "3. The results file your code generated\n"
        prompt += "4. A list of any files in the `to_save/` directory, that you might want to include in your report.\n"
        prompt += "5. Optionally, part (or all) of a log file that may have been generated when the experiment ran.\n"
        prompt += "\n"

        # Add special instructions (e.g. if there was a problem with a previous report generation)
        if (additional_instruction_str is not None):
            prompt += "Additional special instructions for this report generation:\n"
            prompt += "```\n"
            prompt += additional_instruction_str + "\n"
            prompt += "```\n"
            prompt += "\n"

        #prompt += "Your task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        prompt += "Your task description for the code was the the following:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"


        prompt += "The code you generated is below:\n"
        prompt += "```\n"
        prompt += codeFinal + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Results file
        max_section_tokens = 32000
        prompt += "The results file (results.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(lastResultJson, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE
        prompt += self.trimPromptComponent(json.dumps(resultsFile, indent=4), maxTokens=max_section_tokens) + "\n"
        prompt += "```\n"

        # Files downloaded
        prompt += "The files in the `to_save/` directory, and their sizes, are shown below (note, you will need to reference the code to understand what each one represents).  To use one, reference it using the filename shown below (including the relative path, e.g. `to_save/my_figure.png`):\n"
        prompt += "```\n"
        if (len(filesDownloaded) == 0):
            prompt += "No files were saved in the `to_save/` directory.\n"
        else:
            prompt += json.dumps(filesDownloaded, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        # Log file
        prompt += "The log file (log.json) is below:\n"
        prompt += "```\n"
        #prompt += json.dumps(log, indent=4) + "\n"              # TODO: ADD TRIMMING/CHECK FOR SIZE  (and highlighting ERRORs?)
        if (logFile is not None):
            prompt += self.trimPromptComponentLog(logFile, maxTokens=max_section_tokens) + "\n"
        else:
            prompt += "No log file was generated.\n"
        prompt += "```\n"
        prompt += "\n"

        prompt += "You should now reflect on the requested experiment/task, the code, the results, and the log file, and write a clear, informative, faithful, scientific, and accurate summary of the results/findings.\n"
        prompt += "What was the hypothesis (implicit or explicit?).  How was it tested? What did the results show?  Do they support or reject the hypothesis?  What are the limitations of this result?  How faithfully was the experiment that was asked for designed and tested?\n"
        prompt += "The report format is the complete LATEX code, that will be directly (and automatically) copy/pasted into a Latex compiler to produce the PDF, so it must be perfect the first time.\n"
        prompt += "Don't forget to include tables, figures, and other scientific content as needed to support your findings.  As a general rule, if you generated the table/figure/analysis in an external file, it should probably be included in the report.\n"
        prompt += "IMPORTANT: Importing too many external figures (e.g. PDFs/PNGs/etc.) can cause the Latex renderer to freeze. Please try to include no more than 5 of the most important figures.\n"
        prompt += "Similarly, remember that in Latex, you need to escape some special characters or they won't be rendered properly -- e.g. `p < 0.05` should likely be written as `p $<$ 0.05`.\n"
        prompt += "\n"
        prompt += "Your LATEX must be between a single set of codeblocks (```).  For example:\n"
        prompt += "```\n"
        prompt += "Place your complete latex code for a scientific report (similar in content to Association of Computational Linguistics (ACL) papers) here."
        prompt += "```\n"

        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)

        # Look for output between codeblocks
        latexOut = None
        if (responseText != None):
            # Try to find the last JSON block in the response, which starts with "```"
            lines = responseText.split("\n")
            startIdx = -1
            endIdx = -1
            for idx, line in enumerate(lines):
                if (line.startswith("```")):
                    startIdx = endIdx
                    endIdx = idx

            if (startIdx >= 0) and (endIdx > 0):
                # Exclude the start and end line
                linesBlock = lines[startIdx+1:endIdx]
                # Join the lines
                linesBlock = "\n".join(linesBlock)
                latexOut = linesBlock
            else:
                print("ERROR: Could not find codeblock in response.")


        latex_report_filename = None
        success = False
        report_filename = "report.pdf"
        export_path_report = export_path + "/report/"
        if (latexOut != None):
            # Try to compile the LATEX
            try:
                print("Attempting to compile LATEX...")

                # First, make a /report/ subdirectory
                if not os.path.exists(export_path_report):
                    os.makedirs(export_path_report)

                # Next, copy the /to_save/ files to a /report/to_save/ directory
                copy_from_path = fileDownloadLocation + "/to_save/"
                copy_to_path = export_path_report + "/to_save/"
                import shutil
                if os.path.exists(copy_from_path):
                    if not os.path.exists(copy_to_path):
                        os.makedirs(copy_to_path)
                    for filename in os.listdir(copy_from_path):
                        print ("Copying " + copy_from_path + filename + " to " + copy_to_path)
                        shutil.copy(copy_from_path + filename, copy_to_path)

                # Next, create the LATEX file
                latex_report_filename = export_path_report + report_filename
                #doc.generate_pdf(latex_report_filename, clean_tex=False)
                # Export the .tex file
                with open(export_path_report + "report.tex", "w") as f:
                    f.write(latexOut)
                # Compile the .tex file
                #os.system("pdflatex -output-directory=" + export_path_report + "/ " + export_path_report + "/report.tex")
                import subprocess
                import shlex

                try:
                    # Construct the command
                    #command = f"pdflatex -output-directory={export_path_report} {export_path_report}/report.tex"
                    command = f"pdflatex report.tex"

                    # Use subprocess to run the command with a timeout
                    subprocess.run(shlex.split(command),
                                   cwd=export_path_report,      # Run from the root report directory
                                   timeout=30,                  # Timeout after 30 seconds, just in case any errors happen
                                   check=True)

                    success = True
                    print("SUCCESS: LATEX compiled successfully.")
                except subprocess.TimeoutExpired:
                    print("LATEX: The command timed out after 30 seconds.")
                except subprocess.CalledProcessError as e:
                    print(f"LATEX: Command failed with return code {e.returncode}: {e}")
                except Exception as e:
                    print(f"LATEX: An unexpected error occurred: {e}")



            except Exception as e:
                print("ERROR: Could not compile LATEX: " + str(e))

        # Verify that the report PDF was generated.
        if (success == True):
            if (os.path.exists(latex_report_filename)):
                print("SUCCESS: LATEX report was generated successfully.")
            else:
                print("ERROR: LATEX report was not found at: " + latex_report_filename)
                success = False
                latex_report_filename = None
        else:
            latex_report_filename = None

        # Return the response
        packedOut = {
            "latex_report_filename": latex_report_filename,
            "success": success,
            "errors": [],
        }

        return packedOut




    #
    #   Plan-based code generation
    #
    # Combine the codeblocks for a particular purpose
    def generateExperimentPlan(self, instructionStr:str, codeblockNames:list, modelStr="gpt-4o-mini", max_tokens=4096, temperature=0.0, additionalInstructionStr:str=""):
        # First, try to retrieve all the codeblocks mentioned
        retrievedCodeblocks = []
        retrievedCodeblockDict = {}
        retrievalErrors = []
        for name in codeblockNames:
            codeblock = self.getCodeblockByName(name)
            if (codeblock is not None):
                retrievedCodeblocks.append(codeblock)
                retrievedCodeblockDict[name] = codeblock
            else:
                retrievalErrors.append("ERROR: Could not find codeblock with name: " + str(name))

        # # Check if any codeblocks were not found
        # if (len(retrievalErrors) > 0):
        #     print("ERROR: Could not find all requested codeblocks." + "\n".join(retrievalErrors))
        #     return {
        #         "success": False,
        #         "errors": retrievalErrors
        #     }

        # Next, create a prompt with the codeblocks.
        prompt = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
        prompt += "Your high-level task is to produce code that performs a specific task.  To help you accomplish this, you will be provided with one or more example codeblocks for part of the task.  You should base your code on these codeblocks, which provide self-contained examples of how to accomplish certain tasks.  In particular, you should focus on any API and algorithm examples -- it is VERY bad if you hallucinate API functions that don't exist, because the code will crash, or if your algorithms aren't correct, because the code will produce errors (possibly silently).\n"
        prompt += "Your specific task right now is planning. Operationalizing and implementing experiments is a lot of work to do in one step, so your current task is a *PLANNING* step, the hope being that if you implement experiments in a series of consecutive steps/edits, rather than all at once, that they will be easier to implement, highly accurate, and have fewer bugs.\n"
        prompt += "Your task is to come up with a detailed plan, in the form of a series of steps for what code you'll implement at each step. Then that plan will be executed step-by-step, where at each step, you will implement (and test) only the code for a given step.\n"
        prompt += "\n"
        prompt += "Below is an (cartoon) example plan.  Note that your plans will be different, and may need to have more steps, to control the complexity of what is implemented at each step.\n"
        prompt += "Each step must have only the following keys: `step`, `subgoal`, `description`, `success_criteria`, `failure_criteria`, `relevant_codeblocks`.\n"
        prompt += "The last step should always be `subgoal`: `complete`, and requires only `description` and an additional key/value pair, `complete`: `true`.\n"
        prompt += "```json\n"
        prompt += "[\n"
        prompt += "    {\"step\": 1,\n"
        prompt += "     \"subgoal\": \"loading data/benchmark\","
        prompt += "     \"description\": \"Load the data set or benchmark (benchmark: XYZ)\",\n"
        prompt += "     \"success_criteria\": \"Data/benchmark is loaded, several examples are printed to the log file\",\n"
        prompt += "     \"failure_criteria\": \"Data/benchmark is not loaded, or is loaded incorrectly, or no examples are printed to the log file\",\n"
        prompt += "     \"relevant_codeblocks\": [\"benchmark1_codeblock_name\"]\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 2,\n"
        prompt += "     \"subgoal\": \"experiment framework\",\n"
        prompt += "     \"description\": \"Implement a function that runs a complete set of experiments (appropriate to a given pilot mode), running the baseline/experimental models, and obtaining their results.  All the models (e.g. baseline/experimental) should be placeholders (and labeled as such), do something trivial (e.g. randomly select an answer, for a question answering model). No analysis the results should be implemented yet.\",\n"
        prompt += "     \"success_criteria\": \"The function runs without error, produces a `results.json` file, and the results are trivial (e.g. random answers).  The log file clearly shows what model is running, and what data is being processed (e.g. which question in a QA model), to verify the code is working.  The experiment should be in MINI_PILOT mode.\",\n"
        prompt += "     \"failure_criteria\": \"The function does not run, produces an error, or does not produce a results file.  The log file does not clearly show what model is running at what time, or what data is being processed.\",\n"
        prompt += "     \"relevant_codeblocks\": [\"codeblock1_name\", \"codeblock2_name\"]\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 3,\n"
        prompt += "     \"subgoal\": \"experiment results analysis\",\n"
        prompt += "     \"description\": \"Implement a function that analyzes the results of the experiments. This function should report summary statistics (e.g. means, standard deviations), and use inferrential statistics (specifically procedure XYZ) to determine whether the experimental model is significantly different from the baseline model.\",\n"
        prompt += "     \"success_criteria\": \"The function runs without error, produces a `results.json` file that includes the above information (including summary statistics and inferrential statistical results). The log file should show what analyses are running for what model, and what their results are.  A function to create toy data to analyze (e.g. 10 specifically designed samples) should be used to verify the functioning of the statistical/analysis code.\",\n"
        prompt += "     \"failure_criteria\": \"The function does not run, produces an error, or does not produce a results file with the required analyses.  The log file does not clearly show the analyses.  The results of the analysis on toy data do not match expectations (suggesting there may be errors on the analysis code) \",\n"
        prompt += "     \"relevant_codeblocks\": [\"statistical_codeblock_name\"]\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 4,\n"
        prompt += "     \"subgoal\": \"baseline model\",\n"
        prompt += "     \"description\": \"Implement a function that implements the baseline model.  The baseline model (specifics/details here). Relevant information in the baseline model required to debug/verify its functionality should be included in the log file.\",\n"
        prompt += "     \"success_criteria\": \"The baseline model runs without error. Examining the log of the baseline model's functionality (e.g. how it's parsing/processing/generating data) should not reveal functional/implementational errors. The baseline model should run successfully on MINI_PILOT data, and produce results (that are then analyzed).\",\n"
        prompt += "     \"failure_criteria\": \"The baseline model does not run, produces an error, or does not produce results.  The log file does not clearly show the baseline model's functionality, or the results are significantly different than expected.\",\n"
        prompt += "     \"relevant_codeblocks\": [\"baseline_codeblock_name\"]\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 5,\n"
        prompt += "     \"subgoal\": \"experimental model\",\n"
        prompt += "     \"description\": \"Implement a function that implements the experimental model.  The experimental model (specifics/details here, e.g. if it's a modification to the baseline model, or something different). Relevant information in the experimental model required to debug/verify its functionality should be included in the log file.\",\n"
        prompt += "     \"success_criteria\": \"The experimental model runs without error. Examining the log of the experimental model's functionality (e.g. how it's parsing/processing/generating data) should not reveal functional/implementational errors. The experimental model should run successfully on MINI_PILOT data, and produce results (that are then analyzed).\",\n"
        prompt += "     \"failure_criteria\": \"The experimental model does not run, produces an error, or does not produce results.  The log file does not clearly show the experimental model's functionality, or the results are significantly different than expected.\",\n"
        prompt += "     \"relevant_codeblocks\": [\"baseline_codeblock_name\", \"experimental_codeblock_name\"]\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 6,\n"
        prompt += "     \"subgoal\": \"scale experiment\",\n"
        prompt += "     \"description\": \"Modify the experiment framework setting from MINI_PILOT mode to PILOT mode, and run a full pilot experiment.\",\n"
        prompt += "     \"success_criteria\": \"The PILOT experiment runs without error, produces a `results.json` file, and the results are analyzed successfully.  The log files show what models are running, what data they're running on, and suggest they are running appropriately. The experiment should be in PILOT mode.\",\n"
        prompt += "     \"failure_criteria\": \"The PILOT experiment does not run, produces an error, or does not produce a results file.  The log file does not clearly show what model is running at what time, or what data is being processed.\",\n"
        prompt += "     \"relevant_codeblocks\": []\n"
        prompt += "    },\n"
        prompt += "    {\"step\": 7,\n"
        prompt += "     \"subgoal\": \"complete\",\n"
        prompt += "     \"description\": \"We are only running experiments through PILOT mode, before they're selected by a user to run at larger scales.  When we reach this stage, we signify to the user the experiment pilot is complete.\",\n"
        prompt += "     \"complete\": true,\n"
        prompt += "    }\n"
        prompt += "]\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "The information below describes the specific experiment for you to plan.\n"
        prompt += "This includes the following information:\n"
        prompt += "1. A description of the experiment instructions.\n"
        prompt += "2. A list of codeblocks (i.e. code templates) that you can use to assist in the implementation of the experiment.\n"
        prompt += "\n"

        # Experiment instructions
        prompt += "# Experiment Instructions\n"
        prompt += "The experiment instructions are the following:\n"
        prompt += "```\n"
        prompt += instructionStr + "\n"
        prompt += "```\n"
        if (additionalInstructionStr != ""):
            prompt += "\n"
            prompt += "You have been provided with the following additional instructions:\n"
            prompt += "```\n"
            prompt += additionalInstructionStr + "\n"
            prompt += "```\n"
        prompt += "\n"
        prompt += "RESULTS: You should save any results (both final results, and intermediate results for further processing) in a file called `results.json`. It must be called this, or the results file will not automatically be found, and the experiment will not be useful.\n"
        prompt += "\n"

        # Codeblock examples
        # Main examples
        prompt += "# Codeblock Examples\n"
        numCodeblocks = len(retrievedCodeblocks)
        prompt += "You have been provided with " + str(numCodeblocks) + " template codeblocks to assist you.  They are on the following topics, with the actual codeblocks below: " + ", ".join(codeblockNames) + "\n\n"
        prompt += "You should base your code AS MUCH AS POSSIBLE on these codeblocks, as (though they may look a little different than examples on the internet), they are VETTED, KNOWN-GOOD examples that you should DIRECTLY COPY as much as possible.  Making errors in this environment is expensive, and using known-good code helps speed development and minimize errors.  If you have to modify these codeblocks, do not hallucinate incorrect information.\n"
        prompt += "The code in the codeblocks is NOT IMPORTABLE -- it is meant to be COPY AND PASTED (with whatever modifications are required) into your code.\n"
        for idx, codeblock in enumerate(retrievedCodeblocks):
            prompt += "Codeblock " + str(idx+1) + ": " + codeblock["name"] + "\n"
            prompt += "```\n"
            prompt += codeblock["codeblock_raw"] + "\n"
            prompt += "```\n"
            prompt += "\n"


        # Get a list of the summaries for the codeblocks that were NOT included
        codeblock_summaries_for_remaining_codeblocks = self.get_codeblock_summaries_raw()
        # `Codeblock_summaries` is a dictionary with the codeblock name as the key.  Remove any codeblocks (i.e. keys) that were included.
        for name in codeblockNames:
            if (name in codeblock_summaries_for_remaining_codeblocks):
                del codeblock_summaries_for_remaining_codeblocks[name]

        # Codeblock summaries for codeblocks that were NOT picked
        prompt += "Below are summaries of template codeblocks that are in the library but were NOT listed to be included in the full listings above.  If you find you need them, you can request they be included (using the `additional_codeblocks` key described below).\n"
        prompt += "```\n"
        prompt += json.dumps(codeblock_summaries_for_remaining_codeblocks, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"



        # Format prompt for the planning task
        prompt += "Please provide your detailed plan below, which you will use to guide your implementation of the experiment, step-by-step.  Please remember the following:\n"
        prompt += "1. The output format is a JSON list, with each step represented as a dictionary.\n"
        prompt += "2. The dictionaries for each step must contain the following keys: `step`, `subgoal`, `description`, `success_criteria`, `failure_criteria`, `relevant_codeblocks`, with the exception of the final (`completed`) step, described below.\n"
        prompt += "3. The last step should always be `subgoal`: `complete`, and requires only `description` and an additional key/value pair, `complete`: `true`.\n"
        prompt += "4. The `step` key should be an integer, starting at 1, and incrementing by 1 for each step.\n"
        prompt += "5. The `relevant_codeblocks` key should contain a list of the codeblock names that are relevant to the step.  These codeblocks are meant to be copied/modified/otherwise included into your code. The names included here must EXACTLY match the codeblock name, or it will not be found.\n"
        prompt += "6. Each step should not be too complex, and complex steps should be broken down into multiple steps.  The hope here is that implementing the experiment step-by-step rather than in one go will make the experiment assembly process easier, make debugging easier, and will make the process more successful.\n"
        prompt += "7. This is a planning task, not an implementation task. Implementing your plans will be in the next step.  The plans need to be detailed enough to be highly useful for implementation.\n"
        prompt += "\n"
        prompt += "Please provide your plan below.  The plan must be in the JSON format described above, and must be between two codeblocks (```), or it will not be correctly processed, and this step will fail.\n"


        # Now, get the response from the LLM
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=modelStr, maxTokens=max_tokens, temperature=temperature, jsonOut=False)

        # The responseJSON should be the plan.
        plan = None
        success = False
        errors = []
        if (responseJSON is None):
            error_str = "ERROR: Plan Response JSON is None.  Likely a JSON parsing issue."
            print(error_str)
            errors.append(error_str)
        else:
            # Verify that the plan is a list
            if (not isinstance(responseJSON, list)):
                error_str = "ERROR: Plan is not a list."
                print(error_str)
                errors.append(error_str)
            else:
                # Verify that the plan is a list of dictionaries
                if (len(responseJSON) > 0):
                    if (not isinstance(responseJSON[0], dict)):
                        error_str = "ERROR: Plan is not a list of dictionaries."
                        print(error_str)
                        errors.append(error_str)
                    else:
                        # Verify each dictionary has at least `step` as a key.  Also add the `status` key.
                        failure = False
                        for stepDict in responseJSON:
                            if ("step" not in stepDict):
                                error_str = "ERROR: Plan step does not have a `step` key."
                                print(error_str)
                                errors.append(error_str)
                                failure = True
                                break
                            else:
                                stepDict["status"] = "future work (not current step)"

            plan = responseJSON
            success = True

        plan_error = False
        if (len(errors) > 0):
            plan_error = True

        # Return the response
        packedOut = {
            "success": success,
            "instruction_str": instructionStr,
            "codeblock_names": codeblockNames,
            "plan": plan,
            "requirements": None,
            "code": None,
            "codeblock_code": retrievedCodeblockDict,
            "model": modelStr,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "cost_single_step": cost,
            "cost_total": cost,
            "plan_errors": errors,
            "errors": {
                "plan_error": plan_error,
            }
        }

        return packedOut



    # Check for a stuck experiment
    # This examines the last few steps of the history, to check whether both (1) the `plan` is stuck at the same stage, and (2) whether the notes in the change_log signify that critical issues are not being resolved.
    # If the experiment is stuck, it will signify this as a critical_error.
    def checkForStuckExperiment_(self, lastCodeStruct:dict, history:list, model_str:str="gpt-4o-mini", min_stuck_iterations=4, debugLogOutPath:str=None):
        # Figure out a name for the debug log
        debugLogFilename = None
        if (debugLogOutPath is not None):
            historyLength = len(history)
            debugLogFilename = os.path.join(debugLogOutPath, "debug_log_stuck_experiment." + str(historyLength) + ".json")

        # Step 1: Copy the provided code structure (we'll change this, and output a modified version)
        from copy import deepcopy
        newCodeStruct = deepcopy(lastCodeStruct)

        # Step 2: Get the most recent change log from the history
        if (len(history) < min_stuck_iterations):
            # If the history is too short to check for a stuck experiment, just return the (unchanged) newCodeStruct
            if (debugLogFilename is not None):
                with open(debugLogFilename, "w") as f:
                    message_out = {
                        "message": "History is too short to check for a stuck experiment.  Exiting early.",
                        "history_length": len(history),
                        "min_stuck_iterations": min_stuck_iterations,
                        "history": history,
                    }
                    f.write(json.dumps(message_out, indent=4))

            return newCodeStruct

        lastHistoryStep = history[-1]
        change_log = None
        if ("change_log" in lastHistoryStep):
            change_log = lastHistoryStep["change_log"]

        if (change_log == None) or (len(change_log) == 0):
            # If there is no change log, or the change log is empty, just return the (unchanged) newCodeStruct
            if (debugLogFilename is not None):
                with open(debugLogFilename, "w") as f:
                    message_out = {
                        "message": "No change log found in the last history step, or the change log had a length of zero.  Exiting early.",
                        "history_length": len(history),
                        "min_stuck_iterations": min_stuck_iterations,
                        "change_log": change_log,
                        "history": history,
                    }
                    f.write(json.dumps(message_out, indent=4))

            return newCodeStruct

        # Step 3: Check if the plan has been on the same `plan_step` for the last `min_stuck_iterations` iterations
        exceeds_stuck_iterations = False
        # First, get the last `plan_step` (note, some history steps may not have this key).
        lastPlanStepIdx = 0
        for change_log_step in change_log:
            if ("plan_step" in change_log_step):
                lastPlanStepIdx = change_log_step["plan_step"]
        # Now, count how many times we've seen this plan step. If it exceeds `min_stuck_iterations`, we'll mark it as stuck.
        stuck_iterations = 0
        for change_log_step in change_log:
            if ("plan_step" in change_log_step) and (change_log_step["plan_step"] == lastPlanStepIdx):
                stuck_iterations += 1

        if (stuck_iterations >= min_stuck_iterations):
            # If we've been stuck for `min_stuck_iterations` or more, we'll mark this as spending a while on the same step.
            exceeds_stuck_iterations = True

        # Step 4: If we've been stuck for a while, check if progress is being made, or if it's just stuck on the same critical issue (e.g. unable to install a dependency/etc.) over and over, which might signify we should exit early.
        is_experiment_stuck = False
        experiment_stuck_justification_str = ""
        if (exceeds_stuck_iterations == True):
            # Prompt the LLM with the changelog to see if we're making progress or not.
            prompt_stuck = "You are ScientistGPT, the most advanced AI scientist and coder in the world.  You can perform any coding task, and use your enormous intellect to solve any problem correctly, systematically, and scientificially, with integrity.\n"
            prompt_stuck += "Your task has been to automatically construct the code for an experiment, based on high-level instructions.\n"
            prompt_stuck += "This is a reflection step, and you are currently in the process of building/debugging your code. Your current task is to reflect on the experiment code building/debugging process that you are going through to get the code working, to see if the debugging process is stuck on some critical issue that it keeps trying to fix, but has been unable to fix for more than 3-4 iterations.\n"
            prompt_stuck += "To help you make a decision on this task, you will be provided with the following information:\n"
            prompt_stuck += " - A change log that summaries all the experiment building/debugging steps you've taken so far.  Each step summarizes any identified issues, as well as any changes that were made to the code.\n"
            prompt_stuck += " - The experiment building follows a plan. You will be provided with the current `plan_step`, which might help determine if the experiment has been stuck on the same step for a while.\n"
            prompt_stuck += "\n"
            prompt_stuck += "# SECTION: Decision Criteria\n"
            prompt_stuck += "Here are criteria to help you make the decision for whether the experiment is stuck:\n"
            prompt_stuck += " - Is the experiment stuck on one `plan_step` for more than 3-4 iterations, but it's actually making progress (i.e., it's just this plan step has quite a bit of work to do?).  If it's making progres, then the experiment should not be marked as stuck.\n"
            prompt_stuck += " - STUCK: Is the experiment stuck on trying to solve the *same* issue over and over, and it doesn't appear to be solving it?  For example, the code appears to be failing on requiring a specific dependency, and the experiment builder is having trouble meeting that requirment?  This is an example of an experiment that appears stuck, and should be marked as stuck.\n"
            prompt_stuck += "\n"
            prompt_stuck += "# SECTION: Current plan step\n"
            prompt_stuck += "The current plan step is: " + str(lastPlanStepIdx) + "\n"
            prompt_stuck += "\n"
            prompt_stuck += "# SECTION: Change Log\n"
            prompt_stuck += "The change log is below (the most recent steps are at the bottom):\n"
            prompt_stuck += "```\n"
            prompt_stuck += json.dumps(change_log, indent=4) + "\n"
            prompt_stuck += "```\n"
            prompt_stuck += "\n"
            prompt_stuck += "# SECTION: Output Format\n"
            prompt_stuck += "It is now time to decide if the experiment is stuck.\n"
            prompt_stuck += "Your output should be in the form of a JSON dictionary, with two keys: `is_experiment_stuck` (a boolean) and `justification` (a string). The JSON must be output between code blocks (```) or it will not be parsed correctly, and this step will have failed. Here is an example of a `stuck` output:\n"
            prompt_stuck += "```json\n"
            prompt_stuck += "{\n"
            prompt_stuck += " \"is_experiment_stuck\": true,\n"
            prompt_stuck += " \"justification\": \"Place short justification here\"\n"
            prompt_stuck += "}\n"
            prompt_stuck += "```\n"
            prompt_stuck += "\n"
            prompt_stuck += "Here is an example of a `not stuck` output:\n"
            prompt_stuck += "```json\n"
            prompt_stuck += "{\n"
            prompt_stuck += " \"is_experiment_stuck\": false,\n"
            prompt_stuck += " \"justification\": \"Place short justification here\"\n"
            prompt_stuck += "}\n"
            prompt_stuck += "```\n"
            prompt_stuck += "\n"
            prompt_stuck += "Please generate your output below. Your JSON output must be between two codeblocks (```), otherwise it will not be correctly parsed, and this step will fail.\n"

            # Now, get the response from the LLM
            print("INFO: Sending stuck experiment prompt to LLM (TODO: Task ID)")
            responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt_stuck, model=model_str, maxTokens=1000, temperature=0.0, jsonOut=True)

            # Parse the response
            if (responseJSON is not None):
                if ("is_experiment_stuck" in responseJSON):
                    is_experiment_stuck = responseJSON["is_experiment_stuck"]
                if ("justification" in responseJSON):
                    experiment_stuck_justification_str = responseJSON["justification"]

        # Store the `experiment stuck detector` results.
        if ("errors" not in newCodeStruct):
            newCodeStruct["errors"] = {}
        newCodeStruct["errors"]["is_experiment_stuck"] = is_experiment_stuck
        newCodeStruct["errors"]["experiment_stuck_justification_str"] = experiment_stuck_justification_str

        # Mark the experiment as having a critical error if the experiment is stuck
        if (is_experiment_stuck is True):
            newCodeStruct["critical_error"] = True

        # Save the debug log
        if (debugLogFilename is not None):
            with open(debugLogFilename, "w") as f:
                message_out = {
                    "message": "Checking for a stuck experiment.",
                    "history_length": len(history),
                    "min_stuck_iterations": min_stuck_iterations,
                    "lastPlanStepIdx": lastPlanStepIdx,
                    "stuck_iterations": stuck_iterations,
                    "exceeds_stuck_iterations": exceeds_stuck_iterations,
                    "is_experiment_stuck": is_experiment_stuck,
                    "experiment_stuck_justification_str": experiment_stuck_justification_str,
                    "change_log": change_log,
                    "history": history,
                }
                f.write(json.dumps(message_out, indent=4))

        # Return
        return newCodeStruct




# Entry point -- this will just make an instance of the CodeBlockStore class, which will (if required) regenerate the summaries.
if __name__ == "__main__":
    # Load API keys
    loadAPIKeys()

    # Create the CodeBlockStore
    cb = CodeBlockStore(path_codeblocks=PATH_CODEBLOCKS)

    # # Test the trimmer
    # with open("test_log.json", "r") as f:
    #     # Load the log (JSON)
    #     original_log = json.load(f)

    # trimmed = cb.trimPromptComponentLog(original_log, maxTokens=10000)