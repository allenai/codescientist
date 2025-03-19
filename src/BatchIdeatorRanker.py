# BatchIdeatorRanker.py
# (Also includes the idea simplifier)
# A script to (a) add simplifications for each of a set ideas, then (b) rank all the ideas based on implementability scores.

import os
import time
import json

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Utility for querying LLMs
from ExtractionUtils import *

# Codeblock Store
from CodeBlockStore import *



def loadBatchIdeas(filename:str):
    # Load the JSON file, which is an array of dictionaries (each dictionary representing an idea)
    ideas = []
    with open(filename, "r") as f:
        ideas = json.load(f)
    print ("Loaded " + str(len(ideas)) + " ideas from " + filename)
    return ideas


def score_idea(idea):

    # Get the components of this idea
    components = idea.get("research_idea_required_code_and_resources", [])

    # Each component has the following keys: `name`, `description`, `where``, `effort`
    # `where` is a string from the set {"existing codeblock", "build", "external"}
    # `effort` is a string from the set {"minor", "moderate", "major"}

    # Score tuples
    score_tuples = {
        ("existing codeblock", "minor"): 1,
        ("existing codeblock", "moderate"): 2,
        ("existing codeblock", "major"): 3,
        ("build", "minor"): 3,
        ("build", "moderate"): 4,
        ("build", "major"): 5,
        ("external", "minor"): 3,
        ("external", "moderate"): 10,
        ("external", "major"): 15
    }

    # Score the idea based on the components
    score = 0
    num_unknown_components = 0
    for component in components:
        where = component.get("where", "unknown")
        effort = component.get("effort", "unknown")

        # Try to find the score tuple
        score_tuple = score_tuples.get((where, effort), None)
        if score_tuple is not None:
            score += score_tuple
        else:
            print("No score tuple found for component: " + str(component))
            num_unknown_components += 1


    # Return
    return {
        "score": score,
        "num_unknown_components": num_unknown_components
    }



def convert_to_simpler_idea(idea, model_str:str, condition_on_codeblocks:bool=True):
    import copy

    # Load the codeblock store
    codeblockStore = None
    if (condition_on_codeblocks):
        codeblockStore = CodeBlockStore(PATH_CODEBLOCKS)


    # Original ID
    original_id = idea.get("id", "unknown")

    # Sanitize the idea to remove metadata/etc that's not important for the prompt
    research_idea_sanitized = copy.deepcopy(idea)
    # Remove the 'metadata', 'scores', and 'id' fields
    research_idea_sanitized.pop("metadata", None)
    research_idea_sanitized.pop("scores", None)
    research_idea_sanitized.pop("id", None)

    # Assemble the prompt
    prompt = ""
    prompt += "You are ScientistGPT, the most advanced automated scientific model in the world. You can use your enormous intellect to solve any problem, and the solutions to these problems may help improve our knowledge of how the world works, which is a noble and important goal.\n"
    prompt += "You are currently working on generating new research ideas to explore.\n"
    prompt += "Previously, you generated a research idea that is described below.\n"
    prompt += "Your current task is to convert this research idea into a less-ambitious research idea (perhaps appropriate for an undergraduate or MSc research assistant, with limited resources, and perhaps only partial training in computer science), while still maintaining the goal of having an interesting, novel, and potentially impactful research result.\n"
    prompt += "Regardless of the reduced complexity of the research idea, you must still maintain the highest standards of science, research methods, soundness, and correctness, with the hope of the research being interesting enough to (for example) form part of a workshop paper at an academic conference.\n"
    prompt += "\n"

    # Add a condition on codeblocks
    if (condition_on_codeblocks):
        prompt += "You are asked to generate research ideas that are *conditioned*/*related to* the kinds of codeblocks (vetted code templates) that the are available in a codeblock library. Here are high-level summaries of the code templates available:\n"
        prompt += "```\n"
        codeblockSummaries = codeblockStore.get_codeblock_summaries_raw()
        prompt += json.dumps(codeblockSummaries, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"


    prompt += "The original research idea:\n"
    prompt += "```\n"
    prompt += json.dumps(research_idea_sanitized, indent=2)
    prompt += "\n```\n"
    prompt += "\n"

    # Format
    prompt += "Output format:\n"
    prompt += "For context, here is the output format of a single JSON research idea:\n"
    prompt += "```json\n"
    prompt += "    {    # Research Idea 1\n"
    prompt += "         \"research_idea_name\": \"A 2-3 word name of this research idea, hypthen-separated (e.g. my-research-idea)\",\n"
    prompt += "         \"research_idea_long_description\": \"A long (e.g. ~50-100 word) description of the research idea, and what it's investigating.\",\n"
    prompt += "         \"research_idea_short_description\": \"A short (e.g. ~20 word) high-level description of the research idea, and what it's investigating.\",\n"
    prompt += "         \"research_idea_hypothesis\": \"What is the hypothesis of the research idea?  What are you trying to prove or disprove?\",\n"
    prompt += "         \"research_idea_variables\": \"What are the main variables involved in investigating this research program?  What variables are held constant, and what variables are manipulated?\",\n"
    prompt += "         \"research_idea_metric\": \"What is the main metric that will be used to evaluate the success of this research idea?  How will we know if the idea works or not?  How will partial performance be measured?\",\n"
    prompt += "         \"research_baselines\": \"If your system is an experimental system, what baselines will you compare against?  I.e. if you're creating a (a) new method based on an old method, or a (b) modification of an existing method, then you should probably compare to the old method or the existing method.  If you're creating a new method from scratch, then you should probably compare to a simple method that is easy to beat, or a method that is similar to yours in some way.\",\n"
    prompt += "         \"research_idea_pilot\": \"What's the simplest version of this that can be tested, before running a more expensive version?  Usually this is a full (or reasonably full) method, but on a small subset of the input data.\",\n"
    prompt += "         \"research_idea_design_prompt\": \"Provide a detailed design of the experiment here, with enough detail that it can be implemented by a student-level practitioner.  This is the only text they will be provided to build the experiment, so be specific.  This should minimally include at least: (1) Detailed descriptions of what is to be implemented, including any algorithms (designed at a high or low level), (2) Detailed descriptions of what data to use, in the context of a pilot experiment, (3) Detailed descriptions of what output to generate, how to save it (in the context of maximum utility for follow-on experiments), and how to evaluate and report the results.\"\n"
    if (condition_on_codeblocks):
        prompt += "         \"research_idea_codeblocks\": [\"A list of existing codeblocks from the codeblock library that this idea is likely to use\"],\n"
        #prompt += "         \"research_idea_missing_codeblocks\": [\"A list of possible codeblocks that do not exist in the codeblock library, but would ease implementation. Be detailed here (e.g. include `codeblock name (short description of what should be in it)`), since describing them might help find related code.\"], # NOTE: The format here is actually a list of dictionaries -- the keys for the dictionaries is below.\n"
        prompt += "         \"research_idea_required_code_and_resources\": [ # An EXHAUSTIVE list of ALL required CODE, RESOURCES, MODELS, etc. mentioned in this ENTIRE RESERACH IDEA.  CRITICALLY IMPORTANT, USED TO DETERMINE FEASIBILITY! If it's mentioned above, it ABSOLUTELY NEEDS to be here!\n"
        prompt += "             {\"name\": \"example short name\", \"description\": \"a short example description of the code or resource that is needed\", \"where\": \"one of: `existing codeblock`, `external`, or `build`\", \"effort\": \"one of: `minor`, `moderate`, or `major`\"}, # `where` refers to where the code/resource/model comes from (an existing codeblock template, an external source that can be retrieved, or whether we need to build it for this work.  `effort` refers to how much effort that process will take: `minor` (e.g. small modifications/trivial code), `moderate` (a good amount of work), and `major` for large and/or high-difficulty volumes of code.\n"
        prompt += "             {\"name\": \"ReAct baseline\", \"description\": \"A ReAct baseline (targeted for use on Benchmark XYZ)\", \"where\": \"existing codeblock\", \"effort\": \"minor\"}, # `existing codeblock` because there's an existing codeblock covering a ReAct baseline, and `minor` because this is just using the existing codeblock.\n"
        prompt += "             {\"name\": \"Modified ReAct baseline\", \"description\": \"The proposed modified ReAct model\", \"where\": \"existing codeblock\", \"effort\": \"moderate\"}, # `existing codeblock` because there's an existing codeblock covering a ReAct baseline, and `moderate` because this is proposing non-trivial (but not huge) modifications to that agent, so it will take some work to build.\n"
        prompt += "             {\"name\": \"Benchmark X\", \"description\": \"The primary benchmark used to evaluate the models\", \"where\": \"existing codeblock\", \"effort\": \"minor\"},  # `existing codeblock` because this benchmark has an existing codeblock covering it, that just needs to be directly applied \n"
        prompt += "             {\"name\": \"Benchmark Y\", \"description\": \"The secondary (transfer) benchmark used to evaluate the models\", \"where\": \"external\", \"effort\": \"moderate\"},    # `external` because there's no existing codeblock for this specific benchmark. `moderate` because this isn't a popular benchmark available on e.g. huggingface, so it will likely take a bit of work to find/download/load it.\n"
        prompt += "             {\"name\": \"LLM interface\", \"description\": \"The interface to prompt the LLM for the agents\", \"where\": \"existing codeblock\", \"effort\": \"minor\"}, # The agents need LLM calls. This is an existing codeblock with minor modifications (if any).\n"
        prompt += "             {\"name\": \"gpt-4o model\", \"description\": \"The gpt-4o model available from the OpenAI API\", \"where\": \"existing codeblock\", \"effort\": \"minor\"}, # The base model to use for the agents. The LLM codeblock covers using it, so we don't need to download it, and it should be low effort.\n"
        prompt += "             {\"name\": \"Prior Agent ABC\", \"description\": \"An existing agent described in the paper, to serve as a secondary baseline\", \"where\": \"external\", \"effort\": \"major\"}, # `external` because we don't have a codeblock for it and it's something someone else published on github. `moderate` since it's usually a fair amount of work getting someone else's agent working.\n"
        prompt += "             {\"name\": \"Fancy New Agent++\", \"description\": \"A new agent proposed in this work integrating ...\", \"where\": \"build\", \"effort\": \"major\"}, # `build` because we have to largely build it from scratch, and `major` because it's a fairly complex new agent algorithm that is likely to take a lot of work to build.\n"
        prompt += "             {\"name\": \"Bootstrap resampling\", \"description\": \"The bootstrap resampling technique for comparing the performance of two models\", \"where\": \"existing codeblock\", \"effort\": \"minor\"}, # Already compltely covered in an existing codeblock, we just have to use it\n"
        prompt += "             {\"name\": \"New dataset collection\", \"description\": \"A new dataset collection procedure for collecting data for the agents through web scraping\", \"where\": \"build\", \"effort\": \"major\"}, # `build` because we have to build it from scratch, and `major` because it's a fairly complex new data collection procedure that is likely to take a lot of work to build and debug.\n"
        prompt += "             {\"name\": \"Cohen's Kappa\", \"description\": \"The Kappa measure of interannotator agreement for the dataset (use the `sklearn` library implementation)\", \"where\": \"build\", \"effort\": \"minor\"}, # Fairly straightforward use of this library, so it's a minor effort.\n"
        prompt += "             {\"name\": \"Rouge score\", \"description\": \"The Rouge score for evaluating the quality of the generated text (use the `rouge-score` library implementation)\", \"where\": \"existing codeblock\", \"effort\": \"minor\"}, # Already covered in an existing codeblock, so it's a minor effort.\n"
        prompt += "             # ... More code/resources/models/etc, if any\n"
        prompt += "         \"research_idea_external_requirements\": [\"An exhaustive list of libraries or packages that may be required. Format: `python/apt package name (very short description of need)`\", \"sklearn (for kappa)\", \"rouge-score (for rouge score)\", ...]\n"
    prompt += "     } \n"
    prompt += "```\n"
    prompt += "\n"
    prompt += "IMPORTANT NOTE: An exhaustively detailed and complete `research_idea_required_code_and_resources` is *ABSOLUTELY REQUIRED*, as this is used to prepare the experiment workspace, and determine experiment feasibility.  A poorly or incorrectly documented `research_idea_required_code_and_resources` for an idea is a major failure, as it will waste a large amount of resources (time/money/etc) on ideas that may be unlikely to have the resources they need to succeed.\n"
    prompt += "It is likely that your `resaerch_idea_required_code_and_resources` and accompanying `research_idea_external_requirements` will change -- adding, subtracting, or modifying elements based on the new simplified research idea that you're generating.  It is CRITICALLY important that you update these fields to reflect ALL the requirements of the simplified idea.\n"
    prompt += "NOTE: Manual human ratings in the research (e.g. human rating of the quality of generated text from an experiment) is considered an `external` resource of `major` effort, for the purposes of these research proposals, and should generally be avoided (unless absolutely required for the research).\n"
    prompt += "\n"
    prompt += "Your task is now to generate a simpler, less ambitious, easier to implement research idea based on the original research idea (perhaps appropriate for an undergraduate or MSc research assistant, with limited resources, and perhaps only partial training in computer science), while still maintaining the goal of having an interesting, novel, and potentially impactful research result.\n"
    prompt += "Regardless of the reduced complexity of the research idea, you must still maintain the highest standards of science, research methods, soundness, and correctness, with the hope of the research being interesting enough to (for example) form part of a workshop paper at an academic conference.\n"
    prompt += "\n"
    prompt += "The output format is in JSON.  Your output should be a single dictionary, with all the keys of the original research idea, and the same type of value.\n"
    prompt += "Your output must be a valid JSON object, and must be output between triple qutoes (```).\n"

    # Call the LLM
    max_tokens = 8000
    temperature = 0.1
    responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=model_str, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

    # Return the response
    if (responseJSON is None) or (not isinstance(responseJSON, dict)):
        return None

    # Response
    return {
        "original_id": original_id,
        "simplified_idea": responseJSON,
    }




def main(filenameIdeas:str):
    loadAPIKeys()

    # The model to use
    model_str = "claude-3-5-sonnet-20241022"

    # Load the ideas
    ideas = loadBatchIdeas(filenameIdeas)

    simplified_ideas = []

    def process_simplify_idea(idea, model_str, lock):
        #print(f("Running ideas from idea: {idea.get('id', 'unknown')}"))
        id = idea.get("id", "unknown")
        print(f"Running ideas for idea: {id}")
        try:
            result = convert_to_simpler_idea(idea, model_str)
            if (result is None):
                return
            result = result.get("simplified_idea", None)
            if (result is None):
                return

            # Copy the metadata from the original idea
            result["metadata"] = idea.get("metadata", {})
            # Add that it's been simplified into the metadata
            result["metadata"]["simplified"] = True
            # Make a new id, with "-simplified" appended to the end
            result["id"] = idea.get("id", "unknown") + "-simplified"

            #print(json.dumps(result, indent=4))
            #print("")

            with lock:
                simplified_ideas.append(result)

        except Exception as e:
            print(f"ERROR: Could not run ideas for idea: {idea.get('id', 'unknown')}")
            print(e)
            traceback.print_exc()

        # Sleep for a bit (optional, if you still want that delay)
        time.sleep(1)


    def run_in_threads(ideas, model_str):
        # Create a lock for the ideaStore
        lock = threading.Lock()
        from tqdm import tqdm
        # You can wrap the logic in a ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit a future for each paper set
            futures = [
                executor.submit(process_simplify_idea, idea, model_str, lock)
                for idea in ideas
            ]

            # If you want a progress bar that updates as each future completes:
            for future in tqdm(as_completed(futures), total=len(futures)):
                # Gather the results (or catch exceptions) if needed
                try:
                    future.result()  # This will re-raise any exception that occurred
                except Exception as e:
                    print("Exception in thread:", e)
                    traceback.print_exc()

    run_in_threads(ideas, model_str)

    # Add all the simplified ideas to the list of ideas
    ideas.extend(simplified_ideas)

    # Score the ideas
    for idea in ideas:
        scores = score_idea(idea)
        idea["scores"] = scores

    # Rank the ideas by `score` (lower should be at index 0)
    ideas.sort(key=lambda x: x["scores"]["score"])

    # If a given record doesn't have `"simplified": true` in the metadata, then mark it as not simplified
    for idea in ideas:
        metadata = idea.get("metadata", {})
        if (metadata.get("simplified", False) == False):
            metadata["simplified"] = False

    # Save the ranked ideas
    filenameOut = filenameIdeas.replace(".json", ".ranked.simplified.json")
    print("Saving ranked ideas to " + filenameOut)
    with open(filenameOut, "w") as f:
        json.dump(ideas, f, indent=2)


# Entry point
if __name__ == "__main__":
    # The ideastore to import
    filenameIdeas = "batch-generation-example-output.json"

    # Run the simplifier/ranker
    main(filenameIdeas)