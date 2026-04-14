import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const IssuerModel: K8sGroupVersionKind = {
  group: 'cert-manager.io',
  version: 'v1',
  kind: 'Issuer',
};

export const ClusterIssuerModel: K8sGroupVersionKind = {
  group: 'cert-manager.io',
  version: 'v1',
  kind: 'ClusterIssuer',
};
