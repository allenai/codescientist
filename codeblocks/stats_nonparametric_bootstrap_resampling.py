# Name: Non-parametric Bootstrap Resampling
# Description: This is an example of how to use the Non-parametric Bootstrap Resampling inferrential statistic to tell whether two models have different performance on the same dataset.
# inclusion_criteria: If you are comparing two or more groups (e.g. a baseline group and an experimental group) to see if they are significantly different, this codeblock is likely to be useful.
# exclusion_criteria: If you are not comparing two or more groups to see if they are significantly different, this codeblock is unlikely to be useful.
# python_version: 3.8
# pip_requirement:

import random
import json

import sys
import os

# Import the bootstrap resampling functions from the common library
from experiment_common_library import generate_difference_scores_dict, generate_difference_scores_parallel_arrays, bootstrap_resampling


# Example 1: Data stored as a list of dictionaries
def example1():
    # This example is for sample data on a (for example) question answering task, with a hypothetical "baseline" model, and "experimental" model that we're trying to determine if it's significantly better or not.
    # Non-parametric bootstrap resampling relies on difference scores, and keeping the data stored in this way helps make sure the scores for a given model are assigned to a specific piece of evaluation data (e.g. a specific question)
    maximum_p_value_threshold = 0.05    # Set the threshold for the p-value to be considered significant

    # Step 1: Collect data
    data = [
        {"question": "What is the capital of France?", "baseline_model_score": 0.8, "experimental_model_score": 0.9},
        {"question": "What is the capital of Germany?", "baseline_model_score": 0.7, "experimental_model_score": 0.6},
        {"question": "What is the capital of Italy?", "baseline_model_score": 0.9, "experimental_model_score": 0.8},
        {"question": "What is the capital of Spain?", "baseline_model_score": 0.6, "experimental_model_score": 0.7},
        {"question": "What is the capital of Portugal?", "baseline_model_score": 0.5, "experimental_model_score": 0.4},
        {"question": "What is the capital of Belgium?", "baseline_model_score": 0.7, "experimental_model_score": 0.6},
        {"question": "What is the capital of Switzerland?", "baseline_model_score": 0.8, "experimental_model_score": 0.9},
        {"question": "What is the capital of Sweden?", "baseline_model_score": 0.6, "experimental_model_score": 0.7},
        {"question": "What is the capital of Norway?", "baseline_model_score": 0.5, "experimental_model_score": 0.4},
        {"question": "What is the capital of Denmark?", "baseline_model_score": 0.7, "experimental_model_score": 0.6},
        # Add more data points here...
    ]

    # Step 2: Calculate the difference scores
    difference_scores, mean_baseline, mean_experimental = generate_difference_scores_dict(data, "baseline_model_score", "experimental_model_score")

    # Step 3: Perform the bootstrap resampling procedure
    results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)

    # Step 4: Print the results
    print("The raw results of the hypothesis test are:")
    print(json.dumps(results, indent=4))

    p_value = results["p_value"]
    print(f"The p-value for the hypothesis that `the experimental model is performing better than the baseline model` test is: {p_value}")

    if (p_value < maximum_p_value_threshold):
        print("The experimental model is significantly better than the baseline model. (p < ", maximum_p_value_threshold, ")")
    else:
        print("The experimental model is not significantly better than the baseline model. (p >= ", maximum_p_value_threshold, ")")



# Example 2: Data stored in parallel arrays
def example2():
    # This example is for sample data on a (for example) question answering task, with a hypothetical "baseline" model, and "experimental" model that we're trying to determine if it's significantly better or not.
    # Non-parametric bootstrap resampling relies on difference scores.  In this example, the data is stored in parallel arrays, with the i_th datapoint representing the score on the i_th question in both arrays.
    maximum_p_value_threshold = 0.05    # Set the threshold for the p-value to be considered significant

    # Step 1: Collect data
    # Here, index 0 corresponds to performance on the first question, index 1 to the second question, and so on.
    baseline_scores = [0.8, 0.7, 0.9, 0.6, 0.5, 0.7, 0.8, 0.6, 0.5, 0.7]
    experimental_scores = [0.9, 0.6, 0.8, 0.7, 0.4, 0.6, 0.9, 0.7, 0.4, 0.6]

    # Step 2: Calculate the difference scores
    difference_scores, mean_baseline, mean_experimental = generate_difference_scores_parallel_arrays(baseline_scores, experimental_scores)

    # Step 3: Perform the bootstrap resampling procedure
    results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)

    # Step 4: Print the results
    print("The raw results of the hypothesis test are:")
    print(json.dumps(results, indent=4))

    p_value = results["p_value"]
    print(f"The p-value for the hypothesis that `the experimental model is performing better than the baseline model` test is: {p_value}")

    if (p_value < maximum_p_value_threshold):
        print("The experimental model is significantly better than the baseline model. (p < ", maximum_p_value_threshold, ")")
    else:
        print("The experimental model is not significantly better than the baseline model. (p >= ", maximum_p_value_threshold, ")")


# Example 3: Data from repeated runs of a text-game task.
# Also showcases finer-grained hypothesis testing (i.e. testing each task's performance separately), and multiple hypothesis testing.
def example3():
    # This example is for a text-game task, where a given (stochastic) model is tested in the same game environment multiple times, and the scores are recorded for each run.

    # Step 1: Collect the data
    data = [
        {"task": "finder", "parametric_variation": 1, "attempt": 1, "baseline_score": 0.5, "experimental_score": 0.6},
        {"task": "finder", "parametric_variation": 1, "attempt": 2, "baseline_score": 0.55, "experimental_score": 0.62},
        {"task": "finder", "parametric_variation": 1, "attempt": 3, "baseline_score": 0.48, "experimental_score": 0.61},
        {"task": "finder", "parametric_variation": 2, "attempt": 1, "baseline_score": 0.15, "experimental_score": 0.38},
        {"task": "finder", "parametric_variation": 2, "attempt": 2, "baseline_score": 0.19, "experimental_score": 0.36},
        {"task": "finder", "parametric_variation": 2, "attempt": 3, "baseline_score": 0.22, "experimental_score": 0.35},
        {"task": "finder", "parametric_variation": 3, "attempt": 1, "baseline_score": 0.8, "experimental_score": 0.7},
        {"task": "finder", "parametric_variation": 3, "attempt": 2, "baseline_score": 0.85, "experimental_score": 0.82},
        {"task": "finder", "parametric_variation": 3, "attempt": 3, "baseline_score": 0.78, "experimental_score": 0.92},
        {"task": "counting", "parametric_variation": 1, "attempt": 1, "baseline_score": 0.30, "experimental_score": 0.40},
        {"task": "counting", "parametric_variation": 1, "attempt": 2, "baseline_score": 0.35, "experimental_score": 0.42},
        {"task": "counting", "parametric_variation": 1, "attempt": 3, "baseline_score": 0.28, "experimental_score": 0.41},
        {"task": "counting", "parametric_variation": 2, "attempt": 1, "baseline_score": 0.75, "experimental_score": 0.85},
        {"task": "counting", "parametric_variation": 2, "attempt": 2, "baseline_score": 0.79, "experimental_score": 0.83},
        {"task": "counting", "parametric_variation": 2, "attempt": 3, "baseline_score": 0.82, "experimental_score": 0.82},
        {"task": "counting", "parametric_variation": 3, "attempt": 1, "baseline_score": 0.25, "experimental_score": 0.35},
        {"task": "counting", "parametric_variation": 3, "attempt": 2, "baseline_score": 0.29, "experimental_score": 0.33},
        {"task": "counting", "parametric_variation": 3, "attempt": 3, "baseline_score": 0.22, "experimental_score": 0.32},
    ]

    # Step 2: This hypothesis testing can me framed in two ways.
    # Framing 1: One hypothesis might be that the experimental model is better than the baseline model across all tasks and parametric variations.
    # Framing 2: The other (a multiple hypothesis testing case) -- test each task independently.
    maximum_p_value_threshold = 0.05    # Set the threshold for the p-value to be considered significant

    # Step 3A: Let's do framing 1 first -- the overall hypothesis that the experimental model is better than the baseline model across all tasks and parametric variations.
    difference_scores, mean_baseline, mean_experimental = generate_difference_scores_dict(data, "baseline_score", "experimental_score")
    print("Difference scores for all tasks:")
    print(difference_scores)

    # Step 3B: Perform the bootstrap resampling procedure
    results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)

    # Step 3C: Print the results
    print("The raw results of the hypothesis test are:")
    print(json.dumps(results, indent=4))

    p_value = results["p_value"]
    print(f"The p-value for the hypothesis that `the experimental model is performing better than the baseline model across all tasks` test is: {p_value}")

    if (p_value < maximum_p_value_threshold):
        print("The experimental model is significantly better than the baseline model. (p < ", maximum_p_value_threshold, ")")
    else:
        print("The experimental model is not significantly better than the baseline model. (p >= ", maximum_p_value_threshold, ")")


    # Step 4: Now, let's do framing 2 -- test each task independently (i.e. multiple hypothesis testing).
    # This is important because the performance of the models might vary depending on the task.
    # Step 4A: First, we need to find out how many separate conditions (i.e. tasks) we have in the data.
    tasks = set([dataPoint["task"] for dataPoint in data])

    # Step 4B: Perform the bonferroni correction for multiple hypothesis testing
    bonferroni_threshold = maximum_p_value_threshold / len(tasks)
    print("The Bonferroni threshold for multiple hypothesis testing in the case of testing " + str(len(tasks)) + " separate hypotheses, with an initial threshold of " + str(maximum_p_value_threshold) + ", is: ", bonferroni_threshold)

    # Step 4C: For each task, perform the hypothesis test
    for task in tasks:
        # Step 4C1: Filter the data for the current task
        task_data = [dataPoint for dataPoint in data if dataPoint["task"] == task]

        # Step 4C2: Calculate the difference scores for the current task
        difference_scores, mean_baseline, mean_experimental = generate_difference_scores_dict(task_data, "baseline_score", "experimental_score")

        # Step 4C3: Perform the bootstrap resampling procedure
        results = bootstrap_resampling(difference_scores, mean_baseline, mean_experimental)

        # Step 4C4: Print the results
        print(f"\nResults for task: {task}")
        print(json.dumps(results, indent=4))

        p_value = results["p_value"]
        print(f"The p-value for the hypothesis that `the experimental model is performing better than the baseline model on task '{task}'` test is: {p_value}")

        if (p_value < bonferroni_threshold):
            print("The experimental model is significantly better than the baseline model for task '", task, "' (p < ", bonferroni_threshold, ")")
        else:
            print("The experimental model is not significantly better than the baseline model for task '", task, "' (p >= ", bonferroni_threshold, ")")



# Main
if __name__ == "__main__":
    example1()
    example2()
    example3()
