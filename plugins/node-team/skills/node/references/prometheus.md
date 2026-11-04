# Prometheus on OpenShift/Kubernetes

Query cluster metrics using `promtool`. Install: `brew install prometheus` (macOS), `sudo dnf install golang-github-prometheus` (Fedora), or the release tarball from `https://prometheus.io/download/` (any Linux).

## Critical Rules

These caused real failures. Follow exactly.

1. **Run setup + queries in a single bash call.** Shell variables (`$PROM_URL`, `$HTTP_CONFIG`, `$TOKEN`) don't persist across separate bash invocations. Combine with `&&`.

2. **Never use `!=` in PromQL.** Zsh mangles `!=` into `\!=` via history expansion, even inside single quotes. Use `=~".+"` instead of `!=""`, and negated regex instead of `!=`.

3. **JSON output is a raw array.** `promtool -o json` outputs `[{metric:{...}, value:[ts, val]}, ...]`, NOT `{data:{result:...}}`. Parse with `jq '.[]'`, not `jq '.data.result[]'`.

4. **`oc whoami -t` may return empty AND exit non-zero.** Client-cert kubeconfigs have no session token. Always: `TOKEN=$(oc whoami -t 2>/dev/null || true)`, then check if empty and fall back to creating a service account token.

5. **`promtool check healthy/ready` returns 503 on Thanos Querier.** Expected: Thanos doesn't expose `/-/healthy`. Test with `promtool query instant ... 'up'` instead.

6. **Clean up temp files.** Always `rm -f "$HTTP_CONFIG"` and `kill $PF_PID 2>/dev/null` after queries.

## OpenShift Setup Pattern

All in one bash call:

1. Get token: `oc whoami -t`. Only if that is empty, fall back to a service account: ask the user before creating anything, then create SA `prometheus-reader` in `openshift-monitoring`, bind `cluster-monitoring-view` (`oc adm policy add-cluster-role-to-user cluster-monitoring-view -z prometheus-reader -n openshift-monitoring`), and get a short-lived token with `oc create token prometheus-reader -n openshift-monitoring --duration=1h`
2. Get Thanos route: `oc -n openshift-monitoring get route thanos-querier -o jsonpath='{.status.ingress[].host}'`
3. Write HTTP config to a `mktemp` file with mode 600 (Bearer token). Prefer verifying TLS: extract the ingress CA (`oc -n openshift-config-managed get cm default-ingress-cert -o jsonpath='{.data.ca-bundle\.crt}'`) and set `tls_config.ca_file`. Use `insecure_skip_verify: true` only on throwaway dev clusters, because it sends the bearer token to an unverified endpoint
4. Run queries
5. Clean up the temp files. If you created the service account, tell the user and offer to remove it: `oc -n openshift-monitoring delete sa prometheus-reader` and `oc adm policy remove-cluster-role-from-user cluster-monitoring-view -z prometheus-reader -n openshift-monitoring`

For vanilla Kubernetes: find the Prometheus service (`kubectl get svc -A | grep prometheus`), port-forward to 9090, no auth usually needed.

## Cross-Platform Date

macOS and Linux `date` differ. Use: `date -u -d '1 hour ago' +FMT 2>/dev/null || date -u -v-1H +FMT`
