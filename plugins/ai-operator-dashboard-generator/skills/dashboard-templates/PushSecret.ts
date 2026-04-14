import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const PushSecretModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'PushSecret',
};

export const ClusterPushSecretModel: K8sGroupVersionKind = {
  group: 'external-secrets.io',
  version: 'v1beta1',
  kind: 'ClusterPushSecret',
};
