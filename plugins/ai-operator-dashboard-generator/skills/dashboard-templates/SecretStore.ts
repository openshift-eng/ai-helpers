import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const SecretStoreModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'SecretStore',
};

export const ClusterSecretStoreModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'ClusterSecretStore',
};
