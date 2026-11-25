package collect

import (
	"context"
	"fmt"
	"maps"
	"net/http"
	"net/url"
	"regexp"
	"slices"
	"strings"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

const controller = "https://hcp.releases.ci.openshift.org"
const stream = "/releasestream/hypershift"

// Controller translates the HyperShift stream's REST responses into observations.
type Controller struct{ Client *http.Client }

func (c Controller) Tags(ctx context.Context) ([]string, error) {
	var tags struct{ Tags []struct{ Name string } }
	if err := getJSON(ctx, c.Client, controller+"/api/v1"+stream+"/tags", &tags); err != nil {
		return nil, err
	}
	names := make([]string, 0, len(tags.Tags))
	for _, t := range tags.Tags {
		names = append(names, t.Name)
	}
	return names, nil
}

type run struct {
	State               string
	URL                 string
	PreviousAttemptURLs []string
}

type changelog struct {
	UpdatedImages []struct {
		Commits []struct{ PullURL, Subject string }
	}
}

var operatorVersion = regexp.MustCompile(`^([0-9]+\.[0-9]+\.[0-9]+)-`)
var testedOCP = regexp.MustCompile(`^release-([0-9]+\.[0-9]+)-`)

func releasePath(tag string) string { return stream + "/release/" + url.PathEscape(tag) }

func (c Controller) Payload(ctx context.Context, tag string) (api.Payload, error) {
	path := releasePath(tag)
	var release struct {
		Name, Phase string
		Results     struct{ BlockingJobs, InformingJobs map[string]run }
	}
	if err := getJSON(ctx, c.Client, controller+"/api/v1"+path, &release); err != nil {
		return api.Payload{}, err
	}
	if release.Name != tag || release.Phase == "" || release.Results.BlockingJobs == nil {
		return api.Payload{}, fmt.Errorf("incomplete or mismatched controller response for %s", tag)
	}
	version := operatorVersion.FindStringSubmatch(tag)
	if version == nil {
		return api.Payload{}, fmt.Errorf("missing operator version in %s", tag)
	}
	jobs := append(normalizeJobs(release.Results.BlockingJobs, true), normalizeJobs(release.Results.InformingJobs, false)...)
	for _, job := range jobs {
		if strings.TrimSpace(job.State) == "" {
			return api.Payload{}, fmt.Errorf("payload %s: missing state for job %s", tag, job.Name)
		}
	}
	return api.Payload{Tag: tag, OperatorVersion: version[1], URL: controller + path, Phase: release.Phase, Jobs: jobs}, nil
}

func (c Controller) Compare(ctx context.Context, from, to string) (*api.Comparison, error) {
	address := controller + "/api/v1" + releasePath(to) + "?from=" + url.QueryEscape(from)
	var release struct {
		Name          string
		ChangeLogJSON *changelog
	}
	if err := getJSON(ctx, c.Client, address, &release); err != nil {
		return nil, err
	}
	if release.Name != to || release.ChangeLogJSON == nil {
		return nil, fmt.Errorf("missing changelog for %s", to)
	}
	return &api.Comparison{FromTag: from, PullRequests: release.ChangeLogJSON.pullRequests()}, nil
}

func normalizeJobs(runs map[string]run, blocking bool) []api.Job {
	jobs := make([]api.Job, 0, len(runs))
	for _, name := range slices.Sorted(maps.Keys(runs)) {
		r := runs[name]
		j := api.Job{Name: name, State: r.State, Blocking: blocking, Attempts: []api.Attempt{}}
		if v := testedOCP.FindStringSubmatch(name); v != nil {
			j.TestedOCP = v[1]
		}
		for _, runURL := range append(r.PreviousAttemptURLs, r.URL) {
			if runURL != "" {
				j.Attempts = append(j.Attempts, api.Attempt{URL: runURL})
			}
		}
		jobs = append(jobs, j)
	}
	return jobs
}

func (c changelog) pullRequests() []api.PullRequest {
	prs := []api.PullRequest{}
	seen := map[string]bool{}
	for _, image := range c.UpdatedImages {
		for _, commit := range image.Commits {
			if commit.PullURL != "" && !seen[commit.PullURL] {
				prs = append(prs, api.PullRequest{URL: commit.PullURL, Subject: commit.Subject})
				seen[commit.PullURL] = true
			}
		}
	}
	return prs
}
