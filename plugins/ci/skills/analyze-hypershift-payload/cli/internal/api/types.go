package api

// Snapshot contains the requested payload and the available recent comparison
// payloads in newest-first order. CollectionErrors describe unavailable evidence.
type Snapshot struct {
	Target           Payload           `json:"target"`
	History          []Payload         `json:"history"`
	CollectionErrors []CollectionError `json:"collection_errors,omitempty"`
}

// Baseline returns the nearest collected predecessor whose blocking jobs all
// succeeded. A nil result means the snapshot contains no such predecessor.
func (s Snapshot) Baseline() *Payload {
	for i := range s.History {
		if s.History[i].AllBlockingSucceeded() {
			return &s.History[i]
		}
	}
	return nil
}

// Payload is one observation from the HyperShift release controller. Jobs are
// ordered by role and name. Comparison is present only for a collected tag pair.
type Payload struct {
	Tag             string      `json:"tag"`
	URL             string      `json:"url"`
	OperatorVersion string      `json:"operator_version"`
	Phase           string      `json:"phase"`
	Jobs            []Job       `json:"jobs"`
	Comparison      *Comparison `json:"comparison,omitempty"`
}

// AllBlockingSucceeded requires at least one blocking job with an observed
// result and a succeeded state for every blocking job.
func (p Payload) AllBlockingSucceeded() bool {
	hasBlocking := false
	for _, j := range p.Jobs {
		if j.Blocking {
			hasBlocking = true
			if j.State != "Succeeded" {
				return false
			}
		}
	}
	return hasBlocking
}

// Comparison lists PRs identified in the controller's image changelog between
// FromTag and the enclosing payload. Presence alone does not establish causation.
type Comparison struct {
	FromTag      string        `json:"from_tag"`
	PullRequests []PullRequest `json:"pull_requests"`
}

// PullRequest identifies a candidate by its repository-qualified source URL.
type PullRequest struct {
	URL     string `json:"url"`
	Subject string `json:"subject"`
}

// Job preserves the controller's verification name, role and current state.
// TestedOCP is the release line identified by the job name, when available.
// Attempts list previous run URLs in controller order, followed by the current run.
type Job struct {
	Name      string    `json:"name"`
	Blocking  bool      `json:"blocking"`
	State     string    `json:"state"`
	TestedOCP string    `json:"tested_ocp,omitempty"`
	Attempts  []Attempt `json:"attempts"`
}

// FailedBlocking identifies the target jobs requiring individual findings.
func (j Job) FailedBlocking() bool { return j.Blocking && j.State == "Failed" }

// Attempt identifies one Prow run. JUnit evidence belongs to that run even
// when the controller retries the job.
type Attempt struct {
	URL        string     `json:"url"`
	JUnitScope JUnitScope `json:"junit_scope,omitempty"`
	JUnit      []JUnit    `json:"junit,omitempty"`
}

// JUnitScope records which outcomes collection requested for this attempt.
// An empty value means an older snapshot did not record scope. CollectionErrors
// can still describe missing artifacts at any requested scope.
type JUnitScope string

const (
	NotRequested JUnitScope = "not_requested"
	FailuresOnly JUnitScope = "failures_only"
	AllOutcomes  JUnitScope = "all_outcomes"
)

// JUnit identifies a readable artifact. Failed target jobs retain failures.
// Matching predecessor jobs also retain passing and skipped testcases. A
// missing testcase gives no evidence of its outcome.
type JUnit struct {
	URL      string        `json:"url"`
	Failures []TestFailure `json:"failures"`
	Passed   []TestCase    `json:"passed,omitempty"`
	Skipped  []TestCase    `json:"skipped,omitempty"`
}

// TestCase identifies an observed testcase within its artifact. Suite and
// Class are the enclosing suite name and JUnit classname when supplied.
type TestCase struct {
	Suite string `json:"suite,omitempty"`
	Class string `json:"class,omitempty"`
	Name  string `json:"name"`
}

// TestFailure records the failure or error excerpt for a testcase.
type TestFailure struct {
	TestCase
	Detail string `json:"detail"`
}

// CollectionError identifies unavailable evidence by source URL and reason.
type CollectionError struct {
	URL    string `json:"url"`
	Reason string `json:"reason"`
}

// Findings is the investigator's answer for the snapshot's target tag. Jobs is
// a required JSON array containing exactly one finding for each failed blocking
// target job. Use an empty array when there are no such jobs.
type Findings struct {
	Tag  string    `json:"tag"`
	Jobs []Finding `json:"jobs"`
}

// Finding records the investigator's diagnosis of one failed blocking job.
// Explanation must be nonblank and can use Markdown to describe the failure or
// why its cause is unknown. Supply at least one citation in Evidence or
// SupplementalEvidence. Evidence URLs must identify a payload, run or readable
// JUnit artifact in the target or its collected history. CandidatePRs must be
// PR URLs in a collected changelog. The investigator assesses causation.
type Finding struct {
	Job                  string                 `json:"job"`
	Explanation          string                 `json:"explanation"`
	Evidence             []string               `json:"evidence,omitempty"`
	SupplementalEvidence []SupplementalEvidence `json:"supplemental_evidence,omitempty"`
	CandidatePRs         []string               `json:"candidate_prs,omitempty"`
}

// SupplementalEvidence cites a separately inspected source by an absolute HTTP(S)
// URL, unique across that finding's citations. Caption is a nonblank, plain-text
// observation. Excerpt optionally quotes the source verbatim.
type SupplementalEvidence struct {
	URL     string `json:"url"`
	Caption string `json:"caption"`
	Excerpt string `json:"excerpt,omitempty"`
}

// Report binds the observations and validated judgments used by all renderers.
type Report struct {
	Snapshot Snapshot
	Findings Findings
}
