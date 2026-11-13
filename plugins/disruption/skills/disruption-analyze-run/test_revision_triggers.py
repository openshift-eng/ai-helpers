"""Tests for revision_triggers.py — revision-status configmaps, trigger events, and run comparison."""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

import pytest

from revision_triggers import (
    analyze_run,
    clean_reason,
    compare_runs,
    format_text,
    load_items,
    main,
    operator_version_changes,
    revision_statuses,
    revision_triggers,
    upgrade_markers,
)

KAS_OP_NS = "openshift-kube-apiserver-operator"


def _event(reason, message, ts, namespace=KAS_OP_NS, component="kube-apiserver-operator-revisioncontroller",
           first=None, count=1):
    """Event shaped like gather-extra events.json items."""
    return {
        "apiVersion": "v1", "kind": "Event", "count": count, "eventTime": None,
        "firstTimestamp": first or ts, "lastTimestamp": ts,
        "involvedObject": {"kind": "Deployment", "namespace": namespace},
        "metadata": {"namespace": namespace},
        "reason": reason, "message": message,
        "source": {"component": component},
    }


def _status_cm(revision, created, reason, namespace="openshift-kube-apiserver"):
    return {
        "metadata": {"name": "revision-status-%d" % revision, "namespace": namespace,
                     "creationTimestamp": created},
        "data": {"reason": reason, "revision": str(revision)},
    }


def _version(name, old, new, ts):
    return _event("OperatorVersionChanged",
                  'clusteroperator/kube-apiserver version "%s" changed from "%s" to "%s"' % (name, old, new),
                  ts, component="kube-apiserver-operator-status-controller-statussyncer_kube-apiserver")


# Modeled on run 2119937168964063232: install, upgrade rollout (revision 9), then
# an extra rollout (revision 10) when the auth operator rewrites its webhook secret.
AFTER_EVENTS = [
    _version("raw-internal", "", "5.1.0-0.ci-2026-11-09-112923", "2026-11-10T00:09:08Z"),
    _version("operator", "", "5.1.0-0.ci-2026-11-09-112923", "2026-11-10T00:14:42Z"),
    _event("StartingNewRevision", 'new revision 8 triggered by "required configmap/config has changed"',
           "2026-11-10T00:24:14Z"),
    _event("RevisionTriggered", 'new revision 8 triggered by "required configmap/config has changed"',
           "2026-11-10T00:24:46Z"),
    _version("raw-internal", "5.1.0-0.ci-2026-11-09-112923", "5.1.0-0.ci-2026-11-09-232923",
             "2026-11-10T00:49:11Z"),
    _event("ConfigMapUpdated", "Updated ConfigMap/kube-apiserver-pod -n openshift-kube-apiserver: "
           "cause by changes in data.pod.yaml,data.version", "2026-11-10T00:49:17Z",
           component="kube-apiserver-operator-target-config-controller-targetconfigcontroller"),
    _event("StartingNewRevision",
           'new revision 9 triggered by "required configmap/kube-apiserver-pod has changed"',
           "2026-11-10T00:49:17Z"),
    _event("RevisionTriggered",
           'new revision 9 triggered by "required configmap/kube-apiserver-pod has changed"',
           "2026-11-10T00:49:53Z"),
    _version("operator", "5.1.0-0.ci-2026-11-09-112923", "5.1.0-0.ci-2026-11-09-232923",
             "2026-11-10T00:59:28Z"),
    _event("SecretUpdated", "Updated Secret/webhook-authentication-integrated-oauth -n openshift-config "
           "because it changed", "2026-11-10T01:08:29Z", namespace="openshift-authentication-operator",
           component="oauth-apiserver-webhook-authenticator-controller-webhookauthenticatorcontroller"),
    _event("SecretUpdated", "Updated Secret/webhook-authenticator -n openshift-kube-apiserver because it changed",
           "2026-11-10T01:08:29Z",
           component="kube-apiserver-operator-resource-sync-controller-resourcesynccontroller"),
    # The revision controller's own copy is an effect, not a trigger.
    _event("SecretCreated", "Created Secret/webhook-authenticator-10 -n openshift-kube-apiserver because it was missing",
           "2026-11-10T01:08:30Z"),
    _event("StartingNewRevision",
           'new revision 10 triggered by "optional secret/webhook-authenticator has changed"',
           "2026-11-10T01:08:29Z"),
    _event("RevisionTriggered",
           'new revision 10 triggered by "optional secret/webhook-authenticator has changed"',
           "2026-11-10T01:08:56Z"),
    # Unrelated write a few seconds later, and a different operator's revision.
    _event("ConfigMapUpdated", "Updated ConfigMap/config -n openshift-apiserver", "2026-11-10T01:08:33Z",
           namespace="openshift-apiserver-operator", component="openshift-apiserver-operator"),
    _event("StartingNewRevision", 'new revision 9 triggered by "required configmap/etcd-pod has changed"',
           "2026-11-10T00:30:00Z", namespace="openshift-etcd-operator"),
]

AFTER_CONFIGMAPS = [
    _status_cm(8, "2026-11-10T00:24:16Z", "required configmap/config has changed"),
    _status_cm(9, "2026-11-10T00:49:19Z", "required configmap/kube-apiserver-pod has changed"),
    _status_cm(10, "2026-11-10T01:08:30Z", "optional secret/webhook-authenticator has changed"),
    _status_cm(4, "2026-11-10T00:20:00Z", "required configmap/etcd-pod has changed", namespace="openshift-etcd"),
    {"metadata": {"name": "revision-status-x", "namespace": "openshift-kube-apiserver"}, "data": {}},
    {"metadata": {"name": "config", "namespace": "openshift-kube-apiserver"}, "data": {}},
]

BEFORE_EVENTS = [
    _version("raw-internal", "", "5.1.0-0.nightly-2026-11-08-173648", "2026-11-09T15:20:33Z"),
    _event("StartingNewRevision", 'new revision 7 triggered by "secret \\"etcd-client-6\\" not found"',
           "2026-11-09T15:32:04Z"),
    _version("raw-internal", "5.1.0-0.nightly-2026-11-08-173648", "5.1.0-0.nightly-2026-11-09-143447",
             "2026-11-09T16:02:23Z"),
    _event("StartingNewRevision",
           'new revision 11 triggered by "required configmap/kube-apiserver-pod has changed"',
           "2026-11-09T16:02:27Z"),
    _version("operator", "5.1.0-0.nightly-2026-11-08-173648", "5.1.0-0.nightly-2026-11-09-143447",
             "2026-11-09T16:12:51Z"),
]

BEFORE_CONFIGMAPS = [
    _status_cm(7, "2026-11-09T15:32:05Z", 'secret \\"etcd-client-6\\" not found'),
    _status_cm(11, "2026-11-09T16:02:30Z", "required configmap/kube-apiserver-pod has changed"),
]


def test_clean_reason():
    assert clean_reason('secret \\"etcd-client-6\\" not found') == 'secret "etcd-client-6" not found'


def test_revision_statuses_sorted_and_scoped():
    statuses = revision_statuses(AFTER_CONFIGMAPS, "openshift-kube-apiserver")
    assert [(s["revision"], s["created"]) for s in statuses] == [
        (8, "2026-11-10T00:24:16Z"), (9, "2026-11-10T00:49:19Z"), (10, "2026-11-10T01:08:30Z")]
    assert statuses[2]["reason"] == "optional secret/webhook-authenticator has changed"


def test_revision_triggers_match_writes_in_the_same_second():
    triggers = revision_triggers(AFTER_EVENTS, KAS_OP_NS, tolerance=1)
    assert [t["revision"] for t in triggers] == [8, 9, 10]
    rev10 = triggers[2]
    assert rev10["started"] == "2026-11-10T01:08:29Z"
    assert rev10["triggered"] == "2026-11-10T01:08:56Z"
    assert rev10["reason"] == "optional secret/webhook-authenticator has changed"
    assert [(w["namespace"], w["reason"]) for w in rev10["writes"]] == [
        ("openshift-authentication-operator", "SecretUpdated"),
        ("openshift-kube-apiserver-operator", "SecretUpdated")]
    assert "webhook-authentication-integrated-oauth" in rev10["writes"][0]["message"]
    # Only the operand-namespace copy is the resource the reason names; the source write matched on time.
    assert [w["names_reason_resource"] for w in rev10["writes"]] == [False, True]
    assert [w["message"][:35] for w in triggers[1]["writes"]] == ["Updated ConfigMap/kube-apiserver-po"]
    # A wider tolerance picks up the unrelated write 4s later.
    wide = revision_triggers(AFTER_EVENTS, KAS_OP_NS, tolerance=5)
    assert len(wide[2]["writes"]) == 3


def test_aggregated_event_matches_on_first_timestamp():
    events = [
        _event("StartingNewRevision", 'new revision 2 triggered by "required configmap/config has changed"',
               "2026-11-10T00:15:50Z"),
        _event("ConfigMapUpdated", "Updated ConfigMap/config -n openshift-kube-apiserver", "2026-11-10T00:23:52Z",
               first="2026-11-10T00:15:50Z", count=4,
               component="kube-apiserver-operator-target-config-controller-targetconfigcontroller"),
    ]
    triggers = revision_triggers(events, KAS_OP_NS)
    assert triggers[0]["started"] == "2026-11-10T00:15:50Z"
    assert triggers[0]["triggered"] is None
    assert triggers[0]["writes"][0]["count"] == 4
    # The write is reported at the occurrence that matched, not its last occurrence.
    assert triggers[0]["writes"][0]["time"] == "2026-11-10T00:15:50Z"


def test_upgrade_markers_and_phases():
    versions = operator_version_changes(AFTER_EVENTS, "kube-apiserver", KAS_OP_NS)
    assert [(v["name"], v["from"]) for v in versions][:2] == [("raw-internal", ""), ("operator", "")]
    assert upgrade_markers(versions) == ("2026-11-10T00:49:11Z", "2026-11-10T00:59:28Z")
    assert upgrade_markers([]) == (None, None)

    run = analyze_run("after", AFTER_EVENTS, AFTER_CONFIGMAPS, "kube-apiserver", 1)
    phases = {t["revision"]: (t["phase"], t["after_operator_upgrade"]) for t in run["triggers"]}
    assert phases == {8: ("install", False), 9: ("upgrade", False), 10: ("upgrade", True)}
    assert [s["phase"] for s in run["revision_statuses"]] == ["install", "upgrade", "upgrade"]


def test_first_upgrade_revision_is_not_extra_when_operator_reports_early():
    # Run 2119920652067540992: the operator reported its new version 1s before the
    # upgrade's own revision started.
    events = [
        _version("raw-internal", "", "5.1.0-0.ci-2026-11-08-232923", "2026-11-09T22:57:00Z"),
        _version("raw-internal", "5.1.0-0.ci-2026-11-08-232923", "5.1.0-0.ci-2026-11-09-112923",
                 "2026-11-09T23:45:11Z"),
        _version("operator", "5.1.0-0.ci-2026-11-08-232923", "5.1.0-0.ci-2026-11-09-112923",
                 "2026-11-09T23:45:13Z"),
        _event("StartingNewRevision",
               'new revision 7 triggered by "required configmap/kube-apiserver-pod has changed"',
               "2026-11-09T23:45:14Z"),
    ]
    run = analyze_run("runc", events, [], "kube-apiserver", 1)
    assert [(t["revision"], t["phase"], t["after_operator_upgrade"]) for t in run["triggers"]] == [
        (7, "upgrade", False)]


def test_compare_runs_uses_upgrade_revisions():
    before = analyze_run("before", BEFORE_EVENTS, BEFORE_CONFIGMAPS, "kube-apiserver", 1)
    after = analyze_run("after", AFTER_EVENTS, AFTER_CONFIGMAPS, "kube-apiserver", 1)
    assert compare_runs([before, after]) == [{
        "reason": "optional secret/webhook-authenticator has changed",
        "present_in": ["after"], "absent_in": ["before"]}]
    assert compare_runs([after]) == []

    # Without an upgrade marker in one run, every revision is compared.
    no_marker = analyze_run("nomarker", [e for e in BEFORE_EVENTS if e["reason"] != "OperatorVersionChanged"],
                            BEFORE_CONFIGMAPS, "kube-apiserver", 1)
    reasons = {d["reason"] for d in compare_runs([no_marker, after])}
    assert 'secret "etcd-client-6" not found' in reasons
    assert "required configmap/config has changed" in reasons


def test_format_text_hides_install_revisions_unless_all():
    before = analyze_run("before", BEFORE_EVENTS, BEFORE_CONFIGMAPS, "kube-apiserver", 1)
    after = analyze_run("after", AFTER_EVENTS, AFTER_CONFIGMAPS, "kube-apiserver", 1)
    text = format_text([before, after], compare_runs([before, after]))
    assert "revision 10  started 2026-11-10T01:08:29Z  triggered 2026-11-10T01:08:56Z  " \
           "optional secret/webhook-authenticator has changed [after operator upgrade]" in text
    assert "SecretUpdated openshift-authentication-operator" in text
    assert "revision 8 " not in text
    assert "(1 install-time revision hidden; --all shows them)" in text
    assert "version raw-internal: 5.1.0-0.ci-2026-11-09-112923 -> 5.1.0-0.ci-2026-11-09-232923" in text
    assert "Trigger reasons not present in every run:" in text
    assert "present in: after; absent in: before" in text
    full = format_text([after], [], show_all=True)
    assert "revision 8 " in full


def _write_build_dir(root, build_id, events, configmaps):
    gather = os.path.join(root, build_id, "gather")
    os.makedirs(gather)
    with open(os.path.join(gather, "events.json"), "w") as f:
        json.dump({"kind": "EventList", "items": events}, f)
    with open(os.path.join(gather, "configmaps.json"), "w") as f:
        json.dump({"kind": "List", "items": configmaps}, f)
    return os.path.join(root, build_id)


def test_main_build_dirs_json():
    with tempfile.TemporaryDirectory() as tmp:
        before = _write_build_dir(tmp, "111", BEFORE_EVENTS, BEFORE_CONFIGMAPS)
        after = _write_build_dir(tmp, "222", AFTER_EVENTS, AFTER_CONFIGMAPS)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([before, after, "--format", "json"])
    assert code == 0
    data = json.loads(out.getvalue())
    assert [r["run"] for r in data["runs"]] == ["111", "222"]
    assert data["differences"][0]["present_in"] == ["222"]


def test_main_files_and_missing_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        after = _write_build_dir(tmp, "222", AFTER_EVENTS, AFTER_CONFIGMAPS)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--events", os.path.join(after, "gather", "events.json"),
                         "--configmaps", os.path.join(after, "gather", "configmaps.json")])
        assert code == 0
        assert "== input (kube-apiserver)" in out.getvalue()

        empty = os.path.join(tmp, "333")
        os.makedirs(empty)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([empty])
    assert code == 1
    assert "events.json missing or empty" in out.getvalue()


def test_main_other_operator():
    with tempfile.TemporaryDirectory() as tmp:
        after = _write_build_dir(tmp, "222", AFTER_EVENTS, AFTER_CONFIGMAPS)
        out = io.StringIO()
        with redirect_stdout(out):
            main([after, "--operator", "etcd", "--format", "json"])
    run = json.loads(out.getvalue())["runs"][0]
    assert [t["revision"] for t in run["triggers"]] == [9]
    assert [s["revision"] for s in run["revision_statuses"]] == [4]


@pytest.mark.parametrize("content", ["not json", "null", '"x"', '{"items": null}'])
def test_load_items_returns_empty_for_malformed_files(tmp_path, content):
    path = tmp_path / "events.json"
    path.write_text(content)
    assert load_items(str(path)) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
