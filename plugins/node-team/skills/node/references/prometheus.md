# Prometheus on OpenShift/Kubernetes

Query cluster metrics using `promtool`. Install: `brew install prometheus`.

## Critical Rules

These caused real failures — follow exactly.

1. **Run setup + queries in a single bash call.** Shell variables (`$PROM_URL`, `$HTTP_CONFIG`, `$TOKEN`) don't persist across separate bash invocations. Combine with `&&`.

2. **Never use `!=` in PromQL.** Zsh mangles `!=` into `\!=` via history expansion, even inside single quotes. Use `=~".+"` instead of `!=""`, and negated regex instead of `!=`.

3. **JSON output is a raw array.** `promtool -o json` outputs `[{metric:{...}, value:[ts, val]}, ...]` — NOT `{data:{result:...}}`. Parse with `jq '.[]'`, not `jq '.data.result[]'`.

4. **`oc whoami -t` may return empty AND exit non-zero.** Client-cert kubeconfigs have no session token. Always: `TOKEN=$(oc whoami -t 2>/dev/null || true)`, then check if empty and fall back to creating a service account token.

5. **`promtool check healthy/ready` returns 503 on Thanos Querier.** Expected — Thanos doesn't expose `/-/healthy`. Test with `promtool query instant ... 'up'` instead.

6. **Clean up temp files.** Always `rm -f "$HTTP_CONFIG"` and `kill $PF_PID 2>/dev/null` after queries.

## OpenShift Setup Pattern

All in one bash call:

1. Get token: `oc whoami -t` or create SA `prometheus-reader` in `openshift-monitoring` with `cluster-monitoring-view` role, then `oc create token`
2. Get Thanos route: `oc -n openshift-monitoring get route thanos-querier -o jsonpath='{.status.ingress[].host}'`
3. Write HTTP config to temp file (Bearer token + `insecure_skip_verify: true`)
4. Run queries
5. Clean up temp file

For vanilla Kubernetes: find the Prometheus service (`kubectl get svc -A | grep prometheus`), port-forward to 9090, no auth usually needed.

## Cross-Platform Date

macOS and Linux `date` differ. Use: `date -u -d '1 hour ago' +FMT 2>/dev/null || date -u -v-1H +FMT`
