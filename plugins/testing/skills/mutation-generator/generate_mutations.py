#!/usr/bin/env python3
"""
Mutation Generator for Kubernetes Operators

Generates code mutations for operator controllers to enable mutation testing.
Focuses on patterns common in controller-runtime based operators.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Any


class MutationGenerator:
    """Generates mutations for operator controller code."""
    
    # Mutation type configurations
    CONDITIONAL_OPS = {
        '==': ['!='],
        '!=': ['=='],
        '<': ['>', '<='],
        '>': ['<', '>='],
        '<=': ['<', '>'],
        '>=': ['>', '<'],
        '&&': ['||'],
        '||': ['&&'],
    }
    
    K8S_ERROR_TYPES = [
        'IsNotFound',
        'IsAlreadyExists',
        'IsConflict',
        'IsInvalid',
        'IsTimeout',
        'IsServiceUnavailable',
    ]
    
    def __init__(self, operator_path: str, output_dir: str, mutation_types: List[str]):
        self.operator_path = Path(operator_path)
        self.output_dir = Path(output_dir)
        self.mutation_types = mutation_types
        self.mutant_counter = 0
        self.mutations = []
        
    def generate(self) -> Dict[str, Any]:
        """Main entry point to generate all mutations."""
        print(f"🔍 Scanning operator at: {self.operator_path}")
        
        # Find controller files
        controller_files = self._find_controller_files()
        print(f"📄 Found {len(controller_files)} controller files")
        
        # Generate mutations for each file
        for controller_file in controller_files:
            print(f"   Analyzing: {controller_file.relative_to(self.operator_path)}")
            self._generate_mutations_for_file(controller_file)
        
        # Create mutant directories
        print(f"\n🧬 Creating {len(self.mutations)} mutants...")
        self._create_mutants()
        
        # Generate summary
        summary = self._generate_summary()
        
        print(f"✓ Generated {len(self.mutations)} mutations")
        return summary
    
    def _find_controller_files(self) -> List[Path]:
        """Find all controller files in the operator."""
        controller_files = []
        
        # Search patterns
        patterns = [
            '**/controllers/*controller*.go',
            '**/controllers/*reconciler*.go',
            '**/pkg/controller/**/*controller*.go',
            '**/pkg/controller/**/*reconciler*.go',
        ]
        
        for pattern in patterns:
            for file_path in self.operator_path.glob(pattern):
                if '_test.go' not in str(file_path):
                    controller_files.append(file_path)
        
        return list(set(controller_files))  # Remove duplicates
    
    def _generate_mutations_for_file(self, file_path: Path):
        """Generate mutations for a single controller file."""
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Apply each mutation type
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
        """Generate conditional operator mutations."""
        for line_num, line in enumerate(lines, 1):
            # Skip comments and strings
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
            
            # Find conditional operators
            for old_op, new_ops in self.CONDITIONAL_OPS.items():
                if old_op in line and ('if ' in line or 'for ' in line or 'return ' in line):
                    for new_op in new_ops:
                        self._add_mutation(
                            file_path=file_path,
                            line_num=line_num,
                            original=line,
                            mutated=line.replace(old_op, new_op, 1),
                            mutation_type='conditional',
                            description=f'Change {old_op} to {new_op}',
                            pattern='comparison-operator'
                        )
    
    def _mutate_error_handling(self, file_path: Path, lines: List[str]):
        """Generate error handling mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Pattern 1: if err != nil { return ... }
            if 'if err != nil' in stripped and 'return' in stripped:
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=line.replace(line.strip(), f'// MUTANT: Removed error check - {line.strip()}'),
                    mutation_type='error-handling',
                    description='Remove error check',
                    pattern='remove-error-check'
                )
            
            # Pattern 2: Kubernetes error type checks
            for error_type in self.K8S_ERROR_TYPES:
                if error_type in stripped:
                    for alt_type in self.K8S_ERROR_TYPES:
                        if alt_type != error_type:
                            self._add_mutation(
                                file_path=file_path,
                                line_num=line_num,
                                original=line,
                                mutated=line.replace(error_type, alt_type, 1),
                                mutation_type='error-handling',
                                description=f'Change {error_type} to {alt_type}',
                                pattern='k8s-error-type'
                            )
                            break  # Only one alternative per line
    
    def _mutate_returns(self, file_path: Path, lines: List[str]):
        """Generate return statement mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Pattern: return ctrl.Result{}, err
            if 'return' in stripped and 'ctrl.Result' in stripped and ', err' in stripped:
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=line.replace(', err', ', nil'),
                    mutation_type='returns',
                    description='Return nil instead of error',
                    pattern='error-return-nil'
                )
            
            # Pattern: return nil (in error return position)
            if stripped == 'return nil' and line_num > 1:
                # Check if previous line is error check
                prev_line = lines[line_num - 2].strip() if line_num > 1 else ''
                if 'err' in prev_line:
                    self._add_mutation(
                        file_path=file_path,
                        line_num=line_num,
                        original=line,
                        mutated=line.replace('return nil', 'return err'),
                        mutation_type='returns',
                        description='Return error instead of nil',
                        pattern='error-return-err'
                    )
    
    def _mutate_requeue(self, file_path: Path, lines: List[str]):
        """Generate requeue behavior mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Pattern 1: return ctrl.Result{}, nil (add requeue)
            if 'return ctrl.Result{}' in stripped and 'Requeue' not in stripped:
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=line.replace('ctrl.Result{}', 'ctrl.Result{Requeue: true}'),
                    mutation_type='requeue',
                    description='Add unnecessary requeue',
                    pattern='add-requeue'
                )
            
            # Pattern 2: Requeue: true (remove requeue)
            if 'Requeue: true' in stripped:
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=line.replace('Requeue: true', 'Requeue: false'),
                    mutation_type='requeue',
                    description='Remove requeue flag',
                    pattern='remove-requeue'
                )
            
            # Pattern 3: RequeueAfter duration
            if 'RequeueAfter:' in stripped:
                # Set to zero
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=re.sub(r'RequeueAfter:\s*[^,}]+', 'RequeueAfter: 0', line),
                    mutation_type='requeue',
                    description='Set RequeueAfter to zero',
                    pattern='requeue-timing-zero'
                )
    
    def _mutate_status(self, file_path: Path, lines: List[str]):
        """Generate status update mutations."""
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Pattern 1: Status().Update() calls
            if '.Status().Update(' in stripped or '.Status().Patch(' in stripped:
                self._add_mutation(
                    file_path=file_path,
                    line_num=line_num,
                    original=line,
                    mutated=line.replace(line.strip(), f'// MUTANT: Skipped status update - {line.strip()}'),
                    mutation_type='status',
                    description='Skip status update',
                    pattern='skip-status-update'
                )
            
            # Pattern 2: Condition status (True/False)
            if 'SetCondition' in stripped or 'Condition' in stripped:
                if 'corev1.ConditionTrue' in stripped:
                    self._add_mutation(
                        file_path=file_path,
                        line_num=line_num,
                        original=line,
                        mutated=line.replace('corev1.ConditionTrue', 'corev1.ConditionFalse'),
                        mutation_type='status',
                        description='Change condition to False',
                        pattern='condition-value'
                    )
                elif 'corev1.ConditionFalse' in stripped:
                    self._add_mutation(
                        file_path=file_path,
                        line_num=line_num,
                        original=line,
                        mutated=line.replace('corev1.ConditionFalse', 'corev1.ConditionTrue'),
                        mutation_type='status',
                        description='Change condition to True',
                        pattern='condition-value'
                    )
    
    def _mutate_api_calls(self, file_path: Path, lines: List[str]):
        """Generate API call mutations."""
        api_mutations = [
            ('r.Get(', 'r.List(', 'Change Get to List'),
            ('r.Update(', 'r.Patch(', 'Change Update to Patch'),
            ('r.Create(', 'r.Update(', 'Change Create to Update'),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for old_call, new_call, description in api_mutations:
                if old_call in line:
                    self._add_mutation(
                        file_path=file_path,
                        line_num=line_num,
                        original=line,
                        mutated=line.replace(old_call, new_call, 1),
                        mutation_type='api-calls',
                        description=description,
                        pattern='api-operation-type'
                    )
    
    def _add_mutation(self, file_path: Path, line_num: int, original: str, 
                     mutated: str, mutation_type: str, description: str, pattern: str):
        """Add a mutation to the list."""
        self.mutant_counter += 1
        
        mutation = {
            'id': f'mutant-{self.mutant_counter:03d}',
            'type': mutation_type,
            'description': description,
            'file': str(file_path.relative_to(self.operator_path)),
            'line': line_num,
            'pattern': pattern,
            'original': original.strip(),
            'mutated': mutated.strip()
        }
        
        self.mutations.append(mutation)
    
    def _create_mutants(self):
        """Create mutant copies of the operator."""
        os.makedirs(self.output_dir, exist_ok=True)
        
        for i, mutation in enumerate(self.mutations, 1):
            mutant_dir = self.output_dir / mutation['id']
            
            # Copy operator
            if mutant_dir.exists():
                shutil.rmtree(mutant_dir)
            shutil.copytree(self.operator_path, mutant_dir)
            
            # Apply mutation
            mutated_file = mutant_dir / mutation['file']
            self._apply_mutation_to_file(mutated_file, mutation)
            
            # Save metadata
            metadata_file = mutant_dir / 'MUTATION.json'
            with open(metadata_file, 'w') as f:
                json.dump(mutation, f, indent=2)
            
            # Progress indicator
            if i % 10 == 0:
                print(f"   Created {i}/{len(self.mutations)} mutants...")
    
    def _apply_mutation_to_file(self, file_path: Path, mutation: Dict[str, Any]):
        """Apply mutation to a specific file."""
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        target_line = mutation['line'] - 1
        
        if target_line < len(lines):
            # Replace the line
            original_content = lines[target_line].strip()
            mutated_content = mutation['mutated']
            
            # Preserve indentation
            indent = len(lines[target_line]) - len(lines[target_line].lstrip())
            lines[target_line] = ' ' * indent + mutated_content + '\n'
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary of mutations."""
        mutations_by_type = {}
        for mutation in self.mutations:
            mut_type = mutation['type']
            mutations_by_type[mut_type] = mutations_by_type.get(mut_type, 0) + 1
        
        summary = {
            'total_mutations': len(self.mutations),
            'mutations_by_type': mutations_by_type,
            'mutations': self.mutations,
            'output_dir': str(self.output_dir)
        }
        
        # Save to JSON
        summary_file = self.output_dir / 'mutations-summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary


def main():
    parser = argparse.ArgumentParser(
        description='Generate mutations for Kubernetes operator controllers'
    )
    parser.add_argument(
        '--operator-path',
        default='.',
        help='Path to operator repository (default: current directory)'
    )
    parser.add_argument(
        '--mutation-types',
        default='all',
        help='Comma-separated mutation types: conditionals,error-handling,returns,requeue,status,api-calls,all (default: all)'
    )
    parser.add_argument(
        '--output-dir',
        default='.work/mutation-testing/mutants',
        help='Output directory for mutants (default: .work/mutation-testing/mutants)'
    )
    
    args = parser.parse_args()
    
    # Parse mutation types
    if args.mutation_types == 'all':
        mutation_types = ['all']
    else:
        mutation_types = [t.strip() for t in args.mutation_types.split(',')]
    
    # Generate mutations
    generator = MutationGenerator(
        operator_path=args.operator_path,
        output_dir=args.output_dir,
        mutation_types=mutation_types
    )
    
    summary = generator.generate()
    
    # Print summary
    print("\n" + "="*60)
    print("Mutation Generation Summary")
    print("="*60)
    print(f"Total Mutations: {summary['total_mutations']}")
    print("\nBy Type:")
    for mut_type, count in summary['mutations_by_type'].items():
        print(f"  {mut_type:20s}: {count:3d}")
    print(f"\nMutants created in: {summary['output_dir']}")
    print("="*60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

