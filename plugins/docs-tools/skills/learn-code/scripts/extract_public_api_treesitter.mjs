#!/usr/bin/env node
/**
 * Extract public API surface from Go, JavaScript, and TypeScript files using tree-sitter AST parsing.
 *
 * Uses web-tree-sitter (WASM-based, no native compilation required).
 * Drop-in replacement for extract_public_api.mjs (JS/TS) and extract_public_api_go.sh (Go).
 *
 * Usage:
 *   node extract_public_api_treesitter.mjs --files file1.go file2.go --lang go --module mymod
 *   node extract_public_api_treesitter.mjs --files file1.ts file2.ts --lang typescript --module auth
 *   node extract_public_api_treesitter.mjs --files file1.js --lang javascript --module utils
 */

import { readFileSync } from 'fs';
import { basename, dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __dirname = dirname(fileURLToPath(import.meta.url));
const pluginRoot = join(__dirname, '..', '..');
const require = createRequire(import.meta.url);

// --- CLI argument parsing ---

const argv = process.argv.slice(2);
let files = [];
let lang = 'javascript';
let moduleName = 'unknown';

for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--files') {
    i++;
    while (i < argv.length && !argv[i].startsWith('--')) {
      files.push(argv[i]);
      i++;
    }
    i--;
  } else if (argv[i] === '--lang') {
    lang = argv[++i];
  } else if (argv[i] === '--module') {
    moduleName = argv[++i];
  }
}

// --- WASM path resolution ---

function resolveWasmPath(langKey, fileExt) {
  const WASM_MAP = {
    go: 'tree-sitter-go/tree-sitter-go.wasm',
    javascript: 'tree-sitter-javascript/tree-sitter-javascript.wasm',
    typescript: 'tree-sitter-typescript/tree-sitter-typescript.wasm',
    tsx: 'tree-sitter-typescript/tree-sitter-tsx.wasm',
  };

  let key = langKey;
  if (langKey === 'typescript' && (fileExt === '.tsx' || fileExt === '.jsx')) {
    key = 'tsx';
  }

  const pkgName = WASM_MAP[key].split('/')[0];
  const wasmFile = WASM_MAP[key].split('/')[1];
  const pkgDir = dirname(require.resolve(`${pkgName}/package.json`));
  return join(pkgDir, wasmFile);
}

// --- Preceding comment extraction ---

function getPrecedingComment(node) {
  let prev = node.previousNamedSibling;
  if (!prev) {
    prev = node.previousSibling;
  }
  if (!prev) return null;

  if (prev.type === 'comment' || prev.type === 'line_comment' || prev.type === 'block_comment') {
    const text = prev.text.replace(/^\/\/\s?|^\/\*|\*\/$/g, '').trim();
    return text.split('\n')[0].substring(0, 200) || null;
  }
  return null;
}

// --- Go extraction ---

function extractGoExports(rootNode, fileName) {
  const exports = [];

  for (const child of rootNode.namedChildren) {
    if (child.type === 'function_declaration') {
      const nameNode = child.childForFieldName('name');
      if (!nameNode || !/^[A-Z]/.test(nameNode.text)) continue;
      exports.push({
        name: nameNode.text,
        kind: 'function',
        file: fileName,
        line: child.startPosition.row + 1,
        signature: child.text.split('{')[0].trim().substring(0, 400),
        docstring: getPrecedingComment(child),
      });
    }

    if (child.type === 'method_declaration') {
      const nameNode = child.childForFieldName('name');
      if (!nameNode || !/^[A-Z]/.test(nameNode.text)) continue;
      const receiverNode = child.childForFieldName('receiver');
      const receiverText = receiverNode ? receiverNode.text : '';
      exports.push({
        name: nameNode.text,
        kind: 'method',
        file: fileName,
        line: child.startPosition.row + 1,
        signature: child.text.split('{')[0].trim().substring(0, 400),
        docstring: getPrecedingComment(child),
        receiver: receiverText,
      });
    }

    if (child.type === 'type_declaration') {
      for (const spec of child.namedChildren) {
        if (spec.type !== 'type_spec') continue;
        const nameNode = spec.childForFieldName('name');
        if (!nameNode || !/^[A-Z]/.test(nameNode.text)) continue;

        const typeNode = spec.childForFieldName('type');
        let kind = 'type';
        if (typeNode) {
          if (typeNode.type === 'struct_type') kind = 'struct';
          else if (typeNode.type === 'interface_type') kind = 'interface';
        }

        exports.push({
          name: nameNode.text,
          kind,
          file: fileName,
          line: spec.startPosition.row + 1,
          signature: spec.text.split('\n').slice(0, 3).join('\n').substring(0, 400),
          docstring: getPrecedingComment(child),
        });
      }
    }

    if (child.type === 'var_declaration') {
      for (const spec of child.namedChildren) {
        if (spec.type !== 'var_spec') continue;
        const nameNode = spec.childForFieldName('name');
        if (!nameNode || !/^[A-Z]/.test(nameNode.text)) continue;
        exports.push({
          name: nameNode.text,
          kind: 'variable',
          file: fileName,
          line: spec.startPosition.row + 1,
          signature: spec.text.substring(0, 200),
          docstring: getPrecedingComment(child),
        });
      }
    }

    if (child.type === 'const_declaration') {
      for (const spec of child.namedChildren) {
        if (spec.type !== 'const_spec') continue;
        const nameNode = spec.childForFieldName('name');
        if (!nameNode || !/^[A-Z]/.test(nameNode.text)) continue;
        exports.push({
          name: nameNode.text,
          kind: 'constant',
          file: fileName,
          line: spec.startPosition.row + 1,
          signature: spec.text.substring(0, 200),
          docstring: getPrecedingComment(child),
        });
      }
    }
  }

  return exports;
}

function extractGoImports(rootNode, fileName) {
  const imports = [];

  for (const child of rootNode.namedChildren) {
    if (child.type === 'import_declaration') {
      const specs = child.descendantsOfType('import_spec');
      for (const spec of specs) {
        const pathNode = spec.childForFieldName('path');
        if (pathNode) {
          const modPath = pathNode.text.replace(/^"|"$/g, '');
          imports.push({ module: modPath, file: fileName });
        }
      }
    }
  }

  return imports;
}

// --- JavaScript/TypeScript extraction ---

function extractJSExports(rootNode, fileName, isTypeScript) {
  const exports = [];

  for (const child of rootNode.namedChildren) {
    if (child.type !== 'export_statement') continue;

    const decl = child.childForFieldName('declaration') || findDeclarationChild(child);
    if (!decl) {
      // Re-export: export { x, y } from '...'
      const clause = findChildOfType(child, 'export_clause');
      if (clause) {
        const specifiers = clause.descendantsOfType('export_specifier');
        for (const spec of specifiers) {
          const nameNode = spec.childForFieldName('name') || spec.firstNamedChild;
          if (nameNode) {
            exports.push({
              name: nameNode.text,
              kind: 're-export',
              file: fileName,
              line: child.startPosition.row + 1,
              signature: child.text.substring(0, 200),
              docstring: null,
            });
          }
        }
      }
      continue;
    }

    const isDefault = child.text.includes('export default');

    switch (decl.type) {
      case 'function_declaration':
      case 'function_signature': {
        const nameNode = decl.childForFieldName('name');
        exports.push({
          name: nameNode?.text || '(default)',
          kind: 'function',
          file: fileName,
          line: decl.startPosition.row + 1,
          signature: decl.text.split('{')[0].trim().substring(0, 400),
          docstring: getPrecedingComment(child),
        });
        break;
      }

      case 'class_declaration':
      case 'abstract_class_declaration': {
        const nameNode = decl.childForFieldName('name');
        const kind = decl.type === 'abstract_class_declaration' ? 'abstract-class' : 'class';
        exports.push({
          name: nameNode?.text || '(default)',
          kind,
          file: fileName,
          line: decl.startPosition.row + 1,
          signature: decl.text.split('{')[0].trim().substring(0, 400),
          docstring: getPrecedingComment(child),
        });
        break;
      }

      case 'lexical_declaration':
      case 'variable_declaration': {
        const declarators = decl.descendantsOfType('variable_declarator');
        for (const d of declarators) {
          const nameNode = d.childForFieldName('name');
          if (!nameNode) continue;
          const valueNode = d.childForFieldName('value');
          let kind = 'constant';
          if (valueNode && (valueNode.type === 'arrow_function' || valueNode.type === 'function_expression')) {
            kind = 'function';
          }
          exports.push({
            name: nameNode.text,
            kind,
            file: fileName,
            line: d.startPosition.row + 1,
            signature: d.text.substring(0, 400),
            docstring: getPrecedingComment(child),
          });
        }
        break;
      }

      case 'interface_declaration': {
        if (!isTypeScript) break;
        const nameNode = decl.childForFieldName('name');
        exports.push({
          name: nameNode?.text || '(anonymous)',
          kind: 'interface',
          file: fileName,
          line: decl.startPosition.row + 1,
          signature: decl.text.split('{')[0].trim().substring(0, 400),
          docstring: getPrecedingComment(child),
        });
        break;
      }

      case 'type_alias_declaration': {
        if (!isTypeScript) break;
        const nameNode = decl.childForFieldName('name');
        exports.push({
          name: nameNode?.text || '(anonymous)',
          kind: 'type',
          file: fileName,
          line: decl.startPosition.row + 1,
          signature: decl.text.substring(0, 400),
          docstring: getPrecedingComment(child),
        });
        break;
      }

      case 'enum_declaration': {
        if (!isTypeScript) break;
        const nameNode = decl.childForFieldName('name');
        exports.push({
          name: nameNode?.text || '(anonymous)',
          kind: 'enum',
          file: fileName,
          line: decl.startPosition.row + 1,
          signature: decl.text.split('{')[0].trim().substring(0, 400),
          docstring: getPrecedingComment(child),
        });
        break;
      }

      default: {
        if (isDefault) {
          exports.push({
            name: '(default)',
            kind: 'default',
            file: fileName,
            line: decl.startPosition.row + 1,
            signature: decl.text.substring(0, 400),
            docstring: getPrecedingComment(child),
          });
        }
      }
    }
  }

  return exports;
}

function extractJSImports(rootNode, fileName) {
  const imports = [];

  for (const child of rootNode.namedChildren) {
    if (child.type === 'import_statement') {
      const sourceNode = child.childForFieldName('source');
      if (sourceNode) {
        const modPath = sourceNode.text.replace(/^['"]|['"]$/g, '');
        imports.push({ module: modPath, file: fileName });
      }
    }
  }

  // Also catch require() calls at top level
  const requireCalls = rootNode.descendantsOfType('call_expression');
  for (const call of requireCalls) {
    const fnNode = call.childForFieldName('function');
    if (fnNode && fnNode.text === 'require') {
      const argsNode = call.childForFieldName('arguments');
      if (argsNode && argsNode.namedChildCount > 0) {
        const firstArg = argsNode.namedChild(0);
        if (firstArg && (firstArg.type === 'string' || firstArg.type === 'template_string')) {
          const modPath = firstArg.text.replace(/^['"]|['"]$/g, '');
          imports.push({ module: modPath, file: fileName });
        }
      }
    }
  }

  return imports;
}

// --- Helpers ---

function findDeclarationChild(exportNode) {
  for (const child of exportNode.namedChildren) {
    if (child.type.endsWith('_declaration') || child.type.endsWith('_signature')) {
      return child;
    }
  }
  // Check for default value exports: export default <expression>
  if (exportNode.namedChildCount > 0) {
    const last = exportNode.lastNamedChild;
    if (last && last.type !== 'export_clause' && last.type !== 'string') {
      return last;
    }
  }
  return null;
}

function findChildOfType(node, type) {
  for (const child of node.namedChildren) {
    if (child.type === type) return child;
  }
  return null;
}

// --- Main ---

async function main() {
  if (files.length === 0) {
    console.log(JSON.stringify({
      error: 'No files provided',
      module: moduleName,
      language: lang,
      exports: [],
      imports: [],
      export_count: 0,
    }, null, 2));
    return;
  }

  let Parser;
  try {
    Parser = (await import('web-tree-sitter')).default;
    await Parser.init();
  } catch (err) {
    console.log(JSON.stringify({
      error: `Failed to initialize web-tree-sitter: ${err.message}`,
      module: moduleName,
      language: lang,
      exports: [],
      imports: [],
      export_count: 0,
    }, null, 2));
    return;
  }

  const isTypeScript = lang === 'typescript';
  const isGo = lang === 'go';

  const allExports = [];
  const allImports = [];

  // Group files by WASM grammar needed (TS vs TSX)
  for (const filepath of files) {
    let source;
    try {
      source = readFileSync(filepath, 'utf8');
    } catch {
      continue;
    }

    const fileName = basename(filepath);
    const ext = '.' + fileName.split('.').pop().toLowerCase();

    let wasmPath;
    try {
      wasmPath = resolveWasmPath(lang, ext);
    } catch (err) {
      console.error(`Warning: Could not resolve WASM for ${lang}/${ext}: ${err.message}`);
      continue;
    }

    let language;
    try {
      language = await Parser.Language.load(wasmPath);
    } catch (err) {
      console.error(`Warning: Could not load language WASM at ${wasmPath}: ${err.message}`);
      continue;
    }

    const parser = new Parser();
    parser.setLanguage(language);
    const tree = parser.parse(source);

    if (isGo) {
      allExports.push(...extractGoExports(tree.rootNode, fileName));
      allImports.push(...extractGoImports(tree.rootNode, fileName));
    } else {
      allExports.push(...extractJSExports(tree.rootNode, fileName, isTypeScript));
      allImports.push(...extractJSImports(tree.rootNode, fileName));
    }

    tree.delete();
    parser.delete();
  }

  const result = {
    module: moduleName,
    language: lang,
    exports: allExports,
    imports: allImports,
    export_count: allExports.length,
  };

  console.log(JSON.stringify(result, null, 2));
}

main().catch(err => {
  console.log(JSON.stringify({
    error: `Unexpected error: ${err.message}`,
    module: moduleName,
    language: lang,
    exports: [],
    imports: [],
    export_count: 0,
  }, null, 2));
  process.exit(1);
});
