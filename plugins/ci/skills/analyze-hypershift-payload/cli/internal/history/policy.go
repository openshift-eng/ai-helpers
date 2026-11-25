// Package history defines when HyperShift analysis needs an older payload.
package history

import (
	"slices"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
)

// Policy bounds the number of predecessors, excluding the target.
type Policy struct {
	MaxPredecessors int
}

// NeedsPredecessor starts a walk for a failed blocking job and stops at the
// first predecessor whose blocking jobs all succeeded, or at the limit.
func (p Policy) NeedsPredecessor(s api.Snapshot) bool {
	if len(s.History) >= p.MaxPredecessors {
		return false
	}
	if len(s.History) == 0 {
		return slices.ContainsFunc(s.Target.Jobs, api.Job.FailedBlocking)
	}
	return !s.History[len(s.History)-1].AllBlockingSucceeded()
}
