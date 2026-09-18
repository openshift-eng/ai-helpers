#!/usr/bin/env python3
"""Immutable claim inventories and evidence. Stdlib only; no network or model calls."""

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA = 1
STATUSES = {"verified", "failed", "unverified"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                   stderr=subprocess.DEVNULL).strip()


def local_file(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("document/source paths must be relative without '..'")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("document/source path escapes repository")
    return resolved


class Cache:
    def __init__(self, root):
        self.root = Path(root)

    def publish(self, group, value):
        """Hard-link a fully written temporary file: existing records never change."""
        key = digest(value)
        directory = self.root / group
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (key + ".json")
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), 0o400)
            try:
                os.link(temporary, target)
            except FileExistsError:
                if target.read_bytes() != canonical(value):
                    raise ValueError("cache collision or corrupt immutable record: " + key)
        finally:
            os.unlink(temporary)
        return key

    def read(self, group, key):
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("invalid cache record ID")
        value = json.loads((self.root / group / (key + ".json")).read_bytes())
        if digest(value) != key or value.get("schema") != SCHEMA:
            raise ValueError("corrupt or unsupported cache record: " + key)
        return value

    def publish_receipts(self, snapshot_id, entries):
        """Store compact independent-verification receipts for one snapshot."""
        if not entries:
            return None
        snapshot = self.read("snapshots", snapshot_id)
        normalized = {}
        for identifier, supplied in entries.items():
            if identifier not in snapshot["claims"]:
                raise ValueError("receipt references unknown claim: " + identifier)
            entry = json.loads(json.dumps(supplied))
            if entry.get("status") != "verified" or not entry.get("signatures"):
                raise ValueError("receipt requires verified signatures: " + identifier)
            if not entry.get("reviewers"):
                raise ValueError("receipt requires an independent reviewer: " + identifier)
            if entry.get("context") != self.context(snapshot, identifier):
                raise ValueError("receipt context mismatch: " + identifier)
            normalized[identifier] = entry
        return self.publish("receipts/" + snapshot_id,
                            {"schema": SCHEMA, "kind": "receipt_batch",
                             "snapshot": snapshot_id, "entries": normalized})

    def receipt(self, snapshot_id, identifier):
        """Read one claim's compact receipt, rejecting conflicting batches."""
        snapshot = self.read("snapshots", snapshot_id)
        group = "receipts/" + snapshot_id
        found = []
        for path in sorted((self.root / group).glob("*.json")):
            record = self.read(group, path.stem)
            if record.get("kind") != "receipt_batch" or record.get("snapshot") != snapshot_id:
                raise ValueError("invalid compact receipt batch")
            entry = record.get("entries", {}).get(identifier)
            if entry is None:
                continue
            if entry.get("context") != self.context(snapshot, identifier):
                raise ValueError("compact receipt context mismatch")
            found.append(entry)
        if not found:
            return None
        if len({digest(entry) for entry in found}) != 1:
            raise ValueError("conflicting compact receipts")
        return found[0]

    def snapshot(self, repo, inventory, prompt_version):
        root = Path(repo).resolve()
        if not prompt_version:
            raise ValueError("prompt_version must include the verification policy version")
        commit = git(root, "rev-parse", "HEAD")
        try:
            identity = git(root, "remote", "get-url", "origin")
        except subprocess.CalledProcessError:
            identity = str(root)
        documents = {}
        for name in inventory["documents"]:
            if name in documents:
                raise ValueError("duplicate document: " + name)
            data = local_file(root, name).read_bytes()
            documents[name] = {"sha256": file_hash(data), "text": data.decode("utf-8")}
        claims = {}
        for supplied in inventory["claims"]:
            claim = json.loads(json.dumps(supplied))
            identifier = claim["id"]
            if not isinstance(identifier, str) or not identifier or identifier in claims:
                raise ValueError("claim IDs must be unique nonempty strings")
            if not claim.get("assertion") or not claim.get("kind") or not claim.get("occurrences"):
                raise ValueError("claim requires assertion, kind and occurrences: " + identifier)
            for occurrence in claim["occurrences"]:
                count = len(documents[occurrence["path"]]["text"].splitlines())
                if not (1 <= occurrence["start"] <= occurrence["end"] <= count):
                    raise ValueError("invalid inclusive claim line range: " + identifier)
            claim.setdefault("depends_on", [])
            claim.setdefault("source_scope", [])
            for source in claim["source_scope"]:
                if not source.get("repository") or not re.fullmatch(
                        r"(?:[a-f0-9]{40}|[a-f0-9]{64}|sha256:[a-f0-9]{64})",
                        source.get("revision", "")):
                    raise ValueError("sources require repository and immutable revision")
                if "local_root" in source:
                    source_root = Path(source["local_root"]).resolve()
                    source["local_root"] = str(source_root)
                    if git(source_root, "rev-parse", "HEAD") != source["revision"]:
                        raise ValueError("local source HEAD differs from pinned revision")
                    source["sha256"] = file_hash(local_file(source_root, source["path"]).read_bytes())
            claims[identifier] = claim
        for claim in claims.values():
            if any(dependency not in claims for dependency in claim["depends_on"]):
                raise ValueError("unknown claim dependency: " + claim["id"])
        value = {"schema": SCHEMA, "kind": "snapshot", "repository": identity,
                 "commit": commit, "prompt_version": prompt_version,
                 "coverage_complete": inventory.get("coverage_complete") is True,
                 "documents": documents, "claims": claims}
        return self.publish("snapshots", value)

    def context(self, snapshot, identifier):
        claim = snapshot["claims"][identifier]
        def meaning_of(item):
            return {**{key: value for key, value in item.items() if key != "occurrences"},
                    "occurrences": sorted(
                        ({"path": occurrence["path"], "excerpt": excerpt}
                         for occurrence, excerpt in zip(item["occurrences"], self.excerpts(snapshot, item))),
                        key=canonical)}
        meaning = meaning_of(claim)
        dependencies, pending = {}, list(claim["depends_on"])
        while pending:
            dependency = pending.pop()
            if dependency == identifier or dependency in dependencies:
                continue
            related = snapshot["claims"][dependency]
            dependencies[dependency] = {
                "claim": meaning_of(related),
                "documents": {item["path"]: snapshot["documents"][item["path"]]["sha256"]
                              for item in related["occurrences"]}}
            pending.extend(related["depends_on"])
        return digest({"schema": SCHEMA, "repository": snapshot["repository"],
                       "commit": snapshot["commit"], "claim_hash": digest(meaning),
                       "documents": {item["path"]: snapshot["documents"][item["path"]]["sha256"]
                                     for item in claim["occurrences"]},
                       "source_scope": claim["source_scope"],
                       "dependencies": dependencies,
                       "prompt_version": snapshot["prompt_version"]})

    def put(self, snapshot_id, identifier, status, evidence):
        snapshot = self.read("snapshots", snapshot_id)
        if status not in STATUSES or evidence.get("role") not in {"fixer", "reviewer"}:
            raise ValueError("invalid status or observer role")
        if not evidence.get("reviewer") or not isinstance(evidence.get("evidence"), list):
            raise ValueError("evidence requires reviewer, role and evidence list")
        if status == "verified" and not evidence["evidence"]:
            raise ValueError("verified requires source evidence")
        if status == "verified" and not snapshot["claims"][identifier]["source_scope"]:
            raise ValueError("verified requires pinned source_scope")
        def reject_conversation(value):
            if isinstance(value, dict):
                if {"conversation", "transcript", "messages"} & value.keys():
                    raise ValueError("cache must not contain fixer conversation")
                for nested in value.values():
                    reject_conversation(nested)
            elif isinstance(value, list):
                for nested in value:
                    reject_conversation(nested)
        reject_conversation(evidence)
        for item in evidence["evidence"]:
            if not isinstance(item, dict) or not item.get("source") or not item.get("excerpt"):
                raise ValueError("each evidence item requires source and excerpt")
        context = self.context(snapshot, identifier)
        supersedes = evidence.get("supersedes", [])
        if not isinstance(supersedes, list) or (supersedes and evidence["role"] != "reviewer"):
            raise ValueError("only independent reviewers may explicitly supersede evidence")
        for prior in supersedes:
            # Existence under this exact context also excludes cross-claim replacement.
            self.read("observations/" + context, prior)
        return self.publish("observations/" + context,
                            {"schema": SCHEMA, "kind": "observation", "context": context,
                             "snapshot": snapshot_id, "claim": identifier,
                             "status": status, "payload": evidence})

    def observations(self, snapshot_id, identifier):
        snapshot = self.read("snapshots", snapshot_id)
        context = self.context(snapshot, identifier)
        found = {}
        carries = []
        visited = set()
        superseded = set()
        def visit(group):
            if group in visited:
                return
            if not re.fullmatch(r"observations/[a-f0-9]{64}", group):
                raise ValueError("invalid evidence context")
            visited.add(group)
            records = {path.stem: self.read(group, path.stem)
                       for path in sorted((self.root / group).glob("*.json"))}
            replaced = set()
            for record in records.values():
                if "observations/" + record["context"] != group:
                    raise ValueError("evidence context mismatch")
                if record["claim"] != identifier:
                    raise ValueError("evidence claim mismatch")
                origin_snapshot = self.read("snapshots", record["snapshot"])
                if self.context(origin_snapshot, identifier) != record["context"]:
                    raise ValueError("evidence snapshot provenance mismatch")
                payload = record.get("payload", {})
                if payload.get("supersedes"):
                    if payload["role"] != "reviewer":
                        raise ValueError("non-independent supersession")
                    for prior in payload["supersedes"]:
                        if prior not in records:
                            raise ValueError("missing superseded evidence")
                        replaced.add(prior)
            superseded.update(replaced)
            for key, record in records.items():
                if key in replaced:
                    continue
                if record["kind"] == "carry":
                    carries.append({"id": key, "group": group, **record})
                    for reference in record["origins"]:
                        if not re.fullmatch(r"observations/[a-f0-9]{64}", reference["group"]):
                            raise ValueError("invalid evidence context")
                        self.read(reference["group"], reference["id"])
                        visit(reference["group"])
                elif record["kind"] == "observation":
                    found[key] = {"id": key, "group": group, **record}
                else:
                    raise ValueError("unexpected evidence record kind")
        group = "observations/" + context
        try:
            visit(group)
            receipt = self.receipt(snapshot_id, identifier)
        except (OSError, ValueError, KeyError, TypeError) as error:
            return {"status": "unverified", "reason": "cache_error", "error": str(error),
                    "observations": [], "carries": [], "receipts": [], "signatures": [],
                    "reviewers": [], "groups": sorted(visited)}
        observations = list(found.values())
        signatures = {digest({"status": item["status"], "evidence": item["payload"]["evidence"]})
                      for item in observations}
        if receipt:
            signatures.update(receipt["signatures"])
        reviewers = [item for item in observations if item["payload"]["role"] == "reviewer"]
        reviewer_names = {item["payload"]["reviewer"] for item in reviewers}
        statuses = {item["status"] for item in observations}
        if receipt:
            reviewer_names.update(receipt["reviewers"])
            statuses.add("verified")
        reason = "conflicting_evidence" if len(signatures) > 1 or len(statuses) > 1 else (
            "missing_independent_evidence" if not reviewer_names else None)
        status = next(iter(statuses), "unverified")
        return {"status": "unverified" if reason else status,
                "reason": reason, "observations": observations, "carries": carries,
                "receipts": [receipt] if receipt else [],
                "signatures": sorted(signatures), "reviewers": sorted(reviewer_names),
                "groups": sorted(visited), "superseded": sorted(superseded)}

    def plan(self, current_id, previous_id=None):
        current = self.read("snapshots", current_id)
        baseline_error = None
        try:
            previous = self.read("snapshots", previous_id) if previous_id else None
        except (OSError, ValueError, KeyError, TypeError) as error:
            previous, baseline_error = None, str(error)
        removed = sorted(set(previous["claims"]) - set(current["claims"])) if previous else []
        dropped = [identifier for identifier in removed
                   if any(excerpt and any(excerpt in document["text"]
                                          for document in current["documents"].values())
                          for excerpt in self.excerpts(previous, previous["claims"][identifier]))]
        full = (previous is None or not previous["coverage_complete"] or
                not current["coverage_complete"] or
                previous["repository"] != current["repository"] or bool(dropped))
        changed_documents = sorted(name for name in set(current["documents"]) |
                                   set(previous["documents"] if previous else {})
                                   if not previous or current["documents"].get(name) !=
                                   previous["documents"].get(name))
        reasons = {identifier: ["full_inventory"] for identifier in current["claims"]} if full else {}
        if not full:
            for identifier, claim in current["claims"].items():
                old = previous["claims"].get(identifier)
                why = []
                if old is None:
                    why.append("added_claim")
                else:
                    for field in sorted((old.keys() | claim.keys()) - {"id", "occurrences"}):
                        if old.get(field) != claim.get(field):
                            if field == "source_scope" and self.same_source_bytes(
                                    old.get(field, []), claim.get(field, [])):
                                continue
                            why.append("changed_" + field)
                    if previous["prompt_version"] != current["prompt_version"]:
                        why.append("changed_prompt_version")
                    old_paths = {item["path"] for item in old["occurrences"]}
                    new_paths = {item["path"] for item in claim["occurrences"]}
                    if old_paths != new_paths:
                        why.append("changed_document_scope")
                    elif self.touched(previous, current, old, claim):
                        why.append("changed_lines")
                    elif sorted(self.excerpts(previous, old)) != sorted(self.excerpts(current, claim)):
                        why.append("changed_occurrences")
                if why:
                    reasons[identifier] = why
            self.propagate(current, reasons, removed)
        reusable = {}
        unresolved = {identifier: "inventory_drop_without_deleted_occurrence" for identifier in dropped}
        compact_carries = {}
        for identifier in current["claims"]:
            if identifier in reasons:
                continue
            evidence = self.observations(previous_id, identifier)
            current_evidence = self.observations(current_id, identifier)
            signatures = set(evidence["signatures"]) | set(current_evidence["signatures"])
            if current_evidence["reason"] == "cache_error" or len(signatures) > 1:
                evidence = {"status": "unverified", "reason": current_evidence["reason"]
                            if current_evidence["reason"] == "cache_error" else "conflicting_evidence"}
            if evidence["status"] != "verified":
                reasons[identifier] = [evidence["reason"] or evidence["status"]]
                unresolved[identifier] = evidence["status"]
                continue
            origins = [{"group": item["group"], "id": item["id"]}
                       for item in evidence["observations"] if item["payload"]["role"] == "reviewer"]
            reusable[identifier] = origins or [{"receipt": previous_id}]
            if evidence.get("receipts"):
                compact_carries[identifier] = {
                    "context": self.context(current, identifier), "status": "verified",
                    "signatures": evidence["signatures"], "reviewers": evidence["reviewers"]}
        self.propagate(current, reasons, removed)
        reusable = {identifier: origins for identifier, origins in reusable.items() if identifier not in reasons}
        compact_carries = {identifier: entry for identifier, entry in compact_carries.items()
                           if identifier not in reasons}
        for identifier, origins in reusable.items():
            context = self.context(current, identifier)
            if context != self.context(previous, identifier) and identifier not in compact_carries:
                self.publish("observations/" + context,
                             {"schema": SCHEMA, "kind": "carry", "context": context,
                              "snapshot": current_id, "claim": identifier,
                              "baseline": previous_id, "origins": origins})
        self.publish_receipts(current_id, compact_carries)
        return {"schema": SCHEMA, "mode": "full" if full else "delta",
                "current": current_id, "previous": previous_id,
                "baseline_error": baseline_error,
                "coverage_complete": current["coverage_complete"] and not dropped,
                "extraction_required": not current["coverage_complete"] or bool(dropped),
                "changed_documents": changed_documents, "reverify": reasons,
                "reusable": reusable, "removed": [item for item in removed if item not in dropped],
                "unresolved": unresolved}

    def compact(self, snapshot_id):
        """Replace detailed verified observations with aggregate receipts."""
        snapshot = self.read("snapshots", snapshot_id)
        batches = {}
        groups = set()
        verified = []
        retained = []
        for identifier in snapshot["claims"]:
            result = self.observations(snapshot_id, identifier)
            if result["status"] != "verified":
                retained.append(identifier)
                continue
            verified.append(identifier)
            batches.setdefault(snapshot_id, {})[identifier] = {
                "context": self.context(snapshot, identifier), "status": "verified",
                "signatures": result["signatures"], "reviewers": result["reviewers"]}
            for observation in result["observations"]:
                origin_id = observation["snapshot"]
                origin = self.read("snapshots", origin_id)
                if observation["payload"]["role"] != "reviewer":
                    continue
                batches.setdefault(origin_id, {})[identifier] = {
                    "context": self.context(origin, identifier), "status": "verified",
                    "signatures": result["signatures"],
                    "reviewers": result["reviewers"]}
            groups.update(result["groups"])
        receipts = [self.publish_receipts(origin_id, entries)
                    for origin_id, entries in batches.items()]
        removed = 0
        for group in sorted(groups):
            directory = self.root / group
            for path in directory.glob("*.json"):
                path.unlink()
                removed += 1
            try:
                directory.rmdir()
            except OSError:
                pass
        return {"schema": SCHEMA, "snapshot": snapshot_id,
                "verified_count": len(verified), "retained_count": len(retained),
                "retained": retained, "removed_records": removed,
                "receipt_batches": len([item for item in receipts if item])}

    @staticmethod
    def same_source_bytes(previous, current):
        """Allow a new local commit only when snapshot refreshed identical bytes."""
        if len(previous) != len(current):
            return False
        for old, new in zip(previous, current):
            if old == new:
                continue
            if not (old.get("local_root") and new.get("local_root") and
                    old.get("sha256") and new.get("sha256")):
                return False
            if ({key: value for key, value in old.items() if key != "revision"} !=
                    {key: value for key, value in new.items() if key != "revision"}):
                return False
        return True

    @staticmethod
    def propagate(snapshot, reasons, removed):
        while True:
            affected = [identifier for identifier, claim in snapshot["claims"].items()
                        if identifier not in reasons and
                        any(item in reasons or item in removed for item in claim["depends_on"])]
            if not affected:
                return
            reasons.update({identifier: ["changed_dependency"] for identifier in affected})

    @staticmethod
    def excerpts(snapshot, claim):
        return ["".join(snapshot["documents"][item["path"]]["text"].splitlines(keepends=True)
                        [item["start"] - 1:item["end"]]) for item in claim["occurrences"]]

    @staticmethod
    def touched(previous, current, old, claim):
        for path in {item["path"] for item in claim["occurrences"]}:
            before = previous["documents"][path]["text"].splitlines(keepends=True)
            after = current["documents"][path]["text"].splitlines(keepends=True)
            for tag, a, b, c, d in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
                if tag == "equal":
                    continue
                if any(item["path"] == path and item["start"] <= b and item["end"] > a
                       for item in old["occurrences"]) and a < b:
                    return True
                if any(item["path"] == path and item["start"] <= d and item["end"] > c
                       for item in claim["occurrences"]) and c < d:
                    return True
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--repo", required=True)
    snapshot.add_argument("--inventory", required=True)
    snapshot.add_argument("--prompt-version", required=True)
    for name in ("put", "get"):
        command = commands.add_parser(name)
        command.add_argument("--snapshot", required=True)
        command.add_argument("--claim", required=True)
        if name == "put":
            command.add_argument("--status", required=True, choices=sorted(STATUSES))
            command.add_argument("--evidence", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--current", required=True)
    plan.add_argument("--previous")
    compact = commands.add_parser("compact")
    compact.add_argument("--snapshot", required=True)
    args = parser.parse_args()
    cache = Cache(args.cache)
    try:
        if args.command == "snapshot":
            result = {"snapshot": cache.snapshot(args.repo, json.loads(Path(args.inventory).read_text()),
                                                 args.prompt_version)}
        elif args.command == "put":
            result = {"observation": cache.put(args.snapshot, args.claim, args.status,
                                               json.loads(Path(args.evidence).read_text()))}
        elif args.command == "get":
            result = cache.observations(args.snapshot, args.claim)
        elif args.command == "plan":
            result = cache.plan(args.current, args.previous)
        else:
            result = cache.compact(args.snapshot)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(2, "claim-cache: " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
