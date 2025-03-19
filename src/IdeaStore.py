# IdeaStore.py
# A storage class for storing ideas

import os
import json
import random
import threading

from ExtractionUtils import *

# Paths
PATH_IDEASTORE = "data/"
FILE_IDEASTORE = "ideastore.json"

# Thread locks
THREAD_LOCK_FILE_IDEASTORE_JSON = threading.Lock()
THREAD_LOCK_IDEA_COUNTER = threading.Lock()

# Codeblock store
from CodeBlockStore import *
PATH_CODEBLOCKS = "codeblocks/"


# IdeaStore storage class
class IdeaStore():
    # Constructor
    def __init__(self, ideastore_filename:str=None):
        self.ideas = []
        self.ideastore_filename = ideastore_filename
        if (self.ideastore_filename is None):
            self.ideastore_filename = PATH_IDEASTORE + FILE_IDEASTORE
        self.load_ideas()
        self.existing_idea_names = {}


    # Load ideas
    def load_ideas(self):
        print ("Loading ideas from ideas store (" + self.ideastore_filename + ")")
        with THREAD_LOCK_FILE_IDEASTORE_JSON:
            # Load the ideas from the JSON file
            if os.path.exists(self.ideastore_filename):
                with open(self.ideastore_filename, 'r') as file:
                    self.ideas = json.load(file)
            else:
                self.ideas = []

        # Collect the names of all existing ideas
        self.existing_idea_names = {}
        for idea in self.ideas:
            if ("research_idea_name") in idea:
                self.existing_idea_names[idea["research_idea_name"]] = True

        print("Loaded " + str(len(self.ideas)) + " ideas from the idea store.")


    # Save ideas
    def save_ideas(self):
        print ("Saving ideas to ideas store (" + self.ideastore_filename + ")")
        with THREAD_LOCK_FILE_IDEASTORE_JSON:
            # Check that the path exists
            dir_path = os.path.dirname(self.ideastore_filename)
            if not os.path.exists(dir_path) and len(dir_path) > 0:
                os.makedirs(dir_path)
            # Save the ideas to the JSON file
            with open(self.ideastore_filename, 'w') as file:
                json.dump(self.ideas, file, indent=4)

    # Get the next idea id
    def get_next_idea_id(self):
        with THREAD_LOCK_FILE_IDEASTORE_JSON:
            with THREAD_LOCK_IDEA_COUNTER:
                # Find the maximum idea id
                max_id = 0
                for idea in self.ideas:
                    # Convert the idea id into an integer by extracting the number between the first and (optionally) second hyphen
                    idea_id = 0
                    try:
                        idea_id = int(idea['id'].split("-")[1])
                    except:
                        pass
                    if idea_id > max_id:
                        max_id = idea_id

                # Return the next idea id
                next_idea_id = max_id + 1
                return "idea-" + str(next_idea_id)

    # Add a new idea. Automatically assigns an ID to the idea, and returns the ID.
    def add_idea(self, idea, batch_idea:bool=False):
        # Get an ID for the idea
        idea_id = self.get_next_idea_id()
        if (batch_idea):
            idea_id = idea_id.replace("idea-", "batchidea-")    # Replace 'idea' with 'batch_idea'
        idea['id'] = idea_id

        # Check to make sure that the idea name is unique
        if ("research_idea_name" in idea) and (idea["research_idea_name"] in self.existing_idea_names):
            # Add an integer to the end of the name to make it unique
            baseName = idea["research_idea_name"]
            for i in range(1, 1000):
                newName = baseName + "-" + str(i)
                if (newName not in self.existing_idea_names):
                    idea["research_idea_name"] = newName
                    break

        self.ideas.append(idea)
        self.save_ideas()
        return idea_id

    # Get all ideas
    def get_all_ideas(self):
        return self.ideas

    # Get idea by id
    def get_idea_by_id(self, id):
        for idea in self.ideas:
            if idea['id'] == id:
                return idea
        return None


    #
    #   Ideation Prompts
    #

    # Generates (and returns) new ideas
    # If `add_to_idea_store` is True, then any ideas that pass basic format checks are automatically added to the IdeaStore
    def generate_new_ideas(self, paperText:dict, additional_conditioning_text:str, discourage_similar_to_existing_ideas:bool, condition_on_codeblocks:bool, model_str:str, num_ideas:int=5, add_to_idea_store:bool=False, mark_as_batch_idea:bool=False, batch_name:bool=None, metadata_in_separate_key=False, temperature=0.1):
        IDEATOR_NAME = "BasicIdeator-v1"
        # Load the codeblock store
        codeblockStore = None
        if (condition_on_codeblocks):
            codeblockStore = CodeBlockStore(PATH_CODEBLOCKS)

        prompt = ""
        max_tokens = 8191
        if ("gpt-4o-mini" in model_str):
            max_tokens = 16383
        elif ("gpt-4o" in model_str):
            max_tokens = 8191
        elif ("sonnet" in model_str):
            max_tokens = 8191
        elif ("o1" in model_str):
            #max_tokens = 16383
            max_tokens = 24000
        elif ("deepseek/deepseek-reasoner" in model_str):
            max_tokens = 8191

        responseJSON = None
        def mk_prompt(mode="INITIAL"):  # MODES: INITIAL, REFLECT

            prompt = ""
            prompt += "You are ScientistGPT, the most advanced automated scientific model in the world. You can use your enormous intellect to solve any problem, and the solutions to these problems may help improve our knowledge of how the world works, which is a noble and important goal.\n"
            #prompt += "You are currently working on the following task: Identifying and abstracting high-level research programs, to come up with ideas for new research/new experiments to run.\n"
            prompt += "You are currently working on the following task: Generating new research ideas/ideas for new experiments to run.\n"
            prompt += "The goal of running the experiments is to generate novel, interesting, and (ideally) high-impact scientific results.\n"
            prompt += "Below is a set of scientific research papers (expressed as their Latex source).\n"
            if (mode == "INITIAL"):
                prompt += "Your task is to come up with new research ideas, and follow-on research ideas, based on the research questions, research programs, hypotheses, operationalizations of experiments, or any other information provided in these papers.\n"
                prompt += "You are asked to come up with " + str(num_ideas) + " ideas.\n"
                prompt += "You can use content from one paper, or combine content from multiple papers to generate new ideas.\n"
            elif (mode == "REFLECT"):
                prompt += "This is a reflection step.  Previously, your task has been to come up with new research ideas, and follow-on research ideas, based on the research questions, research programs, hypotheses, operationalizations of experiments, or any other information provided in these papers.\n"
                prompt += "You are asked to reflect on the ideas you have generated, and improve them. You should pay particular attention to fixing any issues that you notice.\n"
                prompt += "Though you should reflect and fix issues with all components of the ideas, you should pay particular attention to the following components:\n"
                prompt += " - `research_idea_required_code_and_resources`: MAKE ABSOLUTELY SURE THIS IS COMPLETE.  IS SOMETHING MENTIONED IN THE IDEA THAT IS NOT IN THIS LIST? IF SO, IT NEEDS TO BE!\n"
                prompt += " - `research_idea_external_requirements`: SAME COMMENT AS ABOVE -- MAKE ABSOLUTELY SURE THIS IS COMPLETE.  IS SOMETHING MENTIONED IN THE IDEA OR `research_idea_required_code_and_resources`? IF SO, ITS LIKELY PYTHON LIBRARIES/APT-GET PACKAGES NEED TO BE LISTED HERE!\n"
                prompt += "\n"

            if (mode == "INITIAL"):
                prompt += "The ideas you generate can be highly novel inspired by the research in the papers below, or they can be incremental follow-on ideas based on the papers below. The most important thing is that we're doing good, reasoned, and potentially impactful/useful science.\n"
                prompt += "Some recipes for ideation you might use are the following:\n"
            elif (mode == "REFLECT"):
                prompt += "Previously, for the idea-generation step, you were asked to generate ideas that were either highly novel (inspired by the research papers below), or incremental follow-on ideas based on the papers below. The most important thing is that we're doing good, reasoned, and potentially impactful/useful science.\n"
                prompt += "Some suggested recipes for ideation you might have used were the following:\n"
            prompt += "1. **Filling the gaps**: Identify gaps (high-level or low-level) in the research programs below, and come up with ideas to fill those gaps.\n"
            prompt += "2. **Abstractive**: Abstract the research programs below to a higher level, and come up with new ideas based on those abstractions.\n"
            prompt += "3. **Combining ideas**: Combine ideas from different research programs below to come up with new ideas.\n"
            prompt += "4. **Extending ideas**: Extend the ideas from the research programs below to come up with new ideas.\n"
            prompt += "5. **Challenging assumptions**: Challenge the assumptions made in the research programs below, and come up with new ideas based on those challenges.\n"
            prompt += "6. **What happens if**: Come up with ideas that ask what happens if you change key/important parts of the research programs below.\n"
            prompt += "7. etc.\n"

            prompt += "\n"

            # Add a condition, if any is provided
            if (len(additional_conditioning_text.strip()) > 2):
                if (mode == "INITIAL"):
                    prompt += "You are asked to generate new research ideas that are *conditioned*/*related to* the following text:\n"
                elif (mode == "REFLECT"):
                    prompt += "You were asked to generate new research ideas that were *conditioned*/*related to* the following text:\n"
                prompt += "```\n"
                prompt += additional_conditioning_text + "\n"
                prompt += "```\n"
                prompt += "\n"

            if (mode == "REFLECT"):
                prompt += "Here are more of the instructions you were provided for the idea-generation step:\n"
            prompt += "After reading the research papers (and their implicit or explicit Research Programs, Hypotheses, and Operationalizations of Experiments contained within the papers) below, you will be asked to come up with a list of new research ideas (which can be highly novel or incremental follow-on ideas).\n"
            prompt += "As a strategy, you can try coming up with one idea for *each* of the methods above (i.e. filling the gaps, abstractive, combining ideas, extending ideas, challenging assumptions, etc.), or subsampling this if you need to generate fewer ideas.\n"
            prompt += "The response format (JSON) is below:\n"
            prompt += "```json\n"
            prompt += "[   # List of research ideas\n"
            prompt += "    {    # Research Idea 1\n"
            prompt += "         \"research_idea_name\": \"A 2-3 word name of this research idea, hypthen-separated (e.g. my-research-idea)\",\n"
            prompt += "         \"research_idea_long_description\": \"A long (e.g. ~50-100 word) description of the research idea, and what it's investigating.\",\n"
            prompt += "         \"research_idea_short_description\": \"A short (e.g. ~20 word) high-level description of the research idea, and what it's investigating.\",\n"
            prompt += "         \"research_idea_hypothesis\": \"What is the hypothesis of the research idea?  What are you trying to prove or disprove?\",\n"
            prompt += "         \"research_idea_variables\": \"What are the main variables involved in investigating this research program?  What variables are held constant, and what variables are manipulated?\",\n"
            prompt += "         \"research_idea_metric\": \"What is the main metric that will be used to evaluate the success of this research idea?  How will we know if the idea works or not?  How will partial performance be measured?\",\n"
            prompt += "         \"research_baselines\": \"If your system is an experimental system, what baselines will you compare against?  I.e. if you're creating a (a) new method based on an old method, or a (b) modification of an existing method, then you should probably compare to the old method or the existing method.  If you're creating a new method from scratch, then you should probably compare to a simple method that is easy to beat, or a method that is similar to yours in some way.\",\n"
            prompt += "         \"research_idea_pilot\": \"What's the simplest version of this that can be tested, before running a more expensive version?  Usually this is a full (or reasonably full) method, but on a small subset of the input data.\",\n"
            prompt += "         \"research_idea_design_prompt\": \"Provide a detailed design of the experiment here, with enough detail that it can be implemented by a student-level practitioner (which in actuality, is an automated experiment building system).  This is the only text they will be provided to build the experiment, so be specific.  DO NOT JUST GIVE HIGH-LEVEL DESCRIPTIONS (like 'implement the experiment') because this is useless.  This should minimally include at least: (1) *Detailed* mid-level descriptions of what is to be implemented, including any algorithms (designed at a high or low level), (2) Detailed descriptions of what data to use, in the context of a pilot experiment, (3) Detailed descriptions of what output to generate, how to save it (in the context of maximum utility for follow-on experiments), and how to evaluate and report the results.\"\n"
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
                prompt += "             # ... More code/resources/models/etc, if any\n"
                prompt += "         \"research_idea_external_requirements\": [\"An exhaustive list of libraries or packages that may be required. Format: `python/apt package name (very short description of need)`\", \"transformers (for XYZ)\", \"scikit-learn (for ABC)\", ...]\n"
            prompt += "     }, \n"
            prompt += "     ... # More research ideas\n"
            prompt += "]\n"
            prompt += "```\n"
            prompt += "\n"
            prompt += "IMPORTANT NOTE: An exhaustively detailed and complete `research_idea_required_code_and_resources` is *ABSOLUTELY REQUIRED*, as this is used to prepare the experiment workspace, and determine experiment feasibility.  A poorly or incorrectly documented `research_idea_required_code_and_resources` for an idea is a major failure, as it will waste a large amount of resources (time/money/etc) on ideas that may be unlikely to have the resources they need to succeed.\n"
            prompt += "\n"
            prompt += "NOTE: Below is a simple example `research_idea_design_prompt` for a hypothetical example research idea:\n"
            prompt += "```\n"
            prompt += "Please create an agent that automatically builds an informative, useful knowledge graph from exploring its environment. The knowledge graph should be expressed as triples, i.e. subject-relation-object, and stored in DOT/Graphviz format. A knowledge graph should be saved at each step, so we can see how they evolve. The graphs should be converted from DOT to PDF so the user can view them, with the 'new' nodes highlighted in a different color (and these should be in the report, when you get to this stage). Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`. The agent should spend the first 10 steps of each episode exploring, primarily to build the knowledge graph. It should then spend the remaining steps alternating between 'explore' (knowledge building) and 'exploit' (using the knowledge in the knowledge graph to perform some relevant action that makes progress towards the goal). The agent should use the first 2 parametric variations (i.e. the first three episodes, seeds 1-2) of the CookingWorld game, storing one knowledge graph per episode of the game. The maximum steps per episode should be 40. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file.\n"
            prompt += "```\n"
            prompt += "\n"

            # TODO
            # # De-duplication
            # if (discourage_similar_to_existing_ideas == True):
            #     prompt += "YOU ARE ASKED TO NOT DUPLICATE ANY IDEAS THAT YOU HAVE ALREADY GENERATED.  IF YOU DUPLICATE AN IDEA, IT WILL BE CONSIDERED A CRITICAL ERROR.\n"
            #     prompt += "FOR CONTEXT, HERE ARE THE IDEAS YOU HAVE ALREADY GENERATED:\n"
            #     prompt += "```\n"
            #     for idx, idea in enumerate(existingIdeas):
            #         prompt += str(idx+1) + ". " + idea + "\n"
            #     prompt += "```\n"
            #     prompt += "\n"
            # De-duplication (within batch_name)
            if (discourage_similar_to_existing_ideas == True) and (batch_name is not None):
                # Get all ideas in the batch
                existingIdeasInBatch = []
                print("Looking for existing ideas in batch: " + batch_name)
                print("DEBUG: Current length of existing ideas: " + str(len(self.ideas)))
                for idx, idea in enumerate(self.ideas):
                    existing_idea_batch_name = None
                    if ("metadata" in idea) and ("batch_name" in idea["metadata"]):
                        existing_idea_batch_name = idea["metadata"]["batch_name"]
                    if (existing_idea_batch_name == batch_name):
                        print("Found idea in batch: " + idea["research_idea_name"])
                        existingIdeasInBatch.append(idea)
                    else:
                        print("Skipping idea not in batch: " + idea["research_idea_name"])
                # Add the existing ideas to the prompt
                if (len(existingIdeasInBatch) > 0):
                    prompt += "YOU ARE ASKED TO NOT DUPLICATE ANY IDEAS THAT YOU HAVE ALREADY GENERATED IN THIS BATCH. "
                    prompt += "FOR CONTEXT, HERE ARE THE IDEAS YOU HAVE ALREADY GENERATED IN THIS BATCH:\n"
                    prompt += "```\n"
                    ideaCount = 1
                    for idx, idea in enumerate(existingIdeasInBatch):
                        if ("research_idea_long_description" in idea):
                            research_idea_long_description = idea["research_idea_long_description"]
                            if (len(research_idea_long_description) > 2):
                                prompt += "Existing Idea " + str(ideaCount) + ": " + research_idea_long_description + "\n\n"
                                ideaCount += 1

                    if (ideaCount == 1):
                        prompt += "No ideas have been generated in this batch yet.\n"

                    prompt += "```\n"
                    prompt += "\n"

            # Add a condition, if any is provided
            if (len(additional_conditioning_text.strip()) > 2):
                if (mode == "INITIAL"):
                    prompt += "You are asked to generate new research ideas that are *conditioned*/*related to* the following text:\n"
                elif (mode == "REFLECT"):
                    prompt += "You were asked to generate new research ideas that were *conditioned*/*related to* the following text:\n"
                prompt += "```\n"
                prompt += additional_conditioning_text + "\n"
                prompt += "```\n"
                prompt += "\n"

            # Add a condition on codeblocks
            if (condition_on_codeblocks):
                prompt += "You are asked to generate new research ideas that are *conditioned*/*related to* the kinds of codeblocks that the automated experiment builder has available in the codeblock library. Here are high-level summaries of the code templates available in the experiment builder:\n"
                prompt += "```\n"
                codeblockSummaries = codeblockStore.get_codeblock_summaries_raw()
                prompt += json.dumps(codeblockSummaries, indent=4) + "\n"
                prompt += "```\n"
                prompt += "\n"


            prompt += "Existing Research Papers, from which you should consider their (implicitly or explicitly stated) Research Programs, Hypotheses, and Operationalizations of Experiments:\n"

            paperTextStrs = []
            for paper_id, paperTextStr in paperText.items():
                paperTextStrs.append(paperTextStr)
            # Randomize the order of the papers
            random.shuffle(paperTextStrs)
            for paperIdx in range(len(paperTextStrs)):
                paperTextStr = paperTextStrs[paperIdx]
                prompt += "Example Paper " + str(paperIdx+1) + ":\n"
                prompt += "```\n"
                prompt += paperTextStr + "\n"
                prompt += "```\n"
                prompt += "\n"

            prompt += "\n"

            # # REPEAT: De-duplication, if existing ideas are passed in
            # if (len(existingIdeas) > 0):
            #     prompt += "YOU ARE ASKED TO NOT DUPLICATE ANY IDEAS THAT YOU HAVE ALREADY GENERATED.  IF YOU DUPLICATE AN IDEA, IT WILL BE CONSIDERED A CRITICAL ERROR.\n"
            #     prompt += "FOR CONTEXT, HERE ARE THE IDEAS YOU HAVE ALREADY GENERATED:\n"
            #     prompt += "```\n"
            #     for idx, idea in enumerate(existingIdeas):
            #         prompt += str(idx+1) + ". " + idea + "\n"
            #     prompt += "```\n"
            #     prompt += "\n"

            # REPEAT: Add a condition, if any is provided
            if (len(additional_conditioning_text.strip()) > 2):
                prompt += "You are asked to generate new research ideas that are *conditioned*/*related to* the following text:\n"
                prompt += "```\n"
                prompt += additional_conditioning_text + "\n"
                prompt += "```\n"
                prompt += "\n"

            if (mode == "INITIAL"):
                prompt += "Please generate a list of new research ideas (which can be highly novel or incremental follow-on ideas). The most important thing is that we're doing good, reasoned, and potentially impactful/useful science.\n"
                prompt += "After reading the research papers (and their implicit or explicit Research Programs, Hypotheses, and Operationalizations of Experiments contained within the papers) below, you will be asked to come up with a list of new research ideas (which can be highly novel or incremental follow-on ideas).\n"
                prompt += "You are asked to come up with " + str(num_ideas) + " ideas.\n"
                prompt += "As a strategy, you can try coming up with one idea for *each* of the methods above (i.e. filling the gaps, abstractive, combining ideas, extending ideas, challenging assumptions, etc.), or subsampling this if you need to generate fewer ideas.\n"
            elif (mode == "REFLECT"):
                prompt += "You are nowasked to reflect on the ideas you have generated, and improve them. You should pay particular attention to fixing any issues that you notice.\n"
                prompt += "Though you should reflect and fix issues with all components of the ideas, you should pay particular attention to the following components:\n"
                prompt += " - `research_idea_required_code_and_resources`: MAKE ABSOLUTELY SURE THIS IS COMPLETE.  IS SOMETHING MENTIONED IN THE IDEA THAT IS NOT IN THIS LIST? IF SO, IT NEEDS TO BE!\n"
                prompt += " - `research_idea_external_requirements`: SAME COMMENT AS ABOVE -- MAKE ABSOLUTELY SURE THIS IS COMPLETE.  IS SOMETHING MENTIONED IN THE IDEA OR `research_idea_required_code_and_resources`? IF SO, ITS LIKELY PYTHON LIBRARIES/APT-GET PACKAGES NEED TO BE LISTED HERE!\n"
                prompt += "\n"
                prompt += "You must fix and output ALL the ideas that you previously generated.  They are:\n"
                prompt += "```\n"
                prompt += json.dumps(responseJSON, indent=4) + "\n"
                prompt += "```\n"
                prompt += "\n"


            prompt += "The response format (JSON) is below:\n"
            prompt += "```json\n"
            prompt += "[   # List of research ideas\n"
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
            prompt += "     }, \n"
            prompt += "     ... # More research ideas\n"
            prompt += "]\n"
            prompt += "```\n"
            prompt += "\n"
            prompt += "IMPORTANT NOTE: An exhaustively detailed and complete `research_idea_required_code_and_resources` is *ABSOLUTELY REQUIRED*, as this is used to prepare the experiment workspace, and determine experiment feasibility.  A poorly or incorrectly documented `research_idea_required_code_and_resources` for an idea is a major failure, as it will waste a large amount of resources (time/money/etc) on ideas that may be unlikely to have the resources they need to succeed.\n"
            prompt += "\n"
            prompt += "NOTE: Below is a simple example `research_idea_design_prompt` for a hypothetical example research idea:\n"
            prompt += "```\n"
            prompt += "Please create an agent that automatically builds an informative, useful knowledge graph from exploring its environment. The knowledge graph should be expressed as triples, i.e. subject-relation-object, and stored in DOT/Graphviz format. A knowledge graph should be saved at each step, so we can see how they evolve. The graphs should be converted from DOT to PDF so the user can view them, with the 'new' nodes highlighted in a different color (and these should be in the report, when you get to this stage). Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`. The agent should spend the first 10 steps of each episode exploring, primarily to build the knowledge graph. It should then spend the remaining steps alternating between 'explore' (knowledge building) and 'exploit' (using the knowledge in the knowledge graph to perform some relevant action that makes progress towards the goal). The agent should use the first 2 parametric variations (i.e. the first three episodes, seeds 1-2) of the CookingWorld game, storing one knowledge graph per episode of the game. The maximum steps per episode should be 40. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file.\n"
            prompt += "```\n"
            prompt += "NOTE: You should try to define important terms, as the paper is likely to be unavailable to the automated experiment builder, only the information you provide will be.  Similarly, acronyms can be used, but they should be defined on their first use.\n"
            prompt += "\n"
            prompt += "Your JSON response must be between code blocks (```).  You can write any other text you wish before or after (such as if you want to describe the research programs, hypotheses, and/or operationalizations of experiments in the papers), but only JSON text between a single set of codeblocks (```) will be able to be automatically extracted and used.\n"
            # Add a condition on codeblocks, if any are provided
            if (condition_on_codeblocks == True):
                prompt += "Remember that your research ideas should be ACTUALLY IMPLEMENTABLE by being conditioned on the kinds of codeblocks that the automated experiment builder has available.  Your templates and operationalizations should particularly emphasize existing codeblocks in the experiment builder.\n"
                prompt += "Similarly, while you can use external libraries or packages, you may wish to minimize the use of these, as they may not be available to the automated experiment builder, or (more likely) it may not be fluent in their use.\n"
            if (mode == "REFLECT"):
                prompt += "Remember, you must reflect on, correct, and output ALL the ideas that you previously generated, not just one or two.\n"

            return prompt

        # print the prompt
        #print(prompt)

        # Send initial step to LLM, get response
        startTime = time.time()
        prompt_initial = mk_prompt(mode="INITIAL")
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt_initial, model=model_str, maxTokens=max_tokens, temperature=temperature, jsonOut=True)

        # Send reflection step to LLM, get response
        prompt_reflect = mk_prompt(mode="REFLECT")
        responseJSON, responseText, cost_ = getLLMResponseJSON(promptStr=prompt_reflect, model=model_str, maxTokens=max_tokens, temperature=temperature, jsonOut=True)
        cost += cost_
        deltaTime = time.time() - startTime

        # Print the response
        #print("Response JSON:")
        #print(json.dumps(responseJSON, indent=4))

        # Extract the response
        list_of_ideas = []
        if (type(responseJSON) == list):
            # Normal case -- returned a list of ideas
            for idea in responseJSON:
                if ("research_idea_name" in idea) and ("research_idea_design_prompt" in idea):
                    list_of_ideas.append(idea)
                else:
                    print("Warning: Idea is missing one or more required fields.")
        elif (type(responseJSON) == dict):
            # It might have returned a dictionary with a single key (`ideas`, or something similar) -- can try this one, too
            # Check for one key
            if (len(responseJSON.keys()) == 1):
                key = list(responseJSON.keys())[0]
                if (type(responseJSON[key]) == list):
                    # This might be the list of ideas
                    for idea in responseJSON[key]:
                        if (type(idea) == dict):
                            if ("research_idea_name" in idea) and ("research_idea_design_prompt" in idea):
                                list_of_ideas.append(idea)

        # Validate that we have some ideas
        success = True
        if (len(list_of_ideas) == 0):
            print("Warning: No valid ideas were generated.")
            success = False

        # For each idea, add metadata
        import datetime
        date_generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for idea in list_of_ideas:
            if (metadata_in_separate_key == True):
                idea["metadata"] = {}
                idea["metadata"]["date_generated"] = date_generated
                idea["metadata"]["inspiring_paper_ids"] = list(paperText.keys())
                idea["metadata"]["generated_using_model"] = model_str
                idea["metadata"]["condition_on_codeblocks"] = condition_on_codeblocks
                idea["metadata"]["additional_conditioning_text"] = additional_conditioning_text
                idea["metadata"]["batch"] = mark_as_batch_idea
                idea["metadata"]["batch_name"] = batch_name
                idea["metadata"]["ideator_name"] = IDEATOR_NAME
            else:
                idea["date_generated"] = date_generated
                idea["inspiring_paper_ids"] = list(paperText.keys())
                idea["generated_using_model"] = model_str
                idea["condition_on_codeblocks"] = condition_on_codeblocks
                idea["additional_conditioning_text"] = additional_conditioning_text
                idea["batch"] = mark_as_batch_idea
                idea["batch_name"] = batch_name
                idea["ideator_name"] = IDEATOR_NAME

        # If enabled, add the ideas to the IdeaStore
        idea_ids = []
        if (add_to_idea_store == True):
            # Add the ideas to the IdeaStore
            for idea in list_of_ideas:
                idea_id = self.add_idea(idea, batch_idea=mark_as_batch_idea)
                print("Added idea with ID: " + idea_id)
                idea_ids.append(idea_id)

        # Return the list of ideas
        packed = {
            "success": success,
            "idea_ids": idea_ids,
            "ideas": list_of_ideas,
            "cost": cost,
            "time_seconds": deltaTime
        }

        return packed



    # Convert an experiment idea into an experiment prompt designed for the experiment builder
    def convert_idea_to_experiment_prompt(self, idea:dict, model_str:str, extra_conditioning_text:str=None, expert_notes:str=None):
        condition_on_codeblocks = True

        # Load the codeblock store
        codeblockStore = None
        if (condition_on_codeblocks):
            codeblockStore = CodeBlockStore(PATH_CODEBLOCKS)

        temperature = 0.1

        prompt = ""
        max_tokens = 8000
        if ("gpt-4o-mini" in model_str):
            max_tokens = 16383
        elif ("gpt-4o" in model_str):
            max_tokens = 8191
        elif ("sonnet" in model_str):
            max_tokens = 8191
        elif ("o1" in model_str):
            max_tokens = 16383


        prompt = ""
        prompt += "You are ScientistGPT, the most advanced automated scientific model in the world. You can use your enormous intellect to solve any problem, and the solutions to these problems may help improve our knowledge of how the world works, which is a noble and important goal.\n"
        prompt += "You are currently working on the following task: Converting a high-level idea for an experiment that you generated (based on reading scientific articles) into a very specific prompt to give an experiment building agent, to build and run that experiment according to your detailed specifications.\n"
        prompt += "The experiment building agent is template-based -- that is to say, it (as much as possible) tries to use existing code templates (called codeblocks) to build the experiment.  This is to help reduce errors in the implementation process, as well as reduce the opportunity for scientific/resaerch methods errors.\n"
        prompt += "Below is the high-level experiment idea that you generated.  Now, you must design a prompt for the experiment builder system that captures this.\n"
        prompt += "\n"
        prompt += "Your experiment idea to convert into a prompt for the experiment builder is the following:\n"
        prompt += "(Note that information provided in the idea here may not be completely accurate or usable as-is -- for example, operationalizing the idea may require more or different codeblock templates than what are mentioned in the idea below (if the idea even suggests code blocks).  Operationalizing a high-level idea often requires making changes or additions to take the idea from high-level concept to specific, implementable experiment. Please use your best judgement.)\n"
        prompt += "```\n"
        prompt += json.dumps(idea, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"

        if (extra_conditioning_text is not None):
            prompt += "In addition, you are asked to use the following SPECIAL CONDITIONING INSTRUCTIONS, that usually help re-scope the experiment to be more implementable, scope the experiment to be more towards user goals, and/or help reduce errors in the implementation process:\n"
            prompt += "```\n"
            prompt += extra_conditioning_text + "\n"
            prompt += "```\n"
            prompt += "\n"

        if (expert_notes is not None):
            prompt += "In addition, you are provided with the following EXPERT NOTES, which are usually helpful in guiding the design of the experiment, and ensuring that the experiment is designed in a way that is likely to be successful:\n"
            prompt += "```\n"
            prompt += expert_notes + "\n"
            prompt += "```\n"
            prompt += "\n"

        prompt += "Your output must contain two keys: `prompt` and `codeblocks`.  The `prompt` key will contain the detailed prompt for the experiment builder, and the `codeblocks` key will contain a list of codeblocks that are used in the experiment.\n"
        prompt += "Consequences of errors in `prompt` and `codeblocks`:\n"
        prompt += "1. If the prompt is not detailed or useful, the experiment builder may not be able to build the experiment (but it will still try), and this will waste a lot of time and resources.\n"
        prompt += "2. If the required codeblocks are not included, the experiment builder is highly unlikely to build the experiment successfully (but it will still try), and this will waste a lot of time and resources.\n"
        prompt += "\n"

        prompt += "Here are two (very simple, very rough) examples of what a prompt might look like for a very simple, very hypothetical, toy experiment:\n"
        prompt += "Example Prompt Generation #1:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "    \"prompt\": \"Please investigate the effect of implementing a ReAct agent with and without a small difference. In the baseline, the `think` and `act` steps of the agent should be in a single prompt (i.e. a single LLM call). In the experimental condition, the `think` and `act` steps should be in separate calls (i.e. it thinks, then it acts based on the thought). Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`. The agent should use the first 5 parametric variations (i.e. the first five episodes, seeds 1-5) of the CookingWorld game, and end after this, report the score/success of each episode, and final average score. The maximum steps per episode should be 25. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file. The results file should include number of steps per episode, as well as an average of this. Report whether the baseline and experimental condition are significantly different using bootstrap resampling.\",\n"
        prompt += "    \"codeblocks\": [\"Logger/Debugging\", \"LLM example through proxy server\", \"ReAct Agent Example\", \"TextWorldExpress API Example\", \"Non-parametric Bootstrap Resampling\"]\n"
        prompt += "}\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "Example Prompt Generation #2:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "    \"prompt\": \"Please create an agent that automatically builds an informative, useful knowledge graph from exploring its environment. The knowledge graph should be expressed as triples, i.e. subject-relation-object, and stored in DOT/Graphviz format. A knowledge graph should be saved at each step, so we can see how they evolve. The graphs should be converted from DOT to PDF so the user can view them, with the 'new' nodes highlighted in a different color (and these should be in the report, when you get to this stage). Please test this on CookingWorld, using the default CookingWorld environment parameters (except 3 rooms, and no doors). The base model should be `gpt-4o-mini`.  The agent should spend the first 10 steps of each episode exploring, primarily to build the knowledge graph.  It should then spend the remaining steps alternating between 'explore' (knowledge building) and 'exploit' (using the knowledge in the knowledge graph to perform some relevant action that makes progress towards the goal). The agent should use the first 2 parametric variations (i.e. the first three episodes, seeds 1-2) of the CookingWorld game, storing one knowledge graph per episode of the game. The maximum steps per episode should be 40. The full trajectory (i.e. observation, score, possible valid actions, chosen action at each step) should be in the log file.\n"
        prompt += "    \"codeblocks\": [\"Logger/Debugging\", \"DOT Graphviz Graph\", \"LLM example through proxy server\", \"ReAct Agent Example\", \"TextWorldExpress API Example\"]\n"
        prompt += "}\n"
        prompt += "```\n"
        prompt += "\n"

        # Section on baselines
        prompt += "*Baselines*:\n"
        prompt += "If your system is an experimental system, then it's standard procedure to compare against baselines. Baselines are usually one of the following:\n"
        prompt += "1. If you're creating a new method based on an old method, or a modification of an existing method, then you should probably compare to the old method or the existing method.\n"
        prompt += "2. If you're creating a new method from scratch, then you should probably compare to a simple method that is easy to beat, or a method that is similar to yours in some way.\n"
        prompt += "3. Sometimes, you might compare to both of the above. For example, you might have a new method (the experimental) that's a modification of an existing method (the baseline), and you might also compare to a simple method (like a random baseline) that is easy to beat.\n"
        prompt += "If appropriate, please detail exactly what the baseline and experimental systems are in your prompt, how they differ, and how their performance will be meaningfully compared.\n"
        prompt += "\n"

        # Add a condition on codeblocks
        if (condition_on_codeblocks):
            prompt += "You are asked to generate an experiment prompt that is conditioned on the actual code templates available in the system, as much as possible, to help reduce the errors.  Here is a high-level summary of the codeblocks:\n"
            prompt += "```\n"
            codeblockSummaries = codeblockStore.get_codeblock_summaries_raw()
            prompt += json.dumps(codeblockSummaries, indent=4) + "\n"
            prompt += "```\n"
            prompt += "\n"

        # Add codeblocks that it previously mentioned
        codeblock_names_mentioned = []
        if ("research_idea_codeblocks" in idea):
            codeblock_names_mentioned = idea["research_idea_codeblocks"]
        if (len(codeblock_names_mentioned) > 0):
            codeblock_count = 0
            codeblock_prompt = ""
            codeblock_prompt += "The following codeblocks are mentioned in the research idea, that may help you generate your experiment design prompt:\n"
            for codeblock_idx in range(len(codeblock_names_mentioned)):
                codeblock_name = codeblock_names_mentioned[codeblock_idx]
                # Get codeblock
                codeblock = codeblockStore.getCodeblockByName(codeblock_name)
                if (codeblock is not None):
                    codeblock_prompt += "Codeblock " + str(codeblock_count+1) + ": " + codeblock_name + "\n"
                    codeblock_prompt += "```\n"
                    codeblock_prompt += json.dumps(codeblock, indent=4) + "\n"
                    codeblock_prompt += "```\n"
                    codeblock_prompt += "\n"
                    codeblock_count += 1

            if (codeblock_count > 0):
                prompt += codeblock_prompt
                prompt += "\n"


        prompt += "Please generate a detailed prompt for the experiment builder to construct the experiment for the idea.  That idea again is:\n"
        prompt += "```\n"
        prompt += json.dumps(idea, indent=4) + "\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "Your output must be a JSON dictionary containing two keys: `prompt` and `codeblocks`.  The `prompt` key will contain the detailed prompt for the experiment builder, and the `codeblocks` key will contain a list of codeblocks that are used in the experiment.\n"
        prompt += "Your output must be a JSON dictionary between code blocks (```).  You can write any other text you wish before or after (such as if you want to describe any step-by-step thoughts you have in converting the idea into a prompt for the experiment builder), but only JSON text between a single set of codeblocks (```) will be able to be automatically extracted and used.\n"
        prompt += "For example:\n"
        prompt += "```\n"
        prompt += "{\n"
        prompt += "     \"prompt\": \"The detailed prompt for the experiment builder goes here.\",\n"
        prompt += "     \"codeblocks\": [\"List of codeblocks used in the experiment.  They must exactly match the codeblock names. If zero codeblocks are required, you must output a blank list here.\"]\n"
        prompt += "}\n"
        prompt += "```\n"
        prompt += "\n"
        prompt += "NOTE: The codeblock names must match EXACTLY to the provided names, including capitalization, spacing, spelling, punctuation, parantheses, etc.  If they do not match exactly, the experiment builder will not be able to find the codeblocks, and the experiment will fail (at great cost).\n"
        prompt += "\n"
        prompt += "NOTE: Please frame this as a series of pilot experiments -- so vastly reduce the amount of data/steps/etc. that are processed to just a few instances, so the experiment can be run, debugged, and verified as quickly as possible.  More details on the pilot experiment setting:\n"
        prompt += " - There should be a global variable in your code (PILOT_MODE:str) with three possible settings: `MINI_PILOT`, `PILOT`, or `FULL EXPERIMENT`.\n"
        prompt += " - The `MINI_PILOT` setting should be a very small subset of the data, and should be able to run in a few minutes.  The purpose is for fast debugging and verification of the code. For example, for question answering tasks, this might be 10 questions.  For agent tasks, this might be 2-3 episodes at 10-20 steps each.  The questions/episodes should come from the training set.\n"
        prompt += " - The `PILOT` setting should be a moderate subset of the data, ideally running in less than 1-2 hours. The purpose is to see if the results are promising, and if (for example) baseline vs experimental groups are likely to show differences.  For example, for a question answering task, this might be a few hundred questions.  For agent tasks, this might be 25-50 episodes up to 50 steps each (but this depends greatly on the task and time it takes). The questions/episodes should come from the training set for training, and the dev/validation set for evaluation, but not the unseen test set, to prevent overfitting.\n"
        prompt += " - The `FULL EXPERIMENT` setting should be the full experiment, with all data, all steps, etc.  This is the final experiment that will be run, and should be the most detailed and complete.  Training data should come from the training set.  Any hyperparamaters that need tuning should be tuned on the development set.  The experiment should be evaluated on the test set.\n"
        prompt += " - In all cases, appropriate inferrential and summary statistics should be reported, as well as any follow-on analyses. The difference between pilot levels is simply of scale, not of quality.\n"
        prompt += " - Describe the above in your experiment building prompt, so it's clear what each version should look like."
        prompt += " - In the experiment prompt, say that it should run the MINI_PILOT first, then if everything looks good, the PILOT.  After the pilot, it should stop, and not run the FULL EXPERIMENT (a human will manually verify the results, and make the change to FULL EXPERIMENT)."
        #prompt += " - Add in your instructions what the `pilot` and `full` versions should look like, and require a `PILOT = True` global variable in the code.\n"
        prompt += "Please generate your JSON output now. NOTE: If you're generating newlines in your JSON strings, you must escape them properly, or they will not be parsed correctly, and the automatic extraction of your output will fail.\n"

        startTime = time.time()
        responseJSON, responseText, cost = getLLMResponseJSON(promptStr=prompt, model=model_str, maxTokens=max_tokens, temperature=temperature, jsonOut=True)
        deltaTime = time.time() - startTime

        # Get the response
        prompt_experiment = None
        codeblocks = None
        if (type(responseJSON) == dict):
            if ("prompt" in responseJSON) and ("codeblocks" in responseJSON):
                prompt_experiment = responseJSON["prompt"]
                codeblocks = responseJSON["codeblocks"]
        else:
            print("Warning: JSON does not appear to be a dictionary. Could not extract the prompt and codeblocks from the response.")

        # Return the response
        packed = {}
        if (prompt_experiment is not None) and (codeblocks is not None):
            # Success
            packed = {
                "success": True,
                "prompt": prompt_experiment,
                "codeblocks": codeblocks,
                "cost": cost,
                "time_seconds": deltaTime
            }
        else:
            # Failure
            packed = {
                "success": False,
                "prompt": prompt_experiment,
                "codeblocks": [],
                "cost": cost,
                "time_seconds": deltaTime
            }

        # Return
        return packed




#
#   Test the ideator
#
if __name__ == "__main__":
    # Load the API keys
    loadAPIKeys()

    # Test the IdeaStore class
    idea_store = IdeaStore()


    ###
    # Test to convert idea to experiment prompt
    idea = idea_store.get_idea_by_id("idea-2")
    result = idea_store.convert_idea_to_experiment_prompt(idea, "claude-3-5-sonnet-20241022")
    print("Result:")
    print(json.dumps(result, indent=4))

    exit(1)

    # Grab 3 random paper IDs
    from PaperStore import PaperStore
    paperStore = PaperStore()

    # Get 3 random papers
    #paper_ids = ["2406.06769", "2106.09608", "2010.03790"]

    num_generation_cycles = 5
    for i in range(num_generation_cycles):
        print("Starting " + str(i) + " / " + str(num_generation_cycles))
        all_paper_ids = paperStore.get_paper_ids()
        # Set the random seed
        random.seed(i)
        paper_ids = random.sample(all_paper_ids, 4)

        # Get the text of the papers
        paperText = {}
        print("Getting paper text for papers: " + str(paper_ids))
        for paper_id in paper_ids:
            success, paper_latex_str = paperStore.get_paper_latex(paper_id)
            if (not success):
                print("Error: Could not get the paper text for paper ID: " + paper_id)
            paperText[paper_id] = paper_latex_str



        # Test the idea generation
        #additional_conditioning_text = "This is some additional conditioning text."
        #additional_conditioning_text = "Please generate ideas that could be evaluated using CookingWorld."
        additional_conditioning_text = ""

        discourage_similar_to_existing_ideas = True
        condition_on_codeblocks = True
        model_str = "claude-3-5-sonnet-20241022"
        num_ideas = 3

        result = IdeaStore.generate_new_ideas(paperText, additional_conditioning_text, discourage_similar_to_existing_ideas, condition_on_codeblocks, model_str, num_ideas)
        print("Result:")
        print(json.dumps(result, indent=4))

        # Save the ideas
        packed = {
            "papers": paper_ids,
            "model": model_str,
            "ideas": result
        }

        # Save the ideas to a file
        filenameOut = "debug.ideation." + str(i) + ".json"
        with open(filenameOut, 'w') as f:
            json.dump(packed, f, indent=4)
