import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const CertificateModel: K8sGroupVersionKind = {
  group: 'cert-manager.io',
  version: 'v1',
  kind: 'Certificate',
};
