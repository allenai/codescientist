# ModuleRunPythonInDocker.py
import os
import traceback
import time
import datetime
import json
import random

import modal
from modal import *
from tqdm import tqdm

from func_timeout import func_timeout, FunctionTimedOut


# Add the parent directory to the path, so that we can import the module
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Module import Module


class ModuleRunPythonInModal(Module):
    #
    #   Constructor
    #
    def __init__(self):
        # Set the name of the module
        self.MODULE_NAME = "ModuleRunPythonInModal"
        self.MODULE_DESC = "A module for running arbitrary Python programs, provided as strings to this module (then run in a Modal container)"
        self.MODULE_VERSION = "0.1"
        self.MODULE_AUTHOR = "Nora"

        # A list of other modules that this module prefers input from
        self.preferedModules = {
            "input": [],            # Other modules that this module prefers to get input from
            "output": []            # Other modules that this module perfers to provide input for
        }

        # Register actions
        self.actions = {}

        # Action: Run Program
        # TODO: UPDATE THIS BELOW
        self.ACTION_RUN_PROGRAM = {
            "name": "run_python_program",
            "description": "creates a docker sandbox, and executes a python program in it, reporting the output/results. Has read access to working memory.",
            "input_format": """The input is a dictionary with three keys: 'python_version', `requirements.txt`, and `code`.
NOTE: The code will have access to the working memory, as long as it uses the import command: `from working_memory import *`. It can also re-import the working memory from the Python program to here by using the command: `saveWorkingMemory()`.
The working memory is available as 5 dictionaries: `hypotheses`, `data`, `observations`, `analyses`, and `conclusions`.
Keys are accessed in the normal way.  For example `print(data["0"])` will print the item from the `data` working memory with key "0".""",
            #"example": {"python_version": "3.12", "requirements.txt": "numpy==1.26.4\nscikit-learn==1.3.2\n", "code": "import numpy\nfrom working_memory import *\nprint(\"hello world\")\nprint(hypotheses[\"0\"])\n" },
            "example": {"python_version": "3.11", "requirements.txt": "numpy==1.26.4\nscikit-learn==1.3.2\n", "code": "import numpy\nfrom working_memory import *\nprint(\"hello world\")\nprint(hypotheses[\"0\"])\nhypotheses[\"2\"]=True\nprint(hypotheses[\"2\"])\nsaveWorkingMemory()\n" },
            "output_format": "The output is a copy of the stdout and stderr after running the program."
        }
        self.actions[self.ACTION_RUN_PROGRAM["name"]] = self.ACTION_RUN_PROGRAM

        # Run checks to ensure that the module is properly initialized
        self.initializationChecks()

        # Run Modal-specific initialization checks
        _errors = self.initializeModal()
        self.errors.extend(_errors)

        # Keep a copy of the working memory, to make available for the Python program.
        self.workingMemory = {}


    # Docker-specific initialization checks
    def initializeModal(self):
        errors = []
        # TODO

        # Return
        return errors



    #
    #   Run an action in this module
    #
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

        # Action: Run Program
        if (actionName == self.ACTION_RUN_PROGRAM["name"]):
            return self.actionRunProgram(payload)
        else:
            return {
                "input": payload["input"],
                "output": None,
                "errors": ["The requested action (" + actionName + ") has no interpreter available to run it."]
            }


    #
    #   Module Actions
    #

    # Check the input data is in the correct format
    def checkInputRunProgram(self, inputDict:dict):
        errors = []
        # Check for the 'python_version' key
        if ('python_version' not in inputDict):
            # Default to Python 3.10
            inputDict['python_version'] = "3.10"

        # Check that the 'python_version' key is a string
        if (type(inputDict['python_version']) != str):
            errors.append("The 'python_version' key is not a string, but rather a " + str(type(inputDict['python_version'])))

        # Check for the 'requirements.txt' key
        if ('requirements.txt' not in inputDict):
            inputDict['requirements.txt'] = ""

        # Check that the 'requirements.txt' key is a string
        if (type(inputDict['requirements.txt']) != str):
            errors.append("The 'requirements.txt' key is not a string, but rather a " + str(type(inputDict['requirements.txt'])))

        # Check for the 'code' key
        if ('code' not in inputDict):
            errors.append("The 'code' key is missing from the input data.")
        else:
            # Check that the 'code' key is a string
            if (type(inputDict['code']) != str):
                errors.append("The 'code' key is not a string, but rather a " + str(type(inputDict['code'])))

        # Check for 'base_path' key
        if ('base_path' not in inputDict):
            inputDict['base_path'] = ""


        return errors

    # Load a logfile
    def loadLogFile(self, logFile:str):
        try:
            with open(logFile, "r") as f:
                return f.read()
        except Exception as e:
            return None #"An error occurred while loading the log file: " + str(e)


    # An example/test of using the Modal Sandboxes
    def runModalSandbox(self, mount_folder:str, pythonVersion="3.10", apt_packages=["git", "wget", "curl"], workingDir:str="/", runscriptName="echo 'Hello, World!'", requirements_file="requirements.txt", OUTPUT_SUBFOLDER = "results", filesToDownload = ["stdout.python.txt", "stderr.python.txt", "stdout.pip.txt", "stderr.pip.txt", "log.json"], timeout_seconds=600, save_folder="to_save/"):
        RETAIN_FOLDER = "retain"

        # Error tracking
        sandboxErrors = []
        failure = False

        # Step 1: Create a new "app" with a unique name
        appNamePrefix = "modal-app-"
        appName = appNamePrefix + time.strftime("%Y%m%d-%H%M%S") + "-" + str(random.randint(10000, 99999))        # Create the app name with the time (in YYYYMMDD-HHMMSS format) and a random 5-digit number
        try:
            print("MODAL DEBUG: Creating app with name: " + str(appName) + " (mount_folder: " + str(mount_folder) + ")")
            app = modal.App.lookup(appName, create_if_missing=True)
        except Exception as e:
            error_str = "An error occurred while creating the Modal app: " + str(e) + "\n" + traceback.format_exc()
            print(error_str)
            sandboxErrors.append(error_str)
            failure = True

        # Step 2: Create a new Volume for the file system
        volumeName = None
        volume = None
        if (not failure):
            print("MODAL DEBUG: Creating volume with name: " + str(volumeName) + " (mount_folder: " + str(mount_folder) + ")")
            try:
                volumeName = "volume-" + appName
                volume = modal.Volume.from_name(volumeName, create_if_missing=True)
                # Upload the files in the mount_folder to the volume
                with volume.batch_upload() as batchUpload:
                    for root, dirs, files in os.walk(mount_folder):
                        for file in files:
                            localPath = os.path.join(root, file)
                            remotePath = os.path.relpath(localPath, mount_folder)
                            batchUpload.put_file(localPath, remotePath)
                    #volume.commit()
            except Exception as e:
                error_str = "An error occurred while creating the Modal volume: " + str(e) + "\n" + traceback.format_exc()
                print(error_str)
                sandboxErrors.append(error_str)
                failure = True

        # Step 3: Create a new image for the sandbox
        image = None
        if (not failure):
            print("MODAL DEBUG: Creating image (App Name: " + str(appName) + ", mount_folder: " + str(mount_folder) + ")")
            try:
                # Requirements file (should be in the mount folder)
                requirements_file = os.path.join(mount_folder, requirements_file)
                # The base image (Ubuntu 22.04 with the requested Python version, and any additional apt packages/pip packages)
                # Check if the requirements file exists
                #if (not os.path.exists(requirements_file)):
                # Build without the requirements file
                image=modal.Image.from_registry("ubuntu:22.04", add_python=pythonVersion).apt_install(apt_packages)
                # NOTE: Always uses the above, then does a manual `pip install -r requirements.txt` in the runscript.  REASON: If there are any errors in the requirements.txt file, then the Image creation will fail (but only throws a generic error).
                #image=modal.Image.from_registry("ubuntu:22.04", add_python=pythonVersion).apt_install(apt_packages).pip_install_from_requirements(requirements_file)

                # Mount the folder.  TODO: Read back the results from the sandbox.
                #mounts = [modal.Mount.from_local_dir(mount_folder, remote_path="/app")]
            except Exception as e:
                error_str = "An error occurred while creating the Modal image: " + str(e) + "\n" + traceback.format_exc()
                print(error_str)
                sandboxErrors.append(error_str)
                failure = True

        # Step 4: Run the sandbox
        sandbox = None
        if (not failure):
            print("MODAL DEBUG: Starting sandbox (App Name: " + str(appName) + ", mount_folder: " + str(mount_folder) + ")")
            print("MODAL: Starting sandbox (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")

            # Define the function to run the sandbox
            def run_sandbox(sandbox, image, volume, app, workingDir, runscriptName, timeout_seconds):
                sandboxErrors_ = []
                failure_ = False
                try:
                    with modal.enable_output():
                        sandbox = modal.Sandbox.create(
                            "bash",
                            "-c",
                            "cd " + workingDir + " && " + runscriptName,
                            image=image,
                            volumes={"/app": volume},
                            timeout=timeout_seconds,
                            app=app
                        )

                        # Wait for the sandbox to finish
                        sandbox.wait()
                        print("MODAL: Sandbox finished without error. (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                        return sandbox, sandboxErrors_, failure_
                # SandboxTimeoutError
                except modal.exception.SandboxTimeoutError as e:
                    print("MODAL: Sandbox timed out after " + str(timeout_seconds) + " seconds. (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                    error_str = "An error occured while running the Modal sandbox: The sandbox reached its maximum specified time limit of " + str(timeout_seconds) + " seconds per run, and has stopped/exited."
                    sandboxErrors_.append(error_str)
                    failure_ = True
                    return sandbox, sandboxErrors_, failure_

                # All over
                except Exception as e:
                    error_str = "An error occurred while running the Modal sandbox: " + str(e) + "\n" + traceback.format_exc()
                    print(error_str)
                    sandboxErrors_.append(error_str)
                    failure_ = True
                    return sandbox, sandboxErrors_, failure_

            # Try to run the above, with a timeout
            try:
                sandbox, sandboxErrors_, failure = func_timeout(timeout_seconds, run_sandbox, args=(sandbox, image, volume, app, workingDir, runscriptName, timeout_seconds + 120))  # + 120 for a 2-minute buffer
                sandboxErrors.extend(sandboxErrors_)
            except FunctionTimedOut:
                error_str = "The Modal sandbox timed out after " + str(timeout_seconds) + " seconds.  Stopping the sandbox. (hard stop)"
                sandboxErrors.append(error_str)
                failure = True
            except Exception as e:
                error_str = "An error occurred while running the Modal sandbox: " + str(e) + "\n" + traceback.format_exc()
                print(error_str)
                sandboxErrors.append(error_str)
                failure = True



        # Wrap all the below in a function with a timeout
        MAX_DOWNLOAD_TIME_SEC = 60*5    # 5 minutes

        def download_sandbox_files(volume, mount_folder:str, OUTPUT_SUBFOLDER:str, filesToDownload:list, save_folder:str):
            sandboxErrors_ = []

            # List all the files in the Volume (and, store their sizes for when we want to download some of them)
            if (volume != None):
                print("MODAL DEBUG: Listing files in the volume (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                try:
                    print("Files in the Volume:")
                    fileSizes = {}
                    for file in volume.iterdir(path="/", recursive=True):
                        print(file)                     # Debug
                        filenameFullPath = file.path
                        fileSize = file.size
                        fileSizes[filenameFullPath] = fileSize

                    # Add any files in the save folder to the list of files to download
                    if (save_folder != ""):
                        # Get the list of files in the save folder
                        for filename in fileSizes.keys():
                            if (filename.startswith(save_folder)):
                                print("Adding file to download: " + filename)
                                filesToDownload.append(filename)

                    # Add any files in the "retain" folder to the list of files to download
                    for filename in fileSizes.keys():
                        if (RETAIN_FOLDER in filename):
                            # Make sure the end of the filename isn't "retain", since it causes errors in the download (makes a file called 'retain', which prevents making the directory)
                            # NOTE: We should likely, more generally, check to see whether the filename is a directory or not, and only download files (not directories)
                            # TODO: Not currently sure how to do the above with Modal.
                            if (not filename.endswith(RETAIN_FOLDER)):
                                print("Adding file to download: " + filename)
                                filesToDownload.append(filename)

                except Exception as e:
                    error_str = "An error occurred while listing the files in the Modal volume: " + str(e) + "\n" + traceback.format_exc()
                    print(error_str)
                    sandboxErrors_.append(error_str)
                    # No failure for this one -- just log the error

            # Remove any duplicates
            filesToDownload = list(set(filesToDownload))

            # Try to read back specific files from the sandbox Volume
            filesDownloaded = []
            fileErrors = []
            # Maximum file size to download is 5MB
            maxFileSize = 5 * 1024 * 1024
            always_download_files = ["log.json", "results.json", "experiment-llm-usage.json", "stdout.python.txt", "stderr.python.txt", "stdout.pip.txt", "stderr.pip.txt"] # The file size limit does not apply to these files
            filesTooBig = []
            startTimeDownload = time.time()
            download_exceeded_max_time = False

            if (volume != None):
                print("MODAL DEBUG: Downloading files from the volume (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                print("Downloading " + str(len(filesToDownload)) + " files from the volume " + str(volumeName) + "...")
                # Manually create the output folder
                try:
                    # Create a /results/ folder in the mount folder
                    os.makedirs(os.path.join(mount_folder, OUTPUT_SUBFOLDER), exist_ok=True)
                    # Also create the 'to_save' folder in the output folder
                    os.makedirs(os.path.join(mount_folder, OUTPUT_SUBFOLDER, save_folder), exist_ok=True)
                    # Also create the 'retain' folder in the output folder
                    os.makedirs(os.path.join(mount_folder, OUTPUT_SUBFOLDER, RETAIN_FOLDER), exist_ok=True)
                except Exception as e:
                    error_str = "An error occurred while creating the output folder: " + str(e)
                    sandboxErrors_.append(error_str)
                    print(error_str)

                for fileToRead in filesToDownload:
                    try:
                        # Write the file to the /results/ folder
                        filenameOut = os.path.join(mount_folder, OUTPUT_SUBFOLDER, fileToRead)
                        print("Retrieving " + fileToRead + " to " + filenameOut)

                        # Get the file size (for the progress bar)
                        totalFileSize = 1
                        if (fileToRead in fileSizes):
                            totalFileSize = fileSizes[fileToRead]

                        is_file_always_download = False
                        for always_download_file in always_download_files:
                            if (fileToRead.lower().endswith(always_download_file.lower())):
                                is_file_always_download = True
                                break
                        if (totalFileSize > maxFileSize):
                            if (not is_file_always_download):
                                print("Skipping " + fileToRead + " because it is too large (" + str(totalFileSize) + " bytes). Maximum size is " + str(maxFileSize) + " bytes.")
                                filesTooBig.append(fileToRead)
                                continue
                            else:
                                print("Downloading " + fileToRead + " even though it exceeds size limitations (" + str(totalFileSize) + " bytes). Maximum size is " + str(maxFileSize) + " bytes.")

                        # Get the remote file path (e.g. /x/y/z/filename.txt). Make the directory if it doesn't exist
                        lastSlashIndex = fileToRead.rfind("/")      # Remove everything past the last "/"
                        if (lastSlashIndex != -1):
                            folder = fileToRead[:lastSlashIndex+1]
                            if (len(folder) > 0):
                                # Make the directory
                                try:
                                    outFolder = os.path.join(mount_folder, OUTPUT_SUBFOLDER, folder)
                                    print("Creating directory: " + str(outFolder))
                                    os.makedirs(outFolder, exist_ok=True)
                                except Exception as e:
                                    error_str = "An error occurred while making the directory: " + str(e)
                                    sandboxErrors_.append(error_str)
                                    print("Error making the directory: " + str(e))

                        # Download the file, chunk by chunk
                        with open(filenameOut, 'wb') as fileOut:
                            print("Downloading " + filenameOut)
                            with tqdm(total=totalFileSize, unit='B', unit_scale=True, unit_divisor=1024, desc=fileToRead) as pbar:
                                for chunk in volume.read_file(fileToRead):
                                    if (time.time() - startTimeDownload > MAX_DOWNLOAD_TIME_SEC):
                                        download_exceeded_max_time = True
                                        break
                                    with open(filenameOut, 'ab') as fileOut:
                                        fileOut.write(chunk)
                                        pbar.update(len(chunk))

                        if (download_exceeded_max_time):
                            print("Download exceeded maximum time of " + str(MAX_DOWNLOAD_TIME_SEC) + " seconds.  Stopping download.")
                            break

                        filesDownloaded.append(fileToRead)

                    except Exception as e:
                        # If there's an error downloading the file for whatever reason, print it
                        error_str = "An error occurred while downloading the file (" + str(fileToRead) + "): " + str(e)
                        sandboxErrors_.append(error_str)
                        fileErrors.append(fileToRead)
                        print(f"Error reading {fileToRead}: {e}")
                        pass

                print(f"Downloaded {len(filesDownloaded)} files from Volume " + str(volumeName))
                print(f"Errors downloading {len(fileErrors)} files.")
                print("MODAL DEBUG: Downloaded " + str(len(filesDownloaded)) + " files from the volume (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
            else:
                print("WARNING: Did not download files from Modal volume (Volume is `None`: No volume to download files from).")

            #volume.commit()

            # Before passing the list of files to the LLM, filter out certain files we don't want the debug agent to know about, that might contain sensitive information (like API keys)
            print("MODAL DEBUG: Filtering out certain files from the list of files to download (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
            try:
                filePrefixesToFilter = ["llm-proxy", "prompt", "__pycache__"]
                #filePrefixesToFilter = []
                for filePrefix in filePrefixesToFilter:
                    print("Filtering out mention of files starting with: `" + filePrefix + "`")
                    filteredFileSizes = {}
                    filteredFilesDownloaded = {}
                    for file in fileSizes:
                        if (not file.lower().startswith(filePrefix.lower())):
                            filteredFileSizes[file] = fileSizes[file]
                        if (not file.lower().startswith(filePrefix.lower())):
                            filteredFilesDownloaded[file] = fileSizes[file]

                    # Replace the fileSizes dictionary with the filtered files
                    fileSizes = filteredFileSizes
                    filesDownloaded = filteredFilesDownloaded
            except Exception as e:
                error_str = "An error occurred while filtering out certain files from the list of files to download: " + str(e)
                sandboxErrors_.append(error_str)
                print(error_str)

            if (download_exceeded_max_time):
                error_str = "The download of files from the Modal volume exceeded the maximum time of " + str(MAX_DOWNLOAD_TIME_SEC) + " seconds.  Stopping download."
                sandboxErrors_.append(error_str)
                print(error_str)
            if (len(filesTooBig) > 0):
                error_str = "The following files were too large to download (exceeded the maximum size of " + str(maxFileSize) + " bytes): " + str(filesTooBig)
                sandboxErrors_.append(error_str)
                print(error_str)

            # TODO: Add return here
            packed_file_info = {
                "filesDownloaded": filesDownloaded,
                "fileErrors": fileErrors,
                "filesTooBig": filesTooBig,
                "download_exceeded_max_time": download_exceeded_max_time,
                "files_and_sizes": fileSizes
            }
            return packed_file_info, sandboxErrors_

        # Try to run the above, with a timeout
        fileErrors = []
        filesDownloaded = {}    # Super hacky -- starts as a [] but should return as a {} above
        filesTooBig = []
        fileSizes = {}
        download_exceeded_max_time = False
        try:
            file_info, sandboxErrors_ = func_timeout(MAX_DOWNLOAD_TIME_SEC, download_sandbox_files, args=(volume, mount_folder, OUTPUT_SUBFOLDER, filesToDownload, save_folder))
            fileErrors = file_info["fileErrors"]
            filesDownloaded = file_info["filesDownloaded"]
            filesTooBig = file_info["filesTooBig"]
            download_exceeded_max_time = file_info["download_exceeded_max_time"]
            fileSizes = file_info["files_and_sizes"]
            sandboxErrors.extend(sandboxErrors_)
        except FunctionTimedOut:
            error_str = "The download of files from the Modal volume exceeded the maximum time of " + str(MAX_DOWNLOAD_TIME_SEC) + " seconds.  Stopping download."
            sandboxErrors.append(error_str)
            print(error_str)
        except Exception as e:
            error_str = "An error occurred while downloading files from the Modal volume: " + str(e) + "\n" + traceback.format_exc()
            print(error_str)
            sandboxErrors.append(error_str)


        # Try to get the modal stdout/stderr/return code
        def sandbox_get_info(sandbox):
            sandboxErrors_ = []
            sandbox_stdout = None
            sandbox_stderr = None
            sandbox_returncode = None
            try:
                sandbox_stdout = sandbox.stdout.read()
            except Exception as e:
                error_str = "An error occurred while reading the sandbox stdout: " + str(e)
                sandboxErrors_.append(error_str)
                print(error_str)
                sandbox_stdout = error_str

            try:
                sandbox_stderr = sandbox.stderr.read()
            except Exception as e:
                error_str = "An error occurred while reading the sandbox stderr: " + str(e)
                sandboxErrors_.append(error_str)
                print(error_str)
                sandbox_stderr = error_str

            try:
                sandbox_returncode = sandbox.returncode
            except Exception as e:
                error_str = "An error occurred while reading the sandbox return code: " + str(e)
                sandboxErrors_.append(error_str)
                print(error_str)
                sandbox_returncode = error_str

            # Pack
            packed_sandbox_info = {
                "stdout": sandbox_stdout,
                "stderr": sandbox_stderr,
                "return_code": sandbox_returncode
            }

            return packed_sandbox_info, sandboxErrors_

        # Try to run the above, with a timeout
        MAX_STDOUT_READ_TIME_SEC = 60
        sandbox_info = {}
        sandbox_stdout = None
        sandbox_stderr = None
        sandbox_returncode = None
        try:
            sandbox_info, sandboxErrors_ = func_timeout(MAX_STDOUT_READ_TIME_SEC, sandbox_get_info, args=(sandbox,))
            sandboxErrors.extend(sandboxErrors_)
            sandbox_stdout = sandbox_info["stdout"]
            sandbox_stderr = sandbox_info["stderr"]
            sandbox_returncode = sandbox_info["return_code"]
        except FunctionTimedOut:
            error_str = "The retrieval of the Modal sandbox information (stdout, stderr, return code) exceeded the maximum time of " + str(MAX_STDOUT_READ_TIME_SEC) + " seconds.  Stopping retrieval."
            sandboxErrors.append(error_str)
            print(error_str)
            sandbox_stdout = error_str
            sandbox_stderr = error_str
            sandbox_returncode = None

        # Try to load any files in the 'RETAIN' folder, that should be retained across container runs.
        def get_retain_files(filesDownloaded):
            # Look for any keys that include RETAIN_FOLDER and end with ".json"
            retain_files = {}
            for file in filesDownloaded:
                if (RETAIN_FOLDER in file and file.lower().endswith(".json")):
                    try:
                        filenameToRead = os.path.join(mount_folder, OUTPUT_SUBFOLDER, file)
                        with open(filenameToRead, "r") as f:
                            retain_files[file] = json.load(f)
                    except Exception as e:
                        error_str = "An error occurred while attempting to load the retained file: " + str(e)
                        sandboxErrors.append(error_str)
                        print(error_str)

            return retain_files

        # Try to run the above, with a timeout
        MAX_RETAIN_FILES_TIME_SEC = 60
        retain_files = {}
        try:
            retain_files = func_timeout(MAX_RETAIN_FILES_TIME_SEC, get_retain_files, args=(filesDownloaded,))
        except FunctionTimedOut:
            error_str = "The retrieval of the retained files exceeded the maximum time of " + str(MAX_RETAIN_FILES_TIME_SEC) + " seconds.  Stopping retrieval."
            sandboxErrors.append(error_str)
            print(error_str)


        # Pack the output
        packedOut = {}
        print("MODAL DEBUG: Packing the output (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
        try:
            packedOut["stdout"] = sandbox_stdout             # NOTE: These are read from the versions piped to the local files anyway, so no need to read them here.
            packedOut["stderr"] = sandbox_stderr
            packedOut["return_code"] = sandbox_returncode
            packedOut["filesDownloaded"] = filesDownloaded
            packedOut["fileErrors"] = fileErrors
            packedOut["filesTooBig"] = filesTooBig
            packedOut["download_exceeded_max_time"] = download_exceeded_max_time
            packedOut["files_and_sizes"] = fileSizes
            packedOut["retain_files"] = retain_files
            packedOut["sandbox_errors"] = sandboxErrors
        except Exception as e:
            error_str = "An error occurred while packing the Modal output: " + str(e) + "\n" + traceback.format_exc()
            print(error_str)
            sandboxErrors.append(error_str)


        # Delete the sandbox app
        def delete_sandbox_app(appName):
            sandboxErrors_ = []
            try:
                print("MODAL DEBUG: Stopping the app (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                cmd = "modal app stop " + appName
                os.system(cmd)
            except Exception as e:
                error_str = "An error occurred while deleting the Modal app: " + str(e) + "\n" + traceback.format_exc()
                print(error_str)
                sandboxErrors_.append(error_str)
            return sandboxErrors_

        # Try to run the above, with a timeout
        MAX_DELETE_APP_TIME_SEC = 60
        try:
            sandboxErrors_ = func_timeout(MAX_DELETE_APP_TIME_SEC, delete_sandbox_app, args=(appName,))
            sandboxErrors.extend(sandboxErrors_)
        except FunctionTimedOut:
            error_str = "The deletion of the Modal app exceeded the maximum time of " + str(MAX_DELETE_APP_TIME_SEC) + " seconds.  Stopping deletion."
            sandboxErrors.append(error_str)
            print(error_str)

        # Delete the volume
        def delete_sandbox_volume(volumeName):
            sandboxErrors_ = []
            try:
                print("MODAL DEBUG: Deleting the volume (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
                modal.Volume.delete(volumeName)
            except Exception as e:
                error_str = "An error occurred while deleting the Modal volume: " + str(e) + "\n" + traceback.format_exc()
                print(error_str)
                sandboxErrors_.append(error_str)
            return sandboxErrors_

        # Try to run the above, with a timeout
        MAX_DELETE_VOLUME_TIME_SEC = 60
        try:
            sandboxErrors_ = func_timeout(MAX_DELETE_VOLUME_TIME_SEC, delete_sandbox_volume, args=(volumeName,))
            sandboxErrors.extend(sandboxErrors_)
        except FunctionTimedOut:
            error_str = "The deletion of the Modal volume exceeded the maximum time of " + str(MAX_DELETE_VOLUME_TIME_SEC) + " seconds.  Stopping deletion."
            sandboxErrors.append(error_str)
            print(error_str)


        # Update the sandbox errors (if any)
        packedOut["sandbox_errors"] = sandboxErrors

        # Return
        print("MODAL DEBUG: runModalSandbox() completed (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
        return packedOut


    # Action: Run Program
    def actionRunProgram(self, payload:dict):
        errors = []
        other_errors = []

        # Input data:
        #   "python_version": "3.12",
        #   "requirements.txt": "numpy==1.26.4\nscikit-learn==1.3.2\n",
        #   "code": "print(\"hello world\")",

        # Get the input data
        inputData = payload["input"]
        # Check the input data
        errors = self.checkInputRunProgram(inputData)

        # If errors, append usage and exit
        if (len(errors) > 0):
            errors.append("USAGE: " + str(self.actions[self.ACTION_RUN_PROGRAM["name"]]))
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # Step 1: Output directory: Create an output directory for this job
        # Get the base path
        basePath = inputData["base_path"]
        dateTimeStr = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # folderOut = "scratch/" + self.MODULE_NAME + "/docker-python-" + dateTimeStr       # OLD
        folderOut = basePath + "/modal-python-" + dateTimeStr
        # Make the output directory
        try:
            os.makedirs(folderOut)
        except FileExistsError:
            pass
        # Catch all other errors
        except Exception as e:
            errors.append("An error occurred while creating the output directory: " + str(e) + "\n" + traceback.format_exc())
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # Step 2: Write the requirements.txt file
        requirementsFile = folderOut + "/requirements.txt"
        try:
            with open(requirementsFile, "w") as f:
                f.write(inputData["requirements.txt"])
        except Exception as e:
            errors.append("An error occurred while writing the requirements.txt file: " + str(e) + "\n" + traceback.format_exc())
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # Step 2A: Write any supporting files
        if ("supporting_files" not in inputData):
            inputData["supporting_files"] = []

        supportingFiles = inputData["supporting_files"]
        for supportingFile in supportingFiles:
            supportingFilename = folderOut + "/" + supportingFile["filename"]
            # Get any sub-directories, e.g. for `/x/y/z/filename.txt`, create the `/x/y/z` path
            supportingDir = os.path.dirname(supportingFilename)
            try:
                os.makedirs(supportingDir)
            except FileExistsError:
                pass
            # Catch all other errors
            except Exception as e:
                errors.append("An error occurred while creating the supporting file directory (" + supportingDir + "): " + str(e) + "\n" + traceback.format_exc())
                return {
                    "input": inputData,
                    "output": None,
                    "errors": errors
                }

            # Write the file
            supportingFileContents = supportingFile["contents"]
            try:
                with open(supportingFilename, "w") as f:
                    f.write(supportingFileContents)
            except Exception as e:
                errors.append("An error occurred while writing the supporting file (" + supportingFilename + "): " + str(e) + "\n" + traceback.format_exc())
                return {
                    "input": inputData,
                    "output": None,
                    "errors": errors
                }


        # Step 3: Write the code as 'main.py'
        codeFile = folderOut + "/main.py"
        try:
            with open(codeFile, "w") as f:
                f.write(inputData["code"])
        except Exception as e:
            errors.append("An error occurred while writing the code file: " + str(e) + "\n" + traceback.format_exc())
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # Step 4: Add the runscript
        # Make a random name for the environment
        envName = "expenv" + str(random.randint(10000, 999999999999))
        runScriptFile = folderOut + "/run.sh"
        runScript = """#!/bin/bash

# Create the conda environment
conda create -y -n """ + envName + """ python=""" + str(inputData["python_version"]) + """

# Activate the conda environment
source activate """ + envName + """

# Make a directory for any files to be saved
mkdir to_save

# Make a directory for any datasets to be retained
mkdir retain

# Install any dependencies using pip or conda install
# Ignore the warning about installing as root
export PIP_ROOT_USER_ACTION=ignore
# Redirect stdout to stdout.pip.txt and stderr to stderr.pip.txt
pip install -r requirements.txt >stdout.pip.txt 2>stderr.pip.txt

# Run the LLM proxy in the background, but save it's output to a file
# Required for the LLM proxy
pip install litellm
cd llm-proxy
# Uses the -u option to immediately write to the logfiles, and the & to run in the background
#python -u llm-proxy-server.py >stdout.llm-proxy.txt 2>stderr.llm-proxy.txt &
python -u llm-proxy-server.py >stdout.llm-proxy.txt 2>stderr.llm-proxy.txt &
LLM_PROXY_PID=$!  # Capture the process ID of llm-proxy-server.py

# Wait for the LLM proxy to start up
sleep 5
cd ..

# Run the python script
# Redirect stdout to stdout.python.txt and stderr to stderr.python.txt
python main.py >stdout.python.txt 2>stderr.python.txt

# Wait for any log files to be written
sleep 3

# Kill the LLM proxy process
echo "Stopping llm-proxy-server.py (PID: $LLM_PROXY_PID)..."
kill $LLM_PROXY_PID

# Optional: Ensure the process is really terminated
sleep 2
if ps -p $LLM_PROXY_PID > /dev/null; then
    echo "Force killing llm-proxy-server.py..."
    kill -9 $LLM_PROXY_PID
fi

echo "Script completed."
        """
        try:
            # Export the runscript
            with open(runScriptFile, "w") as f:
                f.write(runScript)
            # Change its permission to be executable
            os.chmod(runScriptFile, 0o755)

        except Exception as e:
            errors.append("An error occurred while writing the runscript file: " + str(e) + "\n" + traceback.format_exc())
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # If any errors, stop here, report them, and return
        if (len(errors) > 0):
            return {
                "input": inputData,
                "output": None,
                "errors": errors
            }

        # Step 5: If we reach here, the code has been exported successfully -- run now it in the docker container
        # Step 5A: Get the maximum runtime in seconds from the payload (`max_runtime_seconds`)
        max_runtime_seconds = 600       # Default of 10 minutes
        if ("max_runtime_seconds" in inputData) and (type(inputData["max_runtime_seconds"]) == int):
            max_runtime_seconds = inputData["max_runtime_seconds"]
            if (max_runtime_seconds < 1):
                max_runtime_seconds = 1

        # Step 5B: Get the list of packages that should be installed by 'apt' in the container
        apt_packages = ["git", "wget", "curl", "openjdk-17-jre"]    # Default packages
        if ("apt_packages" in inputData) and (type(inputData["apt_packages"]) == list):
            apt_packages = inputData["apt_packages"]


        # Run the container
        MODAL_OUTPUT_SUBFOLDER = "modal-output"
        print("Running the Modal container... this may take some time (output is supressed to log files, in the output directory: " + folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + ")")
        startTime = time.time()
        result = None
        modal_container_completed = False
        try:
            # container = self.dockerClient.containers.run(
            #     DOCKER_PYTHON_SANDBOX_IMAGE_NAME,
            #     volumes=volumes,
            #     detach=False,           # Don't detach -- wait for the execution to finish
            #     auto_remove=True        # Auto-remove the container when it finishes (since anything we need should be saved in the shared mount directory)
            # )

            # Run the container

            result = self.runModalSandbox(mount_folder = folderOut,
                                pythonVersion="3.10",
                                #apt_packages=["git", "wget", "curl", "openjdk-17-jre"],
                                apt_packages=apt_packages,
                                workingDir="/app",
                                runscriptName="./run.sh",
                                requirements_file="requirements.txt",
                                OUTPUT_SUBFOLDER = MODAL_OUTPUT_SUBFOLDER,
                                filesToDownload = ["stdout.python.txt", "stderr.python.txt", "stdout.pip.txt", "stderr.pip.txt", "llm-proxy/stdout.llm-proxy.txt", "llm-proxy/stderr.llm-proxy.txt", "llm-proxy/experiment-llm-usage.json", "log.json", "results.json"],
                                timeout_seconds=max_runtime_seconds)

            print("Modal container finished.")
            modal_container_completed = True
# print(result)

        except Exception as e:
            #print("MODAL DEBUG: runModalSandbox() completed (App Name: " + str(appName) + ", Volume Name: " + str(volumeName) + ")")
            print("MODAL DEBUG: An error occurred while running the Modal container (Mount Folder: " + str(folderOut) + "): " + str(e))

            errorStr = "An error occurred while running the Modal container: " + str(e) + "\n" + traceback.format_exc()
            print(errorStr)
            #errors.append(errorStr)
            other_errors.append(errorStr)       # Need some record of this error, that will pass through to the output.
            # Also, since these are a special kind of error, append to a file called 'modal-errors.txt'
            print ("Modal error -- writing to modal-errors.txt")
            with open("modal-errors.txt", "a") as f:
                # Write the timestamp
                f.write("\n\n-----\n" + str(datetime.datetime.now()) + "\n")
                # Write the error
                f.write(errorStr + "\n")

# Errors here should not return -- if there's an error in the Python program, it can cause an error in the container, so we want to continue to report the stdout, stderr, etc.
#            return {
#                "input": inputData,
#                "output": None,
#                "errors": errors
#            }
        deltaTimeSeconds = round(time.time() - startTime, 1)

        # Also try to re-import the log file, if it exists (log.json, in the output directory)
        log = None
        try:
            with open(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/log.json", "r") as f:
                log = json.load(f)
        except Exception as e:
            pass

        # Step 6: Pack the output
        return_code = None
        if (result != None):
            if ("return_code" in result):
                return_code = result["return_code"]
            else:
                other_errors.append("No return code was returned from the Modal container used to run this experiment.")

        if (result == None):
            other_errors.append("No result was returned from the Docker container used to run this experiment.")

        # Add the 'sandbox_errors' to the 'other_errors'
        sandbox_errors = []
        if ("sandbox_errors" in result) and (type(result["sandbox_errors"]) == list):
            other_errors.extend(result["sandbox_errors"])
            sandbox_errors = result["sandbox_errors"]

        files_downloaded = []
        files_errors = []
        files_and_sizes = []
        files_too_big = []
        retain_files = {}
        if (result != None):
            files_downloaded = result.get("filesDownloaded", [])
            files_errors = result.get("fileErrors", [])
            files_and_sizes = result.get("files_and_sizes", [])
            files_too_big = result.get("filesTooBig", [])
            retain_files = result.get("retain_files", {})

        # Try to load the 'results.json' file
        resultsJson = None
        try:
            with open(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/results.json", "r") as f:
                resultsJson = json.load(f)
        except Exception as e:
            pass

        # Load the LLM proxy usage
        llm_proxy_usage = None
        try:
            with open(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/llm-proxy/experiment-llm-usage.json", "r") as f:
                llm_proxy_usage = json.load(f)
        except Exception as e:
            pass

        print("MODAL DEBUG: At packing output")
        output = {
            "pip.stdout": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stdout.pip.txt"),
            "pip.stderr": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stderr.pip.txt"),
            "python.stdout": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stdout.python.txt"),
            "python.stderr": self.loadLogFile(folderOut + "/" + MODAL_OUTPUT_SUBFOLDER + "/stderr.python.txt"),
            "log": log,
            "results_json": resultsJson,
            "llm_proxy_usage": llm_proxy_usage,
            "files_downloaded": files_downloaded,
            "files_errors": files_errors,
            "files_and_sizes": files_and_sizes,
            "files_too_big": files_too_big,
            "retain_files": retain_files,
            "file_path": folderOut + "/" + MODAL_OUTPUT_SUBFOLDER,
            "return_code": return_code,
            "other_errors": other_errors,
            "sandbox_errors": sandbox_errors,
            "modal_container_completed": modal_container_completed,
            "statistics": {
                "runtime_seconds": deltaTimeSeconds
            }
        }


        # Step 7: Remove the output directory
        # TODO
        print("MODAL DEBUG: Finished RunActionProgram() (" + str(folderOut))
        # Return
        return {
            "input": inputData,
            "output": output,
            "errors": errors
        }


    #
    #   Tests
    #

    def runTestRunPythonInModal(self):
        # Faux payload
        payload = {
            "input": {
                "python_version": "3.12",
                "requirements.txt": "numpy==1.26.4\nscikit-learn==1.3.2\n",
                "code": "import numpy\nprint(\"hello world\")",
            }
        }

        # Run the action
        result = self.runAction(self.ACTION_RUN_PROGRAM["name"], payload)

        print("runTestRunPythonInDocker result:")
        print(json.dumps(result, indent=4))

        # Check the result
        if (result["output"] == None):
            return False
        if (len(result["errors"]) > 0):
            return False
        if ("return_code" not in result["output"]):
            return False
        if (result["output"]["return_code"] != 0):
            return False

        # Otherwise, assume OK
        return True


    def runTests(self):
        # Run the tests
        testResults = {}

        # Test 1: Run the LLM inference on TogetherAI
        testResults[self.ACTION_RUN_PROGRAM["name"]] = self.runTestRunPythonInModal()

        return testResults



# Standalone entry point for testing this module independently
if __name__ == "__main__":

    # Instantiate the module
    module = ModuleRunPythonInModal()
    # Run the tests
    result = module.runTests()
    print("\n\n" + "-" * 80 + "\n\n")
    print(result)