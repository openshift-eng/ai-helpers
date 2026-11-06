# Platforms

Platform code (AWS, Azure, GCP, KubeVirt, Agent, OpenStack, PowerVS, IBM Cloud)
manages the cloud infrastructure of running hosted clusters: load balancers,
DNS zones and records, private endpoints (PrivateLink, Private Service
Connect), security groups and firewalls, and identities (IAM roles, workload
identity, service accounts).

- **Critical**: changing DNS records, endpoints, load balancers, or firewall
  rules that running clusters use, since a defect breaks API or ingress
  reachability; provisioning new credentials or identities into control plane
  or guest namespaces, or widening what existing ones can do.
- **Moderate**: additive, opt-in features that change nothing for clusters that
  do not set them.
- A platform's support level (GA, Technology Preview, Developer Preview) does
  not lower the tier for the clusters already running on it.
