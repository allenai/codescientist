# Name: Logger/Debugging
# Description: This is a REQUIRED example of how to use the built-in debugger/logger in the execution environment.
# inclusion_criteria: This codeblock helps you log and debug, and is always useful.
# exclusion_criteria: There are no exclusion criteria for this codeblock -- you must ALWAYS include the logger/debugger codeblock.
# python_version: 3.8
# pip_requirement:

from experiment_common_library import Logger    # Import the logger from the common library

# Create the logger.  THIS SHOULD ALMOST ALWAYS BE GLOBAL, SO IT CAN BE USED THROUGHOUT YOUR CODE.  ALSO, IF MULTIPLE INSTANCES ARE CREATED, THE LOG FILE WILL BE OVERWRITTEN, LOSING INFORMATION.
logger = Logger()

# Example usage (example of writing sample messages to the logger)
def example1():
    # Log a message
    logger.logMessage("info", "This is an informational message.")
    logger.logMessage("warning", "This is a warning message.")
    logger.logMessage("error", "This is an error message.")
    logger.logMessage("debug", "This is a debug message.")

    # Done
    print("Done.")


# Example usage (shows logging errors that were explicitly caught)
def example2():
    sample_data = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": 123,        # Wrong expected type
        "key5": "value5"
    }

    # For every key in the data
    logger.logMessage("info", "Starting to iterate through the dictionary keys.")
    for key in sample_data.keys():
        try:
            # Try to print it in a string
            print("The key (" + key + ") has the value: " + sample_data[key])       # Note, this is a toy example -- this line will fail when the data is not the expected type
        except:
            # If it fails, log the error with an *informative* message that will help you debug the issue
            logger.logMessage("error", "Could not print key: " + key + ", value: " + str(sample_data[key]) + ", because the value was not a string (type: " + str(type(sample_data[key])) + ")")

    logger.logMessage("info", "Finished iterating through the dictionary keys.")

    # Done
    print("Done.")


# Main
if __name__ == "__main__":
    # Log a message
    logger.logMessage("info", "This is an informational message.")
    logger.logMessage("warning", "This is a warning message.")
    logger.logMessage("error", "This is an error message.")
    logger.logMessage("debug", "This is a debug message.")

    # Done
    print("Log written to: " + logger.LOGGER_FILENAME)
    print("Done.")