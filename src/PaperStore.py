# PaperStore.py
# A storage class for downloading and cleaning Arxiv papers

import os
import re
import json
import requests
import datetime
import argparse
import time
from tqdm import tqdm

import shutil
import magic
import tiktoken
import xml.etree.ElementTree as ET


PATH_PAPERSTORE = "paperstore/"
PATH_SUBPATH_PDF = "pdf/"
PATH_SUBPATH_SOURCE = "source/"
PATH_SUBPATH_SOURCE_CLEANED = "source_cleaned/"
FILENAME_PAPER_INDEX = "paper_index.json"


# TikToken -- Get the nubmer of tokens (as seen by GPT-4) in a string.
tiktokenEncoder = tiktoken.encoding_for_model("gpt-4")
def get_num_tokens(text:str):
    # Tokenize the text
    tokens = tiktokenEncoder.encode(text)
    return len(tokens)


# The main PaperStore storage class
class PaperStore:
    def __init__(self, path=PATH_PAPERSTORE):
        # If the path doesn't exist, create it
        if not os.path.exists(path):
            os.makedirs(path)

        # Load the paper index
        self.paper_index = self.load_paper_index(FILENAME_PAPER_INDEX)


        pass

    # Load the paper index from disk
    def load_paper_index(self, filename:str):
        # Try to load the paper index.  If it doesn't exist, return an empty dictionary
        filename_with_path = PATH_PAPERSTORE + filename
        if (not os.path.exists(filename_with_path)):
            print("PaperStore: load_paper_index(): Paper index not found.  Creating a new one.")
            return {}

        # Load the paper index
        with open(filename_with_path, 'r') as f:
            paper_index = json.load(f)
            print("PaperStore: Loaded index containing " + str(len(paper_index)) + " papers.")

        return paper_index


    # Save the paper index to disk
    def save_paper_index(self, filename:str):
        filename_with_path = PATH_PAPERSTORE + filename
        with open(filename_with_path, 'w') as f:
            json.dump(self.paper_index, f, indent=4)
            print("PaperStore: Saved index containing " + str(len(self.paper_index)) + " papers.")

    # Get all paper topics
    def get_topic_list(self):
        topics = set()
        for paper_id in self.paper_index:
            paper = self.paper_index[paper_id]
            if "topics" in paper:
                for topic in paper["topics"]:
                    topics.add(topic)

        # Convert to (sorted) list
        topics = list(topics)
        topics.sort()
        return topics

    # Get all paper IDs
    def get_paper_ids(self, topic_filter:list=[]):
        if (len(topic_filter) == 0):
            # No topic filter
            return list(self.paper_index.keys())
        else:
            # Filter by topic
            paper_ids = []
            for paper_id in self.paper_index:
                paper = self.paper_index[paper_id]
                if "topics" in paper:
                    for topic in paper["topics"]:
                        if topic in topic_filter:
                            paper_ids.append(paper_id)
                            break
            return paper_ids

    # Get all data for all papers
    def get_paper_index(self, topic_filter:list=[]):
        if (len(topic_filter) == 0):
            # No topic filter
            return self.paper_index
        else:
            # Filter by topic
            paper_index_filtered = {}
            for paper_id in self.paper_index:
                paper = self.paper_index[paper_id]
                if "topics" in paper:
                    for topic in paper["topics"]:
                        if topic in topic_filter:
                            paper_index_filtered[paper_id] = paper
                            break
            return paper_index_filtered

    # Get the source file for one paper, by its arxiv id. Returns a tuple of (success:bool, paper_text:str)
    def get_paper_latex(self, arxiv_id:str):
        # Find the paper record
        if (arxiv_id not in self.paper_index):
            return False, "Paper (" + str(arxiv_id) + ") not found in index."

        paper_record = self.paper_index[arxiv_id]
        # Check for the source link
        source_cleaned_filename = paper_record["source_cleaned_filename"]
        if (source_cleaned_filename == None):
            return False, "No source file found for paper (" + str(arxiv_id) + ")."

        # Read the source file
        try:
            pathSource = PATH_PAPERSTORE + source_cleaned_filename
            with open(pathSource, 'r') as f:
                latex_text = f.read()
            return True, latex_text
        except:
            return False, "Error reading source file for paper (" + str(arxiv_id) + ")."



    # Add a new paper to the index
    def add_arxiv_paper(self, arxiv_id:str, topics:list=[], force=False):
        # Check if the paper is already in the index
        if (arxiv_id in self.paper_index) and (force == False):
            print("PaperStore: Paper " + arxiv_id + " is already in the index.")
            return True, "", {}

        # Get metadata (e.g. title, authors, year) from the Arxiv API
        print("PaperStore: Getting metadata for " + arxiv_id + " ...")
        arxiv_metadata = self.get_arxiv_metadata(arxiv_id)
        if ("error" in arxiv_metadata):
            print("PaperStore: Error getting metadata for " + arxiv_id + ": " + arxiv_metadata["error"])
            return False, "Error: Could not locate metadata for paper on Arxiv."
        print("Metadata for " + arxiv_id + ":")
        print(json.dumps(arxiv_metadata, indent=4))


        # Try to download the paper
        result = self.downloadPDFAndSource(arxiv_id, PATH_PAPERSTORE, force=force)

        # If the download failed, return False
        if (not result["success"]):
            print("PaperStore: Failed to download paper " + arxiv_id)
            errorStr = "Unknown error"
            if ("error" in result):
                errorStr = result["error"]
            return False, errorStr, {}

        # Create a record for this paper
        paper_metadata = {}
        paper_metadata.update(result)

        # Add the metadata from the Arxiv API
        paper_metadata.update(arxiv_metadata)

        # Add a timestamp (current time) for when the paper was added.  YYYY-MM-DD HH:MM:SS
        now = datetime.datetime.now()
        paper_metadata["date_added"] = now.strftime("%Y-%m-%d %H:%M:%S")

        # Add the paper topics
        if (type(topics) == str):
            topics = [topics]
        elif (type(topics) != list):
            print("PaperStore: Invalid topics list.  Must be a list of strings.")
            topics = []
        else:
            paper_metadata["topics"] = topics

        # Add the paper to the index
        self.paper_index[arxiv_id] = paper_metadata

        # Save the updated index
        self.save_paper_index(FILENAME_PAPER_INDEX)

        return True, "", paper_metadata





    #
    #   Helper functions
    #

    # Download a paper (PDF) from a link to either Arxiv, the ACL anthology, or similar.
    # Save it using the uniqueID for the filename (e.g. pdf/author-year-title.pdf)
    def downloadPDFAndSource(self, arxiv_id:str, pathOut:str, force:bool=False):
        # Step 1: Check that the Arxiv ID passes a few quick checks
        if (arxiv_id == None) or (len(arxiv_id) <= 2) or (type(arxiv_id) != str):
            print("ERROR: Invalid Arxiv ID: " + arxiv_id)
            return {"success": False, "error": "Invalid Arxiv ID"}

        # Step 2: Make sure the output paths exist
        pathOutPDF = pathOut + PATH_SUBPATH_PDF
        pathOutSource = pathOut + PATH_SUBPATH_SOURCE
        pathOutSourceCleaned = pathOut + PATH_SUBPATH_SOURCE_CLEANED
        if (not os.path.exists(pathOutPDF)):
            os.makedirs(pathOutPDF)
        if (not os.path.exists(pathOutSource)):
            os.makedirs(pathOutSource)
        if (not os.path.exists(pathOutSourceCleaned)):
            os.makedirs(pathOutSourceCleaned)

        # Step 3: PDF: Try to download the PDF
        # Create a download link
        downloadLink = "https://arxiv.org/pdf/" + arxiv_id + ".pdf"

        # If it's an http://arxiv.org link, then replace it with `export.arxiv.org`, which is intended for crawling
        if ("//arxiv.org" in downloadLink):
            downloadLink = downloadLink.replace("//arxiv.org", "//export.arxiv.org")

        # Download the PDF
        print("Attempting to download " + str(arxiv_id) + " from " + downloadLink + " ...")
        #response = requests.get(downloadLink)
        # As above, but pretend to be a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        filenameOutPDF = pathOutPDF + arxiv_id + ".pdf"
        if (os.path.exists(filenameOutPDF) and not force):
            # If the file already exists, don't try to download it again
            print(" * PDF already exists: " + filenameOutPDF + " . Skipping download.")
        else:
            # File doesn't exist -- download PDF
            response = requests.get(downloadLink, headers=headers)
            if (response.status_code == 200):
                # Save the PDF
                with open(filenameOutPDF, 'wb') as fileOut:
                    fileOut.write(response.content)

                print("Downloaded " + str(arxiv_id) + " to " + filenameOutPDF)
            else:
                print("ERROR: Failed to download " + str(arxiv_id) + " from " + downloadLink + " . Status code: " + str(response.status_code))
                return {"success": False, "error": "Failed to download PDF"}

        # Step 4: Source: Try to download the source (the filenames typically end in .tar.gz)
        #filenameOutSource = pathOutSource + arxiv_id + ".source.tar.gz"
        print("Attempting to download source for " + str(arxiv_id) + " ...")
        # Try to download the source
        # Reformat the URL to get the latex source
        # Arxiv links are of the form: https://arxiv.org/abs/2406.06769
        # Source links are of the form: https://arxiv.org/src/2406.06769
        #if (os.path.exists(filenameOutSource) and not force):
        #    # If the file already exists, don't try to download it again
        #    print(" * Source already exists: " + filenameOutSource + " . Skipping download.")
        #else:
        filenameOutPrefixSource = pathOutSource + arxiv_id
        # File doesn't exist -- download source
        sourceLink = "https://export.arxiv.org/src/" + arxiv_id
        print("Source link: " + sourceLink)
        response = requests.get(sourceLink, headers=headers)
        # Save the source
        # Save the downloaded content with a temporary name
        temp_filename = filenameOutPrefixSource + ".tmp"
        with open(temp_filename, 'wb') as fileOut:
            fileOut.write(response.content)
            print("Downloaded " + str(arxiv_id) + " source to " + temp_filename)

        # Use python-magic to determine the file type
        file_type = magic.from_file(temp_filename, mime=True)
        print(f"Detected file type: {file_type}")

        final_filename_source = None
        # Rename and handle the file based on its detected type
        if file_type == "application/x-gzip":
            final_filename = filenameOutPrefixSource + ".tar.gz"
        elif file_type == "application/x-tar":
            final_filename = filenameOutPrefixSource + ".tar"
        elif file_type == "application/zip":
            final_filename = filenameOutPrefixSource + ".zip"
#            elif file_type.startswith("text/"):
#                final_filename = filenameOutSource + ".txt"
        else:
            final_filename = filenameOutPrefixSource + ".unknown"

        os.rename(temp_filename, final_filename)
        print(f"File saved as {final_filename}")

        if (final_filename.endswith(".unknown")):
            print("ERROR: Unknown file type for source file.  Skipping source download.")
            return {"success": False, "error": "Unknown file type for source file"}


        # Step 4B: Source: Extract the source files to a new directory
        pathSource = pathOutSource + arxiv_id + "/"
        if (not os.path.exists(pathSource)):
            os.makedirs(pathSource)

        # Extract the source files depending on the file type (using command line tools)
        if (file_type == "application/x-gzip"):
            # Extract the tar.gz file
            os.system("tar -xzf " + final_filename + " -C " + pathSource)

        elif (file_type == "application/x-tar"):
            # Extract the tar file
            os.system("tar -xf " + final_filename + " -C " + pathSource)

        elif (file_type == "application/zip"):
            # Extract the zip file
            os.system("unzip " + final_filename + " -d " + pathSource)


        # Step 5: Source: Clean the source files
        # Make a temporary path for the cleaner to do it's work
        pathTemp = pathOut + "/temp-cleaner/"
        # Remove the directory, and any contents, if it exists
        if (os.path.exists(pathTemp)):
            shutil.rmtree(pathTemp, ignore_errors=True)
        # Copy the source files to the temp directory
        shutil.copytree(pathSource, pathTemp)

        # Call the Arxiv latex cleaner on it
        # arxiv_latex_cleaner /path/to/latex --config cleaner_config.yaml
        systemStr = "arxiv_latex_cleaner --config cleaner_config.yaml " + pathTemp
        print("Running " + systemStr)
        ret = os.system(systemStr)
        if (ret != 0):
            print("Error running arxiv_latex_cleaner on " + pathTemp)
            return {"success": False, "error": "Error running arxiv_latex_cleaner"}

        # Convert to a single .tex file
        singleFile = self.convert_to_single_tex_file(pathTemp)
        # Remove everything but the filename from the path
        singleFile = singleFile.replace(pathTemp, "")
        # Add the PATH_SUBPATH_SOURCE_CLEANED to the path
        singleFile = PATH_SUBPATH_SOURCE_CLEANED + str(arxiv_id) + "/" + singleFile

        # Make a new folder in the pathOut directory with the UUID
        pathOutSourceCleaned = pathOut + PATH_SUBPATH_SOURCE_CLEANED + arxiv_id + "/"
        if (os.path.exists(pathOutSourceCleaned)):
            # Remove the existing directory
            shutil.rmtree(pathOutSourceCleaned, ignore_errors=True)

        os.makedirs(pathOutSourceCleaned)

        # Move the contents of the temporary directory to the extracted directory
        filesInTempDir = os.listdir(pathTemp)
        for fileInTempDir in filesInTempDir:
            #shutil.move(tempDir + fileInTempDir, extractedDir)
            # Use command line tools
            # If the file is a .tex file, only move it if it also has "consolidated" in the name
            if ("consolidated" in fileInTempDir) or (".tex" not in fileInTempDir):
                systemStr = "mv " + pathTemp + fileInTempDir + " " + pathOutSourceCleaned
                print("Running " + systemStr)
                ret = os.system(systemStr)


        # Step 6: If we reach here, success!
        # Remove the leading 'paperstore/" from the path

        pdf_filename = filenameOutPDF.replace(PATH_PAPERSTORE, "")
        source_cleaned_filename = singleFile.replace(PATH_PAPERSTORE, "")

        # Get a rough estimate of the number of tokens in the source file
        source_token_count_estimate = None
        try:
            print("Counting tokens in " + pathOut + singleFile)
            with open(pathOut + singleFile, 'r') as f:
                source_text = f.read()
                source_token_count_estimate = get_num_tokens(source_text)
        #except:
        except Exception as e:
            import traceback
            print("Error counting tokens in source file:")
            print(traceback.format_exc())
            print(e)

            pass

        # Packed
        packed = {
            "success": True,
            "arxiv_id": arxiv_id,
            "pdf_filename": pdf_filename,
            "source_cleaned_filename": source_cleaned_filename,
            "source_token_count_estimate": source_token_count_estimate
        }

        return packed


    # Tries to consolodate Latex papers that were distributed across multiple files into a single file.
    def convert_to_single_tex_file(self, pathIn:str):
        # Recursively get a list of all the ".tex" files in the directory
        texFiles = []
        for root, dirs, files in os.walk(pathIn):
            for file in files:
                if file.endswith(".tex"):
                    texFiles.append(os.path.join(root, file))

        # Look through the files for the one that starts with "\documentclass"
        mainFiles = []
        for file in texFiles:
            with open(file, 'r') as f:
                lines = f.readlines()
                if (len(lines) > 0):
                    for line in lines:
                        if ("\\documentclass" in line):
                            mainFiles.append(file)
                            break

        print("Main Files Found: " + str(len(mainFiles)))
        print("Main Files: " + str(mainFiles))

        # For each main file, go through it and add in any input files that it references.
        largestFile = ""
        largestFileSize = 0

        for mainFile in mainFiles:
            with open(mainFile, 'r') as f:
                lines = f.readlines()

                idx = 0
                numFilesAdded = 0
                while (idx < len(lines)):
                #for idx, line in enumerate(lines):
                    line = lines[idx]
                    if ("\\input" in line):
                        # Get the filename
                        filename = re.search(r'\\input{(.+?)}', line).group(1)
                        # Get the full path
                        fullPathLinkedFile = os.path.dirname(mainFile) + "/" + filename
                        if (not fullPathLinkedFile.endswith(".tex")):
                            fullPathLinkedFile += ".tex"
                        # Read the file
                        print("Adding " + fullPathLinkedFile + " to " + mainFile)
                        try:
                            with open(fullPathLinkedFile, 'r') as f2:
                                linesLinkedFile = f2.readlines()
                            # Insert the lines into the main file
                            #lines = lines[:idx] + linesLinkedFile + lines[idx+1:]
                            # As above, but add some "%%%%%%% IMPORTED FROM FILENAME %%%%%%%" lines
                            lines = lines[:idx] + ["% " + lines[idx]] + ["%%%%%%% IMPORTED FROM " + filename + " %%%%%%%\n"] + linesLinkedFile + ["%%%%%%% END IMPORTED FROM " + filename + " %%%%%%%\n"] + lines[idx+1:]
                            # Comment out the \input line
                            #lines[idx] = "% " + lines[idx]
                            numFilesAdded += 1
                        # Keyboard exception
                        except KeyboardInterrupt:
                            exit(1)
                        except:
                            print("Error reading " + fullPathLinkedFile)
                            # Comment out the \input line
                            lines[idx] = "% " + lines[idx]
                            # Add a failure message
                            lines = lines[:idx+1] + ["% ERROR READING " + fullPathLinkedFile] + lines[idx+1:]


                    idx += 1

                print("Added " + str(numFilesAdded) + " files to " + mainFile)

                # Look for a .bbl file with the same name as the main file
                bblFile = mainFile.replace(".tex", ".bbl")
                if (os.path.exists(bblFile)):
                    print("Adding " + bblFile + " to " + mainFile)
                    with open(bblFile, 'r') as f:
                        linesBBL = f.readlines()
                    # Insert the lines into the main file
                    lines = lines + ["\n", "%%%%%%% IMPORTED FROM " + bblFile + " %%%%%%%\n"] + linesBBL + ["%%%%%%% END IMPORTED FROM " + bblFile + " %%%%%%%\n"]

                # If there are 2 or more blank lines in a row, remove all but one
                idx = 0
                while (idx < len(lines)-1):
                    if (lines[idx].strip() == "") and (lines[idx+1].strip() == ""):
                        del lines[idx]
                    else:
                        idx += 1

                # Table Numbering: Go through the paper, and find all the tables.  In the line directly above them, add a comment saying "TABLE X", where X is the table number
                tableNum = 1
                lineIdx = 0
                while (lineIdx < len(lines)):
                    line = lines[lineIdx]
                    if ("begin{table" in line.lower()):
                        lineToAdd = "% TABLE " + str(tableNum) + "\n"
                        lines.insert(lineIdx, lineToAdd)
                        tableNum += 1
                        lineIdx += 1
                    lineIdx += 1

                # Figure Numbering: Go through the paper, and find all the figures.  In the line directly above them, add a comment saying "FIGURE X", where X is the figure number
                figureNum = 1
                lineIdx = 0
                while (lineIdx < len(lines)):
                    line = lines[lineIdx]
                    if ("begin{figure" in line.lower()):
                        lineToAdd = "% FIGURE " + str(figureNum) + "\n"
                        lines.insert(lineIdx, lineToAdd)
                        figureNum += 1
                        lineIdx += 1
                    lineIdx += 1

                # Look for any `\newcommand{` commands
                findReplace = []
                for line in lines:
                    lineSanitized = line.strip()
                    if (lineSanitized.startswith("\\newcommand{")):
                        # Get the command
                        command = re.search(r'\\newcommand{(.+?)}', line).group(1)
                        stringAfterCommand = line[line.find(command) + len(command):].strip()
                        # Get the replacement
                        # Find the first curly brace
                        idx = stringAfterCommand.find("{")
                        # Make sure the last character is a curly brace
                        if (stringAfterCommand[-1] != "}"):
                            #print("ERROR: Missing closing curly brace in line: " + line)
                            continue
                        replacement = stringAfterCommand[idx+1:-1]

                        # Make sure there's not an argument in the replacement
                        if ("#" in replacement):
                            #print("ERROR: Replacement contains an argument in line: " + line)
                            continue

                        # Add to the list
                        findReplace.append({"find": command, "replace": replacement})

                # Do several rounds of find/replace on the 'replace' output, since it may be self-referential
                for i in range(5):
                    for fr in findReplace:
                        for fr2 in findReplace:
                            fr["replace"] = fr["replace"].replace(fr2["find"], fr2["replace"])

                # Then, do find/replace on all the lines in the file
                for fr in findReplace:
                    print("Find: " + fr["find"] + "   Replace: " + fr["replace"])
                    lines = [x.replace(fr["find"], fr["replace"]) for x in lines]

                # Write the lines to the output file
                filenameOut = mainFile.replace(".tex", ".consolidated.tex")
                print("Writing to " + filenameOut)
                with open(filenameOut, 'w') as f:
                    f.writelines(lines)

                # Measure the file's size, in terms of characters
                with open(filenameOut, 'r') as f:
                    lines = f.readlines()
                    numChars = 0
                    for line in lines:
                        numChars += len(line)
                print("File size: " + str(numChars) + " characters")
                if (numChars > largestFileSize):
                    largestFileSize = numChars
                    largestFile = filenameOut


        print("Largest File: " + largestFile)
        print("Largest File Size: " + str(largestFileSize) + " characters")
        return largestFile


    # Get basic metadata (title, authors, year) for a paper from its Arxiv ID
    def get_arxiv_metadata(self, arxiv_id):
        # Base URL for arXiv API
        base_url = "http://export.arxiv.org/api/query"
        # Query parameter for the specific paper ID
        query = f"id_list={arxiv_id}"
        # Make the request
        response = requests.get(f"{base_url}?{query}")

        if response.status_code == 200:
            # Parse XML response
            root = ET.fromstring(response.text)
            entry = root.find("{http://www.w3.org/2005/Atom}entry")
            if entry is not None:
                # Extract metadata
                title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip()
                published = entry.find("{http://www.w3.org/2005/Atom}published").text
                authors = [
                    author.find("{http://www.w3.org/2005/Atom}name").text
                    for author in entry.findall("{http://www.w3.org/2005/Atom}author")
                ]

                # Remove any newlines (e.g. "\n") from the title
                title = title.replace("\n", " ")
                # Condense multiple spaces to a single space
                title = re.sub(r"\s+", " ", title)

                return {
                    "title": title,
                    "year": published[:4],  # Extracting year from published date
                    "authors": authors,
                }
            else:
                return {"error": "No entry found for this paper ID"}
        else:
            return {"error": f"API request failed with status code {response.status_code}"}



# # Test the PaperStore class
# if __name__ == "__main__":
#     paperStore = PaperStore()

#     # Test downloading a paper
#     #arxiv_id = "2406.06769"
#     #result = paperStore.downloadPDFAndSource(arxiv_id, PATH_PAPERSTORE, force=False)
#     #print("Result:")
#     #print(json.dumps(result, indent=4))
#     #paperStore.add_arxiv_paper(arxiv_id, force=True)

# Manually regenerate the paper index by re-downloading all the papers
def main():
    paperStore = PaperStore()
    # Get the entire paper index
    paper_index = paperStore.get_paper_index()
    # Get all the Arxiv IDs
    arxiv_ids = []
    topics_by_id = {}
    for paper_id in paper_index.keys():
        try:
            arxiv_id = paper_index[paper_id]["arxiv_id"]
            topics = paper_index[paper_id]["topics"]
            if (arxiv_id != None):
                arxiv_ids.append(arxiv_id)
                if (topics != None):
                    topics_by_id[arxiv_id] = topics

        except:
            pass


    # List all the papers (and their topics)
    for idx, arxiv_id in enumerate(arxiv_ids):
        topicStr = ""
        if (arxiv_id in topics_by_id):
            topicStr = "   Topics: " + ", ".join(topics_by_id[arxiv_id])
        print("Paper " + str(idx+1) + ": " + arxiv_id + topicStr)
    print("Found " + str(len(arxiv_ids)) + " papers in the index.")

    # Ask the user to confirm (yes/no) if they want to manually regenerate the index by redownloading/reprocessing all the papers
    print("Do you want to regenerate the paper index by redownloading all the papers? This may take a while. (yes/no)")
    user_input = input()
    if (user_input.lower() != "yes"):
        print("Exiting.")
        return

    # Try to re-download all the papers
    num_success = 0
    num_errors = 0
    errorful_paper_ids = []
    for arxiv_id in tqdm(arxiv_ids):
        topics = []
        if (arxiv_id in topics_by_id):
            topics = topics_by_id[arxiv_id]

        success = False
        max_attempts = 5
        for attempt_idx in range(max_attempts):
            try:
                # Rate limit the requests
                time.sleep(1)
                # Attempt to re-download the paper (force overwrite/re-download)
                success, errorStr, _ = paperStore.add_arxiv_paper(arxiv_id, topics=topics, force=True)
                # Check success
                if (not success):
                    print("Error adding paper " + arxiv_id + ": " + errorStr)
                else:
                    success = True

            except Exception as e:
                print("Error adding paper " + arxiv_id + ": " + str(e))

            if (success):
                num_success += 1
                break
            else:
                delay_time = 5 * (attempt_idx + 1)
                print("Retrying... (attempt " + str(attempt_idx+1) + " of " + str(max_attempts) + ", pausing for " + str(delay_time) + " seconds)")
                time.sleep(delay_time)

        if (not success):
            print("Final error adding paper " + arxiv_id + ": " + errorStr)
            print("Was unable to add paper " + arxiv_id + " after " + str(max_attempts) + " attempts.")
            num_errors += 1
            errorful_paper_ids.append(arxiv_id)


        print("Running statistics: " + str(num_success) + " successes, " + str(num_errors) + " errors.")
        if (num_errors > 0):
            print("Paper IDs with errors:")
            print(", ".join(errorful_paper_ids))


    print("Finished regenerating the paper index.")
    print("Errors: " + str(num_errors))
    if (num_errors > 0):
        print("Paper IDs with errors:")
        print(", ".join(errorful_paper_ids))


if __name__ == "__main__":
    main()
