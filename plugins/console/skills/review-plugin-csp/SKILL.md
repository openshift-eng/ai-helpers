---
name: review-plugin-csp
description: "Review an OpenShift Console dynamic plugin's source, build configuration and resource declarations for CSP compatibility. Use when preparing a plugin for CSP enforcement or investigating reported CSP violations."
argument-hint: "[plugin-path] [--policy-file <path>] [--console-ref <git-ref>]"
compatibility: Designed for Claude Code. Requires a local plugin repository. Optional gh CLI or internet access for fetching Console source baselines.
license: Apache-2.0
---

# Review Console plugin CSP compatibility

Scan a Console dynamic plugin for code, configuration and resource patterns that conflict with a given Content Security Policy, and produce a report with file locations, affected directives and migration steps.

## Background

Content Security Policy (CSP) is a browser security mechanism delivered via an HTTP response header that controls which sources of scripts, styles, images, connections and other resources are permitted on a page. OpenShift Console serves a single CSP header on its HTML document. Dynamic plugins load over the network at runtime via Module Federation and execute within the Console document — so the Console's CSP governs all plugin code. Plugin assets are proxied through the Console backend at `/api/plugins/<name>/`, making them same-origin (`'self'`). A plugin's `spec.contentSecurityPolicy` in its ConsolePlugin CR declares additional source allowances that the console-operator aggregates into the document-wide policy; this is not per-plugin isolation.

## Usage

```text
/console:review-plugin-csp [plugin-path] [--policy-file path] [--console-ref git-ref]
```

- `plugin-path` defaults to the current repository.
- `--policy-file` supplies a file containing CSP directive values or CSP response-header lines. Prefer the policy on the Console HTML document where the plugin runs.
- `--console-ref` identifies an OpenShift Console Git revision for a source-derived baseline when a deployed policy is unavailable.

Additional policy, origin, build-mode or browser-report context may be supplied in the request. These arguments guide the review; they do not change Console configuration.

Perform source/configuration review and report recommendations. Apply fixes, run builds or exercise a running application when the user's request includes that work. A review alone does not authorize dependency installation, deployment or changes to a cluster policy.

## Establish scope and policy

1. Locate the plugin metadata, source entry points, webpack/Rspack configuration, lockfile, ConsolePlugin manifests and any existing build output. Identify the build modes and plugin versions in scope.
   If the path does not identify a Console dynamic plugin or the supplied artifact, ask for the intended path/context before treating unrelated files as plugin code.
2. Establish the Console document origin if known. Resolve relative resource URLs against that origin/base path, not the plugin container's own host.
3. Select and record the policy basis:
   - **Supplied effective policy:** distinguish enforcing headers from report-only headers. If several enforcing policies are present, a request must satisfy all of them; do not merge their source lists into a more permissive policy.
   - **Source-derived baseline:** use the caller's Console checkout/revision, or fetch the requested revision from `openshift/console`. Inspect `pkg/utils/utils.go`, the serving header in `pkg/server/server.go`, and configuration mapping in `pkg/serverconfig/config.go`. Record the resolved revision and relevant defaults. Cluster/operator additions remain unverified unless supplied.
   - **Conditional assessment:** if no reliable policy can be established, report requirements such as “this path requires dynamic evaluation to be permitted.” State unknowns; do not invent the final policy of a future release.
4. A plugin's `spec.contentSecurityPolicy` shows intended additions. Check supported directive names against the target Console's vendored API/schema when needed; do not recommend declaring a directive type that does not exist in the target API version (for example, `ObjectSrc` was removed from the ConsolePlugin API in January 2025). Verify additions against a supplied effective policy where possible; a manifest alone does not prove deployment or propagation. Declarations contribute to the Console document policy, not a separate sandbox for each plugin. The API imposes limits: a plugin may declare at most 5 directive entries with up to 16 values each; values may not contain wildcards (`*`), single quotes, whitespace, commas or semicolons. The `spec.contentSecurityPolicy` field is available only in `console.openshift.io/v1`; manifests using `v1alpha1` cannot declare CSP sources and should be upgraded.

If the ConsolePlugin CR is managed by an operator (e.g., CMO, COO, HCO) rather than included in the plugin repository, note this as a verification gap — the deployed CR should be checked separately for CSP declarations. Note unused dependencies, dead webpack rules or vestigial environment variables (e.g., an empty `SEGMENT_KEY`) that hint at removed features — these are not current findings but signal code that could introduce CSP requirements if re-enabled.

Read only relevant files and dependencies. Candidate searches are a starting point: inspect executable context and import/build paths before concluding that a pattern is relevant. Avoid scanning all of node_modules or assuming every installed dependency enters the delivered bundle.

Keep these distinctions in the report: policy contents, report-only/enforcement mode, and rollout defaults. A reported violation under report-only does not establish that an operation was blocked.

## Inspect the plugin

### Executable scripts and evaluation

- Trace actual `eval()`, `new Function()`, string-based timers and generated evaluation through reachable plugin code or bundler output. Compare string compilation with `script-src` (or its default-src fallback), including `unsafe-eval`; a script-src-elem allowance alone does not authorize evaluation.
- Inspect production and development `devtool` settings separately. Eval-based source maps may affect only a development build.
- Follow dependencies or polyfills implicated by the source/build configuration. Report installed-but-untraced code as a verification gap, not an executed violation. Pay special attention to `NodePolyfillPlugin` / `node-polyfill-webpack-plugin` — it registers `vm-browserify` as a polyfill for Node's `vm` module, and `vm-browserify` calls `eval()`. Check whether the polyfill is provided via `resolve.fallback` (bundled only if a module explicitly imports `vm`) or `ProvidePlugin` (injected when the provided identifier appears in any module, without an explicit import). Either way, confirm the polyfill actually appears in the emitted bundle before reporting an eval violation. If bundled, it requires `'unsafe-eval'`; exclude it with `excludeAliases: ['vm']` if `vm` is not needed. This is the most common source of accidental eval in Console plugins.
- Check for Monaco editor (`monaco-editor`, `@monaco-editor/react`, `@patternfly/react-code-editor`). `@monaco-editor/loader` defaults to loading Monaco from `cdn.jsdelivr.net` — verify the plugin calls `loader.config({ monaco })` or bundles Monaco locally to avoid external script loads. Monaco also creates web workers, typically via `blob:` URLs; without `MonacoWebpackPlugin` or a `MonacoEnvironment.getWorker` override, these may be blocked under `worker-src` (falls back to `script-src`). If Console provides Monaco as a shared module, worker management is Console's responsibility.
- Check for `echarts` in dependencies (common via Perses). echarts renders to `<canvas>` (CSP-safe) but some features (custom formatters, tooltip templates) may use `new Function()`, requiring `'unsafe-eval'`. Verify with a bundle search if present.
- Check for `ajv` (common via `@rjsf/validator-ajv8` for JSON Schema form validation). Ajv 8 compiles validators using `new Function()` at runtime, requiring `'unsafe-eval'`. If `'unsafe-eval'` is removed, switch to Ajv standalone code generation (pre-compile validators at build time).
- Check for `lodash` `_.template()` usage. It compiles template strings via `new Function()`, requiring `'unsafe-eval'`. Replace with ES template literal functions when the substitutions are simple string interpolations.
- Check activation conditions for conditionally-executed code. Analytics SDKs, telemetry helpers and feature-flagged paths may be bundled but only execute when explicitly configured — for example, a non-empty API key, a runtime feature flag or a user opt-in. Trace the guard conditions and initialization flow before reporting an active incompatibility; being bundled does not prove code runs on every page load.
- Inspect dynamically created script elements, inline HTML scripts and actual inline event-handler attributes. React event callbacks are not automatically HTML inline handlers.
- Check the bundler's `output.publicPath` configuration. Module Federation loads remote entry points and shared chunks by inserting script elements at runtime. If `publicPath` points to a different origin than the Console document, those loads require that origin in `script-src`. `ConsoleRemotePlugin` normally forces `publicPath` to `/api/plugins/<name>/` (same-origin), but a custom override would change this.
- Check the directive applicable to each mechanism: `script-src-elem`, `script-src-attr` and their fallbacks can differ from `script-src`. A nonce on a script element does not authorize string evaluation or event-handler attributes.
- Under a policy without `strict-dynamic`, a matching host-source, scheme-source or `'self'` in the effective directive is sufficient to authorize an external script or stylesheet. A valid nonce is an alternative authorization, not an additional requirement on top of a source match. Do not recommend that a plugin add a nonce to a script that is already allowed by a declared source.
- If `strict-dynamic` is present in `script-src`: host-based sources, scheme-based sources, `'unsafe-inline'` and `'self'` are all ignored for script loading — only nonce or hash authorization applies. Additionally, trust propagates: scripts loaded dynamically by an already-authorized script (non-parser-inserted) are automatically allowed without their own nonce. This matters for Module Federation chunk loading and any plugin code that creates script elements at runtime.

### Styles and bundler configuration

- Inspect CSS loading/extraction and runtime style insertion. A style-loader path without effective nonce support may conflict with a policy prohibiting inline style elements.
- Check the applicable `style-src-elem`/`style-src-attr` policy and fallbacks. A script nonce does not authorize an unrelated style element.
- Inspect how a style nonce is actually obtained and applied. A configured nonce option without a demonstrated value/propagation path is incomplete evidence.
- Do not flag every JSX `style` prop or DOM style-property assignment as an inline-style violation. Determine the emitted mechanism; request browser verification when the distinction matters.
- Suggest compatible extraction or valid nonce support as appropriate to the plugin's bundler/version, without assuming a webpack option also works in Rspack. Rspack's native CSS handling (rules with `type: 'css'` and `builtin:lightningcss-loader`) extracts CSS to separate files rather than injecting inline styles — this is CSP-compatible and does not require `'unsafe-inline'` in `style-src`.
- Check for CSS-in-JS libraries (typestyle, styled-components, emotion, MUI/`@mui/material` which uses Emotion internally, etc.) that create `<style>` elements at runtime. A matching nonce or hash in the effective `style-src-elem` directive, or its `style-src`/`default-src` fallback, can authorize the element without `'unsafe-inline'`; otherwise, permitting it requires `'unsafe-inline'`, just like `style-loader`. Note that `CSSStyleSheet.insertRule()` itself is not currently blocked by CSP in browsers, but CSS-in-JS libraries typically create the `<style>` element first (which is the CSP-relevant step) and then call `insertRule()` on it. If migrating away from `'unsafe-inline'`, these libraries need a nonce-aware configuration or replacement with static CSS extraction.
- Inspect CSS files for `@import` rules and `@font-face` `src` declarations that reference external URLs. These are governed by `style-src` and `font-src` respectively, even when the parent stylesheet is same-origin. Shared dependencies such as PatternFly may also inject runtime styles that the plugin does not directly control.

### Resource URLs and connections

- Identify external scripts, stylesheets, fonts, images, worker scripts and browser requests such as fetch/XHR/axios, WebSocket, EventSource and sendBeacon.
- For `new Worker()`, `new SharedWorker()` and `navigator.serviceWorker.register()`, the governing directive is `worker-src`, falling back to `child-src`, then `script-src`, then `default-src`. The Console CSP API does not expose `worker-src` as a declarable directive; if a plugin requires non-self workers, document this as a platform limitation.
- Blob URLs (`blob:`) and data URLs (`data:`) require the corresponding scheme source in the applicable directive — they are not covered by `'self'`. Check for `URL.createObjectURL()` used with workers or scripts, and data URI construction. Note that `blob:` URLs used as `<a href>` for file downloads are navigations, not resource loads — CSP does not restrict them.
- Associate each request with its actual directive and fallback. For example, fetching an image with JavaScript uses `connect-src` for that fetch; an image element uses `img-src`.
- Compare destinations with the applicable sources and known origin. Respect scheme, host, port, path and directive-specific behavior; substring equality is not CSP source matching. Missing `connect-src` falls back to `default-src` rather than automatically permitting all destinations.
- Assets served through the Console proxy at `/api/plugins/<name>/` are same-origin with the Console document and match `'self'` under normal deployment. Plugin proxy endpoints (`/api/proxy/plugin/<name>/<alias>/`) are also same-origin, so `connect-src` declarations are not needed for proxied backend requests. Direct requests to the plugin's own service endpoint bypass the proxy and have a different origin.
- Console hardcodes `frame-src 'none'` and `frame-ancestors 'none'` — these cannot be extended through the plugin API. Any plugin embedding iframes or expecting to be embedded will be blocked with no declaration workaround.
- Console does not currently set a `form-action` directive. If one is added in the future, form submissions to external origins (e.g., OAuth redirect flows) would need to be declared. Unlike most directives, `form-action` does not fall back to `default-src`.
- Do not flag every HTTPS image as prohibited: policies may intentionally allow `https:` for images. Likewise, evaluation or inline styles may be permitted by the assessed policy.
- For dynamic URLs, redirects, worker behavior or WebSocket source matching that cannot be resolved reliably, identify the specific uncertainty and a browser check.
- Prefer declaring required approved sources or changing the resource delivery mechanism over recommending a blanket wildcard as the automatic fix. The recommendation must fit the target API and administrator configuration.

A stricter migration assumption, such as removing `unsafe-eval`, must be labeled separately from the current-policy assessment. Do not present it as an approved future Console default.

When suggesting migration options, be aware of these targeted CSP keywords:
- `'unsafe-hashes'` allows specific inline event handlers and `style` attributes to be authorized by hash, without `'unsafe-inline'`. Useful when a small number of inline handlers cannot be refactored.
- `'wasm-unsafe-eval'` allows WebAssembly compilation (`WebAssembly.compile`, `WebAssembly.instantiate`) without the broader `'unsafe-eval'`. Relevant if a plugin bundles WASM modules.

After a redirect, CSP drops path-based source matching and checks only scheme, host and port. If a plugin loads resources through redirect chains, verify that the final destination's origin is permitted even without a path match.

## Interpret evidence and suggest migration

Use these verification states:

- **Observed violation:** an actual supplied or captured browser CSP report identifies the request/code path and policy. Record its directive, destination and disposition.
- **Expected incompatibility:** concrete behavior conflicts with the stated policy if that path executes. Describe that condition; do not call it observed.
- **Needs verification:** policy, destination, generated output or execution path is unresolved. Give a bounded next step.
- **Permitted in reviewed context:** relevant code/source is allowed by the assessed policy. Mention it when it explains a likely false positive or a different stricter-policy result.

Choose severity based on the affected workflow and deployment context, separately from verification state. Comments, string literals and search matches without executable evidence are not actionable findings on their own. Do not invent line numbers, active imports, runtime URLs or report data.

For each finding, propose the smallest appropriate migration and verification step. If changing source declarations could affect other plugins or the whole Console document, explain that scope. Proposed fixes are recommendations until applied under the user's requested workflow.

## Verify when evidence is available

Use supplied reports or an authorized running test application to check relevant workflows under the actual policy. Capture `SecurityPolicyViolationEvent`/CSP reports and the resource or operation outcome. A CORS error, HTTP failure or missing UI alone does not prove CSP caused it.

Exercise both the affected behavior and a permitted control when practical. Confirm that a deliberate unexpected violation is detected if relying on a test tracker. Keep expected negative cases narrowly scoped; do not disable all CSP checks to make a test pass.

Without runtime access, provide specific verification steps and leave predictions labeled as such. Builds can clarify emitted code but cannot demonstrate every runtime path. Tests cover the exercised workflows, not all possible plugin behavior.

When `node_modules` are not installed or a production bundle is unavailable, suggest concrete verification steps: build the plugin and search the output for known patterns (e.g., `eval(this.code)` for vm-browserify, `cdn.jsdelivr.net` for Monaco CDN loading), or use `npm pack <package>` to inspect a critical dependency's source without a full install. Also search the lockfile (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) for known CSP-problematic packages such as `vm-browserify`.

## Report

Include:

1. **Scope and policy basis:** plugin/build/version, origin if known, policy source/revision, mode and assumptions. State what was inspected and what was unavailable.
2. **Findings:** use a compact table with these columns, or an equivalent structured format:

   | Location | Directive | State | Impact / condition | Migration |
   |----------|-----------|-------|--------------------|-----------|

3. **Verification and remaining gaps:** checked workflows/results, targeted next steps and unresolved policy decisions.

Example findings, when supported by the inspected files and policy:

> | `src/api.ts:42` | `connect-src` | Expected incompatibility | `fetch('https://api.example.test/data')` is absent from connect-src; blocked under enforcement | Declare the approved source via `ConnectSrc` in the ConsolePlugin CR, or route through a Console proxy endpoint |
> | `webpack.config.ts:62` | `style-src` | Permitted | `style-loader` injects `<style>` elements, but current policy includes `'unsafe-inline'` | No action under current policy; switch to CSS extraction if `'unsafe-inline'` is removed |
> | `src/utils/telemetry.ts:50` | `script-src` | Needs verification | Segment SDK script element created only when API key is non-empty (currently `''`); if activated, `cdn.segment.com` is not in script-src | Confirm whether the key will be populated; if so, declare the source or use the Console SDK analytics helper |

If no actionable incompatibility is found, say so within the reviewed scope. An empty static review is not complete CSP certification.

Suggest next steps based on the findings: apply proposed migrations, add `spec.contentSecurityPolicy` declarations to the ConsolePlugin CR, build and verify the bundle contains no unexpected patterns, or test in a browser with CSP enforcement enabled.

## References

Use these when source matching, directive fallbacks or platform behavior needs clarification:

- [Content Security Policy specification](https://www.w3.org/TR/CSP3/)
- [Console policy builder](https://github.com/openshift/console/blob/main/pkg/utils/utils.go)
- [Console plugin CSP API](https://github.com/openshift/api/blob/master/console/v1/types_console_plugin.go)

The linked main/master files are entry points, not version-specific baselines. Use the requested/identified revision and effective policy for the actual assessment.
