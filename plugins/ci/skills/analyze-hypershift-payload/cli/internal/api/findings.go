package api

import (
	"fmt"
	"net/url"
	"slices"
	"strings"
	"unicode"
)

// ValidateAgainst checks the findings' target, failed blocking job coverage,
// and citations against the supplied snapshot. All checks run offline.
func (f Findings) ValidateAgainst(s Snapshot) error {
	if err := validateTargetSnapshot(s.Target); err != nil {
		return err
	}
	if err := validateFindingsTag(f.Tag, s.Target.Tag); err != nil {
		return err
	}
	if err := validateJobsList(f.Jobs, s.Target.Tag); err != nil {
		return err
	}

	required := failedBlockingJobs(s.Target.Jobs)
	reported := map[string]bool{}
	refs := referencesIn(s)
	for _, finding := range f.Jobs {
		if err := validateFailedBlockingJob(finding.Job, required); err != nil {
			return err
		}
		if err := validateUniqueFinding(finding.Job, reported); err != nil {
			return err
		}
		if err := validateExplanation(finding); err != nil {
			return err
		}
		if err := validateCitations(finding, refs.evidence); err != nil {
			return fmt.Errorf("%s: %w", finding.Job, err)
		}
		if err := validateCandidatePRs(finding.CandidatePRs, refs.pullRequests); err != nil {
			return fmt.Errorf("%s: %w", finding.Job, err)
		}
		reported[finding.Job] = true
	}
	return validateJobCoverage(s.Target.Jobs, reported)
}

func validateTargetSnapshot(target Payload) error {
	if target.Tag == "" || target.URL == "" || target.Phase == "" || target.Jobs == nil {
		return fmt.Errorf("incomplete target snapshot")
	}
	return nil
}

func validateFindingsTag(tag, target string) error {
	if tag != target {
		return fmt.Errorf("findings must specify target %q and a jobs list", target)
	}
	return nil
}

func validateJobsList(jobs []Finding, target string) error {
	if jobs == nil {
		return fmt.Errorf("findings must specify target %q and a jobs list", target)
	}
	return nil
}

func failedBlockingJobs(jobs []Job) map[string]bool {
	required := map[string]bool{}
	for _, j := range jobs {
		if j.FailedBlocking() {
			required[j.Name] = true
		}
	}
	return required
}

func validateFailedBlockingJob(job string, required map[string]bool) error {
	if !required[job] {
		return fmt.Errorf("unexpected or duplicate finding for %q", job)
	}
	return nil
}

func validateUniqueFinding(job string, reported map[string]bool) error {
	if reported[job] {
		return fmt.Errorf("unexpected or duplicate finding for %q", job)
	}
	return nil
}

func validateJobCoverage(jobs []Job, reported map[string]bool) error {
	for _, j := range jobs {
		if j.FailedBlocking() && !reported[j.Name] {
			return fmt.Errorf("missing finding for %s", j.Name)
		}
	}
	return nil
}

func validateExplanation(f Finding) error {
	if strings.TrimSpace(f.Explanation) == "" {
		return fmt.Errorf("%s needs an explanation", f.Job)
	}
	return nil
}

type snapshotReferences struct {
	evidence     map[string]bool
	pullRequests map[string]bool
}

func referencesIn(s Snapshot) snapshotReferences {
	refs := snapshotReferences{evidence: map[string]bool{}, pullRequests: map[string]bool{}}
	for _, p := range slices.Concat([]Payload{s.Target}, s.History) {
		refs.evidence[p.URL] = true
		for _, j := range p.Jobs {
			for _, a := range j.Attempts {
				refs.evidence[a.URL] = true
				for _, art := range a.JUnit {
					refs.evidence[art.URL] = true
				}
			}
		}
		if p.Comparison != nil {
			for _, pr := range p.Comparison.PullRequests {
				refs.pullRequests[pr.URL] = true
			}
		}
	}
	return refs
}

func validateCitations(f Finding, observed map[string]bool) error {
	if err := validateCitationPresence(f); err != nil {
		return err
	}
	cited := map[string]bool{}
	for _, ref := range f.Evidence {
		if err := validateSnapshotCitation(ref, observed); err != nil {
			return err
		}
		cited[ref] = true
	}
	for _, source := range f.SupplementalEvidence {
		if err := validateSupplementalURL(source.URL); err != nil {
			return err
		}
		if err := validateCaption(source); err != nil {
			return err
		}
		if err := validateUniqueCitation(source.URL, cited); err != nil {
			return err
		}
		cited[source.URL] = true
	}
	return nil
}

func validateCitationPresence(f Finding) error {
	if len(f.Evidence)+len(f.SupplementalEvidence) == 0 {
		return fmt.Errorf("at least one evidence citation is required")
	}
	return nil
}

func validateSnapshotCitation(ref string, observed map[string]bool) error {
	if ref == "" || !observed[ref] {
		return fmt.Errorf("unknown evidence %q", ref)
	}
	return nil
}

func validateSupplementalURL(raw string) error {
	u, err := url.Parse(raw)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" || strings.ContainsFunc(raw, unicode.IsSpace) {
		return fmt.Errorf("supplemental evidence needs an absolute HTTP(S) URL, got %q", raw)
	}
	return nil
}

func validateCaption(source SupplementalEvidence) error {
	if strings.TrimSpace(source.Caption) == "" {
		return fmt.Errorf("supplemental evidence %q needs a caption", source.URL)
	}
	return nil
}

func validateUniqueCitation(ref string, cited map[string]bool) error {
	if cited[ref] {
		return fmt.Errorf("duplicate citation %q", ref)
	}
	return nil
}

func validateCandidatePRs(refs []string, known map[string]bool) error {
	for _, ref := range refs {
		if ref == "" || !known[ref] {
			return fmt.Errorf("unknown candidate PR %q", ref)
		}
	}
	return nil
}
