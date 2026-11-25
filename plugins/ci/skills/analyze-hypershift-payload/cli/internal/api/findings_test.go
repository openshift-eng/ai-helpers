package api

import "testing"

func TestFindingsCoverFailedBlockingJobs(t *testing.T) {
	target := Payload{Tag: "target", Phase: "Rejected", URL: "https://controller/target", Jobs: []Job{
		{Name: "aks", State: "Failed", Blocking: true},
		{Name: "aws", State: "Failed", Blocking: true},
		{Name: "gcp", State: "Failed"},
	}}
	finding := func(job string) Finding {
		return Finding{Job: job, Explanation: "Cause unknown", Evidence: []string{target.URL}}
	}
	aks, aws, gcp := finding("aks"), finding("aws"), finding("gcp")
	for _, tc := range []struct {
		name      string
		f         Findings
		wantValid bool
	}{
		{"all blockers in a different order", Findings{Tag: target.Tag, Jobs: []Finding{aws, aks}}, true},
		{"different target with the same jobs", Findings{Tag: "earlier", Jobs: []Finding{aws, aks}}, false},
		{"omitted blocker", Findings{Tag: target.Tag, Jobs: []Finding{aks}}, false},
		{"duplicate blocker", Findings{Tag: target.Tag, Jobs: []Finding{aws, aks, aks}}, false},
		{"extra informing failure", Findings{Tag: target.Tag, Jobs: []Finding{aws, aks, gcp}}, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := tc.f.ValidateAgainst(Snapshot{Target: target})
			if (err == nil) != tc.wantValid {
				t.Fatalf("ValidateAgainst returned %v, want valid=%t", err, tc.wantValid)
			}
		})
	}
}

func TestFindingsRequireExplicitEmptyJobsForGreenPayload(t *testing.T) {
	s := Snapshot{Target: Payload{Tag: "green", URL: "https://controller/green", Phase: "Accepted",
		Jobs: []Job{{Name: "aks", State: "Succeeded", Blocking: true}},
	}}
	f := Findings{Tag: s.Target.Tag}
	if err := f.ValidateAgainst(s); err == nil {
		t.Fatal("accepted findings with no jobs field")
	}
	f.Jobs = []Finding{}
	if err := f.ValidateAgainst(s); err != nil {
		t.Fatal(err)
	}
}

func TestFindingCitationSources(t *testing.T) {
	const junit = "https://prow/previous/junit.xml"
	const pr = "https://github.com/openshift/hypershift/pull/1"
	run := Attempt{URL: "https://prow/previous", JUnit: []JUnit{{URL: junit}}}
	log := SupplementalEvidence{URL: "https://prow/target/build-log.txt", Caption: "Quota exhausted"}
	s := Snapshot{
		Target: Payload{Tag: "target", URL: "https://controller/target", Phase: "Rejected",
			Jobs:       []Job{{Name: "aks", State: "Failed", Blocking: true}},
			Comparison: &Comparison{FromTag: "previous", PullRequests: []PullRequest{{URL: pr}}},
		},
		History: []Payload{{Tag: "previous", Jobs: []Job{{Name: "aks", Attempts: []Attempt{run}}}}},
	}
	for _, tc := range []struct {
		name         string
		evidence     []string
		supplemental []SupplementalEvidence
		prs          []string
		wantValid    bool
	}{
		{"predecessor JUnit and changelog PR", []string{junit}, nil, []string{pr}, true},
		{"separately inspected log alone", nil, []SupplementalEvidence{log}, nil, true},
		{"external link without an observation", nil, []SupplementalEvidence{{URL: log.URL}}, nil, false},
		{"uncollected log cited as snapshot evidence", []string{log.URL}, nil, nil, false},
		{"JUnit cited as a candidate PR", []string{junit}, nil, []string{junit}, false},
		{"candidate PR alone", nil, nil, []string{pr}, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			f := Findings{Tag: s.Target.Tag, Jobs: []Finding{{
				Job: "aks", Explanation: "Quota exhausted", Evidence: tc.evidence,
				SupplementalEvidence: tc.supplemental, CandidatePRs: tc.prs,
			}}}
			err := f.ValidateAgainst(s)
			if (err == nil) != tc.wantValid {
				t.Fatalf("ValidateAgainst returned %v, want valid=%t", err, tc.wantValid)
			}
		})
	}
}
