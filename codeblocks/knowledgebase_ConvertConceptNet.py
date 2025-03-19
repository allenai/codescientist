# DISABLED
# Preprocessing script for converting ConceptNet raw edge dump into a reduced JSON format.
# ConvertConceptNet.py

# The full file
filenameIn = "conceptnet-assertions-5.7.0.csv"
filenameOut = "conceptnet-assertions-5.7.0.reduced.json"


# Step 1: Load the file line-by-line
print("Loading " + filenameIn)
with open(filenameIn, "r") as f:
    lines = f.readlines()

print ("Loaded", len(lines), "lines")
# Filter out any lines that don't contain "/c/en/"
lines = [line for line in lines if "/c/en/" in line]
print ("Filtered to", len(lines), "lines with /c/en/")


# Step 2: Extract each relation
relations = []
for line in lines:
    fields = line.split("\t")
    relation = fields[1]
    nodeStart = fields[2]
    nodeEnd = fields[3]

    # Let's just remove /r/ from the start of the relation, and /c/en/ from the start of the nodes.
    if relation.startswith("/r/"):
        relation = relation[3:]
    if nodeStart.startswith("/c/en/"):
        nodeStart = nodeStart[6:]
    if nodeEnd.startswith("/c/en/"):
        nodeEnd = nodeEnd[6:]

    # Remove anything after a "/n" in the nodes
    #nodeStart = nodeStart.split("/n")[0]
    #nodeEnd = nodeEnd.split("/n")[0]

    # If either node starts with "/c/", skip this line (it means it's not in English)
    #if nodeStart.startswith("/c/") or nodeEnd.startswith("/c/"):
    #    continue
    # If either node starts with a slash, skip this line
    if nodeStart.startswith("/") or nodeEnd.startswith("/"):
        continue


    packed = {
        "subj": nodeStart,
        "relation": relation,
        "obj": nodeEnd
    }
    relations.append(packed)

# Step 3: Write the relations to a new file
import json
print("Writing to " + filenameOut)
with open(filenameOut, "w") as f:
    json.dump(relations, f, indent=2)

# Step 4: Now do it in the form of a look-up table
look_up_table = {}
for relation in relations:
    subjStr = relation["subj"]
    relStr = relation["relation"]
    objStr = relation["obj"]

    if subjStr not in look_up_table:
        look_up_table[subjStr] = []

    look_up_table[subjStr].append([relStr, objStr])
    # Also add an "inverse" lookup
    if objStr not in look_up_table:
        look_up_table[objStr] = []
    look_up_table[objStr].append(["INV_" + relStr, subjStr])

# Before saving, sort all the lists
print ("Sorting...")
for key in look_up_table:
    look_up_table[key] = sorted(look_up_table[key])

filenameOut = "conceptnet-assertions-5.7.0.reduced.lookup.json"
print("Writing to " + filenameOut)
with open(filenameOut, "w") as f:
    json.dump(look_up_table, f, indent=2)