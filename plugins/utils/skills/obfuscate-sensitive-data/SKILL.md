---
name: Obfuscate Sensitive Data
description: "A skill for identifying and obfuscating sensitive information in text data before it is processed or shared."
---

# Skill: Obfuscate Sensitive Data

This skill provides a standardized and secure process for commands to sanitize text data. It uses a local helper script to ensure that sensitive information is never exposed to the LLM.

## When to Use This Skill
Use this skill whenever a command handles data that might contain sensitive information, such as:
- Log files
- Configuration files
- JIRA issue descriptions
- User-provided text inputs

## Implementation Steps

### Step 1: Write Data to a Temporary File
Before processing, write the data that needs to be sanitized into a temporary file. It is recommended to use the `.work` directory, as it is ignored by version control.

**Example**:
```bash
# A command has fetched a JIRA description into a variable
JIRA_DESCRIPTION="..." 

# Save it to a temporary file
TEMP_INPUT_FILE=".work/jira/solve/jira-description-raw.txt"
echo "$JIRA_DESCRIPTION" > $TEMP_INPUT_FILE
```

### Step 2: Invoke the Local Obfuscation Script
Execute the local Python script on the temporary file. This script will read the file, process it, and write the sanitized output to a new file without the LLM ever accessing the content.

**Example**:
```bash
# Execute the local script
python3 plugins/utils/skills/obfuscate-sensitive-data/obfuscate.py .work/jira/solve/jira-description-raw.txt
```
This will create a new file named `.work/jira/solve/jira-description-raw.txt.obfuscated` and print a summary of its actions.

### Step 3: Use the Sanitized Data
After the script has run successfully, your command can now safely use the sanitized file for its next steps.

**Example**:
```bash
# Define the path to the sanitized file
SANITIZED_FILE=".work/jira/solve/jira-description-raw.txt.obfuscated"

# The LLM can now be asked to read and process this safe file
echo "Analyzing the sanitized JIRA description from $SANITIZED_FILE"
```

### Step 4: Clean Up (Optional)
After you are done with the processing, you can remove the temporary files.

**Example**:
```bash
rm .work/jira/solve/jira-description-raw.txt
rm .work/jira/solve/jira-description-raw.txt.obfuscated
```

## Example Integration
For an example of how this skill is integrated into an existing command, see the `Implementation` section of the `/jira:solve` command. It has been updated to use this skill to sanitize JIRA issue descriptions before analysis.
