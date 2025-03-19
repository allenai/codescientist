# llm-proxy-server.py

import http.server
import socketserver
import json
import litellm
import signal
import threading
import os

PORT = 4000
FILENAME_API_KEYS = "api_keys.donotcommit.json"

# Keep track of any errors, to stop early if something is wrong
MAX_ERRORS = 10
errors = []

# LLM USAGE INFORMATION
FILENAME_LLM_USAGE = "experiment-llm-usage.json"
FILENAME_LLM_COST = "experiment-llm-cost.json"

# EXPERIMENT SETUP -- INCLUDES THE MAXIMUM COSTS FOR THIS EXPERIMENT
FILENAME_EXPERIMENT_SETUP = "experiment-setup.json"
MAX_COST_USD = 0.00     # The maximum cost.  If zero, all calls will be refused.
ALLOWED_LLMS = None     # If 'None', all LLMs are allowed. If a list, only the LLMs in the list are allowed.
RESTRICTED_LLMS = None  # If 'None', no LLMs are restricted. If a list, the LLMs in the list are restricted.

# Load the experiment setup
try:
    with open(FILENAME_EXPERIMENT_SETUP, 'r') as f:
        print("Loading LLM proxy experiment setup...")
        experiment_setup = json.load(f)
        if ("max_cost_usd" in experiment_setup):
            MAX_COST_USD = experiment_setup["max_cost_usd"]
            print("Maximum cost for this experiment: " + str(MAX_COST_USD))
        if ("allowed_llms" in experiment_setup):
            ALLOWED_LLMS = experiment_setup["allowed_llms"]
            print("Allowed LLMs for this experiment: " + str(ALLOWED_LLMS))
        if ("restricted_llms" in experiment_setup):
            RESTRICTED_LLMS = experiment_setup["restricted_llms"]
            print("Restricted LLMs for this experiment: " + str(RESTRICTED_LLMS))
except FileNotFoundError:
    print("WARNING: Experiment setup file not found. LLM access will not be available through this proxy.")

# DEFAULT COST INFORMATION
# If an LLM isn't specified in the cost information, we'll use these default values
DEFAULT_COST_PER_1M_TOKENS = 20.0   # A very high cost -- generally higher than most LLMs, to be safe
DEFAULT_COST_PER_1M_TOKENS_EMBEDDING = 1.0   # A very high cost -- generally higher than most embedding models, to be safe


# The total cost of all LLM usage so far.
TOTAL_LLM_COST = 0.0            # Running cost
LLM_COST_EXCEEDED = False       # Flag to indicate if the cost has been exceeded

# Check to see if the cost has been exceeded already -- i.e if the allowed cost is zero.
if (TOTAL_LLM_COST >= MAX_COST_USD):
    LLM_COST_EXCEEDED = True

# A threading lock to make sure the usage information isn't being read/written to by more than one thread at a time.
LLM_USAGE_LOCK = threading.Lock()

# Load the API keys and set them as environment variables
try:
    with open(FILENAME_API_KEYS, 'r') as f:
        api_keys = json.load(f)
        for key in api_keys:
            if (key == "openai"):
                os.environ["OPENAI_API_KEY"] = api_keys[key]
            elif (key == "anthropic"):
                os.environ["ANTHROPIC_API_KEY"] = api_keys[key]
            elif (key == "togetherai"):
                os.environ["TOGETHERAI_API_KEY"] = api_keys[key]
            else:
                os.environ[key] = api_keys[key]
except FileNotFoundError:
    print("WARNING: API keys file not found. API keys will need to be set as environment variables.")



# Main handler for the proxy server
class Handler(http.server.BaseHTTPRequestHandler):

    # NOTE: Needs to allow only one thread at a time, to avoid competing writes.
    def save_cost_information(self, num_tokens_prompt, num_tokens_completion, model_name, embedding:bool=False, num_embeddings:int=0):
        global TOTAL_LLM_COST
        global LLM_COST_EXCEEDED

        with LLM_USAGE_LOCK:    # Acquire the lock to make sure we're the only thread reading/writing to the usage information.
            # Step 1: Import the LLM cost information
            try:
                with open(FILENAME_LLM_COST, 'r') as f:
                    llm_cost = json.load(f)
            except FileNotFoundError:
                llm_cost = {}

            # Step 2: Import the LLM usage information
            try:
                with open(FILENAME_LLM_USAGE, 'r') as f:
                    llm_usage_info = json.load(f)
            except FileNotFoundError:
                llm_usage_info = {"metadata": {"total_cost_usd": 0.0, "max_cost_usd": MAX_COST_USD, "llm_cost_exceeded": False, "num_errors": 0, "num_cost_quota_refusals": 0}, "usage": {}}

            llm_usage_metadata = llm_usage_info["metadata"]
            llm_usage = llm_usage_info["usage"]

            # Step 3: Update the LLM usage information
            # Step 3A: First, update the token counts
            if (model_name in llm_usage):
                if (embedding == False):
                    if ("prompt_tokens" not in llm_usage[model_name]):
                        llm_usage[model_name]["prompt_tokens"] = num_tokens_prompt
                    else:
                        llm_usage[model_name]["prompt_tokens"] += num_tokens_prompt

                    if ("completion_tokens" not in llm_usage[model_name]):
                        llm_usage[model_name]["completion_tokens"] = num_tokens_completion
                    else:
                        llm_usage[model_name]["completion_tokens"] += num_tokens_completion

                    if ("number_of_requests" not in llm_usage[model_name]):
                        llm_usage[model_name]["number_of_requests"] = 1
                    else:
                        llm_usage[model_name]["number_of_requests"] += 1
                else:
                    if ("num_embedding_requests" not in llm_usage[model_name]):
                        llm_usage[model_name]["num_embedding_requests"] = num_embeddings
                    else:
                        llm_usage[model_name]["num_embedding_requests"] += num_embeddings

            else:
                if (embedding == False):
                    llm_usage[model_name] = {
                        "prompt_tokens": num_tokens_prompt,
                        "completion_tokens": num_tokens_completion,
                        "number_of_requests": 1,
                        "cost_usd": 0.0
                    }
                else:
                    llm_usage[model_name] = {
                        "embedding_model": True,
                        "num_embedding_requests": num_embeddings,
                        "cost_usd": 0.0
                    }

            # Step 3B: Next, update the total cost
            cost_per_1M_prompt_tokens = 0.0
            cost_per_1M_completion_tokens = 0.0
            if (model_name in llm_cost):
                if ("embedding_model" not in llm_usage[model_name]) or (llm_usage[model_name]["embedding_model"] == False):
                    cost_per_1M_prompt_tokens = llm_cost[model_name]["cost_per_1M_prompt_tokens"]
                    cost_per_1M_completion_tokens = llm_cost[model_name]["cost_per_1M_completion_tokens"]
                    # Calculate the cost for all tokens so far
                    cost_prompt = (float(llm_usage[model_name]["prompt_tokens"]) / 1000000) * cost_per_1M_prompt_tokens
                    cost_completion = (float(llm_usage[model_name]["completion_tokens"]) / 1000000) * cost_per_1M_completion_tokens
                    llm_usage[model_name]["cost_usd"] = round(cost_prompt + cost_completion, 4)
                else:
                    cost_per_1M_tokens = llm_cost[model_name]["cost_per_1M_tokens"]
                    # Calculate the cost for all tokens so far
                    # Just estimate at 8192 tokens per request
                    num_tokens = 8192 * llm_usage[model_name]["num_embedding_requests"]
                    cost_embedding = (float(num_tokens) / 1000000) * cost_per_1M_tokens
                    llm_usage[model_name]["cost_usd"] = round(cost_embedding, 4)

            else:
                if ("embedding_model" not in llm_usage[model_name]) or (llm_usage[model_name]["embedding_model"] == False):
                    # If we don't have cost information for this LLM, use the default (high) cost
                    cost_per_1M_prompt_tokens = DEFAULT_COST_PER_1M_TOKENS
                    cost_per_1M_completion_tokens = DEFAULT_COST_PER_1M_TOKENS
                    # Calculate the cost for all tokens so far
                    cost_prompt = (float(llm_usage[model_name]["prompt_tokens"]) / 1000000) * cost_per_1M_prompt_tokens
                    cost_completion = (float(llm_usage[model_name]["completion_tokens"]) / 1000000) * cost_per_1M_completion_tokens
                    llm_usage[model_name]["cost_usd_estimate"] = round(cost_prompt + cost_completion, 4)  # Note, uses a different key to mark that this is only an estimated cost
                else:
                    # If we don't have cost information for the embedding model, use the default (high) cost
                    cost_per_1M_tokens = DEFAULT_COST_PER_1M_TOKENS_EMBEDDING
                    # Calculate the cost for all tokens so far
                    # Just estimate at 8192 tokens per request
                    num_tokens = 8192 * llm_usage[model_name]["num_embedding_requests"]
                    cost_embedding = (float(num_tokens) / 1000000) * cost_per_1M_tokens
                    llm_usage[model_name]["cost_usd_estimate"] = round(cost_embedding, 4)  # Note, uses a different key to mark that this is only an estimated cost


            # Calculate the total cost
            total_cost = 0.0
            for llm in llm_usage:
                if ("cost_usd" in llm_usage[llm]):
                    total_cost += llm_usage[llm]["cost_usd"]
                if ("cost_usd_estimate" in llm_usage[llm]):
                    total_cost += llm_usage[llm]["cost_usd_estimate"]
            llm_usage_info["metadata"]["total_cost_usd"] = round(total_cost, 4)
            TOTAL_LLM_COST = total_cost

            # Check to see if the limit was met or exceeded
            if (total_cost >= MAX_COST_USD):
                llm_usage_info["metadata"]["llm_cost_exceeded"] = True
                LLM_COST_EXCEEDED = True

            # Count the number of errors
            num_errors = 0
            num_cost_quota_refusals = 0
            for llm in llm_usage:
                if ("num_errors" in llm_usage[llm]):
                    num_errors += llm_usage[llm]["num_errors"]
                if ("num_cost_quota_refusals" in llm_usage[llm]):
                    num_cost_quota_refusals += llm_usage[llm]["num_cost_quota_refusals"]
            llm_usage_info["metadata"]["num_errors"] = num_errors
            llm_usage_info["metadata"]["num_cost_quota_refusals"] = num_cost_quota_refusals


            # Step 4: Save the updated LLM usage information
            with open(FILENAME_LLM_USAGE, 'w') as f:
                packed = {"metadata": llm_usage_metadata, "usage": llm_usage}
                json.dump(packed, f, indent=4)


    # Another method that marks whether specific models have had errors, in the usage information.
    def mark_error(self, model_name, generic_error:bool, exceeded_cost_quota:bool):
        with LLM_USAGE_LOCK:
            # Step 1: Import the LLM usage information
            try:
                with open(FILENAME_LLM_USAGE, 'r') as f:
                    llm_usage_info = json.load(f)
            except FileNotFoundError:
                llm_usage_info = {"metadata": {"total_cost_usd": 0.0, "max_cost_usd": MAX_COST_USD, "llm_cost_exceeded": False}, "usage": {}}

            llm_usage_metadata = llm_usage_info["metadata"]
            llm_usage = llm_usage_info["usage"]

            # Step 2: Mark the error
            if (model_name not in llm_usage):
                llm_usage[model_name] = {
                    "num_errors": 0,
                    "num_cost_quota_refusals": 0
                }
            else:
                if ("num_errors" not in llm_usage[model_name]):
                    llm_usage[model_name]["num_errors"] = 0
                if ("num_cost_quota_refusals" not in llm_usage[model_name]):
                    llm_usage[model_name]["num_cost_quota_refusals"] = 0

            if (generic_error):
                llm_usage[model_name]["num_errors"] += 1
            if (exceeded_cost_quota):
                llm_usage[model_name]["num_cost_quota_refusals"] += 1

            # Count the number of errors
            num_errors = 0
            num_cost_quota_refusals = 0
            for llm in llm_usage:
                if ("num_errors" in llm_usage[llm]):
                    num_errors += llm_usage[llm]["num_errors"]
                if ("num_cost_quota_refusals" in llm_usage[llm]):
                    num_cost_quota_refusals += llm_usage[llm]["num_cost_quota_refusals"]
            llm_usage_info["metadata"]["num_errors"] = num_errors
            llm_usage_info["metadata"]["num_cost_quota_refusals"] = num_cost_quota_refusals

            # Step 3: Save the updated LLM usage information
            with open(FILENAME_LLM_USAGE, 'w') as f:
                packed = {"metadata": llm_usage_metadata, "usage": llm_usage}
                json.dump(packed, f, indent=4)



    def do_POST(self):
        global errors

        print("Received a request: " + self.path)

        #print("Received a request:")
        #print(f"Method: {self.command}")
        #print(f"Path: {self.path}")
        #print("Headers:")
        #for key, value in self.headers.items():
        #    print(f"{key}: {value}")

        # Read and print the request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        print("Body:")
        print(body.decode('utf-8'))

        # Parse the request body as JSON
        try:
            request_data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            print("400: Invalid JSON")
            self.send_error(400, 'Invalid JSON')
            return

        # ERROR CHECKING: Check if the cost limit is exceeded -- if so, return an error.
        cost_exceeded = False
        with LLM_USAGE_LOCK:
            cost_exceeded = LLM_COST_EXCEEDED

        if (cost_exceeded):
            errorStr = "ERROR: Cost limit exceeded ($" + str(round(MAX_COST_USD, 2)) + "). No further requests will be processed."
            print(errorStr)
            errors.append(errorStr)

            # Keep track of these types of errors
            model_name = "unknown"
            if ("model" in request_data):
                model_name = request_data["model"]
            self.mark_error(model_name, generic_error=False, exceeded_cost_quota=True)

            # Prepare the error response
            error_response = {
                'error': {
                    'message': errorStr,
                    'type': 'cost_limit_exceeded',
                    'param': None,
                    'code': None
                }
            }
            response_json = json.dumps(error_response)

            # Send error response
            self.send_response(402)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
            return


        # ERROR CHECKING: Check if the number of errors exceeds the maximum allowed.
        if (len(errors) >= MAX_ERRORS):
            # Prepare the error response
            error_response = {
                'error': {
                    'message': "Too many LLM errors have occurred (" + len(errors) + "), which exceeds the maximum threshold. No further requests will be processed.",
                    'type': 'too_many_errors',
                    'param': None,
                    'code': None
                }
            }
            response_json = json.dumps(error_response)

            # Send error response
            self.send_response(402)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
            return


        # Prepare a response based on the endpoint
        try:
            if self.path == '/chat/completions' or self.path == '/completions':
                # Forward the request to litellm.completion
                response = litellm.completion(**request_data, drop_params=True)

                # Convert the ModelResponse object to a dictionary
                response_data = response.to_dict()

            elif self.path == '/embeddings':
                # Forward the request to litellm.embedding
                response = litellm.embedding(**request_data, drop_params=True)

                # Convert the ModelResponse object to a dictionary
                response_data = response.to_dict()

            else:
                # Default response for other endpoints
                response_data = {'message': 'Endpoint not supported'}

        # Catch BadRequestError and send back an error in OpenAI API error format
        except litellm.BadRequestError as e:
            # Add to the errors
            errorStr = "ERROR: BadRequestError occurred: " + e.message
            print(errorStr)
            errors.append(errorStr)

            # Keep track of these types of errors
            model_name = "unknown"
            if ("model" in request_data):
                model_name = request_data["model"]
            self.mark_error(model_name, generic_error=True, exceeded_cost_quota=False)

            # Prepare the error response
            error_response = {
                'error': {
                    'message': e.message,
                    'type': 'invalid_request',
                    'param': e.param,
                    'code': e.code
                }
            }
            response_json = json.dumps(error_response)

            # Send error response
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
            return


        except Exception as e:
            # Add to the errors
            errorStr = "ERROR: Exception occurred: " + str(e)
            print(errorStr)
            errors.append(errorStr)

            # Keep track of these types of errors
            model_name = "unknown"
            if ("model" in request_data):
                model_name = request_data["model"]
            self.mark_error(model_name, generic_error=True, exceeded_cost_quota=False)

            # Log the exception (optional)
            print(f"Exception occurred: {e}")

            # If an exception occurs, send back an error in OpenAI API error format
            error_response = {
                'error': {
                    'message': 'An internal error occurred.',
                    'type': 'internal_error',
                    'param': None,
                    'code': None
                }
            }
            response_json = json.dumps(error_response)

            # Send error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json.encode('utf-8'))
            return

        # Parse the response for token/costing information.
        if (self.path == '/chat/completions' or self.path == '/completions'):
            num_tokens_prompt = 0
            num_tokens_completion = 0
            if ("usage" in response_data) and ("prompt_tokens" in response_data["usage"]):
                num_tokens_prompt = response_data["usage"]["prompt_tokens"]
            if ("usage" in response_data) and ("completion_tokens" in response_data["usage"]):
                num_tokens_completion = response_data["usage"]["completion_tokens"]

            # If the number of tokens in the prompt and/or completion are zero, this is likely an error -- keep track of these, so we can exit early if something is wrong.
            if (num_tokens_prompt == 0) or (num_tokens_completion == 0):
                errorStr = "WARNING: Number of tokens in prompt or completion is zero. This may indicate an error."
                print(errorStr)
                errors.append(errorStr)

            # Save the token/costing information
            model_name = "unknown"
            if ("model" in request_data):
                model_name = request_data["model"]
            self.save_cost_information(num_tokens_prompt, num_tokens_completion, model_name)

            # Add the cost keys to the response data
            response_data["cost"] = {
                "total_running_cost_usd": TOTAL_LLM_COST,
                "llm_cost_limit_usd": MAX_COST_USD,
                "llm_cost_exceeded": LLM_COST_EXCEEDED
            }

        elif (self.path == '/embeddings'):
            # Save the token/costing information
            model_name = "unknown"
            if ("model" in request_data):
                model_name = request_data["model"]

            # To keep the proxy light, we'll just assume each embedding request is the max tokens (8192).
            num_embeddings = 0
            if ("input" in request_data):
                num_embeddings = len(request_data["input"])

            num_tokens = 8192 * num_embeddings  # TODO: Use actual count

            self.save_cost_information(0, 0, model_name, embedding=True, num_embeddings=num_embeddings)

            # Add the cost keys to the response data
            response_data["cost"] = {
                "total_running_cost_usd": TOTAL_LLM_COST,
                "llm_cost_limit_usd": MAX_COST_USD,
                "llm_cost_exceeded": LLM_COST_EXCEEDED
            }

        # Convert the response data to JSON
        response_json = json.dumps(response_data)

        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json.encode('utf-8'))
        print("200: Response sent.")


# Function to handle graceful shutdown
def signal_handler(sig, frame):
    print("\nShutting down gracefully...")
    httpd.shutdown()  # Stop the server
    print("Server has been stopped.")

# Set up signal handling for SIGINT (Ctrl+C) and SIGTERM (termination)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Start the server in a separate thread to allow for graceful shutdown
with socketserver.ThreadingTCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT}")

    # Run the server in a separate thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.start()

    # Wait for the server thread to complete
    server_thread.join()
