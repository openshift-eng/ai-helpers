#!/usr/bin/env python3
"""
Apply or revert a single mutation in-place.
No file copying - just modify the original file temporarily.
"""

import argparse
import json
import sys
from pathlib import Path


def apply_mutation(mutation: dict, operator_path: Path) -> bool:
    """Apply a mutation to the file."""
    file_path = operator_path / mutation['file']
    line_num = mutation['line']
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if line_num <= len(lines):
            # Replace the specific line
            lines[line_num - 1] = mutation['mutated'] + '\n'
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True
        else:
            print(f"Error: Line {line_num} out of range in {file_path}")
            return False
            
    except Exception as e:
        print(f"Error applying mutation: {e}")
        return False


def revert_mutation(mutation: dict, operator_path: Path) -> bool:
    """Revert a mutation (restore original line)."""
    file_path = operator_path / mutation['file']
    line_num = mutation['line']
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if line_num <= len(lines):
            # Restore original line
            lines[line_num - 1] = mutation['original'] + '\n'
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True
        else:
            print(f"Error: Line {line_num} out of range in {file_path}")
            return False
            
    except Exception as e:
        print(f"Error reverting mutation: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Apply or revert a mutation')
    parser.add_argument('--mutation-json', required=True, help='Path to mutation JSON file')
    parser.add_argument('--operator-path', required=True, help='Path to operator')
    parser.add_argument('--action', choices=['apply', 'revert'], required=True, help='Action to perform')
    
    args = parser.parse_args()
    
    # Load mutation
    with open(args.mutation_json, 'r') as f:
        mutation = json.load(f)
    
    operator_path = Path(args.operator_path).resolve()
    
    if args.action == 'apply':
        success = apply_mutation(mutation, operator_path)
    else:
        success = revert_mutation(mutation, operator_path)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

