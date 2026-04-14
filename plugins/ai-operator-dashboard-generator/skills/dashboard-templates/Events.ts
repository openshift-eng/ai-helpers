import { K8sGroupVersionKind } from '@openshift-console/dynamic-plugin-sdk/lib/extensions/console-types';

export const EventModel: K8sGroupVersionKind = {
  group: '',
  version: 'v1',
  kind: 'Event',
};

export interface K8sEvent {
  apiVersion?: string;
  kind?: string;
  metadata?: {
    name?: string;
    namespace?: string;
    creationTimestamp?: string;
    [key: string]: unknown;
  };
  type?: string;
  reason?: string;
  message?: string;
  count?: number;
  firstTimestamp?: string;
  lastTimestamp?: string;
  involvedObject?: {
    kind?: string;
    name?: string;
    namespace?: string;
    [key: string]: unknown;
  };
}

const RESOURCE_TYPE_TO_KIND: Record<string, string> = {
  certificates: 'Certificate',
  issuers: 'Issuer',
  clusterissuers: 'ClusterIssuer',
  externalsecrets: 'ExternalSecret',
  clusterexternalsecrets: 'ClusterExternalSecret',
  secretstores: 'SecretStore',
  clustersecretstores: 'ClusterSecretStore',
  pushsecrets: 'PushSecret',
  clusterpushsecrets: 'ClusterPushSecret',
  secretproviderclasses: 'SecretProviderClass',
};

export function getInvolvedObjectKind(resourceType: string): string {
  return RESOURCE_TYPE_TO_KIND[resourceType] ?? resourceType;
}
