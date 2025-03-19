# Name: LLM example through proxy server
# Description: This is an example of using all LLMs available from OpenAI, Anthropic, or Together.AI, through a litellm proxy server.  If you use an LLM, it *MUST* be through this proxy server, as the proxy server is responsible for managing costs.  Do not attempt to use an API-based LLM except through this proxy server.
# inclusion_criteria: If you need to use an API-based language model (e.g. OpenAI, Anthropic, Together.AI, etc.), then you *need* this codeblock.
# exclusion_criteria: If you're not using an API-based language model, then this codeblock is unlikely to be useful.
# python_version: >=3.8

import os
import time
import json
import requests

from experiment_common_library import llm_response, llm_get_embedding, cosine_embedding, find_codeblocks    # Import the LLM functions

# Known models and their cost
# {
#     "example-model-name":           {"cost_per_1M_prompt_tokens": 20.0, "cost_per_1M_completion_tokens": 20.0},
#     "gpt-3.5-turbo-1106":           {"cost_per_1M_prompt_tokens": 1.00, "cost_per_1M_completion_tokens": 2.00},
#     "gpt-4-turbo":                  {"cost_per_1M_prompt_tokens": 10.0, "cost_per_1M_completion_tokens": 30.00},
#     "gpt-4o":                       {"cost_per_1M_prompt_tokens": 2.50, "cost_per_1M_completion_tokens": 10.00},
#     "gpt-4o-mini":                  {"cost_per_1M_prompt_tokens": 0.15, "cost_per_1M_completion_tokens": 0.60},
#     "o1-preview":                   {"cost_per_1M_prompt_tokens": 15.00, "cost_per_1M_completion_tokens": 60.00},
#     "o1-mini":                      {"cost_per_1M_prompt_tokens": 3.00, "cost_per_1M_completion_tokens": 12.00},
#     "claude-3-5-sonnet-20240620":   {"cost_per_1M_prompt_tokens": 3.00, "cost_per_1M_completion_tokens": 15.00},
#     "claude-3-5-sonnet-20241022":   {"cost_per_1M_prompt_tokens": 3.00, "cost_per_1M_completion_tokens": 15.00},
#     "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1": {"cost_per_1M_prompt_tokens": 0.60, "cost_per_1M_completion_tokens": 0.60},
#     "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": {"cost_per_1M_prompt_tokens": 0.18, "cost_per_1M_completion_tokens": 0.18}
#     "together_ai/allenai/OLMo-7B-Instruct": {"cost_per_1M_prompt_tokens": 0.18, "cost_per_1M_completion_tokens": 0.18} (CURRENTLY NOT AVAILABLE)
# }
# Known embedding models:
# {
#     "text-embedding-3-small": {"cost_per_1M_tokens": 0.02},   # NOTE: Current cost estimate for all embedding models assumes all requests are max (8192) tokens, since the cost is so low.
#     "text-embedding-3-large": {"cost_per_1M_tokens": 0.12}
# }

# This example shows querying several different LLMs with the same prompt.
def example1():
    prompt = "What is 3 + 5?"
    models = ["gpt-4o", "gpt-4o-mini", "o1-mini", "claude-3-5-sonnet-20240620", "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"]

    for model in models:
        print("Model: " + model)
        success, responseText = llm_response(prompt, model, temperature=0, max_tokens=1000, json_out=False)

        if (success == False):
            print("Critical error: " + str(responseText))   # If success is FALSE, the responseText will be an error message.
        else:
            print("Response:")
            print(responseText)

        print("-----\n\n")



# This example shows an example of a format prompt that prompts the LLM to output JSON, in an easily-parsed format.
# Using a JSON format prompt makes it much easier to extract the response from the LLM, for LLMs that can reliably output JSON.
# NOTE: While there is a `json_out` parameter in the `llm_response` function, this is almost never used in practice, because some LLMs require explicit formatting schemas (which is not supported by this API).  It's often easier just to provide a format prompt to the LLM, and ask it to place its JSON response between codeblocks (```), as in the example below.
def example2():
    prompt = "What is 3 + 5?\n"
    prompt += "Please respond in JSON format, as a dictionary with a single key, `answer', which is a number.\n"
    prompt += "The JSON should be between code ticks (```), and the code ticks (```) must be alone on new lines, as in the following:\n"
    prompt += "```\n"
    prompt += "{\n"
    prompt += "  \"answer\": 123\n"
    prompt += "}\n"
    prompt += "```\n"

    models = ["gpt-4o", "gpt-4o-mini", "o1-mini", "claude-3-5-sonnet-20240620", "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"]
    for model in models:
        print("Model: " + model)
        success, responseText = llm_response(prompt, model, temperature=0, max_tokens=1000, json_out=False)

        if (success == False):
            print("Critical error: " + str(responseText))   # If success is FALSE, the responseText will be an error message.
        else:
            print("Response:")
            print(responseText)

        # Extract the JSON from the response.
        # First, look for codeblocks
        codeblocks = find_codeblocks(responseText)
        responseOutJSON = None
        # There should only be one codeblock here -- and it should have the JSON response.
        if (len(codeblocks) > 0):
            codeblock = codeblocks[0]       # If there's more than one codeblock, just take the first.
            # Join the lines
            codeblockStr = "\n".join(codeblock)
            # Try to convert to JSON
            print("CODEBLOCK STRING:")
            print("-----")
            print(codeblockStr)
            print("-----")
            try:
                responseOutJSON = json.loads(codeblockStr)
                print("Response JSON:")
                print(responseOutJSON)
            except Exception as e:
                print("ERROR: Could not convert response to JSON. ")

        # Check the answer
        if (responseOutJSON != None):
            # Look for expected 'answer' key
            if ("answer" in responseOutJSON):
                print("Answer: " + str(responseOutJSON["answer"]))
            else:
                print("ERROR: Could not find 'answer' key in JSON response. ")


        print("-----\n\n")


def example_embedding():
    # NOTE: You should be careful not to submit strings longer than ~8000 characters to the LLM, or more than ~100 strings at a time, or this may cause an error.
    # Test embeddings
    embedding_strings = ["The person saw a cat", "The person saw a dog", "Trees have green leaves"]
    embedding_model = "text-embedding-3-small"
    embeddings = []

    success, embeddings = llm_get_embedding(embedding_strings, embedding_model)

    if (success == False):
        print("LLM call error: " + str(embeddings))   # If there's an error, the embeddings response will be an error message.
    else:
        print("Embeddings:")
        for i in range(0, len(embedding_strings)):
            print("Sentence: " + embedding_strings[i])
            # Show the first 10 values of the embedding
            if (len(embeddings[i]) > 10):
                print("Embedding: " + str(embeddings[i][0:10]))
            else:
                print("Embedding: " + str(embeddings[i]))
        print("-----\n\n")

    # Calculate the cosines between the embeddings
    for i in range(0, len(embedding_strings)):
        for j in range(i+1, len(embedding_strings)):
            print("Cosine similarity between:")
            print("   " + embedding_strings[i])
            print("   " + embedding_strings[j])
            similarity = cosine_embedding(embeddings[i], embeddings[j])     # Cosine will be between -1 and 1 (None if there was an error)
            if (similarity == None):
                print("ERROR: There was an error calculating the cosine.")
            else:
                print("Similarity: " + str(similarity))
            print("-----\n\n")

#
#   Main
#
if __name__ == "__main__":
    example1()
    example2()

    example_embedding()