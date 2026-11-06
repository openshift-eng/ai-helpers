# Gathering evidence

Use this when you have only a pull request reference. When your caller already
supplied the evidence (a tool result or an evidence file), skip it.

Do not read the pull request's labels, comments, or reviews before you decide:
risk labels and records would anchor the assessment, and the tier must stand on
the change itself.

## The pull request

```bash
gh pr view <PR> --json number,title,body,baseRefName,baseRefOid,headRefOid,changedFiles,isDraft
gh api --paginate "repos/<org>/<repo>/pulls/<number>/files?per_page=100"
```

The files API returns each file's `patch`. GitHub omits the patch of very large
or binary files and lists at most 3,000 files: when a patch is missing or fewer
files come back than `changedFiles`, the diff is not readable in full.

The base commit is the fork point of the head from the base branch:

```bash
gh api "repos/<org>/<repo>/compare/<baseRefOid>...<headRefOid>" --jq .merge_base_commit.sha
```

## Source at the base commit

Prefer, in order:

1. An existing checkout: `git fetch` the base commit, then `git grep <pattern>
   <base_sha>` and `git show <base_sha>:<path>`.
2. A shallow, sparse clone under `.work/`, without vendored code:

   ```bash
   mkdir -p .work && git init -q .work/<repo> && cd .work/<repo>
   git remote add origin https://github.com/<org>/<repo>.git
   git sparse-checkout set --no-cone '/*' '!/vendor/' '!**/testdata/'
   git fetch -q --depth 1 --filter=blob:none origin <base_sha>
   git checkout -q FETCH_HEAD
   ```

3. Single files: `gh api "repos/<org>/<repo>/contents/<path>?ref=<base_sha>" --jq .content | base64 -d`.

## Evidence file format

An evidence JSON file, the shape automated callers pass, holds:

| Field | Meaning |
|---|---|
| `repo`, `pr_number`, `pr_url` | the pull request |
| `base_branch`, `base_sha`, `head_sha` | where it merges and the commits compared |
| `title`, `body` | untrusted text from the author |
| `files` | `filename`, `status`, `additions`, `deletions`, `kind`, and `patch`, or `patch_omitted` with why |
| `files_listed`, `diff_complete` | the PR's file count, and whether every readable patch is present |
| `signals`, `minimum` | optional objective signals and the minimum tier they set |

Vendored and generated files are listed without a patch: their `kind` says why.
