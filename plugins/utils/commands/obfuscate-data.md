---
description: "Obfuscates sensitive data within a file before sharing or analysis."
argument-hint: "<input-file-path> [output-file-path]"
---

## Name
utils:obfuscate-data

## Synopsis
```
/utils:obfuscate-data <input-file-path> [output-file-path]
```

## Description
The `utils:obfuscate-data` command sanitizes a text file by identifying and replacing common types of sensitive information. **This operation is performed by a local script, ensuring that the content of the file is never exposed to the LLM.**

This is particularly useful when you need to share logs, configuration files, or other text-based data with an LLM or a third party, ensuring that private or secret information is not exposed.

The command can detect and obfuscate the following types of data:
- IP Addresses (IPv4 and IPv6)
- Email Addresses
- UUIDs
- MAC Addresses
- Common API keys and secrets patterns
- URLs containing credentials

## Implementation
1.  **Execute Local Script**: The command will execute a Python helper script located at `plugins/utils/skills/obfuscate-sensitive-data/obfuscate.py`. This script runs entirely on your local machine.
    ```bash
    python3 plugins/utils/skills/obfuscate-sensitive-data/obfuscate.py <input-file-path> [output-file-path]
    ```
2.  **Local Processing**: The Python script performs the following actions locally:
    - Reads the content from the specified `<input-file-path>`.
    - Applies a series of regular expressions to find and replace sensitive data.
    - Writes the obfuscated content to the output file.
3.  **Return Summary**: The script will print the path to the new file and a summary of the obfuscation actions. This is the only information that is returned to the LLM.

## Return Value
- **On Success**: A confirmation message from the local script with the path to the newly created obfuscated file and a summary of the changes made.
- **On Failure**: An error message from the local script if the input file cannot be read or the output file cannot be written.

## Examples
1. **Obfuscate a log file and save it to a new file**:
   ```
   /utils:obfuscate-data /path/to/my/app.log /path/to/my/app.sanitized.log
   ```
2. **Obfuscate a file and let the command create the output file automatically**:
   ```
   /utils:obfuscate-data ./debug-logs/latest.log
   ```
   This would create a file named `latest.log.obfuscated` in the `./debug-logs/` directory.

## Arguments
- **$1 – input-file-path**: The full path to the text file that needs to be obfuscated. (required)
- **$2 – output-file-path** *(optional)*: The full path where the obfuscated output file will be saved. If not provided, the output will be saved to `<input-file-path>.obfuscated`.
