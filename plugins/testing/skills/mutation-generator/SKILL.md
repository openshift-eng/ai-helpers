---
name: Mutation Generator for Operator Controllers
description: Generate code mutations for Kubernetes operator controllers to enable mutation testing. Applies operator-specific mutations to reconciliation logic, error handling, and API interactions.
---

# Mutation Generator for Operator Controllers

This skill generates mutations (deliberate bugs) in operator controller code to enable mutation testing. It focuses on patterns common in Kubernetes operators built with controller-runtime.

## When to Use This Skill

Use this skill when:
- You need to generate mutants for operator mutation testing
- You want to create realistic bugs that tests should catch
- You're analyzing operator controller code for mutation points
- You need operator-specific mutations (requeue, status updates, API calls)

## Prerequisites

1. **Go operator code** using controller-runtime framework
2. **Python 3.8+** for mutation generation scripts
3. **Go AST parsing** capability (via go/parser or Python ast module)

## Mutation Strategy for Operators

### Understanding Operator Mutation Points

Kubernetes operators have specific patterns that should be tested:

**1. Reconciliation Logic:**
- Conditional checks on resource state
- Decision trees for state transitions
- Owner reference checks
- Finalizer logic

**2. Error Handling:**
- API call error handling
- Client-go errors (NotFound, AlreadyExists, Conflict)
- Wrapped errors
- Error return paths

**3. Requeue Behavior:**
- `ctrl.Result{Requeue: true}`
- `ctrl.Result{RequeueAfter: duration}`
- Rate limiting
- Conditional requeueing

**4. Status Updates:**
- Condition setting (Ready, Available, Degraded)
- ObservedGeneration tracking
- Status subresource updates
- Partial status updates

**5. API Interactions:**
- Get vs. List operations
- Create vs. Update logic
- Patch vs. Update
- Delete with preconditions

## Implementation Steps

### Step 1: Parse Controller Code

**1.1 Identify Reconcile Functions**

Look for the standard controller-runtime reconciliation signature:

```go
func (r *MyReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error)
```

**1.2 Extract Abstract Syntax Tree (AST)**

Use Go's parser to build AST:

```python
import go_parser  # or use subprocess to call go/ast tools

def parse_controller(file_path):
    """Parse Go controller file into AST."""
    # Read file
    with open(file_path, 'r') as f:
        source = f.read()
    
    # Parse into AST
    ast = parse_go_file(source)
    
    # Find Reconcile function
    reconcile_func = find_reconcile_function(ast)
    
    return {
        'source': source,
        'ast': ast,
        'reconcile': reconcile_func,
        'file_path': file_path
    }
```

**1.3 Identify Mutation Candidates**

Walk the AST to find mutation points:

```python
def find_mutation_points(ast_node):
    """Find all locations where mutations can be applied."""
    mutation_points = []
    
    # Walk AST nodes
    for node in walk_ast(ast_node):
        if is_conditional(node):
            mutation_points.append({
                'type': 'conditional',
                'location': node.position,
                'original': node.text,
                'node': node
            })
        elif is_error_check(node):
            mutation_points.append({
                'type': 'error-handling',
                'location': node.position,
                'original': node.text,
                'node': node
            })
        # ... more patterns
    
    return mutation_points
```

---

### Step 2: Generate Conditional Mutations

**2.1 Comparison Operator Mutations**

Mutate comparison operators:

```python
CONDITIONAL_MUTATIONS = {
    '==': ['!='],
    '!=': ['=='],
    '<': ['>', '<=', '>='],
    '>': ['<', '<=', '>='],
    '<=': ['<', '>='],
    '>=': ['>', '<='],
}

def mutate_conditional(node):
    """Generate mutations for conditional expressions."""
    mutations = []
    
    if node.operator in CONDITIONAL_MUTATIONS:
        for new_op in CONDITIONAL_MUTATIONS[node.operator]:
            mutations.append({
                'id': generate_mutant_id(),
                'type': 'conditional',
                'description': f'Change {node.operator} to {new_op}',
                'location': f'{node.file}:{node.line}',
                'original': node.text,
                'mutated': node.text.replace(node.operator, new_op, 1),
                'pattern': 'comparison-operator'
            })
    
    return mutations
```

**2.2 Boolean Expression Mutations**

Negate boolean expressions:

```python
def mutate_boolean_expr(node):
    """Negate boolean expressions."""
    mutations = []
    
    # if condition → if !condition
    # if !condition → if condition
    
    if node.is_negated:
        # Remove negation
        mutated = node.text.lstrip('!')
        description = 'Remove negation'
    else:
        # Add negation
        mutated = f'!({node.text})'
        description = 'Add negation'
    
    mutations.append({
        'id': generate_mutant_id(),
        'type': 'conditional',
        'description': description,
        'location': f'{node.file}:{node.line}',
        'original': node.text,
        'mutated': mutated,
        'pattern': 'boolean-negation'
    })
    
    return mutations
```

**2.3 Operator-Specific Conditional Mutations**

Target operator patterns:

```python
# Example: Mutate finalizer checks
# Original: if contains(obj.Finalizers, MyFinalizer)
# Mutated:  if !contains(obj.Finalizers, MyFinalizer)

# Example: Mutate generation checks
# Original: if obj.Generation != obj.Status.ObservedGeneration
# Mutated:  if obj.Generation == obj.Status.ObservedGeneration
```

---

### Step 3: Generate Error Handling Mutations

**3.1 Remove Error Checks**

Most critical mutation type for operators:

```python
def mutate_error_handling(node):
    """Mutate error handling code."""
    mutations = []
    
    # Pattern: if err != nil { return ... }
    if is_error_check_pattern(node):
        mutations.append({
            'id': generate_mutant_id(),
            'type': 'error-handling',
            'description': 'Remove error check',
            'location': f'{node.file}:{node.line}',
            'original': node.text,
            'mutated': f'// MUTANT: Removed error check\n// {node.text}',
            'pattern': 'remove-error-check'
        })
    
    return mutations
```

**3.2 Change Error Returns**

```python
def mutate_error_return(node):
    """Mutate error return statements."""
    mutations = []
    
    # Pattern: return ctrl.Result{}, err
    # Mutate to: return ctrl.Result{}, nil
    
    if is_error_return(node):
        mutations.append({
            'id': generate_mutant_id(),
            'type': 'error-handling',
            'description': 'Return nil instead of error',
            'location': f'{node.file}:{node.line}',
            'original': node.text,
            'mutated': node.text.replace(', err', ', nil'),
            'pattern': 'error-return-nil'
        })
    
    return mutations
```

**3.3 Ignore Specific Error Types**

Kubernetes-specific error mutations:

```python
def mutate_k8s_errors(node):
    """Mutate Kubernetes error handling."""
    mutations = []
    
    # Pattern: if errors.IsNotFound(err)
    # Mutate to: if errors.IsAlreadyExists(err)
    
    # Pattern: if errors.IsAlreadyExists(err)
    # Mutate to: if errors.IsNotFound(err)
    
    if is_k8s_error_check(node):
        error_types = ['IsNotFound', 'IsAlreadyExists', 'IsConflict', 'IsInvalid']
        current_type = extract_error_type(node)
        
        for new_type in error_types:
            if new_type != current_type:
                mutations.append({
                    'id': generate_mutant_id(),
                    'type': 'error-handling',
                    'description': f'Change {current_type} to {new_type}',
                    'location': f'{node.file}:{node.line}',
                    'original': node.text,
                    'mutated': node.text.replace(current_type, new_type),
                    'pattern': 'k8s-error-type'
                })
    
    return mutations
```

---

### Step 4: Generate Requeue Mutations

**4.1 Toggle Requeue Flag**

```python
def mutate_requeue(node):
    """Mutate requeue behavior."""
    mutations = []
    
    # Pattern: return ctrl.Result{}, nil
    # Mutate to: return ctrl.Result{Requeue: true}, nil
    
    if is_result_return(node):
        # If no requeue, add requeue
        if 'Requeue' not in node.text:
            mutations.append({
                'id': generate_mutant_id(),
                'type': 'requeue',
                'description': 'Add unnecessary requeue',
                'location': f'{node.file}:{node.line}',
                'original': node.text,
                'mutated': node.text.replace('ctrl.Result{}', 'ctrl.Result{Requeue: true}'),
                'pattern': 'add-requeue'
            })
        
        # If requeue exists, remove it
        if 'Requeue: true' in node.text:
            mutations.append({
                'id': generate_mutant_id(),
                'type': 'requeue',
                'description': 'Remove requeue flag',
                'location': f'{node.file}:{node.line}',
                'original': node.text,
                'mutated': node.text.replace('Requeue: true', 'Requeue: false'),
                'pattern': 'remove-requeue'
            })
    
    return mutations
```

**4.2 Change Requeue Timing**

```python
def mutate_requeue_after(node):
    """Mutate RequeueAfter duration."""
    mutations = []
    
    # Pattern: RequeueAfter: 5 * time.Second
    # Mutate to: RequeueAfter: 0
    # Or:        RequeueAfter: 5 * time.Minute (change unit)
    
    if 'RequeueAfter' in node.text:
        mutations.extend([
            {
                'id': generate_mutant_id(),
                'type': 'requeue',
                'description': 'Set RequeueAfter to zero',
                'location': f'{node.file}:{node.line}',
                'original': node.text,
                'mutated': set_requeue_after_zero(node.text),
                'pattern': 'requeue-timing-zero'
            },
            {
                'id': generate_mutant_id(),
                'type': 'requeue',
                'description': 'Change RequeueAfter time unit',
                'location': f'{node.file}:{node.line}',
                'original': node.text,
                'mutated': change_time_unit(node.text),
                'pattern': 'requeue-timing-unit'
            }
        ])
    
    return mutations
```

---

### Step 5: Generate Status Update Mutations

**5.1 Skip Status Updates**

```python
def mutate_status_update(node):
    """Mutate status update calls."""
    mutations = []
    
    # Pattern: r.Status().Update(ctx, obj)
    # Mutate to: // MUTANT: Skipped status update
    
    if is_status_update_call(node):
        mutations.append({
            'id': generate_mutant_id(),
            'type': 'status',
            'description': 'Skip status update',
            'location': f'{node.file}:{node.line}',
            'original': node.text,
            'mutated': f'// MUTANT: Skipped status update\n// {node.text}',
            'pattern': 'skip-status-update'
        })
    
    return mutations
```

**5.2 Change Condition Values**

```python
def mutate_condition(node):
    """Mutate condition setting."""
    mutations = []
    
    # Pattern: SetCondition(Ready, True, "Ready", "...")
    # Mutate to: SetCondition(Ready, False, "Ready", "...")
    
    if is_set_condition_call(node):
        # Toggle condition status
        if 'True' in node.text:
            mutated = node.text.replace('True', 'False', 1)
            desc = 'Change condition to False'
        else:
            mutated = node.text.replace('False', 'True', 1)
            desc = 'Change condition to True'
        
        mutations.append({
            'id': generate_mutant_id(),
            'type': 'status',
            'description': desc,
            'location': f'{node.file}:{node.line}',
            'original': node.text,
            'mutated': mutated,
            'pattern': 'condition-value'
        })
    
    return mutations
```

---

### Step 6: Generate API Call Mutations

**6.1 Change API Operation Type**

```python
def mutate_api_call(node):
    """Mutate Kubernetes API calls."""
    mutations = []
    
    # Pattern: r.Get(ctx, key, obj)
    # Mutate to: r.List(ctx, obj) [intentional API misuse]
    
    if is_client_call(node):
        operation = extract_operation(node)  # Get, List, Create, Update, Delete
        
        alternative_ops = {
            'Get': ['List'],  # Get → List (wrong cardinality)
            'Update': ['Patch'],  # Update → Patch (different semantics)
            'Create': ['Update'],  # Create → Update (wrong operation)
        }
        
        if operation in alternative_ops:
            for alt_op in alternative_ops[operation]:
                mutations.append({
                    'id': generate_mutant_id(),
                    'type': 'api-calls',
                    'description': f'Change {operation} to {alt_op}',
                    'location': f'{node.file}:{node.line}',
                    'original': node.text,
                    'mutated': node.text.replace(operation, alt_op, 1),
                    'pattern': 'api-operation-type'
                })
    
    return mutations
```

---

### Step 7: Apply Mutations and Create Mutants

**7.1 Create Mutant Copy**

For each mutation:

```python
def create_mutant(mutation, operator_path, output_dir):
    """Create a mutant copy of the operator with mutation applied."""
    
    mutant_id = mutation['id']
    mutant_dir = os.path.join(output_dir, f'mutant-{mutant_id}')
    
    # Copy entire operator
    shutil.copytree(operator_path, mutant_dir)
    
    # Apply mutation to specific file
    mutated_file = os.path.join(mutant_dir, mutation['file'])
    apply_mutation_to_file(mutated_file, mutation)
    
    # Save mutation metadata
    metadata = {
        'id': mutant_id,
        'type': mutation['type'],
        'description': mutation['description'],
        'file': mutation['file'],
        'line': mutation['line'],
        'original': mutation['original'],
        'mutated': mutation['mutated'],
        'pattern': mutation['pattern']
    }
    
    with open(os.path.join(mutant_dir, 'MUTATION.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return mutant_dir
```

**7.2 Apply Single Mutation to File**

```python
def apply_mutation_to_file(file_path, mutation):
    """Apply mutation to a specific file."""
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find and replace the specific line
    target_line = mutation['line'] - 1  # 0-indexed
    
    if target_line < len(lines):
        # Replace exact match on that line
        lines[target_line] = lines[target_line].replace(
            mutation['original'],
            mutation['mutated'],
            1  # Replace only first occurrence
        )
    
    # Write back
    with open(file_path, 'w') as f:
        f.writelines(lines)
```

---

## Output Format

The mutation generator produces:

**1. Mutations Catalog (JSON)**

```json
{
  "total_mutations": 145,
  "mutations_by_type": {
    "conditional": 42,
    "error-handling": 38,
    "requeue": 18,
    "status": 25,
    "api-calls": 15,
    "returns": 7
  },
  "mutations": [
    {
      "id": "mutant-001",
      "type": "error-handling",
      "description": "Remove error check after API Get",
      "file": "controllers/pod_controller.go",
      "line": 87,
      "function": "Reconcile",
      "pattern": "remove-error-check",
      "original": "if err != nil { return ctrl.Result{}, err }",
      "mutated": "// MUTANT: Removed error check"
    }
  ]
}
```

**2. Mutant Directories**

```
.work/mutation-testing/mutants/
├── mutant-001/           # Full operator copy with mutation applied
│   ├── MUTATION.json     # Metadata about this mutation
│   ├── controllers/
│   ├── api/
│   └── ...
├── mutant-002/
├── mutant-003/
...
```

## Error Handling

- **No controllers found**: Warn user and provide suggestions
- **Parse errors**: Skip files with syntax errors, report them
- **Invalid mutations**: Validate mutations don't break Go syntax
- **Disk space**: Check available space before creating mutants (can be GB of data)

## Best Practices

1. **Focus on High-Value Mutations**: Prioritize error handling and conditionals
2. **Avoid Equivalent Mutants**: Don't generate mutations that don't change behavior
3. **Limit Mutations**: For large controllers, consider sampling strategy
4. **Validate Syntax**: Ensure mutated code compiles before creating mutant
5. **Track Coverage**: Keep mapping of which mutations test which behavior

## Example Usage

```python
# Generate mutations for all controllers
mutations = generate_mutations(
    operator_path="/path/to/operator",
    mutation_types=["error-handling", "conditional", "requeue"],
    output_dir=".work/mutation-testing/mutants"
)

print(f"Generated {len(mutations)} mutations")
print(f"Mutants created in: {output_dir}")
```

## See Also

- [mutation-tester skill](../mutation-tester/SKILL.md) - Tests each mutant
- [go-mutesting](https://github.com/zimmski/go-mutesting) - Existing Go mutation testing tool
- [Mutation Testing Best Practices](https://pedrorijo.com/blog/intro-mutation/)

