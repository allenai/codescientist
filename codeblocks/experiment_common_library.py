# experiment_common_library.py
# This is a common library of experiment functions that can be directly imported by the experiment builder agent.

import os
import json
import random
import datetime
import subprocess

# LLM Library (intentionally not shown to the experiment builder agent, here we just wrap these functions to provide access to the experiment builder agent)
from llm_proxy_usage import llm_response_, llm_get_embedding_, cosine_embedding_   # This file will automatically be provided in the container.

#
#   (CRITICAL) Logger: Logging and Debugging
#

# The logger -- you *MUST* use this in your code.
class Logger:
    def __init__(self):
        self.LOGGER_FILENAME = "log.json"       # THIS FILENAME MUST ALWAYS BE `log.json` FOR THE EXECUTION ENVIRONMENT TO WORK -- DO NOT CHANGE IT
        self.log = []
        self.start_time = datetime.datetime.now()

    # Log a message.  Including an informative "type" will allow filtering down to specific types of messages.
    # Common Types:
    # "info": Information on what your code is doing/what it's currently processing.
    # "warning": A warning message that something might be wrong, potentially indicating a bug, but the code can continue.
    # "error": An error message that something is wrong, almost always indicating a bug, and the code cannot continue.
    # "debug": A helpful message for debugging a current issue.
    def logMessage(self, type:str, message:str):
        # Add a timestamp to the log (time of message, referenced from the start of program execution). This can help debug performance issues/timeouts.
        delta_time = datetime.datetime.now() - self.start_time
        runtime_seconds = round(delta_time.total_seconds(), 2)  # Only keep 2 decimal places, to prevent the log from getting too large
        # Add the message to the log
        self.log.append({"type": type, "runtime_sec": runtime_seconds, "message": message})
        # Save the log
        with open(self.LOGGER_FILENAME, 'w') as fileOut:
            json.dump(self.log, fileOut, indent=4)

#
#   (CRITICAL) Large Language Models (LLMs): Proxy usage
#   Generally all LLMs will be unavailable except through this proxy, which is the only way to access them.  It tracks costs and usage.
#

# Wapper function to get an LLM response from the LLM proxy
def llm_response(prompt:str, model:str, temperature:float=0, max_tokens:int=100, json_out:bool=False): # Wrapper
    success, responseText = llm_response_(prompt, model, temperature, max_tokens, json_out)
    return success, responseText

# Wrapper function to get embeddings from the LLM proxy
def llm_get_embedding(strings_to_embed:list[str], model:str): # Wrapper
    success, embeddings = llm_get_embedding_(strings_to_embed, model)
    return success, embeddings

# Wrapper function to calculate the cosine similarity between two embeddings
def cosine_embedding(embedding1:list, embedding2:list): # Wrapper
    return cosine_embedding_(embedding1, embedding2)


#
#   Large Language Model (LLMs): Parsing
#

# Finds all the codeblocks in a string, and returns them as a list of lists of strings.
# Very useful when providing a format prompt to an LLM, as you can ask it to provide specific structured responses within a codeblock, then extract these.
# e.g. "Please respond in JSON format, as a dictionary with a single key, `answer', which is a number. Place your response between codeblocks (```)"
# Expected input_str:
# ```
# {
#    "answer": 42
# }
# ```
# Returns: [["{", "\"answer\": 42", "}"]]
# Will handle multiple codeblocks in the input string.
# NOTE: This function is used in the LLM proxy code, and is critical for extracting structured data from LLM responses.
def find_codeblocks(input_str):
    # Find all codeblocks in the input string
    codeblocks = []
    lines = input_str.split("\n")
    current_codeblock = []
    active = False

    for idx, line in enumerate(lines):
        if line.startswith("```"):
            if (active == True):
                # Finish off the current codeblock
                codeblocks.append(current_codeblock)
                current_codeblock = []
                active = False
            else:
                # Start a new codeblock
                active = True
        else:
            # If we're currently in the middle of a codeblock, add the line to the current codeblock (we never want the ``` to be included in the codeblock)
            if (active == True):
                current_codeblock.append(line)

    return codeblocks



#
#   Knowledge Bases: WordNet
#

# Setup: Install and download WordNet data
def setup_wordnet():
    import nltk

    try:
        nltk.data.find('corpora/wordnet.zip')
    except LookupError:
        print("Downloading WordNet data...")
        nltk.download('wordnet')
        nltk.download('omw-1.4')  # For multilingual WordNet


#
#   Knowledge Base: ConceptNet
#

class ConceptNet:
    # Constructor
    def __init__(self):
        self.conceptNet = {}                    # A dictionary. Keys = node names. Values = a list of edges. Each edge is a list of [relation, end_node].  No weights.
        self.download_and_load_conceptnet()

    # Install a package (using apt-get), if it's not already installed
    def install_apt_get(self, package_name):
        # Check if the package is installed
        try:
            result = subprocess.run(["dpkg-query", "-W", package_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (result.returncode != 0):
                # If the package is not installed, install it
                print(f"Installing package '{package_name}'...")
                subprocess.run(["apt-get", "install", "-y", package_name], check=True)
                print(f"Package '{package_name}' installed successfully.")
            else:
                print(f"Package '{package_name}' is already installed.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install package '{package_name}': {str(e)}")
            raise

    # Download and load the ConceptNet knowledge base (NOTE: This code is critical, as this is a pre-processed version of ConceptNet that makes it easier to use)
    def download_and_load_conceptnet(self):
        # Download a special pre-processed English-only version of ConceptNet knowledge base
        #CONCEPTNET_URL = "https://drive.google.com/uc?export=download&id=1yYDLazj_pgupsC3JQMmGV33Tfo8wRIoO"   # Link for a file called `codeblocks/knowledgebases/conceptnet-assertions-5.7.0.reduced.lookup.zip`
        CONCEPTNET_URL = "http://cognitiveai.org/wp-content/uploads/2024/12/conceptnet-assertions-5.7.0.reduced.lookup.zip"   # Link for a file called `codeblocks/knowledgebases/conceptnet-assertions-5.7.0.reduced.lookup.zip`
        destination = "conceptnet-assertions-5.7.0.reduced.lookup.zip"
        knowledgebase_file = "conceptnet-assertions-5.7.0.reduced.lookup.json"

        # Download the ConceptNet knowledge base using gdown
        print("Downloading ConceptNet Knowledge Base...")
        try:
            #os.system(f"gdown '{CONCEPTNET_URL}' -O {destination}")
            os.system(f"wget -O --output-document={destination} {CONCEPTNET_URL}")     # KEEP THIS EXACT LINE
        except Exception as e:
            print("Error downloading ConceptNet knowledge base: " + str(e))

        # Unzip the downloaded file
        print("Unzipping ConceptNet Knowledge Base...")
        try:
            # Check if unzip is installed
            self.install_apt_get("unzip")
            # Unzip the file
            os.system(f"unzip -o {destination}")    # DESTINATION MUST BE IDENTICAL BETWEEN THIS LINE AND LINE ABOVE!
        except Exception as e:
            print("Error unzipping ConceptNet knowledge base: " + str(e))

        # Load the ConceptNet knowledge base
        print("Loading ConceptNet Knowledge Base (this may take a moment...)")
        with open(knowledgebase_file, "r") as f:
            self.conceptnet = json.load(f)

        print("ConceptNet Knowledge Base loaded successfully.")

        # Get a list of all nodes and all relations in the graph
        self.nodeNames = set(self.conceptnet.keys())
        self.relations = set()
        for nodeName in self.nodeNames:
            for edge in self.conceptnet[nodeName]:
                self.relations.add(edge[0])
        self.relations = sorted(list(self.relations))


    # Find nodes that start with a given string. Return a list of node names.
    # NOTE: Node names in this ConceptNet are English-only, so are of the form "cat" instead of "/c/en/cat". Spaces for multi-word nodes are replaced with underscores. Some (but not all) nodes end with "/n" (noun), "/a" (adjective), "/v" (verb), or other suffixes.
    def find_nodes(self, startswith:str, strict:bool=False):
        # REQUIRED SANITIZATION: Replace any spaces with underscores
        startswith = startswith.replace(" ", "_")
        # REQUIRED SANITIZATION: Convert to lowercase
        startswith = startswith.lower()

        # Search
        results = []
        for nodeName in self.nodeNames:
            if (strict):
                # Strict mode: Only returns nodes that are (1) exact matches, or (2) exact matches with a slash (which usually indicates part of speech, like "cat/n")
                if (nodeName == startswith) or (nodeName.startswith(startswith + "/")):
                    results.append(nodeName)
            else:
                # Starts with
                if nodeName.startswith(startswith):
                    results.append(nodeName)

        return results


    # Get edges for a node
    # Returns a list of [start_node, relation, end_node] pairs for this node, where `start_node` is always `node_name`.
    # Optionally, you can filter by a list of relation types. For example, to get only "IsA" relations, use `filter_relation_types=["IsA"]`.
    def get_node_edges(self, node_name:str, filter_relation_types:list=None):
        # Check if the node exists
        if (node_name not in self.conceptnet):
            return []
        # If the node exists, return a list of [start_node, relation, end_node] pairs for this node, where `start_node` is always `node_name`.
        edges = [[node_name, edge[0], edge[1]] for edge in self.conceptnet[node_name]]
        # Filter, if appropriate
        if (filter_relation_types is not None):
            edges = [edge for edge in edges if edge[1] in filter_relation_types]
        return edges

    # Get a list of all relation types across all edges in the graph
    def get_all_relations(self):
        return list(self.relations)

    # Get a list of all nodes in the graph (node names only). NOTE: This list is expected to be VERY large (millions of nodes).
    def get_all_nodes(self):
        return list(self.nodeNames)



#
#   Plotting: DOT Graphviz Graph
#

# Check for a GraphViz installation. If it's not installed, try to install it.
def check_and_install_dot_graphviz():
    import subprocess

    # First, check that 'dot' is installed and available in the system path
    try:
        subprocess.run(["dot", "-V"], check=True)
        return True
    except FileNotFoundError:
        print("Error: 'dot' (Graphviz) is not installed or not available in the system path.")

    # If we reach here, try to install DOT/Graphviz
    try:
        print("Attempting to install 'dot' (Graphviz)...")
        subprocess.run(["apt-get", "install", "-y", "graphviz"], check=True)
        # Add a small delay to allow the system to recognize the installation
        import time
        time.sleep(5)

        return True
    except subprocess.CalledProcessError:
        print("Error: 'dot' (Graphviz) installation failed.")

    return False


def run_dot_graphviz(dot_file:str, image_filename_out:str):
    """
    Runs the DOT/Graphviz program to create a graph from the specified DOT file.
    The output file format is determined by the extension of the output file name.

    Parameters:
    dot_file (str): The path to the DOT file to be processed.
    out_file (str): The path to the output file where the graph will be saved.
    """
    import subprocess

    # First, check that 'dot' is installed and available in the system path
    if (not check_and_install_dot_graphviz()):
        return

    # Run the 'dot' program to create a graph from the DOT file
    subprocess.run(["dot", "-Tpdf", dot_file, "-o", image_filename_out])


#
#   Statistics: Non-parametric bootstrap resampling (an inferrential statistic to compare two distributions (e.g. scores from models) to see if one is better than the other)
#

# (Topic: Bootstrap resampling)
# Main bootstrap resampling procedure.
def bootstrap_resampling(difference_scores:list, mean_baseline, mean_experimental, num_resamples:int=10000):
    # Initialize a random number generator with a seed that's the time of day
    r = random.Random()

    # Store how many times the resampled mean was greater than zero (i.e. the experimental model was better than the baseline model)
    count_better = 0

    # Step 1: Perform the resampling proceure `num_resamples` times
    for i in range(num_resamples):
        # Step 2: Sample (with replacement) a new array of difference scores that's the same size as the original one.
        array_size = len(difference_scores)
        resampled_scores = []
        for j in range(array_size):
            # Sample an index from the original array
            random_index = r.randint(0, array_size-1)
            # Add the score at that index to the resampled array
            resampled_scores.append(difference_scores[random_index])

        # Step 3: Calculate the mean of the resampled scores
        resampled_mean = sum(resampled_scores) / array_size

        # Step 4: Check if the resampled mean is greater than zero.
        if (resampled_mean > 0):
            # If so, increment the counter
            count_better += 1

    # Step 5: Calculate the probability that the experimental model is better than the baseline model
    probability_better = count_better / num_resamples

    # Step 6: Calculate the P-value
    p_value = 1 - probability_better

    # Step 7: Pack the output
    packedOut = {
        "mean_baseline": mean_baseline,
        "mean_experimental": mean_experimental,
        "p_value": p_value,
        "dataset_size": len(difference_scores),
        "num_resamples": num_resamples,
    }

    return packedOut


# (Topic: Bootstrap resampling) Data preparation for bootstrap resampling: Creating difference scores (from either an array of dictionaries, or parallel arrays)
# Takes an array of dictionaries as input, where each dictionary represents one item of data both models were tested on, and what their scores were on that specific data point -- i.e. each dictionary must have scores from a baseline model and an experimental model.
# Returns an array of the difference scores between the baseline and experimental models, for each data point (and the means of the two models)
def generate_difference_scores_dict(dataIn:list, key_baseline:str, key_experimental:str):
    # Calculate the difference scores between the two models for each data point
    baseline_scores = []
    experimental_scores = []
    difference_scores = []
    errors = 0
    for dataPoint in dataIn:
        if (key_baseline not in dataPoint):
            print(f"ERROR: generate_difference_scores_dict(): Key '{key_baseline}' not found in data point: {dataPoint}")
            errors += 1
        if (key_experimental not in dataPoint):
            print(f"ERROR: generate_difference_scores_dict(): Key '{key_experimental}' not found in data point: {dataPoint}")
            errors += 1
        if (errors > 0):
            print(f"ERROR: {errors} errors found in data. Exiting.")
            exit(1)

        # Get the individual model scores
        baselineScore = dataPoint[key_baseline]
        experimentalScore = dataPoint[key_experimental]
        # Store the individual model scores
        baseline_scores.append(baselineScore)
        experimental_scores.append(experimentalScore)
        # Calculate the difference scores
        differenceScore = experimentalScore - baselineScore
        # Store the difference score
        difference_scores.append(differenceScore)
        # Also calculate the means
        baselineMean = sum(baseline_scores) / len(baseline_scores)
        experimentalMean = sum(experimental_scores) / len(experimental_scores)

    return difference_scores, baselineMean, experimentalMean


# (Topic: Bootstrap resampling) Data preparation for bootstrap resampling: Creating difference scores (from either an array of dictionaries, or parallel arrays)
# Takes two arrays as input, where the i_th score in both arrays corresponds to the respective model's score on the i_th data point.
# Returns an array of the difference scores between the baseline and experimental models, for each data point (and the means of the two models)
def generate_difference_scores_parallel_arrays(baseline_scores:list, experimental_scores:list):
    # Check that the arrays from the two models are the same length.
    if (len(baseline_scores) != len(experimental_scores)):
        print(f"ERROR: generate_difference_scores_parallel_arrays(): The two arrays are not the same length: {len(baseline_scores)} vs {len(experimental_scores)}")
        exit(1)

    # Calculate the difference scores between the two models for each data point
    difference_scores = []
    for i in range(len(baseline_scores)):
        # Get the individual model scores
        baselineScore = baseline_scores[i]
        experimentalScore = experimental_scores[i]
        # Calculate the difference scores
        differenceScore = experimentalScore - baselineScore
        # Store the difference score
        difference_scores.append(differenceScore)

    # Also calculate the means
    baselineMean = sum(baseline_scores) / len(baseline_scores)
    experimentalMean = sum(experimental_scores) / len(experimental_scores)

    return difference_scores, baselineMean, experimentalMean


#
#   Generating datasets with LLMs
#

# This is a helper function for generating the dataset -- it should generally only be called by the `generate_dataset_json` function.
def generate_dataset_one_pass(task_description, format_prompt, model, temperature, max_tokens, existing_dataset_so_far, num_samples_to_generate=10):
    prompt = "This is a dataset generation task.  Your task is to generate a dataset according to the specific instructions provided below.\n"
    prompt += "You will be provided with the following:\n"
    prompt += " 1. A task description, which describes the dataset generation task.\n"
    prompt += " 2. A format prompt, which describes the JSON format each record of the dataset should be generated in.\n"
    prompt += " 3. Previous data you generated for this dataset, so that you don't duplicate data you've generated before.\n"
    prompt += " 4. The number of new, unique samples you should generate for this dataset.\n"
    prompt += "You will then be asked to generate those new samples, following the requested format.\n"
    prompt += "\n"
    prompt += "*SECTION: Task description*\n"
    prompt += "The following is your task description for this dataset:\n"
    prompt += "```\n"
    prompt += task_description + "\n"
    prompt += "```\n"
    prompt += "\n"
    prompt += "*SECTION: Format prompt*\n"
    prompt += "The following is the format for each record in this dataset:\n"
    prompt += "```\n"
    prompt += format_prompt + "\n"
    prompt += "```\n"
    prompt += "\n"
    prompt += "*SECTION: Existing dataset*\n"
    prompt += "The following is the data that you've generated so far for this dataset.  Unless otherwise specified above, you should not duplicate this data, and try to generate new, unique, diverse samples for this task.\n"
    prompt += "```\n"
    prompt += json.dumps(existing_dataset_so_far, indent=2) + "\n"
    prompt += "```\n"
    prompt += "\n"
    prompt += "*SECTION: Number of samples to generate*\n"
    prompt += "You should generate " + str(num_samples_to_generate) + " new, unique samples for this dataset.\n"
    prompt += "\n"
    prompt += "*SECTION: Output Instructions\n"
    prompt += "Please respond in JSON format, as a list of dictionaries, where each dictionary represents a record in the dataset.\n"
    prompt += "The JSON should be between a singele set of ticks (```), and the code ticks (```) must be alone on new lines, as in the following:\n"
    prompt += "```\n"
    prompt += "[\n"
    prompt += "  {\"field1\": \"value1\", \"field2\": \"value2\"}, # One record\n"
    prompt += "  {\"field1\": \"value3\", \"field2\": \"value4\"}, # Second record\n"
    prompt += "  {\"field1\": \"value5\", \"field2\": \"value6\"},  # Third record\n"
    prompt += "  # And so on, for " + str(num_samples_to_generate) + " records\n"
    prompt += "]\n"
    prompt += "```\n"
    if (num_samples_to_generate == 1):
        prompt += "Even though you have been asked to generate only 1 sample, you must still provide it wrapped in a list, the list will just contain the single dictionary.\n"
    prompt += "You should ONLY generate new sampels in your output -- that is, DO NOT try to output the entire dataset, only the NEW SAMPLES for the dataset.\n"


    # Call the LLM
    success, responseText = llm_response(prompt, model, temperature=temperature, max_tokens=max_tokens, json_out=False)
    if (success == False):
        return False, {"success": False, "errors": ["ERROR calling the LLM.", responseText]}

    # Extract the JSON from the response.
    # First, look for codeblocks
    codeblocks = find_codeblocks(responseText)

    # There should only be one codeblock here -- and it should have the JSON response.
    response_out_json = None
    if (len(codeblocks) > 0):
        codeblock = codeblocks[0]       # If there's more than one codeblock, just take the first.
        # Join the lines
        codeblockStr = "\n".join(codeblock)
        # Try to convert to JSON
        try:
            response_out_json = json.loads(codeblockStr)
        except Exception as e:
            return False, {"success": False, "errors": ["ERROR: Could not convert response to JSON."]}

    # Add the new samples to the existing dataset
    # Check that the output format is a list of dictionaries
    if (isinstance(response_out_json, list) == False):
        return False, {"success": False, "errors": ["The output was not a list of dictionaries."]}

    # Add the samples to the dataset
    new_samples = []
    new_samples_added = 0
    new_samples_with_errors = 0
    for new_sample in response_out_json:
        if (isinstance(new_sample, dict) == True):
            new_samples.append(new_sample)
            existing_dataset_so_far.append(new_sample)
            new_samples_added += 1
        else:
            new_samples_with_errors += 1

    # If no samples were added, return an error
    if (new_samples_added == 0):
        return False, {"success": False, "errors": ["No new samples were generated."]}

    # Return the new dataset
    packed = {
        "success": True,
        "new_samples": new_samples,
        "new_samples_added": new_samples_added,
        "new_samples_with_errors": new_samples_with_errors,
        "dataset": existing_dataset_so_far,
        "errors": []
    }
    return True, packed


# Calls the above function multiple times to generate a dataset
# Generally, for most models, num_to_generate_per_batch should not be larger than 10, or data quality decreases.
def generate_dataset_json(dataset_name, task_description, format_prompt, model, num_total_samples, num_to_generate_per_batch, temperature, max_tokens):
    # Initialize the dataset
    dataset = []
    errors = []
    MAX_ERRORS = 10  # Maximum number of errors before we stop trying to generate the dataset
    MAX_BATCHES = 100   # If we reach this many batches, we stop trying to generate the dataset

    # Generate the dataset
    failed = False
    dataset_batch_num = 0
    print("generate_dataset_json: Generating dataset with " + str(num_total_samples) + " samples.")
    while (len(dataset) < num_total_samples):
        dataset_batch_num += 1
        print("generate_dataset_json: Generating dataset batch " + str(dataset_batch_num) + "...")
        # Generate the next batch
        success, result = generate_dataset_one_pass(task_description, format_prompt, model, temperature, max_tokens, dataset, num_to_generate_per_batch)
        if (success == False):
            errors.extend(result["errors"])
        else:
            # Success -- Add the new samples to the dataset
            print("Successfully generated " + str(result["new_samples_added"]) + " new samples.")
            dataset = result["dataset"]

        if (len(errors) > MAX_ERRORS):
            failed = True
            break

        if (dataset_batch_num > MAX_BATCHES):
            failed = True
            errors.append("ERROR: Maximum number of batches reached.")
            break

    # Successful datasets are automatically saved under the dataset name
    if (failed == False):
        save_dataset_json(dataset_name, dataset)

    # Return
    packed = {
        "success": not failed,
        "dataset": dataset,
        "errors": errors
    }

    return packed


# Save dataset
def save_dataset_json(dataset_name:str, dataset):
    # Make the `retain` directory if it doesn't exist
    RETAIN_PATH = "retain/"
    try:
        #if (os.path.exists("retain") == False):
        if (os.path.exists(RETAIN_PATH) == False):
            os.makedirs(RETAIN_PATH)
        # Save the dataset to a file
        filename = RETAIN_PATH + dataset_name + ".json"
        with open(filename, "w") as f:
            f.write(json.dumps(dataset, indent=2))
    except Exception as e:
        print("ERROR: Could not save the dataset to a file.")
        print(e)
        return False
    print("Dataset saved successfully (name = `" + dataset_name + "`, with " + str(len(dataset)) + " samples).")
    return True

# Load the dataset
def load_dataset_json(dataset_name:str):
    # Load the dataset from a file
    RETAIN_PATH = "retain/"
    filename = RETAIN_PATH + dataset_name + ".json"
    dataset = []
    if (os.path.exists(filename) == False):
        print("ERROR: Could not find an exsiting dataset under that name.")
        return None
    with open(filename, "r") as f:
        dataset = json.load(f)
    print("Loaded dataset (name = " + dataset_name + ", with " + str(len(dataset)) + " samples).")
    return dataset
