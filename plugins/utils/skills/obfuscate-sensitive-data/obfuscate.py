import re
import argparse
import sys

def obfuscate_text(text):
    """
    Finds and replaces sensitive information in a block of text.
    Returns the sanitized text and a summary of what was changed.
    """
    # Regex for IPv4 and IPv6
    ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b')
    # Regex for email addresses
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    # Regex for UUIDs
    uuid_pattern = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
    # Regex for MAC addresses
    mac_pattern = re.compile(r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b')
    # Regex for URLs with credentials
    url_creds_pattern = re.compile(r'(https?://)[^:]+:[^@]+@')

    # Find all matches before replacing
    ips_found = len(ip_pattern.findall(text))
    emails_found = len(email_pattern.findall(text))
    uuids_found = len(uuid_pattern.findall(text))
    macs_found = len(mac_pattern.findall(text))
    urls_found = len(url_creds_pattern.findall(text))

    # Replace all found patterns
    text = ip_pattern.sub('[OBFUSCATED_IP]', text)
    text = email_pattern.sub('[OBFUSCATED_EMAIL]', text)
    text = uuid_pattern.sub('[OBFUSCATED_UUID]', text)
    text = mac_pattern.sub('[OBFUSCATED_MAC]', text)
    text = url_creds_pattern.sub(r'\1[OBFUSCATED_USER]:[OBFUSCATED_PWD]@', text)

    summary = {
        "IPs": ips_found,
        "Emails": emails_found,
        "UUIDs": uuids_found,
        "MACs": macs_found,
        "Credentialed URLs": urls_found
    }

    return text, summary

def main():
    parser = argparse.ArgumentParser(description="Obfuscate sensitive data in a file.")
    parser.add_argument("input_file", help="Path to the input file.")
    parser.add_argument("output_file", nargs='?', help="Path to the output file. Defaults to <input_file>.obfuscated.")
    args = parser.parse_args()

    # Determine the output file path
    output_file_path = args.output_file
    if not output_file_path:
        output_file_path = f"{args.input_file}.obfuscated"

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {args.input_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    sanitized_content, summary = obfuscate_text(original_content)

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(sanitized_content)
    except Exception as e:
        print(f"Error writing to output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Print a summary of the results
    print(f"Successfully obfuscated data and saved to {output_file_path}")
    summary_parts = []
    for key, value in summary.items():
        if value > 0:
            summary_parts.append(f"{value} {key}")
    if summary_parts:
        print("Summary of changes: " + ", ".join(summary_parts) + ".")
    else:
        print("No sensitive data was found to obfuscate.")

if __name__ == "__main__":
    main()
