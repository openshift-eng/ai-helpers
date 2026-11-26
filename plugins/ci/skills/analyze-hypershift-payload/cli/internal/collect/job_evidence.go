package collect

import (
	"context"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

// Artifacts reads the requested JUnit outcomes for one attempt. Partial reads
// return both usable artifacts and source-specific collection errors.
type Artifacts interface {
	JUnit(ctx context.Context, run string, scope api.JUnitScope) ([]api.JUnit, []api.CollectionError)
}

type jobEvidence struct {
	job        *api.Job
	payloadURL string
	scope      api.JUnitScope
}

// Selection depends only on controller observations. Match historical jobs by
// verification name even when their state or blocking role changed.
func planJobEvidence(s *api.Snapshot) []jobEvidence {
	var requests []jobEvidence
	failedBlocking := make(map[string]bool)
	for i := range s.Target.Jobs {
		job := &s.Target.Jobs[i]
		scope := api.NotRequested
		if job.State == "Failed" {
			scope = api.FailuresOnly
		}
		requests = append(requests, jobEvidence{job, s.Target.URL, scope})
		if job.FailedBlocking() {
			failedBlocking[job.Name] = true
		}
	}
	for _, previous := range s.History {
		for i := range previous.Jobs {
			job := &previous.Jobs[i]
			scope := api.NotRequested
			if failedBlocking[job.Name] {
				scope = api.AllOutcomes
			}
			requests = append(requests, jobEvidence{job, previous.URL, scope})
		}
	}
	return requests
}

func (r jobEvidence) collect(ctx context.Context, source Artifacts) ([]api.CollectionError, error) {
	if len(r.job.Attempts) == 0 && r.scope != api.NotRequested {
		return []api.CollectionError{{URL: r.payloadURL, Reason: "missing Prow run for " + r.job.Name}}, nil
	}
	var issues []api.CollectionError
	for i := range r.job.Attempts {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		attempt := &r.job.Attempts[i]
		attempt.JUnitScope = r.scope
		if r.scope == api.NotRequested {
			continue
		}
		evidence, errs := source.JUnit(ctx, attempt.URL, r.scope)
		attempt.JUnit = evidence
		issues = append(issues, errs...)
	}
	return issues, ctx.Err()
}
