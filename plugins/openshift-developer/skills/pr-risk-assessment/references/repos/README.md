# Repository guidance

Each repository can teach the pr-risk-assessment skill how its changes reach
installations, without growing the skill itself. The skill reads a
repository's guidance only for that repository's pull requests, and reads only
the topic files the diff touches.

## Layout

```text
references/repos/<org>/<repo>/
├── README.md     # the index: read for every pull request in the repository
└── <topic>.md    # read only when the diff touches the topic's paths
```

## The index

Keep it short; it is read for every pull request:

1. **What ships and where it runs**: the components, and how a change reaches
   installations (with an upgrade of what, or at once across a fleet).
2. **Branches**: which branches feed which releases.
3. **Topics**: a table mapping paths to topic files, with one line on why the
   area matters.
4. **What does not ship**: paths that are Low unless they change what ships.

## Topic files

Describe the mechanisms that set the blast radius in one area:

- who consumes what the code produces, and whether existing installations
  receive it;
- what makes a change there Critical, and what keeps it Moderate or Low;
- where to verify those facts in the source at the base commit.

Write durable mechanisms, not verdicts on particular pull requests, and keep
each statement checkable in the source. Guidance helps place a change against
the skill's definitions; it never replaces them or lowers a tier below them.

## Adding a repository

1. Create `references/repos/<org>/<repo>/README.md` following the outline above,
   and topic files for the areas that need them. See
   [openshift/hypershift](openshift/hypershift/README.md) for an example.
2. Add eval cases for representative pull requests, ideally ones a reviewer
   would tier differently from a quick read, and register them in the plugin's
   evals README.
3. To have the repository's maintainers approve changes to its guidance, add an
   `OWNERS` file in its directory.
