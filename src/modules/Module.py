# ModuleTemplate.py
# A template for creating new modules with the AutoNORA API


class Module:
    # Constructor
    def __init__(self):
        self.MODULE_NAME = "ModuleTemplate"
        self.MODULE_DESC = "A template for creating new modules with the AutoNORA API"
        self.MODULE_VERSION = "0.1"
        self.MODULE_AUTHOR = "Nora"

        # Initialization, module checks
        self.initialized = False
        self.errors = []

        # A list of other modules that this module prefers input from
        self.preferedModules = {
            "input": [],            # Other modules that this module prefers to get input from
            "output": []            # Other modules that this module perfers to provide input for
        }

        # Register actions
        self.actions = {}

        # Action: Loopback
        self.ACTION_LOOPBACK = {
            "name": "loopback",
            "description": "loopback: returns the input data as the output",
            "input_format": "The input is any python dictionary.",
            "output_format": "The output is a copy of the input data."
        }
        self.actions[self.ACTION_LOOPBACK["name"]] = self.ACTION_LOOPBACK

        # Run checks to ensure that the module is properly initialized
        self.initializationChecks()


    # Run checks to ensure that the module is properly initialized
    def initializationChecks(self):
        errors = []
        # Check that the module name, description, version, and author are set
        if (self.MODULE_NAME == None):
            errors.append("The module name (MODULE_NAME) is not set")
        if (self.MODULE_DESC == None):
            errors.append("The module description (MODULE_DESC) is not set")
        if (self.MODULE_VERSION == None):
            errors.append("The module version (MODULE_VERSION) is not set")
        if (self.MODULE_AUTHOR == None):
            errors.append("The module author (MODULE_AUTHOR) is not set")

        # Check that the action names and descriptions are set
        for actionKey in self.actions.keys():
            action = self.actions[actionKey]
            if (action["name"] == None):
                errors.append("The action name is not set for an action (" + str(action) + ")")
            if (action["description"] == None):
                errors.append("The action description is not set for an action (" + str(action) + ")")
            if (action["input_format"] == None):
                errors.append("The action input format is not set for an action (" + str(action) + ")")
            if (action["output_format"] == None):
                errors.append("The action output format is not set for an action (" + str(action) + ")")


        # Set the errors
        self.errors = errors

        # Set the initialized flag
        if (len(errors) == 0):
            self.initialized = True


    # Get a full name for this module (including the version)
    def getModuleFullName(self):
        #return self.MODULE_NAME + "_v" + self.MODULE_VERSION
        return self.MODULE_NAME

    # Get a description of this module
    def getModuleDescription(self, withActions:bool = False):
        if (withActions):
            return {
                "name": self.MODULE_NAME,
                "description": self.MODULE_DESC,
                "version": self.MODULE_VERSION,
                "author": self.MODULE_AUTHOR,
                "actions": self.actions
            }

        else:
            return {
                "name": self.MODULE_NAME,
                "description": self.MODULE_DESC,
                "version": self.MODULE_VERSION,
                "author": self.MODULE_AUTHOR
            }


    # Get a description of the actions available in this module
    def getModuleActions(self):
        return self.actions

    def getModuleActionNames(self):
        return list(self.actions.keys())

    # Check if an action is valid.  If not, return an error message
    def _checkIfValidAction(self, actionName:str, payload:dict):
        # First, try to find the action
        if (actionName in self.getModuleActionNames()):
            # Action found -- return None
            return None
        else:
            # If the action is not found, return an error
            packed = {
                "input": payload["input"],
                "output": None,
                "errors": ["Invalid action: " + actionName + ".  Known actions for this module (" + str(self.getModuleFullName()) + ") are: " + str(self.getModuleActionNames())]
            }
            return packed


    # Run an action in this module
    def runAction(self, actionName:str, payload:dict):
        # Payload is passed with one key
        #   "input": the input data
        # Additional key(s) are added after running:
        #   "output": the output of the module
        #   "errors": a list contianing any errors that occurred

        # Check that the action is valid
        invalidActionCheck = self._checkIfValidAction(actionName, payload)
        if (invalidActionCheck != None):
            return invalidActionCheck

        # Action interpeter: Call the appropriate action
        if actionName == self.ACTION_SUMMARIZE:
            return self.summarize(payload)
        elif actionName == self.ACTION_CAPITALIZE:
            return self.capitalize(payload)
        elif actionName == self.ACTION_CONVERT_TO_LOWER_CASE:
            return self.convertToLowerCase(payload)
        else:
            return {
                "input": payload["input"],
                "errors": ["The requested action (" + actionName + ") has no interpreter available to run it."]
            }



    #
    #   Module Actions
    #

    # Action: Loopback
    #   input: the input data
    #   output: a copy of the input data
    def actionLoopback(self, payload:dict):
        return {
            "input": payload["input"],
            "output": payload["input"],
            "errors": []
        }

    # def action1(self, payload:dict):
    #    ...
    #    return {
    #        "input": payload["input"],
    #        "output": outputData,
    #        "errors": []
    #    }


    #
    #   Tests
    #

    # Returns a dictionary of test results.  Keys are individual actions, and values are boolean (True if the test passed, False if it failed)
    def runTests(self):
        return {"no_tests_defined": False}