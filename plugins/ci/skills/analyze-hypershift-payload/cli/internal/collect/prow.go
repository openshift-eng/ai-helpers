package collect

import (
	"context"
	"net/http"
	"net/url"
	"strings"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

// Prow reads public JUnit artifacts from the GCS location in a Prow run URL.
type Prow struct{ Client *http.Client }

func (p Prow) JUnit(ctx context.Context, run string, scope api.JUnitScope) ([]api.JUnit, []api.CollectionError) {
	var evidence []api.JUnit
	var issues []api.CollectionError
	addError := func(source, reason string) {
		issues = append(issues, api.CollectionError{URL: source, Reason: reason})
	}
	u, err := url.Parse(run)
	if err != nil || u.Host != "prow.ci.openshift.org" || !strings.HasPrefix(u.Path, "/view/gs/") {
		addError(run, "unsupported Prow artifact location")
		return nil, issues
	}
	bucket, dir, ok := strings.Cut(strings.TrimPrefix(u.Path, "/view/gs/"), "/")
	if !ok || bucket == "" || dir == "" {
		addError(run, "missing bucket or run path")
		return nil, issues
	}
	query := url.Values{
		"prefix":    {strings.TrimSuffix(dir, "/") + "/artifacts/"},
		"matchGlob": {"**/junit*.xml"},
		"fields":    {"nextPageToken,items(name)"},
	}
	found := false
	for {
		listURL := "https://storage.googleapis.com/storage/v1/b/" + url.PathEscape(bucket) + "/o?" + query.Encode()
		var page struct {
			Items         []struct{ Name string }
			NextPageToken string
		}
		if err := getJSON(ctx, p.Client, listURL, &page); err != nil {
			addError(run, "listing JUnit: "+err.Error())
			return evidence, issues
		}
		for _, object := range page.Items {
			found = true
			source := (&url.URL{Scheme: "https", Host: "storage.googleapis.com", Path: "/" + bucket + "/" + object.Name}).String()
			body, err := get(ctx, p.Client, source)
			if err != nil {
				if ctx.Err() != nil {
					return evidence, issues
				}
				addError(source, err.Error())
				continue
			}
			artifact, err := parseJUnit(body, scope)
			if err != nil {
				addError(source, err.Error())
				continue
			}
			artifact.URL = source
			evidence = append(evidence, artifact)
		}
		if page.NextPageToken == "" {
			break
		}
		query.Set("pageToken", page.NextPageToken)
	}
	if !found {
		addError(run, "no JUnit files found")
	}
	return evidence, issues
}
