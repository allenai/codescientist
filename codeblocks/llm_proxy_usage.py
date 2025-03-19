# DISABLED
# This is only in this directory so the `llm_submit_proxy.py` script can import it when testing.
# Otherwise, it should be disregarded, and will NOT be automatically loaded by the compositional codeblocks code.


# An example library of LLM proxy usage.
import os
import time
import json
import requests

# Get an LLM response from the LLM proxy
# Returns a tuple of (success:bool, responseText:str)
# If 'success' is FALSE, the program should probably stop making LLM calls, exit, and the issue should be investigated.
def llm_response_(prompt:str, model:str, temperature:float=0, max_tokens:int=100, json_out:bool=False): # Wrapper
    return llm_response(prompt, model, temperature, max_tokens, json_out)

def llm_response(prompt:str, model:str, temperature:float=0, max_tokens:int=100, json_out:bool=False):
    # Pack the messages
    messages=[{"role": "user", "content": prompt}]

    # DEBUG: Dump the whole prompt to a file called (prompt-debug.txt) in the 'prompts' directory
    if not os.path.exists("prompts"):
        os.makedirs("prompts")
    #print("Writing prompt to prompt-debug.txt...")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filenameOut = "prompts/prompt-debug." + timestamp + ".txt"
    with open(filenameOut, "w") as f:
        f.write(prompt)

    # Assemble the packet to the LLM proxy
    response_format = None
    if json_out:
        response_format = {"type": "json_object"}

    # Extra headers
    extra_headers = None

    packet = {
        "messages": messages,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": response_format,
        "extra_headers": extra_headers
    }

    # Send this packet to the LLM proxy, at localhost:4000, and wait for the response
    response = requests.post("http://localhost:4000/chat/completions", json=packet)
    response = response.json()

    # Check for an error response from the proxy
    if ("error" in response):
        # Check for specific critical errors
        if ("type" in response["error"]):
            error_type = response["error"]["type"]
            if (error_type == "cost_limit_exceeded"):
                return False, "ERROR: LLM cost limit exceeded. No additional requests will be processed."
            if (error_type == "too_many_errors"):
                return False, "ERROR: Too many errors in processing LLM requests. No additional requests will be processed."

        # Generic error
        return False, "ERROR: LLM error. " + str(response["error"])

    # # DEBUG: PRINT FULL RESPONSE
    # print("FULL RESPONSE:")
    # print(response)

    responseText = response["choices"][0]["message"]["content"]

    # DEBUG: Also dump the (timestamped) response to the 'prompts' directory
    filenameOut = "prompts/prompt-debug." + timestamp + ".response.txt"
    with open(filenameOut, "w") as f:
        f.write(responseText)

    # If we reach here, success!
    # Return
    return True, responseText


# Returns a list of embeddings for the list of input strings. The model is the model to use for the embeddings.
# Use the `http://localhost:4000/embeddings` endpoint.
# Returns a tuple of (success:bool, embeddings:list)
def llm_get_embedding_(strings_to_embed:list[str], model:str): # Wrapper
    return llm_get_embedding(strings_to_embed, model)

def llm_get_embedding(strings_to_embed:list[str], model:str):
    # Create the packet
    packet = {
        "input": strings_to_embed,
        "model": model,
    }

    # Send this packet to the LLM proxy, at localhost:4000, and wait for the response
    response = requests.post("http://localhost:4000/embeddings", json=packet)
    response = response.json()

    # Check for an error response from the proxy
    if ("error" in response):
        # Check for specific critical errors
        if ("type" in response["error"]):
            error_type = response["error"]["type"]
            if (error_type == "cost_limit_exceeded"):
                return False, ["ERROR: LLM cost limit exceeded. No additional requests will be processed."]
            if (error_type == "too_many_errors"):
                return False, ["ERROR: Too many errors in processing LLM requests. No additional requests will be processed."]

        # Generic error
        return False, ["ERROR: LLM error. " + str(response["error"])]

    # # DEBUG: PRINT FULL RESPONSE
    print("FULL RESPONSE:")
    print(response)


    # put the keys of the response
    print(response.keys())

    # Extract the embeddings
    embeddings = [0] * len(strings_to_embed)
    count_extracted_embeddings = 0
    data = None
    if ("data" in response):
        data = response["data"]
    if (data != None) and (isinstance(data, list)):
        # Get the embeddings, one by one
        for i in range(0, len(data)):
            embedding_struct = data[i]
            embedding = None
            index = None
            if ("embedding" in embedding_struct):
                embedding = embedding_struct["embedding"]
            if ("index" in embedding_struct):
                index = embedding_struct["index"]
            if (embedding != None) and (index != None):
                embeddings[index] = embedding
                count_extracted_embeddings += 1

    # Verify that we recieved all the embeddings
    if (count_extracted_embeddings != len(strings_to_embed)):
        return False, ["ERROR: Not all embeddings were extracted. Only " + str(count_extracted_embeddings) + " out of " + str(len(strings_to_embed)) + " were found."]

    # If we reach here, success!
    # Return
    return True, embeddings


# Calculate cosine similarity between two embeddings
def cosine_embedding_(embedding1:list, embedding2:list): # Wrapper
    return cosine_embedding(embedding1, embedding2)

def cosine_embedding(embedding1:list, embedding2:list):
    # Verify the embeddings are the same length
    if (len(embedding1) != len(embedding2)):
        return None

    # Calculate the dot product
    dot_product = 0
    for i in range(0, len(embedding1)):
        dot_product += embedding1[i] * embedding2[i]

    # Calculate the magnitudes
    magnitude1 = 0
    magnitude2 = 0
    for i in range(0, len(embedding1)):
        magnitude1 += embedding1[i] * embedding1[i]
        magnitude2 += embedding2[i] * embedding2[i]
    magnitude1 = magnitude1 ** 0.5
    magnitude2 = magnitude2 ** 0.5

    # Calculate the cosine similarity
    cosine_similarity = dot_product / (magnitude1 * magnitude2)

    return cosine_similarity

#
#   Main
#
if __name__ == "__main__":
    # Try a sample prompt

    # Test embeddings
    embedding_strings = ["The person saw a cat", "The person saw a dog", "Trees have green leaves"]
    embedding_models = ["text-embedding-3-large", "text-embedding-3-small"]
    embeddings = []
    for model in embedding_models:
        print("Model: " + model)
        success, embeddings = llm_get_embedding(embedding_strings, model)

        if (success == False):
            print("LLM call error: " + str(embeddings))   # If there's an error, the responseText will be an error message.
        else:
            print("Embeddings:")
            for i in range(0, len(embedding_strings)):
                print("Sentence: " + embedding_strings[i])
                # Show the first 10 values of the embedding
                if (len(embeddings[i]) > 10):
                    print("Embedding: " + str(embeddings[i][0:10]))
                else:
                    print("Embedding: " + str(embeddings[i]))



            #print(embeddings)

        print("-----\n\n")

    # Calculate the cosines between the embeddings
    for i in range(0, len(embedding_strings)):
        for j in range(i+1, len(embedding_strings)):
            print("Cosine similarity between:")
            print("   " + embedding_strings[i])
            print("   " + embedding_strings[j])
            similarity = cosine_embedding(embeddings[i], embeddings[j])
            print("Similarity: " + str(similarity))
            print("-----\n\n")

    exit(0)

    # Test LLMs
    for i in range(0, 20):
        prompt = "What is 3 + 5?" # Please respond in JSON format."
        models = ["gpt-4o", "gpt-4o-mini", "o1-mini", "gpt-4o-mini", "gpt-4o-mini", "o1-mini", "claude-3-5-sonnet-20240620", "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1", "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"]

        for model in models:
            print("Model: " + model)
            success, responseText = llm_response(prompt, model, temperature=0, max_tokens=1000, json_out=False)

            if (success == False):
                print("LLM call error: " + str(responseText))   # If there's an error, the responseText will be an error message.
            else:
                print("Response:")
                print(responseText)

            print("-----\n\n")
