**Runtime result.**

```
--- Summary: submariner/release-0.24 ---
Fix branch: fix-0.24-cves-2026-10-16
Fixed: 1 pkgs / 30 CVEs · Ignored: 0 · Needs Review: 2 · Outstanding: 36 · Run time: 1324s
FIXED: golang.org/x/net v0.60.0 for GO-2026-6603 ... (5 CVEs)
NEEDS_REVIEW: stdlib — build image has Go 1.26.8, fix needs 1.26.9 (update build image)
NEEDS_REVIEW: 36 CVE(s) still present after fixes

(1 commit — see Commits: below)
Commits:
2716c2ff Bump x/net for CVEs

NOTE: 36 CVE/package/location tuple(s) remain — PR title reflects a partial fix.
PR command:
git push fork fix-0.24-cves-2026-10-16 && \
gh pr create \
  --title Partial\ CVE\ fix\ in\ release-0.24\ \(36\ unresolved\) \
  --body See\ commit\ message\ for\ details. \
  --base release-0.24 \
  --head example:fix-0.24-cves-2026-10-16 \
  --assignee "@me"
exit=2
```

**Evidence.**

Compiled Go binary coverage is unverified.

All 36 outstanding CVE/package/location tuples are `stdlib go1.26.8`. The initial scan distinguishes two fix tiers:
- 5 advisories (GO-2026-6603, GO-2026-6610, GO-2026-6611, GO-2026-6612, GO-2026-6617) with FIXED-IN `1.26.9` — 20 tuples across 4 binaries
- 4 advisories (GO-2026-6605, GO-2026-6607, GO-2026-6608, GO-2026-6613) with FIXED-IN `1.27.2` only — 16 tuples across 4 binaries

**Next actions.**

1. **stdlib CVEs fixable within Go 1.26.x (20 tuples / 5 advisories including Critical GO-2026-6612)**
   - **Action:** Bump Go to 1.26.9 in the Shipyard dapper-base image for `release-0.24`, then publish `quay.io/submariner/shipyard-dapper-base:release-0.24`.
   - **Owner:** Shipyard maintainers (build image), then CVE-fix operator (rerun).
   - **Before rerun:** Updated `shipyard-dapper-base:release-0.24` image with Go 1.26.9 published to quay.io.
   - **Verification:** pending.

2. **stdlib CVEs requiring Go 1.27.x (16 tuples / 4 advisories, all High)**
   - **Action:** Investigate whether Go 1.26.10+ backports exist for GO-2026-6605, GO-2026-6607, GO-2026-6608, GO-2026-6613; if not, the published fix (1.27.2) is blocked by Go minor guard on this release branch — team decision needed on Go minor upgrade vs. accepting these on `release-0.24`.
   - **Owner:** Submariner maintainers (policy decision), Shipyard maintainers (image build if approved).
   - **Before rerun:** Team decision on Go minor upgrade policy for `release-0.24`; if approved, updated build image with Go 1.27.2+.
   - **Verification:** pending.
