#!/usr/bin/env python3
"""Extract agent session metrics from OTEL JSONL and produce autodl JSON.

Parses the OTEL JSONL output produced by agentic-ci's OTLP collector.
Claude Code and Codex telemetry emitted by agentic-ci are supported. Identity
fields can also be supplemented from a Claude stream-json log via --stream-log.

Usage:
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json]
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json] --stream-log claude-output.log
    python3 extract_metrics.py claude-otel.jsonl [output-autodl.json] --prompt-file initial-prompt.txt
"""

import codecs
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


REDACTED_PROMPTS = {"[redacted]", "<redacted>", "redacted"}
CODEX_METRIC_ALIASES = {
    "codex.token.usage": "agentic_ci.codex.token.usage",
    "codex.cost.usage": "agentic_ci.codex.cost.usage",
}
SUPPORTED_METRICS = {
    "claude_code.token.usage",
    "claude_code.cost.usage",
    "claude_code.active_time.total",
    "agentic_ci.codex.token.usage",
    "agentic_ci.codex.cost.usage",
}


def _is_real_prompt(prompt):
    """Return whether a prompt is usable rather than a telemetry placeholder."""
    return bool(prompt and prompt.strip().casefold() not in REDACTED_PROMPTS)


def _parse_span_attrs(span):
    """Extract span attributes as a flat dict."""
    attrs = {}
    for a in span.get("attributes", []):
        key = a["key"]
        val = a.get("value", {})
        v = val.get("stringValue", val.get("intValue", val.get("doubleValue")))
        if v is not None:
            attrs[key] = v
    return attrs


def _attribute_value(value):
    """Return the scalar value from an OTLP AnyValue."""
    if not isinstance(value, dict):
        return None
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return value[key]
    return None


def _attributes(item):
    """Extract OTLP attributes as a flat dict."""
    attrs = {}
    for attr in item.get("attributes", []):
        key = attr.get("key")
        if key:
            attrs[key] = _attribute_value(attr.get("value"))
    return attrs


def _canonical_structure(value):
    """Return a stable representation of structured OTLP producer identity."""
    if isinstance(value, dict):
        return {key: _canonical_structure(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        items = [_canonical_structure(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(
            item, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ))
    return value


def _producer_key(value):
    """Serialize resource or instrumentation-scope identity deterministically."""
    return json.dumps(
        _canonical_structure(value or {}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _normalized_model(value):
    """Use one join key for missing model attributes in metrics and logs."""
    return str(value or "unknown")


def _aware_timestamp(value):
    """Parse an ISO timestamp only when it includes an explicit UTC offset."""
    if not value:
        return None
    timestamp = str(value)
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _chronology_key(parsed, sequence):
    """Sort valid timestamps chronologically, then undated events by input order."""
    return (0, parsed) if parsed is not None else (1, sequence)


class MetricAccumulator:
    """Accumulate OTLP points without double-counting cumulative snapshots.

    Cumulative series share a startTimeUnixNano. Only their latest snapshot is
    retained. A resumed/new invocation has a new start time and is additive.
    Delta points and legacy points without temporality retain the historical
    behavior of being summed.
    """

    def __init__(self):
        """Initialize independent delta totals and cumulative snapshots."""
        self.totals = defaultdict(float)
        self.cumulative = {}

    def add(self, metric, resource_identity=None, scope_identity=None):
        """Add all numeric data points from one OTLP metric."""
        name = CODEX_METRIC_ALIASES.get(metric.get("name", ""), metric.get("name", ""))
        if name not in SUPPORTED_METRICS:
            return
        resource_key = _producer_key(resource_identity)
        scope_key = _producer_key(scope_identity)
        data = metric.get("sum", metric.get("gauge", metric.get("histogram", {})))
        is_cumulative = "sum" in metric and data.get("aggregationTemporality") == 2
        for point in data.get("dataPoints", []):
            raw = point.get("asDouble", point.get("asInt"))
            try:
                value = float(raw)
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(value):
                continue
            attrs = _attributes(point)
            attrs_key = tuple(sorted(attrs.items()))
            series = (name, resource_key, scope_key, attrs_key)
            if not is_cumulative:
                self.totals[series] += value
                continue
            start = str(point.get("startTimeUnixNano", ""))
            try:
                timestamp = int(point.get("timeUnixNano", 0) or 0)
            except (TypeError, ValueError, OverflowError):
                timestamp = 0
            key = (name, resource_key, scope_key, attrs_key, start)
            previous = self.cumulative.get(key)
            if previous is None or timestamp >= previous[0]:
                self.cumulative[key] = (timestamp, value)

    def values(self):
        """Return totals with only the latest value of each cumulative series."""
        totals = self.totals.copy()
        for key, (_timestamp, value) in self.cumulative.items():
            name, resource_key, scope_key, attrs_key, _start = key
            totals[(name, resource_key, scope_key, attrs_key)] += value
        combined = defaultdict(float)
        for (name, _resource_key, _scope_key, attrs_key), value in totals.items():
            combined[(name, attrs_key)] += value
        return [
            (name, dict(attrs_key), value)
            for (name, attrs_key), value in combined.items()
        ]


class CodexLogAccumulator:
    """Accumulate Codex identity and activity fields from OTEL log events."""

    def __init__(self):
        """Initialize per-model identity, prompt, timing, and turn state."""
        self.identity_events = defaultdict(list)
        self.prompts = []
        self.turns = Counter()
        self.ttft = []
        self.api_duration_ms = 0
        self.min_timestamp = None
        self.max_timestamp = None
        self.sequence = 0

    def add(self, attrs):
        """Add one flattened Codex OTEL log event."""
        sequence = self.sequence
        self.sequence += 1
        event = attrs.get("event.name", "")
        model = _normalized_model(attrs.get("model"))
        session_id = str(attrs.get("conversation.id") or "")
        timestamp = str(attrs.get("event.timestamp", ""))
        parsed = _aware_timestamp(timestamp)
        chronology = _chronology_key(parsed, sequence)
        if parsed is not None:
            if self.min_timestamp is None or parsed < self.min_timestamp:
                self.min_timestamp = parsed
            if self.max_timestamp is None or parsed > self.max_timestamp:
                self.max_timestamp = parsed
        version = str(attrs.get("app.version") or "")
        self.identity_events[model].append((chronology, session_id, version))
        if event == "codex.user_prompt":
            prompt = str(attrs.get("prompt", ""))
            if _is_real_prompt(prompt):
                self.prompts.append((chronology, model, session_id, version, prompt[:500]))
        elif (event == "codex.sse_event"
              and attrs.get("event.kind") == "response.completed"):
            self.turns[model] += 1
        elif event == "codex.turn_ttft":
            try:
                duration = int(float(attrs.get("duration_ms", 0)))
                self.ttft.append((chronology, model, duration))
            except (TypeError, ValueError, OverflowError):
                pass
        elif event == "codex.api_request":
            try:
                self.api_duration_ms += int(float(attrs.get("duration_ms", 0)))
            except (TypeError, ValueError, OverflowError):
                pass

    def result(self, model):
        """Return accumulated identity and activity for the selected model."""
        prompts = sorted(
            (prompt for prompt in self.prompts if prompt[1] == model),
            key=lambda prompt: prompt[0],
        )
        identity_events = sorted(self.identity_events.get(model, []), key=lambda item: item[0])
        prompt_event = prompts[0] if prompts else None

        def identity_value(prompt_index, event_index):
            """Prefer the first prompt identity, then the earliest populated event."""
            if prompt_event and prompt_event[prompt_index]:
                return prompt_event[prompt_index]
            return next((item[event_index] for item in identity_events if item[event_index]), "")

        ttft = sorted(
            (item for item in self.ttft if item[1] == model),
            key=lambda item: item[0],
        )
        duration_ms = 0
        if self.min_timestamp is not None and self.max_timestamp is not None:
            duration_ms = int((self.max_timestamp - self.min_timestamp).total_seconds() * 1000)
        return {
            "session_id": identity_value(2, 1),
            "claude_code_version": identity_value(3, 2),
            "prompt": prompt_event[4] if prompt_event else "",
            "num_turns": self.turns.get(model, 0),
            "ttft_ms": ttft[0][2] if ttft else 0,
            "duration_api_ms": self.api_duration_ms,
            "duration_ms": duration_ms,
        }


class TraceAccumulator:
    """Accumulates session metadata across batched /v1/traces payloads."""

    def __init__(self):
        self.session_id = ""
        self.claude_code_version = ""
        self.permission_mode = ""
        self.min_start_ns = None
        self.max_end_ns = None
        self.first_interaction_start_ns = None
        self.first_ttft_ms = 0
        self.num_turns = 0
        self.last_stop_reason = ""
        self.prompt = ""
        self.first_prompt_start_ns = None
        self.skills = []
        self.files_written = 0
        self.num_subagents = 0

    def add(self, payload):
        """Process one /v1/traces payload."""
        for rs in payload.get("resourceSpans", []):
            for ra in rs.get("resource", {}).get("attributes", []):
                if ra["key"] == "service.version" and not self.claude_code_version:
                    val = ra.get("value", {})
                    self.claude_code_version = val.get("stringValue", "")

            for ss in rs.get("scopeSpans", []):
                for span in ss.get("spans", []):
                    attrs = _parse_span_attrs(span)
                    name = span.get("name", "")
                    start_ns = span.get("startTimeUnixNano")
                    end_ns = span.get("endTimeUnixNano")

                    if start_ns is not None:
                        start_ns = int(start_ns)
                        if self.min_start_ns is None or start_ns < self.min_start_ns:
                            self.min_start_ns = start_ns
                    if end_ns is not None:
                        end_ns = int(end_ns)
                        if self.max_end_ns is None or end_ns > self.max_end_ns:
                            self.max_end_ns = end_ns

                    if not self.session_id:
                        self.session_id = str(attrs.get("session.id", ""))
                    if not self.permission_mode:
                        self.permission_mode = str(attrs.get("permission_mode", ""))

                    if name == "claude_code.llm_request":
                        context = attrs.get("llm_request.context", "")
                        if context == "interaction":
                            self.num_turns += 1
                            self.last_stop_reason = str(attrs.get("stop_reason", ""))
                            if start_ns is not None:
                                if (self.first_interaction_start_ns is None
                                        or start_ns < self.first_interaction_start_ns):
                                    self.first_interaction_start_ns = start_ns
                                    ttft = attrs.get("ttft_ms")
                                    if ttft is not None:
                                        self.first_ttft_ms = int(float(ttft))

                    elif name == "claude_code.interaction":
                        user_prompt = str(attrs.get("user_prompt", ""))
                        if user_prompt and start_ns is not None:
                            if (self.first_prompt_start_ns is None
                                    or start_ns < self.first_prompt_start_ns):
                                self.first_prompt_start_ns = start_ns
                                self.prompt = user_prompt[:500]

                    elif name == "claude_code.tool":
                        tool_name = attrs.get("tool_name", "")
                        if tool_name == "Skill":
                            skill = attrs.get("skill_name", "")
                            if skill:
                                self.skills.append(skill)
                        elif tool_name == "Write":
                            self.files_written += 1
                        elif tool_name == "Agent":
                            self.num_subagents += 1

    def result(self):
        duration_ms = 0
        if self.min_start_ns is not None and self.max_end_ns is not None:
            duration_ms = (self.max_end_ns - self.min_start_ns) // 1_000_000

        return {
            "session_id": self.session_id,
            "claude_code_version": self.claude_code_version,
            "permission_mode": self.permission_mode,
            "duration_ms": duration_ms,
            "ttft_ms": self.first_ttft_ms,
            "num_turns": self.num_turns,
            "prompt": self.prompt,
            "stop_reason": self.last_stop_reason,
            "skills": self.skills,
            "files_written": self.files_written,
            "num_subagents": self.num_subagents,
        }


def parse_otel(path):
    """Parse an OTEL JSONL log and return a metrics row dict."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print("ERROR: empty OTEL log file", file=sys.stderr)
        sys.exit(1)

    metrics = MetricAccumulator()
    api_requests = []
    tool_uses = []
    traces = TraceAccumulator()
    codex_logs = CodexLogAccumulator()

    for rec in records:
        rpath = rec.get("path", "")
        payload = rec.get("payload", {})

        if "/v1/metrics" in rpath:
            for rm in payload.get("resourceMetrics", []):
                resource_identity = {
                    "resource": rm.get("resource", {}),
                    "schemaUrl": rm.get("schemaUrl", ""),
                }
                for sm in rm.get("scopeMetrics", []):
                    scope_identity = {
                        "scope": sm.get("scope", {}),
                        "schemaUrl": sm.get("schemaUrl", ""),
                    }
                    for metric in sm.get("metrics", []):
                        metrics.add(metric, resource_identity, scope_identity)

        elif "/v1/logs" in rpath:
            for rl in payload.get("resourceLogs", []):
                for sl in rl.get("scopeLogs", []):
                    for lr in sl.get("logRecords", []):
                        event_attrs = _attributes(lr)
                        event_name = event_attrs.get("event.name", "")
                        if event_name in ("api_request", "claude_code.api_request"):
                            api_requests.append(event_attrs)
                        elif event_name in ("tool_decision", "codex.tool_decision"):
                            tool = event_attrs.get("tool_name", "")
                            if tool:
                                tool_uses.append(tool)
                        if event_name.startswith("codex."):
                            codex_logs.add(event_attrs)

        elif "/v1/traces" in rpath:
            traces.add(payload)

    token_totals = defaultdict(float)
    cost_totals = defaultdict(float)
    active_time = defaultdict(float)
    codex_token_totals = defaultdict(float)
    codex_cost_totals = defaultdict(float)
    for name, attrs, value in metrics.values():
        model_name = _normalized_model(attrs.get("model"))
        token_type = attrs.get("type", "unknown")
        if name == "claude_code.token.usage":
            token_totals[(model_name, token_type)] += value
        elif name == "claude_code.cost.usage":
            cost_totals[model_name] += value
        elif name == "claude_code.active_time.total":
            active_time[token_type] += value
        elif name == "agentic_ci.codex.token.usage":
            codex_token_totals[(model_name, token_type)] += value
        elif name == "agentic_ci.codex.cost.usage":
            codex_cost_totals[model_name] += value

    is_codex = bool(codex_cost_totals or codex_token_totals)
    if is_codex:
        if codex_cost_totals:
            model = max(codex_cost_totals, key=codex_cost_totals.get)
        else:
            token_by_model = defaultdict(float)
            for (model_name, _token_type), value in codex_token_totals.items():
                token_by_model[model_name] += value
            model = max(token_by_model, key=token_by_model.get)
        # One autodl row represents the primary Codex conversation. Token and
        # turn counts are scoped to its model; total cost includes auxiliary
        # models used by that conversation (matching agentic-ci's TOTAL).
        total_cost_usd = sum(codex_cost_totals.values())
        input_tokens = int(codex_token_totals[(model, "input")])
        output_tokens = int(codex_token_totals[(model, "output")])
        cache_read_tokens = int(codex_token_totals[(model, "cacheRead")])
        cache_creation_tokens = int(codex_token_totals[(model, "cacheCreation")])
    else:
        total_cost_usd = sum(cost_totals.values())
        input_tokens = int(sum(v for (_model, token_type), v in token_totals.items()
                               if token_type == "input"))
        output_tokens = int(sum(v for (_model, token_type), v in token_totals.items()
                                if token_type == "output"))
        cache_read_tokens = int(sum(v for (_model, token_type), v in token_totals.items()
                                    if token_type == "cacheRead"))
        cache_creation_tokens = int(sum(v for (_model, token_type), v in token_totals.items()
                                        if token_type == "cacheCreation"))
        model = max(cost_totals, key=cost_totals.get) if cost_totals else ""

    total_input = input_tokens + cache_read_tokens + cache_creation_tokens
    cache_hit_rate = (cache_read_tokens / total_input * 100) if total_input > 0 else 0

    tool_counts = Counter()
    if tool_uses:
        tool_counts.update(tool_uses)
    else:
        for req in api_requests:
            tool = req.get("tool_name", "")
            if tool:
                tool_counts[tool] += 1
    total_tool_calls = sum(tool_counts.values())

    duration_api_s = active_time.get("api", 0)
    analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    trace_data = traces.result()
    codex_data = codex_logs.result(model) if is_codex else {}
    codex_prompt = codex_data.get("prompt", "")
    trace_prompt = trace_data.get("prompt", "")
    prompt = (codex_prompt if _is_real_prompt(codex_prompt)
              else trace_prompt if _is_real_prompt(trace_prompt) else "")
    skills = trace_data.get("skills", [])
    skills_str = ",".join(dict.fromkeys(skills)) if skills else ""

    return {
        "session_id": codex_data.get("session_id", "") or trace_data.get("session_id", ""),
        "model": model,
        "claude_code_version": (codex_data.get("claude_code_version", "")
                                or trace_data.get("claude_code_version", "")),
        "permission_mode": trace_data.get("permission_mode", ""),
        "entrypoint": "",
        "prompt": prompt,
        "plugins_loaded": "",
        "analyzed_at": analyzed_at,
        "duration_ms": str(trace_data.get("duration_ms", 0)
                           or codex_data.get("duration_ms", 0)),
        "duration_api_ms": str(codex_data.get("duration_api_ms", 0)
                               if is_codex else int(duration_api_s * 1000)),
        "ttft_ms": str(codex_data.get("ttft_ms", 0) or trace_data.get("ttft_ms", 0)),
        "num_turns": str(codex_data.get("num_turns", 0)
                         if is_codex else trace_data.get("num_turns", 0)),
        "total_cost_usd": f"{total_cost_usd:.6f}",
        "input_tokens": str(input_tokens),
        "output_tokens": str(output_tokens),
        "cache_read_input_tokens": str(cache_read_tokens),
        "cache_creation_input_tokens": str(cache_creation_tokens),
        "cache_hit_rate_pct": f"{cache_hit_rate:.1f}",
        "total_tool_calls": str(total_tool_calls),
        "tool_call_breakdown": json.dumps(dict(tool_counts.most_common())),
        "skills_invoked": skills_str,
        "files_written": str(trace_data.get("files_written", 0)),
        "num_thinking_blocks": "0",
        "num_subagents": str(trace_data.get("num_subagents", 0)),
        "subagent_total_tool_uses": "0",
        "subagent_total_duration_ms": "0",
        "is_error": "0",
        "terminal_reason": "",
        "stop_reason": trace_data.get("stop_reason", ""),
    }


def _stream_user_prompt(lines):
    """Return the first usable text prompt from Claude stream user messages."""
    for item in lines:
        if item.get("type") != "user":
            continue
        message = item.get("message", item)
        if not isinstance(message, dict):
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            candidates = [content]
        elif isinstance(content, list):
            candidates = [block.get("text", "") for block in content
                          if isinstance(block, dict) and block.get("type") == "text"]
        else:
            candidates = []
        for candidate in candidates:
            if _is_real_prompt(candidate):
                return candidate[:500]
    return ""


def enrich_from_stream_log(row, stream_log_path):
    """Fill in identity/outcome fields from a stream-json log."""
    try:
        with open(stream_log_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return row

    inits = [l for l in lines if l.get("type") == "system" and l.get("subtype") == "init"]
    results = [l for l in lines if l.get("type") == "result"]

    if inits:
        init = inits[0]
        row["session_id"] = row["session_id"] or init.get("session_id", "")
        row["model"] = row["model"] or init.get("model", "")
        row["claude_code_version"] = row["claude_code_version"] or init.get("claude_code_version", "")
        row["permission_mode"] = row["permission_mode"] or init.get("permissionMode", "")
        plugins = [p.get("name", "") for p in init.get("plugins", [])]
        row["plugins_loaded"] = row["plugins_loaded"] or ",".join(plugins)

    if not row["entrypoint"]:
        for l in lines:
            if l.get("type") == "user" and l.get("entrypoint"):
                row["entrypoint"] = l["entrypoint"]
                break

    if not row["prompt"]:
        row["prompt"] = _stream_user_prompt(lines)
    if not row["prompt"]:
        for l in lines:
            if l.get("type") == "queue-operation" and l.get("operation") == "enqueue":
                prompt = l.get("content", "")[:500]
                if _is_real_prompt(prompt):
                    row["prompt"] = prompt
                    break
    if not row["prompt"]:
        for l in lines:
            if l.get("type") != "assistant":
                continue
            msg = l.get("message", l)
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("name") == "Skill":
                        skill = block.get("input", {}).get("skill", "")
                        args = block.get("input", {}).get("args", "")
                        row["prompt"] = f"/{skill} {args}".strip()[:500]
                        break
            if row["prompt"]:
                break

    if results:
        last_result = results[-1]
        if row["duration_ms"] in ("", "0"):
            row["duration_ms"] = str(sum(r.get("duration_ms", 0) for r in results))
        if row["ttft_ms"] in ("", "0"):
            row["ttft_ms"] = str(results[0].get("ttft_ms", 0))
        if row["num_turns"] in ("", "0"):
            row["num_turns"] = str(sum(r.get("num_turns", 0) for r in results))
        row["is_error"] = str(1 if last_result.get("is_error", False) else 0)
        row["terminal_reason"] = last_result.get("terminal_reason", "")
        row["stop_reason"] = row["stop_reason"] or last_result.get("stop_reason", "")

    seen_tool_ids = set()
    skills = []
    files_written_count = 0
    num_thinking = 0
    for l in lines:
        if l.get("type") != "assistant":
            continue
        msg = l.get("message", l)
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_id = block.get("id", "")
                if tool_id and tool_id in seen_tool_ids:
                    continue
                seen_tool_ids.add(tool_id)
                inp = block.get("input", {})
                if block.get("name") == "Skill":
                    skills.append(inp.get("skill", ""))
                elif block.get("name") == "Write":
                    files_written_count += 1
            elif block.get("type") == "thinking":
                num_thinking += 1

    if skills:
        row["skills_invoked"] = row["skills_invoked"] or ",".join(dict.fromkeys(skills))
    if row["files_written"] in ("", "0"):
        row["files_written"] = str(files_written_count)
    row["num_thinking_blocks"] = str(num_thinking)

    task_starts = [l for l in lines if l.get("subtype") == "task_started"]
    task_notifications = [l for l in lines if l.get("subtype") == "task_notification"]
    if row["num_subagents"] in ("", "0"):
        row["num_subagents"] = str(len(task_starts))
    row["subagent_total_tool_uses"] = str(sum(t.get("usage", {}).get("tool_uses", 0) for t in task_notifications))
    row["subagent_total_duration_ms"] = str(sum(t.get("usage", {}).get("duration_ms", 0) for t in task_notifications))

    return row


def enrich_from_prompt_file(row, prompt_path):
    """Use the initial harness prompt when telemetry redacts or omits it."""
    if _is_real_prompt(row.get("prompt", "")):
        return row
    try:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        characters = []
        with open(prompt_path, "rb") as prompt_file:
            while len(characters) < 500:
                byte = prompt_file.read(1)
                if not byte:
                    tail = decoder.decode(b"", final=True)
                    if tail:
                        characters.extend(tail)
                    break
                decoded = decoder.decode(byte, final=False)
                if decoded:
                    characters.extend(decoded)
        prompt = "".join(characters[:500])
    except (OSError, UnicodeError):
        return row
    if _is_real_prompt(prompt):
        row["prompt"] = prompt
    return row


SCHEMA = {
    "session_id": "string",
    "model": "string",
    "claude_code_version": "string",
    "permission_mode": "string",
    "entrypoint": "string",
    "prompt": "string",
    "plugins_loaded": "string",
    "analyzed_at": "string",
    "duration_ms": "int64",
    "duration_api_ms": "int64",
    "ttft_ms": "int64",
    "num_turns": "int64",
    "total_cost_usd": "float64",
    "input_tokens": "int64",
    "output_tokens": "int64",
    "cache_read_input_tokens": "int64",
    "cache_creation_input_tokens": "int64",
    "cache_hit_rate_pct": "float64",
    "total_tool_calls": "int64",
    "tool_call_breakdown": "string",
    "skills_invoked": "string",
    "files_written": "int64",
    "num_thinking_blocks": "int64",
    "num_subagents": "int64",
    "subagent_total_tool_uses": "int64",
    "subagent_total_duration_ms": "int64",
    "is_error": "int64",
    "terminal_reason": "string",
    "stop_reason": "string",
}


def build_autodl(row):
    return {
        "table_name": "claude_session_metrics",
        "schema": SCHEMA,
        "schema_mapping": None,
        "rows": [row],
        "chunk_size": 0,
        "expiration_days": 0,
        "partition_column": "",
    }


def main():
    stream_log = None
    prompt_file = None
    args = list(sys.argv[1:])

    if "--stream-log" in args:
        idx = args.index("--stream-log")
        if idx + 1 < len(args):
            stream_log = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("ERROR: --stream-log requires a path argument", file=sys.stderr)
            sys.exit(2)

    if "--prompt-file" in args:
        idx = args.index("--prompt-file")
        if idx + 1 < len(args):
            prompt_file = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("ERROR: --prompt-file requires a path argument", file=sys.stderr)
            sys.exit(2)

    if not args:
        print(f"Usage: {sys.argv[0]} <otel.jsonl> [output-autodl.json] "
              "[--stream-log <claude-output.log>] [--prompt-file <initial-prompt.txt>]",
              file=sys.stderr)
        sys.exit(2)

    log_path = args[0]
    output_path = args[1] if len(args) > 1 else "claude-session-metrics-autodl.json"

    row = parse_otel(log_path)
    if stream_log:
        row = enrich_from_stream_log(row, stream_log)
    if prompt_file:
        row = enrich_from_prompt_file(row, prompt_file)
    if not _is_real_prompt(row.get("prompt", "")):
        row["prompt"] = ""

    autodl = build_autodl(row)

    with open(output_path, "w") as f:
        json.dump(autodl, f, indent=4)

    print(f"OK: wrote {output_path}")
    print(f"  model={row['model']} cost=${row['total_cost_usd']} "
          f"duration={int(row['duration_ms'])//1000}s "
          f"turns={row['num_turns']} tools={row['total_tool_calls']} "
          f"subagents={row['num_subagents']}")
    print(f"  tokens: in={row['input_tokens']} out={row['output_tokens']} "
          f"cache_read={row['cache_read_input_tokens']} "
          f"cache_create={row['cache_creation_input_tokens']} "
          f"hit_rate={row['cache_hit_rate_pct']}%")

    required = {
        "session_id": row.get("session_id", ""),
        "duration_ms": row.get("duration_ms", "0"),
        "num_turns": row.get("num_turns", "0"),
        "total_cost_usd": row.get("total_cost_usd", "0.000000"),
        "prompt": row.get("prompt", ""),
    }
    missing = [k for k, v in required.items()
               if not v or v in ("0", "0.000000")]
    if missing:
        print(f"ERROR: required fields are empty or zero: {', '.join(missing)}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
