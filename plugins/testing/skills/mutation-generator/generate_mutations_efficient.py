#!/usr/bin/env python3
"""
Efficient Mutation Generator for Kubernetes Operators

Generates mutation metadata WITHOUT copying the repository.
Mutations are applied in-place during testing, then reverted.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


class EfficientMutationGenerator:
    """Generates mutation metadata without creating copies."""
    
    CONDITIONAL_OPS = {
        '==': ['!='],
        '!=': ['=='],
        '<': ['>'],
        '>': ['<'],
        '<=': ['>'],
        '>=': ['<'],
        '&&': ['||'],
        '||': ['&&'],
    }
    
    K8S_ERROR_TYPES = [
        'IsNotFound',
        'IsAlreadyExists',
        'IsConflict',
        'IsInvalid',
    ]
    
    def __init__(self, operator_path: str, mutation_types: List[str]):
        self.operator_path = Path(operator_path).resolve()
        self.mutation_types = mutation_types
        self.mutant_counter = 0
        self.mutations = []
        
    def generate(self) -> Dict[str, Any]:
        """Generate mutation metadata only (no file copies)."""
        print(f"🔍 Scanning operator at: {self.operator_path}")
        
        controller_files = self._find_controller_files()
        print(f"📄 Found {len(controller_files)} controller files")
        
        for controller_file in controller_files:
            rel_path = controller_file.relative_to(self.operator_path)
            print(f"   Analyzing: {rel_path}")
            self._generate_mutations_for_file(controller_file)
        
        summary = self._generate_summary()
        print(f"✓ Generated {len(self.mutations)} mutation definitions")
        
        return summary
    
    def _find_controller_files(self) -> List[Path]:
        """Find all controller files."""
        controller_files = []
        patterns = [
            '**/controllers/*controller*.go',
            '**/controllers/*reconciler*.go',
            '**/pkg/controller/**/*controller*.go',
            '**/pkg/controller/**/*reconciler*.go',
        ]
        
        for pattern in patterns:
            for file_path in self.operator_path.glob(pattern):
                if '_test.go' not in str(file_path) and file_path.is_file():
                    controller_files.append(file_path)
        
        return list(set(controller_files))
    
    def _generate_mutations_for_file(self, file_path: Path):
        """Generate mutations for a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"   ⚠️  Skipping {file_path.name}: {e}")
            return
        
        # Apply mutation types
        if 'conditionals' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_conditionals(file_path, lines)
        
        if 'error-handling' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_error_handling(file_path, lines)
        
        if 'returns' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_returns(file_path, lines)
        
        if 'requeue' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_requeue(file_path, lines)
        
        if 'status' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_status(file_path, lines)
        
        if 'api-calls' in self.mutation_types or 'all' in self.mutation_types:
            self._mutate_api_calls(file_path, lines)
    
    def _mutate_conditionals(self, file_path: Path, lines: List[str]):
        """Generate conditional mutations."""
        for line_num, line in enumerate(lines, 1):
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
            
            for old_op, new_ops in self.CONDITIONAL_OPS.items():
                # Need word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(old_op) + r'\b'
                if re.search(pattern, line) and ('if ' in line or 'for ' in line):
                    for new_op in new_ops:
                        mutated = re.sub(pattern, new_op, line, count=1)
                        self._add_mutation(
                            file_path=file_path,
                            line_num=line_num,
                            original_line=line,
                            mutated_line=mutated,
                            mutation_type='conditional',
                            description=f'Change {old_op} to {new_op}',
                            pattern='comparison-operator'
                        )
                        break  # Only one mutation per line
    
    def _mutate_error_handling(self, file_path: Path, lines: List[str]):
        """Generate error handling mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Pattern 1: if err != nil { return ... }
            if 'if err != nil' in stripped:
                # Comment out the error check
                indent = len(line) - len(line.lstrip())
                mutated = ' ' * indent + '// MUTANT: Removed error check - ' + stripped + '\n'
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='error-handling',
                    description='Remove error check',
                    pattern='remove-error-check'
                )
            
            # Pattern 2: K8s error types
            for error_type in self.K8S_ERROR_TYPES:
                if error_type in stripped:
                    for alt_type in self.K8S_ERROR_TYPES:
                        if alt_type != error_type:
                            mutated = line.replace(error_type, alt_type, 1)
                            self._add_mutation(
                                file_path=file_path,
                                line_num=line_num,
                                original_line=line,
                                mutated_line=mutated,
                                mutation_type='error-handling',
                                description=f'Change {error_type} to {alt_type}',
                                pattern='k8s-error-type'
                            )
                            break
                    break
    
    def _mutate_returns(self, file_path: Path, lines: List[str]):
        """Generate return mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if 'return' in stripped and 'ctrl.Result' in stripped and ', err' in stripped:
                mutated = line.replace(', err', ', nil', 1)
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='returns',
                    description='Return nil instead of error',
                    pattern='error-return-nil'
                )
    
    def _mutate_requeue(self, file_path: Path, lines: List[str]):
        """Generate requeue mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if 'return ctrl.Result{}' in stripped and 'Requeue' not in stripped:
                mutated = line.replace('ctrl.Result{}', 'ctrl.Result{Requeue: true}', 1)
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='requeue',
                    description='Add unnecessary requeue',
                    pattern='add-requeue'
                )
            
            if 'Requeue: true' in stripped:
                mutated = line.replace('Requeue: true', 'Requeue: false', 1)
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='requeue',
                    description='Remove requeue flag',
                    pattern='remove-requeue'
                )
            
            if 'RequeueAfter:' in stripped:
                mutated = re.sub(r'RequeueAfter:\s*[^,}]+', 'RequeueAfter: 0', line)
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='requeue',
                    description='Set RequeueAfter to zero',
                    pattern='requeue-timing-zero'
                )
    
    def _mutate_status(self, file_path: Path, lines: List[str]):
        """Generate status mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if '.Status().Update(' in stripped or '.Status().Patch(' in stripped:
                indent = len(line) - len(line.lstrip())
                mutated = ' ' * indent + '// MUTANT: Skipped status update - ' + stripped + '\n'
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='status',
                    description='Skip status update',
                    pattern='skip-status-update'
                )
            
            if 'corev1.ConditionTrue' in stripped:
                mutated = line.replace('corev1.ConditionTrue', 'corev1.ConditionFalse', 1)
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original_line=line,
                    mutated_line=mutated,
                    mutation_type='status',
                    description='Change condition to False',
                    pattern='condition-value'
                )
    
    def _mutate_api_calls(self, file_path: Path, lines: List[str]):
        """Generate API call mutations."""
        api_mutations = [
            ('r.Get(', 'r.List(', 'Change Get to List'),
            ('r.Update(', 'r.Patch(', 'Change Update to Patch'),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for old_call, new_call, description in api_mutations:
                if old_call in line:
                    mutated = line.replace(old_call, new_call, 1)
                    self._add_mutation(
                        file_path=file_path,
                        line_num=line_num,
                        original_line=line,
                        mutated_line=mutated,
                        mutation_type='api-calls',
                        description=description,
                        pattern='api-operation-type'
                    )
                    break
    
    def _add_mutation(self, file_path: Path, line_num: int, original_line: str,
                     mutated_line: str, mutation_type: str, description: str, pattern: str):
        """Add mutation to list."""
        self.mutant_counter += 1
        
        mutation = {
            'id': f'mutant-{self.mutant_counter:03d}',
            'type': mutation_type,
            'description': description,
            'file': str(file_path.relative_to(self.operator_path)),
            'line': line_num,
            'pattern': pattern,
            'original': original_line.rstrip('\n'),
            'mutated': mutated_line.rstrip('\n')
        }
        
        self.mutations.append(mutation)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary."""
        mutations_by_type = {}
        for mutation in self.mutations:
            mut_type = mutation['type']
            mutations_by_type[mut_type] = mutations_by_type.get(mut_type, 0) + 1
        
        return {
            'total_mutations': len(self.mutations),
            'mutations_by_type': mutations_by_type,
            'mutations': self.mutations,
            'operator_path': str(self.operator_path)
        }


def main():
    parser = argparse.ArgumentParser(
        description='Generate efficient mutation metadata for operators'
    )
    parser.add_argument(
        '--operator-path',
        default='.',
        help='Path to operator repository'
    )
    parser.add_argument(
        '--mutation-types',
        default='all',
        help='Comma-separated mutation types or "all"'
    )
    parser.add_argument(
        '--output',
        default='.work/mutation-testing/mutations.json',
        help='Output file for mutation metadata'
    )
    
    args = parser.parse_args()
    
    # Parse mutation types
    if args.mutation_types == 'all':
        mutation_types = ['all']
    else:
        mutation_types = [t.strip() for t in args.mutation_types.split(',')]
    
    # Generate mutations (metadata only)
    generator = EfficientMutationGenerator(
        operator_path=args.operator_path,
        mutation_types=mutation_types
    )
    
    summary = generator.generate()
    
    # Save to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("Mutation Generation Summary")
    print("="*60)
    print(f"Total Mutations: {summary['total_mutations']}")
    print("\nBy Type:")
    for mut_type, count in summary['mutations_by_type'].items():
        print(f"  {mut_type:20s}: {count:3d}")
    print(f"\nMetadata saved to: {output_path}")
    print("="*60)
    print("\n💡 TIP: No repository copies created - mutations applied in-place during testing!")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

