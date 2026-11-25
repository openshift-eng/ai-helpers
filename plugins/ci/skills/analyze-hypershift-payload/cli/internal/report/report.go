// Package report renders validated payload findings and their snapshot offline.
package report

import (
	_ "embed"
	"html/template"
	"io"
	"strings"
	"unicode/utf8"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

//go:embed report.html.tmpl
var html string

var page = template.Must(template.New("report").Funcs(template.FuncMap{
	"foldExcerpt": foldExcerpt,
}).Parse(html))

func foldExcerpt(excerpt string) bool {
	return strings.Count(strings.TrimSuffix(excerpt, "\n"), "\n") >= 4 || utf8.RuneCountInString(excerpt) > 400
}

// Render writes a self-contained HTML report without external assets.
func Render(w io.Writer, r api.Report) error { return page.Execute(w, r) }
