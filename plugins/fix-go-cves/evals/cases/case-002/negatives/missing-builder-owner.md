The recorded run exited 2 and retained `2716c2ff` on
`fix-0.24-cves-2026-10-16`. It is a partial repair with 36 outstanding
stdlib findings and no ignored findings. The original ref was `devel`.

```text
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
```

The remaining findings were reported from four built binaries using the
release-0.24 Shipyard image with Go 1.26.8; the recorded scan lists Go 1.26.9
as their fixed version. This replay does not establish independently authenticated
native catalog coverage or validate today's remediation engine.

The remaining findings need investigation. A rerun may help. The partial publication recipe above was
printed by the recorded run; no push or PR creation has been executed here.
