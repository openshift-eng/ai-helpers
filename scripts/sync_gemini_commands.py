#!/usr/bin/env python3
import os
import re
import toml
import yaml

def parse_markdown_command(md_content):
    """
    Parses the Claude command markdown file.
    Returns a dictionary with 'description' and 'prompt' content for Gemini.
    """
    # Split front matter
    parts = md_content.split('---', 2)
    front_matter = {}
    body = md_content
    if len(parts) == 3:
        try:
            front_matter = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            pass
        body = parts[2].strip()

    # Extract sections using simple regex/splitting
    # We expect ## Name, ## Synopsis, ## Description, ## Implementation, ## Arguments
    
    sections = {}
    current_section = None
    lines = body.split('\n')
    buffer = []

    for line in lines:
        match = re.match(r'^##\s+(.+)$', line)
        if match:
            if current_section:
                sections[current_section] = '\n'.join(buffer).strip()
            # Remove trailing colon and convert to lowercase for consistent key names
            current_section = match.group(1).rstrip(':').lower()
            buffer = []
        else:
            if current_section:
                buffer.append(line)
    
    if current_section:
        sections[current_section] = '\n'.join(buffer).strip()

    # Construct Gemini Description
    # Prefer content from '## Description' section, falling back to front-matter
    description_text = sections.get('description', front_matter.get('description', ''))
    
    # Heuristic: Split 'Description' into summary (for TOML description) and examples (for TOML prompt)
    # If "Usage Examples" or "Examples" header exists in description (markdown sub-headers), split there.
    # We use re.IGNORECASE and allow for optional whitespace/newlines around
    usage_split = re.split(r'(\n\s*\*\*Usage Examples\*\*:?|\n\s*\*\*Examples\*\*:?)', description_text, flags=re.IGNORECASE)
    
    toml_description = usage_split[0].strip()
    extra_prompt_context = ""
    if len(usage_split) > 1:
        extra_prompt_context = usage_split[1] + usage_split[2]

    # Construct Gemini Prompt
    # Combine: Implementation + Arguments + Any extra context from Description
    prompt_parts = []
    
    # Add a generic instruction header if not present
    # (The LLM/User might want to customize this, but we provide a sensible default)
    # prompt_parts.append("Execute the following command based on these instructions:")

    if extra_prompt_context:
        prompt_parts.append(extra_prompt_context)

    if 'implementation' in sections:
        prompt_parts.append("## Implementation\n" + sections['implementation'])
    
    if 'return value' in sections:
         prompt_parts.append("## Return Value\n" + sections['return value'])

    if 'arguments' in sections:
        prompt_parts.append("## Arguments:\n" + sections['arguments'])

    prompt_text = '\n\n'.join(prompt_parts)

    # Perform Substitutions (Claude -> Gemini)
    prompt_text = prompt_text.replace("Claude Code", "Gemini CLI")
    prompt_text = prompt_text.replace("Claude agent", "Gemini agent")
    prompt_text = prompt_text.replace("/claude", "/gemini")
    
    # Replace examples like `/jira-solve ... enxebre` with `/jira-solve ... origin`
    prompt_text = prompt_text.replace(" enxebre", " origin")

    return {
        "description": toml_description,
        "prompt": prompt_text
    }

    # -------------------------------------------------------------------------
    # ALTERNATIVE: LLM-BASED CONVERSION (The "Claudeable" approach)
    # If you prefer to use an LLM to generate the TOML (better for nuanced text):
    #
    # prompt_template = f"""
    # You are an expert developer tool configurator.
    # Convert the following Claude Command (Markdown) into a Gemini Command (TOML).
    #
    # Input Markdown:
    # {md_content}
    #
    # Rules:
    # 1. Extract the 'description' from the Front Matter or 'Description' section.
    # 2. Create a 'prompt' field that contains the detailed instructions (Implementation, Arguments, Examples).
    # 3. Replace references to 'Claude' with 'Gemini'.
    # 4. Return ONLY valid TOML content.
    # """
    # 
    # response = call_llm_api(prompt_template) # Implement your API call here (e.g. Anthropic, Google GenAI)
    # return parse_toml_from_response(response)
    # -------------------------------------------------------------------------

def main():
    plugins_dir = "plugins"
    gemini_dir = ".gemini/commands"
    
    if not os.path.exists(plugins_dir):
        print(f"Error: {plugins_dir} not found.")
        return

    for root, dirs, files in os.walk(plugins_dir):
        for file in files:
            if file.endswith(".md"):
                md_path = os.path.join(root, file)
                
                # Determine relative path structure
                # plugins/jira/commands/solve.md -> jira/solve.toml
                rel_path = os.path.relpath(md_path, plugins_dir)
                path_parts = rel_path.split(os.sep)
                
                # We expect plugins/<plugin_name>/commands/<command_name>.md
                if len(path_parts) >= 3 and path_parts[1] == 'commands':
                    plugin_name = path_parts[0]
                    command_name = os.path.splitext(path_parts[-1])[0]
                    
                    dest_dir = os.path.join(gemini_dir, plugin_name)
                    dest_file = os.path.join(dest_dir, f"{command_name}.toml")
                    
                    # Read MD
                    with open(md_path, 'r') as f:
                        md_content = f.read()
                    
                    # Convert
                    data = parse_markdown_command(md_content)
                    
                    # Prepare TOML content
                    toml_content = {
                        "description": data['description'],
                        "prompt": data['prompt']
                    }
                    
                    # Ensure directory exists
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # Write TOML
                    with open(dest_file, 'w') as f:
                        toml.dump(toml_content, f)
                        
                    print(f"Generated {dest_file}")

if __name__ == "__main__":
    main()
