# API and version skew

`api/hypershift/v1beta1` defines HostedCluster, NodePool, and the related CRDs.
The HO installs them on management clusters; the HO, the CPO of every supported
release, the CLI, and external automation (managed services, multicluster
engines) read and write them.

- **Moderate**: new optional fields, and new feature-gated or tech-preview
  fields, that existing objects never set and that change nothing until set.
- **Critical**: changes to existing fields' meaning, defaults, validation (CEL
  rules, enums, immutability), or serialization. Existing objects and clients
  may be rejected, defaulted differently, or misread.
- **Skew**: one HO serves control planes of several releases, and their CPOs
  read the same objects. A field the HO starts writing or reading must be safe
  for every supported CPO version, and the reverse. Behaviour that depends on
  both sides agreeing is an upgrade and version-skew path: Critical.
- Generated files (`zz_generated*`, CRD manifests, `client/`) and vendored
  copies of the API module follow their source change.
