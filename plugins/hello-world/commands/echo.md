---
description: Hello world plugin implementation
argument-hint: [name]
---

## Name
hello-world:echo

## Synopsis
```
/hello-world:echo [name]
```

## Description
The `hello-world:echo` command prints a greeting message to the console. By default, it prints "Hello world", but when provided with a name argument `hello-world:echo $1`, it prints "Hello ${1}". This command serves as a basic example of a Claude Code plugin implementation, demonstrating the minimal structure required for a functional plugin command.

It provides a reference implementation for plugin developers. It demonstrates:
- Basic command structure
- Shell command execution within a plugin
- Handling arguments
- Minimal configuration requirements

The spec sections is inspired by https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page

## Implementation
- The command executes a simple bash `echo` statement
- Accepts an optional name argument (`$1`)
- If `$1` is provided, outputs "Hello $1"
- If no argument is provided, outputs "Hello world"
- Output is sent directly to standard output
- The command is stateless and has no side effects

Implementation logic:
```bash
if [ -n "$1" ]; then
  echo "Hello $1"
else
  echo "Hello world"
fi
```

## Return Value
- **Claude agent text**: "Hello world" (default) or "Hello $1" (when name is provided)

## Examples

1. **Basic usage (no arguments)**:
   ```
   /hello-world:echo
   ```
   Output:
   ```
   Hello world
   ```

2. **With a name argument**:
   ```
   /hello-world:echo Alice
   ```
   Output:
   ```
   Hello Alice
   ```

3. **With multiple words as name**:
   ```
   /hello-world:echo "John Doe"
   ```
   Output:
   ```
   Hello John Doe
   ```

## Arguments:
- $1: The name to be printed "Hello ${1}"