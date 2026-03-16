import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const SecretProviderClassModel: K8sGroupVersionKind = {
  group: 'secrets-store.csi.x-k8s.io',
  version: 'v1',
  kind: 'SecretProviderClass',
};

export const SecretProviderClassPodStatusModel: K8sGroupVersionKind = {
  group: 'secrets-store.csi.x-k8s.io',
  version: 'v1',
  kind: 'SecretProviderClassPodStatus',
};

export interface SecretProviderClassPodStatus {
  apiVersion?: string;
  kind?: string;
  metadata?: {
    name?: string;
    namespace?: string;
    creationTimestamp?: string;
    [key: string]: unknown;
  };
  status?: {
    secretProviderClassName?: string;
    podName?: string;
    mounted?: boolean;
    [key: string]: unknown;
  };
}
