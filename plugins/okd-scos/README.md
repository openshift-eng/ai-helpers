# okd-scos plugin

OKD SCOS bootimage management for the `okd_assistant` persona.

## Skills

### bump-scos-bootimage

Updates `data/data/coreos/scos.json` in `openshift/installer` to point at a
newer CentOS Stream CoreOS 10 (SCOS) build.

**Usage:**
```
/okd-scos:bump-scos-bootimage [--build-id <BUILD_ID>]
```

The skill discovers the latest eligible build (available for all four
architectures: x86_64, aarch64, s390x, ppc64le), runs `plume cosa2stream`
inside the CoreOS Assembler container to regenerate the JSON, verifies the
result, and opens a PR against `openshift/installer`.

See [SKILL.md](skills/bump-scos-bootimage/SKILL.md) for full details.
