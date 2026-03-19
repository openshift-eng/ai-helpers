---
name: upgrade-sdk
description: Assists in the upgrade of an OpenShift Console dynamic plugin to the latest Console SDK version.
compatibility: Designed for Claude Code. Requires Node.js, gh CLI, and internet access.
argument-hint: "<current-target-version> <new-target-version>"
allowed-tools: Bash(gh api repos/openshift/console/contents/*), Bash(gh api repos/*/releases/tags/*), WebFetch(domain:raw.githubusercontent.com), AskUserQuestion, Bash(yarn npm info *), Bash(npm info *)
license: Apache-2.0
---

# Upgrade SDK

You are a senior software engineer with expertise in TypeScript, React, and webpack module federation, particularly in the context of OpenShift Console dynamic plugins. Your task is to assist developers in upgrading their Console dynamic plugins to a newer Console SDK version.

## Usage

```text
# Upgrade a Console plugin from version 4.18 to 4.22
/console:upgrade-sdk 4.18 4.22
```

Note that the `current-target-version` and `new-target-version` arguments are mandatory -- when not provided, use the `AskUserQuestion` tool to gather this information from the user.

## Background knowledge

### What is OpenShift Console?

OpenShift Console is the web-based UI for Red Hat OpenShift Container Platform. It provides cluster management, workload monitoring, and administrative capabilities. Console is built with React and TypeScript, and is designed as an extensible platform that allows **dynamic plugins** to add functionality without rebuilding or redeploying the console itself.

### How dynamic plugins work

Dynamic plugins use **webpack module federation** to load plugin code over the network at runtime. This means:

- Plugins are **completely decoupled** from the Console application -- they can be built, deployed, and upgraded independently.
- Plugins are delivered as container images and registered on the cluster via a `ConsolePlugin` custom resource.
- At startup, Console discovers enabled plugins and loads their assets (manifest, entry chunk, and exposed module chunks) from the cluster network.
- Console and plugins **share specific modules** (React, Redux, PatternFly topology, etc.) at runtime via webpack's share scope. This ensures a single copy of React is running and plugins can use Console-provided hooks and components. Plugins must NOT bundle their own copies of shared modules.
- Each plugin declares **extensions** (in `console-extensions.json` or inline in `webpack.config.ts`) that hook into Console's extension points -- adding pages, navigation items, resource views, dashboard cards, actions, and more.
- Plugin code is referenced via **`$codeRef`** entries that point to exposed webpack modules, which are loaded on demand.

### SDK packages

There are two distributable SDK packages plugins depend on:

| Package | Purpose |
|---------|---------|
| `@openshift-console/dynamic-plugin-sdk` | Core runtime APIs, types, hooks, and components used by plugins at runtime |
| `@openshift-console/dynamic-plugin-sdk-webpack` | Webpack `ConsoleRemotePlugin` that generates plugin manifests, configures module federation, and manages shared modules |

There is also `@openshift-console/dynamic-plugin-sdk-internal` which exposes additional Console code but has **no backwards compatibility guarantees**.

### SDK package versioning

SDK packages follow a semver scheme where the **major and minor version** indicates the earliest supported OCP Console version, and the patch version indicates the release of that particular package. For example, `4.22.0` is the initial release targeting Console 4.22. Pre-release versions use the format `4.22.0-prerelease.1`.

### Shared modules

Console provides specific modules (e.g., React, Redux, routing libraries) to plugins at runtime via webpack's share scope. Plugins should list these as `devDependencies` (not `dependencies`) since Console supplies them. The exact list and versions change between Console releases -- when Console upgrades a shared module (e.g., React 17 to 18), **all plugins must also upgrade** to the matching version, since only one version of each singleton module can be loaded at runtime.

Always fetch the SDK README at runtime to get the current shared modules list.

### Plugin metadata

Plugin metadata (`consolePlugin` object) can be specified in `package.json` or passed directly to `ConsoleRemotePlugin` in `webpack.config.ts`. Key fields:

- **`name`** -- unique plugin identifier, must match the `ConsolePlugin` resource name on the cluster (must be a valid DNS subdomain name)
- **`version`** -- semver version of the plugin
- **`exposedModules`** -- map of module names to file paths that can be referenced via `$codeRef`
- **`dependencies`** -- `@console/pluginAPI` semver range declaring which Console versions the plugin supports (e.g., `"^4.21.0"`)

## Reference documentation

The following remote sources are the **single source of truth** for upgrade information. You MUST fetch and read these at runtime -- do NOT rely on memorized or cached data about version-specific changes. If a fetch fails (e.g., a release notes file doesn't exist yet for a pre-release version, or a rate limit is hit), inform the user and proceed with the data you have.

### SDK README (shared modules, versioning, PatternFly compatibility)

Fetch this file to determine shared modules, SDK version mapping, and PatternFly version compatibility:

`https://raw.githubusercontent.com/openshift/console/refs/heads/main/frontend/packages/console-dynamic-plugin-sdk/README.md`

### SDK changelogs

Fetch both of these to identify breaking changes, type changes, deprecations, and new features across versions:

- `https://raw.githubusercontent.com/openshift/console/refs/heads/main/frontend/packages/console-dynamic-plugin-sdk/CHANGELOG-core.md`
- `https://raw.githubusercontent.com/openshift/console/refs/heads/main/frontend/packages/console-dynamic-plugin-sdk/CHANGELOG-webpack.md`

### Release notes

Fetch the release notes for EACH version in the upgrade range (from one version above the current through the target). Release notes document shared module changes, CSS removals, migration guides, and upgrade tips.

Available release notes versions:

!`gh api repos/openshift/console/contents/frontend/packages/console-dynamic-plugin-sdk/release-notes --jq .[].name`

Fetch each relevant version using this URL pattern:

`https://raw.githubusercontent.com/openshift/console/refs/heads/main/frontend/packages/console-dynamic-plugin-sdk/release-notes/<version>`

### Console plugin template (canonical reference implementation)

The [console-plugin-template](https://github.com/openshift/console-plugin-template) is the canonical reference for a Console dynamic plugin. Fetch its `package.json`, `tsconfig.json`, and `webpack.config.ts` for correct dependency versions, build configuration, and compiler options:

- `https://raw.githubusercontent.com/openshift/console-plugin-template/refs/heads/main/package.json`
- `https://raw.githubusercontent.com/openshift/console-plugin-template/refs/heads/main/tsconfig.json`
- `https://raw.githubusercontent.com/openshift/console-plugin-template/refs/heads/main/webpack.config.ts`

Key patterns to note from the template:
- SDK packages use dist-tags like `4.21-latest` rather than exact versions. Check what dist-tag is current for the target version.
- The `consolePlugin.dependencies` field uses a semver range like `"@console/pluginAPI": "^4.21.0"` to declare Console version compatibility.
- The template may not always be updated to the very latest in-development SDK version. Cross-reference with the changelogs and release notes for the actual target version.

## Upgrade procedure

Follow these steps in order:

### Step 1: Gather information

1. Read the plugin's `package.json` to understand current SDK versions, shared module versions, and PatternFly versions.
2. Read the plugin's `webpack.config.ts` (or `.js`) to understand the build setup.
3. Read the plugin's `tsconfig.json` to check compiler options.
4. Read `console-extensions.json` if it exists, to understand extension types in use.
5. Identify the current and target Console versions from the user's arguments.
6. Detect the plugin's package manager (see below).

#### Detecting the package manager

Determine which package manager the plugin uses by checking these indicators in order:

1. **`packageManager` field in `package.json`** -- e.g., `"packageManager": "yarn@4.13.0"` means Yarn Berry (v4). This is the most reliable signal.
2. **Lock file present in the repo root:**
   - `yarn.lock` -- Yarn (check format to distinguish v1 from Berry)
   - `package-lock.json` -- npm
   - `pnpm-lock.yaml` -- pnpm
3. **`.yarnrc.yml` file exists** -- indicates Yarn Berry (v2 to v5). Yarn v1 uses `.yarnrc` (no `.yml`).
4. **If ambiguous**, ask the user.

Use the detected package manager for ALL dependency operations throughout the upgrade:

| Package Manager | Install | Add/upgrade a dep |
|-----------------|---------|-------------------|
| npm | `npm install` | `npm install <pkg>@<version>` |
| Yarn Classic (v1) | `yarn install` | `yarn upgrade <pkg>@<version>` |
| Yarn Berry (v2, v3, v4, v5) | `yarn install` | `yarn up <pkg>@<version>` |
| pnpm | `pnpm install` | `pnpm update <pkg>@<version>` |

### Step 2: Fetch and research breaking changes

1. Fetch the **SDK README** to determine the current shared modules list, PatternFly compatibility table, and SDK version mapping.
2. Fetch **both changelogs** (core and webpack) and extract all entries between the current and target versions. Categorize changes as:
   - **Breaking** -- requires code changes, plugin will not work without them
   - **Type breaking** -- TypeScript type changes that may cause build failures
   - **Deprecated** -- still works but should be updated
   - **New features** -- optional improvements available
3. Fetch the **release notes** for each version in the upgrade range. These contain critical information about shared module version changes, CSS removals, and migration guides not always covered in the changelogs.
4. Fetch the **plugin template** files to use as a reference for correct dependency versions.
5. If the upgrade requires **major version bumps to shared modules** (e.g., React 17 to 18, react-i18next v11 to v16, react-redux v7 to v9), fetch the upstream migration/upgrade guides for those libraries to inform your code migration steps:
   - React: fetch the changelog, then follow links to the relevant upgrade guide (e.g., `react.dev/blog/2022/03/08/react-18-upgrade-guide` for React 18):
     `https://raw.githubusercontent.com/facebook/react/refs/heads/main/CHANGELOG.md`
   - react-i18next: `https://raw.githubusercontent.com/i18next/react-i18next/refs/heads/master/CHANGELOG.md`
   - react-redux: changelogs are in GitHub release notes. Fetch the relevant major version release (e.g., for v9: `gh api repos/reduxjs/react-redux/releases/tags/v9.0.0 --jq .body`)
   - PatternFly: fetch the upgrade guide and release highlights from the `patternfly-org` repo (raw markdown, easier to parse than the website):
     - `https://raw.githubusercontent.com/patternfly/patternfly-org/refs/heads/main/packages/documentation-site/patternfly-docs/content/releases/upgrade-guide.md`
     - `https://raw.githubusercontent.com/patternfly/patternfly-org/refs/heads/main/packages/documentation-site/patternfly-docs/content/releases/release-highlights.md`
   - For any other shared module with a major version bump, search for its changelog or migration guide on GitHub/npm

### Step 3: Present upgrade plan

Present a clear, versioned upgrade plan to the user that includes:

1. **Summary of breaking changes** across the version range, ordered by impact
2. **SDK package version updates** -- the exact `package.json` dependency changes needed
3. **Shared module version updates** -- version bumps for shared modules like `react`, `react-i18next`, `react-redux`, `redux`, `redux-thunk`, etc. Use the plugin template and release notes as the source of truth for correct versions.
4. **PatternFly version changes** -- if a PF major version change is required (refer to the compatibility table in the SDK README)
5. **Build tooling changes** -- webpack version requirements, TypeScript version requirements, tsconfig changes
6. **Code migration steps** -- specific code changes needed, with before/after examples drawn from the release notes migration guides
7. **Deprecation warnings** -- things that still work but should be updated

### Step 4: Execute changes (with user approval)

After the user approves the plan, make the changes:

1. Update `package.json` SDK and shared module versions
2. Update `tsconfig.json` if needed (e.g., `jsx` compiler option)
3. Update `webpack.config.ts` if needed
4. Apply code migrations for breaking changes
5. Update `console-extensions.json` if extension types changed
6. Run the appropriate install command for the detected package manager to update the lockfile
7. Attempt a build and fix any remaining issues
8. Run the plugin's test suite if available to catch regressions

## Important notes

- Always update the `@console/pluginAPI` semver range in plugin metadata (`consolePlugin.dependencies`) to match the new target version.
- Shared modules should be listed as `devDependencies` (not `dependencies`) in the plugin's `package.json`, since Console provides them at runtime.
- When upgrading across multiple major shared module versions (e.g., React 17 to 18), warn the user about potential runtime behavior changes beyond just type errors.
- When React has a major version bump, `@types/react` must also be updated to match. Major `@types/react` versions introduce their own breaking changes (e.g., v18 removed implicit `children` from `React.FC`). Check the plugin template for the correct `@types/react` version.
- PatternFly major version upgrades are significant -- recommend the user run the official PF codemods and review the PF upgrade guide.
- If the plugin uses `@openshift-console/dynamic-plugin-sdk-internal`, warn that this package has no backwards compatibility guarantees.
