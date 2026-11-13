// Inventory deprecated declarations and candidate identifiers for gate review.
// This does not resolve identifier bindings or decide a gate verdict.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type declaration struct {
	Name, File, Package, Kind, Receiver, Doc string
	Line                                     int
}

type use struct {
	Name, File string
	Line       int
}

type inventory struct {
	Module          string
	DependencyRoots []string
	DependencyFiles int
	SourceFiles     int
	Declarations    []declaration
	Candidates      []use
}

var deprecated = regexp.MustCompile(`(?i)\bdeprecated\b`)

func main() {
	if len(os.Args) < 3 {
		fail(fmt.Errorf("usage: deprecation-scan <module-directory> <dependency-source-directory>..."))
	}
	root, err := filepath.Abs(os.Args[1])
	fail(err)
	result := inventory{Module: root, Declarations: []declaration{}, Candidates: []use{}}
	names := map[string]bool{}
	fset := token.NewFileSet()
	for _, argument := range os.Args[2:] {
		dependency, err := filepath.Abs(argument)
		fail(err)
		result.DependencyRoots = append(result.DependencyRoots, dependency)
		fail(filepath.WalkDir(dependency, func(path string, entry fs.DirEntry, err error) error {
			if err != nil || entry.IsDir() || !strings.HasSuffix(path, ".go") {
				return err
			}
			file, err := parser.ParseFile(fset, path, nil, parser.ParseComments|parser.SkipObjectResolution)
			if err != nil {
				return err
			}
			result.DependencyFiles++
			attached := map[*ast.CommentGroup]bool{}
			add := func(name, kind, receiver string, pos token.Pos, groups ...*ast.CommentGroup) {
				for _, group := range groups {
					if group == nil || !deprecated.MatchString(group.Text()) {
						continue
					}
					attached[group] = true
					result.Declarations = append(result.Declarations, declaration{
						Name: name, File: path, Package: file.Name.Name, Kind: kind,
						Receiver: receiver, Doc: group.Text(), Line: fset.Position(pos).Line,
					})
					if name != "" {
						names[name] = true
					}
				}
			}
			ast.Inspect(file, func(node ast.Node) bool {
				switch node := node.(type) {
				case *ast.FuncDecl:
					receiver := ""
					if node.Recv != nil && len(node.Recv.List) != 0 {
						receiver = typestring(node.Recv.List[0].Type)
					}
					add(node.Name.Name, "func", receiver, node.Name.Pos(), node.Doc)
				case *ast.GenDecl:
					for _, spec := range node.Specs {
						switch spec := spec.(type) {
						case *ast.TypeSpec:
							add(spec.Name.Name, "type", "", spec.Name.Pos(), node.Doc, spec.Doc, spec.Comment)
						case *ast.ValueSpec:
							for _, name := range spec.Names {
								add(name.Name, node.Tok.String(), "", name.Pos(), node.Doc, spec.Doc, spec.Comment)
							}
						}
					}
				case *ast.Field:
					for _, name := range node.Names {
						add(name.Name, "field-or-interface-method", "", name.Pos(), node.Doc, node.Comment)
					}
				}
				return true
			})
			// Retain comments without a named declaration for manual resolution,
			// including embedded fields. Do not silently discard parser gaps.
			for _, group := range file.Comments {
				if !attached[group] && deprecated.MatchString(group.Text()) {
					add("", "unbound-comment", "", group.Pos(), group)
				}
			}
			return nil
		}))
	}
	if result.DependencyFiles == 0 {
		fail(fmt.Errorf("no dependency Go source files found"))
	}
	fail(filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			if path != root {
				if entry.Name() == "vendor" || strings.HasPrefix(entry.Name(), ".") {
					return filepath.SkipDir
				}
				if _, err := os.Stat(filepath.Join(path, "go.mod")); err == nil {
					return filepath.SkipDir
				} else if !os.IsNotExist(err) {
					return err
				}
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		file, err := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if err != nil {
			return err
		}
		result.SourceFiles++
		ast.Inspect(file, func(node ast.Node) bool {
			if identifier, ok := node.(*ast.Ident); ok && names[identifier.Name] {
				result.Candidates = append(result.Candidates, use{identifier.Name, path, fset.Position(identifier.Pos()).Line})
			}
			return true
		})
		return nil
	}))
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	fail(encoder.Encode(result))
}

func typestring(expr ast.Expr) string {
	switch expr := expr.(type) {
	case *ast.Ident:
		return expr.Name
	case *ast.StarExpr:
		return "*" + typestring(expr.X)
	case *ast.IndexExpr:
		return typestring(expr.X)
	case *ast.IndexListExpr:
		return typestring(expr.X)
	}
	return ""
}

func fail(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
