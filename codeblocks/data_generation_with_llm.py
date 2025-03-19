# Name: Data generation with LLM
# Description: This is an example of using a large language model to generate a modest sized dataset
# inclusion_criteria: If you'd like to generate a dataset using a large language model, then you may want to use this codeblock.
# exclusion_criteria: If you don't want to generate a dataset using a large language model, then you may not find this codeblock useful.
# python_version: >=3.8

import os
import json

from experiment_common_library import llm_response, find_codeblocks, load_dataset_json, save_dataset_json, generate_dataset_json


# This example shows querying several different LLMs with the same prompt.
def example1():

    dataset_name = "science-questions-1"
    # REQUIRED: Normally we want to keep datasets identical across experiments, so first we check if we've already generated this dataset under this name, and if so, load it.
    # NOTE: If you do not like a previous dataset for any reason, and want to generate a new one, just index the dataset name to a previously unused name (e.g. change "science-questions-1" to "science-questions-2").
    dataset = load_dataset_json(dataset_name)   # If 'None', then a dataset under this name has not been generated yet.
    if (dataset == None):
        # A dataset with that name has not previously been generated -- generate it now
        task_description = "Please generate multiple choice 4-choice questions about any topic covered in 4th grade science in the United States. For this condition, the distractors (i.e. incorrect answers) should all have the following property: one should be obviously incorrect, the remaining two distractors should contain words that are highly associated with the correct answer."
        format_prompt = "Each dictionary should have the following keys:\n"
        format_prompt += " 1. 'question': The question text.\n"
        format_prompt += " 2. 'choices': A dictionary of answer choices (keys = A, B, C, D, values = the answer choice)\n"
        format_prompt += " 3. 'correct': The correct answer choice (A, B, C, or D).\n"
        format_prompt += " 4. 'explanation': An explanation of the correct answer.\n"

        model = "gpt-4o-mini"
        num_total_samples = 25
        num_to_generate_per_batch = 5
        temperature = 0.5       # High temperatures will make the LLM more creative/more diverse, but also more likely to make mistakes.

        # Note, successfully generated datasets are automatically saved under 'dataset_name'.  Generating a dataset multiple times under the same name will overwrite the previous dataset.
        dataset_result = generate_dataset_json(dataset_name, task_description, format_prompt, model, num_total_samples, num_to_generate_per_batch, temperature, max_tokens=8000)

        if (dataset_result["success"] == False):
            print("There were one or more errors generating the dataset:")
            print(dataset_result["errors"])
        else:
            print("Dataset generated successfully.")
            dataset = dataset_result["dataset"]

    # Print the dataset
    print("Dataset:")
    print(json.dumps(dataset, indent=2))


def example2_negative():
    # We likely wouldn't want to use a language model to generate a dataset that (1) we know the LLM is not good at, and (2) that could be generated more accurately another way.
    # For example, LLMs are generally bad at arithmetic, and we would not expect they would generate a dataset of (for example) 10-digit multiplication problems correctly,
    # where as a simple Python script could do so easily.
    dataset_name = "10-digit-multiplication-1"
    # REQUIRED: Normally we want to keep datasets identical across experiments, so first we check if we've already generated this dataset under this name, and if so, load it.
    # NOTE: If you do not like a previous dataset for any reason, and want to generate a new one, just index the dataset name to a previously unused name (e.g. change "science-questions-1" to "science-questions-2").
    dataset = load_dataset_json(dataset_name)   # If 'None', then a dataset under this name has not been generated yet.
    if (dataset == None):
        # A dataset with that name has not previously been generated -- generate it now
        task_description = "Please generate 10-digit multiplication problems."
        format_prompt = "Each dictionary should have the following keys:\n"
        format_prompt += " 1. 'problem': The multiplication problem.\n"
        format_prompt += " 2. 'answer': The correct answer to the problem.\n"

        model = "gpt-4o-mini"
        num_total_samples = 10
        num_to_generate_per_batch = 5
        temperature = 0.5

        # Note, successfully generated datasets are automatically saved under 'dataset_name'.  Generating a dataset multiple times under the same name will overwrite the previous dataset.
        dataset_result = generate_dataset_json(dataset_name, task_description, format_prompt, model, num_total_samples, num_to_generate_per_batch, temperature, max_tokens=8000)

        if (dataset_result["success"] == False):
            print("There were one or more errors generating the dataset:")
            print(dataset_result["errors"])
        else:
            print("Dataset generated successfully.")
            dataset = dataset_result["dataset"]

    # Print the dataset
    print("Dataset:")
    print(json.dumps(dataset, indent=2))


#
#   Main
#
if __name__ == "__main__":
    example1()
    example2_negative()