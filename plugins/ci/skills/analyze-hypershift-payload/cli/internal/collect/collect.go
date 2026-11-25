// Package collect assembles an offline snapshot from release and job evidence.
package collect

import (
	"context"
	"fmt"
	"slices"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

// Releases provides newest-first stream membership, per-tag job observations,
// and changelogs for explicitly selected tag pairs.
type Releases interface {
	Tags(context.Context) ([]string, error)
	Payload(ctx context.Context, tag string) (api.Payload, error)
	Compare(ctx context.Context, from, to string) (*api.Comparison, error)
}

// Snapshot collects a release window and attaches the selected job evidence.
func Snapshot(ctx context.Context, releases Releases, artifacts Artifacts, tag string, needsPredecessor func(api.Snapshot) bool) (api.Snapshot, error) {
	s, err := releaseWindow(ctx, releases, tag, needsPredecessor)
	if err != nil {
		return api.Snapshot{}, err
	}
	for _, request := range planJobEvidence(&s) {
		issues, err := request.collect(ctx, artifacts)
		if err != nil {
			return api.Snapshot{}, err
		}
		s.CollectionErrors = append(s.CollectionErrors, issues...)
	}
	return s, ctx.Err()
}

// releaseWindow evaluates the policy after each observation. Only tag pairs
// inside the selected window get a comparison.
func releaseWindow(ctx context.Context, releases Releases, tag string, needsPredecessor func(api.Snapshot) bool) (api.Snapshot, error) {
	target, err := releases.Payload(ctx, tag)
	if err != nil {
		return api.Snapshot{}, err
	}
	s := api.Snapshot{Target: target, History: []api.Payload{}}
	if !needsPredecessor(s) {
		return s, nil
	}
	tags, err := releases.Tags(ctx)
	if err != nil {
		return api.Snapshot{}, err
	}
	start := slices.Index(tags, tag)
	if start < 0 {
		return api.Snapshot{}, fmt.Errorf("payload %q is absent from the HyperShift stream", tag)
	}
	newer := &s.Target
	for _, name := range tags[start+1:] {
		older, err := releases.Payload(ctx, name)
		if err != nil {
			return api.Snapshot{}, err
		}
		newer.Comparison, err = releases.Compare(ctx, older.Tag, newer.Tag)
		if err != nil {
			if ctx.Err() != nil {
				return api.Snapshot{}, ctx.Err()
			}
			s.CollectionErrors = append(s.CollectionErrors, api.CollectionError{URL: newer.URL, Reason: fmt.Sprintf("changelog from %s: %v", older.Tag, err)})
		}
		s.History = append(s.History, older)
		if !needsPredecessor(s) {
			break
		}
		newer = &s.History[len(s.History)-1]
	}
	return s, nil
}
