package collect

import (
	"bytes"
	"encoding/xml"
	"fmt"
	"strings"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

type suite struct {
	XMLName xml.Name
	Name    string  `xml:"name,attr"`
	Suites  []suite `xml:"testsuite"`
	Cases   []struct {
		Name     string         `xml:"name,attr"`
		Class    string         `xml:"classname,attr"`
		Status   string         `xml:"status,attr"`
		Skipped  *struct{}      `xml:"skipped"`
		Failures []junitProblem `xml:"failure"`
		Errors   []junitProblem `xml:"error"`
	} `xml:"testcase"`
}

type junitProblem struct {
	Message string `xml:"message,attr"`
	Body    string `xml:",chardata"`
}

func parseJUnit(data []byte, scope api.JUnitScope) (api.JUnit, error) {
	const removalNotice = "This file contained potentially sensitive information and has been removed."
	if bytes.Equal(bytes.TrimSpace(data), []byte(removalNotice)) {
		return api.JUnit{}, fmt.Errorf("JUnit removed by the artifact service")
	}
	var root suite
	if err := xml.Unmarshal(data, &root); err != nil {
		return api.JUnit{}, fmt.Errorf("unreadable JUnit: %w", err)
	}
	if root.XMLName.Local != "testsuite" && root.XMLName.Local != "testsuites" {
		return api.JUnit{}, fmt.Errorf("expected JUnit, found <%s>", root.XMLName.Local)
	}
	artifact := api.JUnit{Failures: []api.TestFailure{}}
	root.record(&artifact, scope)
	return artifact, nil
}

func (s suite) record(out *api.JUnit, scope api.JUnitScope) {
	for _, c := range s.Cases {
		test := api.TestCase{Suite: s.Name, Class: c.Class, Name: c.Name}
		problems := append(c.Failures, c.Errors...)
		switch {
		case len(problems) != 0:
			for _, problem := range problems {
				out.Failures = append(out.Failures, api.TestFailure{TestCase: test, Detail: problem.excerpt()})
			}
		case scope == api.FailuresOnly:
			continue
		case c.Skipped != nil || c.Status == "notrun" || c.Status == "skipped":
			out.Skipped = append(out.Skipped, test)
		case c.Status == "" || c.Status == "run" || c.Status == "passed":
			out.Passed = append(out.Passed, test)
		}
	}
	for _, child := range s.Suites {
		child.record(out, scope)
	}
}

func (p junitProblem) excerpt() string {
	const maxExcerpt = 4000
	detail := strings.TrimSpace(p.Message + " " + p.Body)
	if text := []rune(detail); len(text) > maxExcerpt {
		return string(text[:maxExcerpt]) + "…"
	}
	return detail
}
