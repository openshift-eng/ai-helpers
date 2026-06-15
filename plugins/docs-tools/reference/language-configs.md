# Language Configuration Reference

Per-language rules for module boundary detection, config files, coupling types, and AST extraction guidance. Used by agents and scripts.

## Python

- **Module boundary**: Directory containing `.py` files. Each top-level directory under the project root is one module. `__init__.py` presence marks a package but is not required (namespace packages).
- **Config files**: `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`, `README.md`, `__init__.py`
- **Public API**: Functions and classes not starting with `_`. Use `ast` module for extraction.
- **Import signal**: `from X import Y` and `import X` statements reveal internal dependencies.
- **Coupling types**: `data-shape`, `interface-contract`, `config`, `inheritance`, `event`, `none`
- **Walker note**: Group by top-level directory. Each dir = one agent domain.

## Go

- **Module boundary**: Directory containing `.go` files = one Go package. `go.mod` defines the module root.
- **Config files**: `go.mod`, `go.sum`, `README.md`
- **Public API**: Exported symbols start with an uppercase letter. AST-aware extraction via tree-sitter (functions, methods, types, structs, interfaces, variables, constants).
- **Import signal**: `import` blocks reveal internal package dependencies.
- **Coupling types**: `interface-contract`, `data-shape`, `config`, `embedding`, `channel`, `none`
- **Special guidance**: Look for implicit interface satisfaction — a type in package A may implement an interface in package B without an explicit import.
- **Walker note**: Group by Go package (directory). go.mod defines the module root.

## JavaScript

- **Module boundary**: Directory or feature slice under `src/`. `index.js` files define the public API boundary.
- **Config files**: `package.json`, `README.md`
- **Public API**: AST-aware extraction via tree-sitter — `export function`, `export class`, `export const`, `export default`, re-exports.
- **Import signal**: `import ... from` and `require()` statements reveal dependencies.
- **Coupling types**: `data-shape`, `event`, `config`, `duck-typing`, `callback`, `none`
- **Special guidance**: Look for duck-typing and callback shape assumptions between modules.
- **Walker note**: Group by top-level src/ directory. index.js files are the public API boundary.

## TypeScript

- **Module boundary**: Directory or feature slice. `index.ts` barrel files + exported types define the public contract.
- **Config files**: `package.json`, `tsconfig.json`, `README.md`
- **Public API**: AST-aware extraction via tree-sitter — `export function`, `export class`, `export const`, `export default`, `export interface`, `export type`, `export enum`, abstract classes, re-exports.
- **Import signal**: `import` and `import type` statements. Type-only imports reveal interface contracts.
- **Coupling types**: `explicit-type-import`, `structural-subtype`, `data-shape`, `event`, `config`, `generic-constraint`, `none`
- **Special guidance**: Pay special attention to structural subtyping — two modules may share a type shape without a direct import. `{ id: string; name: string }` in module A may satisfy `interface User` in module B with no shared import.
- **Walker note**: Group by top-level src/ directory. index.ts + exported types define the contract.

## Common Exclusions

Directories always excluded from module mapping:

```
.git, node_modules, vendor, __pycache__, .mypy_cache, .pytest_cache,
.tox, .venv, venv, env, .env, dist, build, out, target, bin, obj,
.idea, .vscode, .claude, .agent_workspace, coverage, .nyc_output,
.next, .nuxt, .cache, tmp, temp
```

File patterns always excluded:

```
*.pyc, *.pyo, *.class, *.o, *.so, *.dylib, *.dll,
*.min.js, *.bundle.js, *.map, *.lock, *.sum
```
