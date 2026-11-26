package collect

import (
	"context"
	"fmt"
	"slices"
	"testing"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/history"
)

// Track source reads so early stopping is verified at the I/O boundary.
type releaseStream struct {
	payloads []api.Payload
	reads    []string
	pairs    [][2]string
}

func (r *releaseStream) Tags(context.Context) ([]string, error) {
	var tags []string
	for _, p := range r.payloads {
		tags = append(tags, p.Tag)
	}
	return tags, nil
}

func (r *releaseStream) Payload(_ context.Context, tag string) (api.Payload, error) {
	r.reads = append(r.reads, tag)
	for _, payload := range r.payloads {
		if payload.Tag == tag {
			return payload, nil
		}
	}
	return api.Payload{}, fmt.Errorf("unexpected payload %q", tag)
}

func (r *releaseStream) Compare(_ context.Context, from, to string) (*api.Comparison, error) {
	r.pairs = append(r.pairs, [2]string{from, to})
	return &api.Comparison{FromTag: from}, nil
}

func TestHistoryWalk(t *testing.T) {
	failed := api.Job{Blocking: true, State: "Failed"}
	passed := api.Job{Blocking: true, State: "Succeeded"}
	stream := []api.Payload{
		{Tag: "red", Jobs: []api.Job{failed}},
		{Tag: "force-accepted", Phase: "Accepted", Jobs: []api.Job{passed, failed}},
		{Tag: "no-blockers", Jobs: []api.Job{{State: "Succeeded"}}},
		{Tag: "pending", Jobs: []api.Job{{Blocking: true, State: "Pending"}}},
		{Tag: "green", Jobs: []api.Job{passed, {State: "Failed"}}},
		{Tag: "older", Jobs: []api.Job{passed}},
	}
	for _, tc := range []struct {
		name     string
		tags     []api.Payload
		max      int
		want     []string
		baseline string
	}{
		{"first all-green predecessor", stream, 19, []string{"red", "force-accepted", "no-blockers", "pending", "green"}, "green"},
		{"cap excludes target", stream, 1, []string{"red", "force-accepted"}, ""},
		{"zero cap", stream, 0, []string{"red"}, ""},
		{"history exhausted", stream[:2], 19, []string{"red", "force-accepted"}, ""},
		{"green target with informing failure", stream[4:], 19, []string{"green"}, ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			source := &releaseStream{payloads: tc.tags}
			policy := history.Policy{MaxPredecessors: tc.max}
			s, err := releaseWindow(t.Context(), source, tc.tags[0].Tag, policy.NeedsPredecessor)
			if err != nil {
				t.Fatal(err)
			}
			if !slices.Equal(source.reads, tc.want) {
				t.Fatalf("read %v, want %v", source.reads, tc.want)
			}
			var pairs [][2]string
			for i := 1; i < len(tc.want); i++ {
				pairs = append(pairs, [2]string{tc.want[i], tc.want[i-1]})
			}
			if !slices.Equal(source.pairs, pairs) {
				t.Fatalf("compared %v, want %v", source.pairs, pairs)
			}
			var baseline string
			if p := s.Baseline(); p != nil {
				baseline = p.Tag
			}
			if baseline != tc.baseline {
				t.Fatalf("baseline %q, want %q", baseline, tc.baseline)
			}
		})
	}
}
