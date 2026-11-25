package collect

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/history"
)

type transport func(*http.Request) (*http.Response, error)

func (f transport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

// Follow the same job across a rejection and an acceptance. A missing JUnit
// file, a skip, and an explicit pass convey different evidence.
func TestCollectTargetAndPredecessorEvidence(t *testing.T) {
	const tag = "0.1.87-0036"
	const previous = "0.1.87-0033"
	const accepted = "0.1.87-0030"
	const origin = "https://prow.ci.openshift.org/view/gs/results/"
	const release = "/api/v1/releasestream/hypershift/release/"
	const removed = "This file contained potentially sensitive information and has been removed."
	const aks = "release-5.1-e2e-aks"
	responses := map[string]string{
		"/api/v1/releasestream/hypershift/tags": fixtureJSON(t, tagListFixture{
			Tags: []namedItemFixture{{Name: "newer"}, {Name: tag}, {Name: previous}, {Name: accepted}},
		}),
		release + tag: fixtureJSON(t, releaseFixture{
			Name: tag, Phase: "Rejected",
			Results: jobResultsFixture{Blocking: map[string]jobFixture{
				aks: {State: "Failed", URL: origin + "2", PreviousAttemptURLs: []string{origin + "1"}},
			}},
		}),
		release + previous: fixtureJSON(t, releaseFixture{
			Name: previous, Phase: "Rejected",
			Results: jobResultsFixture{Blocking: map[string]jobFixture{
				aks:         {State: "Failed", URL: origin + "previous", PreviousAttemptURLs: []string{origin + "redacted"}},
				"unrelated": {State: "Failed", URL: origin + "unrelated"},
			}},
		}),
		release + accepted: fixtureJSON(t, releaseFixture{
			Name: accepted, Phase: "Accepted",
			Results: jobResultsFixture{
				Blocking:  map[string]jobFixture{"other": {State: "Succeeded"}},
				Informing: map[string]jobFixture{aks: {State: "Succeeded", URL: origin + "accepted"}},
			},
		}),
		release + tag + "?from=" + previous:      fixtureFile(t, "target-changelog.json"),
		release + previous + "?from=" + accepted: fixtureFile(t, "previous-changelog.json"),
		"/results/1/artifacts/junit.xml":         removed,
		"/results/2/artifacts/junit.xml":         fixtureFile(t, "target.xml"),
		"/results/redacted/artifacts/junit.xml":  removed,
		"/results/previous/artifacts/junit.xml":  fixtureFile(t, "previous.xml"),
		"/results/accepted/artifacts/junit.xml":  fixtureFile(t, "accepted.xml"),
	}
	client := &http.Client{Transport: transport(func(r *http.Request) (*http.Response, error) {
		body, ok := responses[r.URL.RequestURI()]
		if r.URL.Path == "/storage/v1/b/results/o" {
			body = fixtureJSON(t, objectListFixture{
				Items: []namedItemFixture{{Name: r.URL.Query().Get("prefix") + "junit.xml"}},
			})
			ok = true
		}
		if !ok {
			t.Fatalf("unexpected collection request %s", r.URL)
		}
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body))}, nil
	})}
	policy := history.Policy{MaxPredecessors: 19}
	s, err := Snapshot(t.Context(), Controller{client}, Prow{client}, tag, policy.NeedsPredecessor)
	if err != nil {
		t.Fatal(err)
	}
	change := s.Target.Comparison
	if change == nil || change.FromTag != previous || len(change.PullRequests) != 1 || change.PullRequests[0].URL != "https://example.org/pr/1" {
		t.Fatalf("target changelog: %+v", change)
	}
	job := s.Target.Jobs[0]
	if job.TestedOCP != "5.1" || s.Target.OperatorVersion != "0.1.87" {
		t.Fatalf("incorrect version or job: %+v", job)
	}
	var unavailable []string
	for _, issue := range s.CollectionErrors {
		unavailable = append(unavailable, issue.URL)
	}
	slices.Sort(unavailable)
	if !slices.Equal(unavailable, []string{
		"https://storage.googleapis.com/results/1/artifacts/junit.xml",
		"https://storage.googleapis.com/results/redacted/artifacts/junit.xml",
	}) {
		t.Fatalf("unavailable JUnit sources: %v", unavailable)
	}
	if len(job.Attempts) != 2 || len(job.Attempts[0].JUnit) != 0 {
		t.Fatalf("target retry evidence: %+v", job.Attempts)
	}
	target := job.Attempts[1].JUnit[0]
	azure := api.TestCase{Suite: "e2e", Class: "azure", Name: "setup"}
	want := []api.TestFailure{{TestCase: azure, Detail: "quota exceeded"}}
	if !slices.Equal(target.Failures, want) || len(target.Passed) != 0 {
		t.Fatalf("target evidence: %+v", target)
	}
	prior := s.History[0].Jobs[0].Attempts
	if job.Attempts[0].JUnitScope != api.FailuresOnly || prior[0].JUnitScope != api.AllOutcomes || s.History[0].Jobs[1].Attempts[0].JUnitScope != api.NotRequested {
		t.Fatal("requested scope must distinguish unreadable artifacts from unselected attempts")
	}
	if len(prior) != 2 || len(prior[0].JUnit) != 0 || !slices.Equal(prior[1].JUnit[0].Failures, want) {
		t.Fatalf("predecessor retry evidence: %+v", prior)
	}
	baseline := s.History[1].Jobs[1].Attempts[0].JUnit[0]
	other := api.TestCase{Suite: "e2e", Class: "other", Name: "setup"}
	if !slices.Equal(baseline.Passed, []api.TestCase{azure}) || !slices.Equal(baseline.Skipped, []api.TestCase{other}) {
		t.Fatalf("accepted predecessor outcomes: %+v", baseline)
	}
}

func TestCancellationInterruptsCollection(t *testing.T) {
	ctx, cancel := context.WithCancel(t.Context())
	defer cancel()
	client := &http.Client{Transport: transport(func(r *http.Request) (*http.Response, error) {
		cancel()
		if r.Context().Err() == nil {
			t.Fatal("request outlived collection context")
		}
		return nil, r.Context().Err()
	})}
	policy := history.Policy{MaxPredecessors: 1}
	_, err := Snapshot(ctx, Controller{client}, Prow{client}, "target", policy.NeedsPredecessor)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("expected cancellation, got %v", err)
	}
}

type namedItemFixture struct {
	Name string `json:"name"`
}

type tagListFixture struct {
	Tags []namedItemFixture `json:"tags"`
}

type objectListFixture struct {
	Items []namedItemFixture `json:"items"`
}

type releaseFixture struct {
	Name    string            `json:"name"`
	Phase   string            `json:"phase"`
	Results jobResultsFixture `json:"results"`
}

type jobResultsFixture struct {
	Blocking  map[string]jobFixture `json:"blockingJobs"`
	Informing map[string]jobFixture `json:"informingJobs,omitempty"`
}

type jobFixture struct {
	State               string   `json:"state"`
	URL                 string   `json:"url,omitempty"`
	PreviousAttemptURLs []string `json:"previousAttemptURLs,omitempty"`
}

func fixtureJSON(t *testing.T, value any) string {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

func fixtureFile(t *testing.T, name string) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}
