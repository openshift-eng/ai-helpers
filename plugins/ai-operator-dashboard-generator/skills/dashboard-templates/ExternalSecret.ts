import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const ExternalSecretModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'ExternalSecret',
};

export const ClusterExternalSecretModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'ClusterExternalSecret',
};
