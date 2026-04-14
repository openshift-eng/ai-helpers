import * as React from 'react';
import { useTranslation } from 'react-i18next';
import Helmet from 'react-helmet';
import {
  Title,
  Card,
  CardTitle,
  CardBody,
  Grid,
  GridItem,
  Button,
  Label,
  DescriptionList,
  DescriptionListTerm,
  DescriptionListDescription,
  DescriptionListGroup,
  Alert,
  AlertVariant,
  Switch,
} from '@patternfly/react-core';
import { ArrowLeftIcon, KeyIcon, CheckCircleIcon, TimesCircleIcon } from '@patternfly/react-icons';
import { useK8sWatchResource } from '@openshift-console/dynamic-plugin-sdk';
import { CertificateModel } from './components/crds/Certificate';
import { IssuerModel, ClusterIssuerModel } from './components/crds/Issuer';
import { ExternalSecretModel, ClusterExternalSecretModel } from './components/crds/ExternalSecret';
import { SecretStoreModel, ClusterSecretStoreModel } from './components/crds/SecretStore';
import { PushSecretModel, ClusterPushSecretModel } from './components/crds/PushSecret';
import {
  SecretProviderClassModel,
  SecretProviderClassPodStatusModel,
  SecretProviderClassPodStatus,
} from './components/crds/SecretProviderClass';
import { EventModel, getInvolvedObjectKind, K8sEvent } from './components/crds/Events';
import { dump as yamlDump } from 'js-yaml';

// YAML syntax colors (on black background): blue (keys), mustard yellow (values)
const YAML_KEY_COLOR = '#60a5fa';
const YAML_VALUE_COLOR = '#eab308';
const HIDDEN_VALUE_PLACEHOLDER = '********';

function colorizeYaml(yamlString: string): React.ReactNode {
  const lines = yamlString.split('\n');
  return (
    <>
      {lines.map((line, i) => {
        // Key: value
        const keyValueMatch = line.match(/^(\s*)(.+?)(\s*:\s*)(.*)$/);
        if (keyValueMatch) {
          const [, indent, key, sep, value] = keyValueMatch;
          return (
            <span key={i}>
              {indent}
              <span style={{ color: YAML_KEY_COLOR }}>{key}</span>
              {sep}
              <span style={{ color: YAML_VALUE_COLOR }}>{value}</span>
              {'\n'}
            </span>
          );
        }
        // List item: - value
        const listMatch = line.match(/^(\s*)(-\s+)(.*)$/);
        if (listMatch) {
          const [, indent, dash, rest] = listMatch;
          return (
            <span key={i}>
              {indent}
              <span style={{ color: YAML_KEY_COLOR }}>{dash.trim() || '-'}</span>
              <span style={{ color: YAML_VALUE_COLOR }}>{rest}</span>
              {'\n'}
            </span>
          );
        }
        // Comment or continuation line: use value color for non-empty, keep structure
        if (line.trim().startsWith('#')) {
          return (
            <span key={i} style={{ color: '#6b7280' }}>
              {line}
              {'\n'}
            </span>
          );
        }
        return (
          <span key={i}>
            {line ? <span style={{ color: YAML_VALUE_COLOR }}>{line}</span> : null}
            {'\n'}
          </span>
        );
      })}
    </>
  );
}

export const ResourceInspect: React.FC = () => {
  const { t } = useTranslation('plugin__ocp-secrets-management');

  // State for revealing sensitive data (separate for spec and status)
  const [showSpecSensitiveData, setShowSpecSensitiveData] = React.useState(false);
  const [showStatusSensitiveData, setShowStatusSensitiveData] = React.useState(false);

  // Parse URL manually since useParams() isn't working in plugin environment
  const pathname = window.location.pathname;
  const pathParts = pathname.split('/');

  // Expected format: /secrets-management/inspect/{resourceType}/{namespace}/{name}
  // or: /secrets-management/inspect/{resourceType}/{name} (for cluster-scoped)
  const baseIndex = pathParts.findIndex((part) => part === 'inspect');
  const resourceType =
    baseIndex >= 0 && pathParts.length > baseIndex + 1 ? pathParts[baseIndex + 1] : '';

  let namespace: string | undefined;
  let name: string;

  if (pathParts.length > baseIndex + 3) {
    // Format: /secrets-management/inspect/{resourceType}/{namespace}/{name}
    namespace = pathParts[baseIndex + 2];
    name = pathParts[baseIndex + 3];
  } else {
    // Format: /secrets-management/inspect/{resourceType}/{name} (cluster-scoped)
    name = pathParts[baseIndex + 2] || '';
  }

  const handleBackClick = () => {
    window.history.back();
  };

  // Determine the correct model based on resource type
  const getResourceModel = () => {
    switch (resourceType) {
      case 'certificates':
        return CertificateModel;
      case 'issuers':
        return IssuerModel;
      case 'clusterissuers':
        return ClusterIssuerModel;
      case 'externalsecrets':
        return ExternalSecretModel;
      case 'clusterexternalsecrets':
        return ClusterExternalSecretModel;
      case 'secretstores':
        return SecretStoreModel;
      case 'clustersecretstores':
        return ClusterSecretStoreModel;
      case 'pushsecrets':
        return PushSecretModel;
      case 'clusterpushsecrets':
        return ClusterPushSecretModel;
      case 'secretproviderclasses':
        return SecretProviderClassModel;
      default:
        return null;
    }
  };

  const model = getResourceModel();
  const isClusterScoped =
    resourceType === 'clusterissuers' ||
    resourceType === 'clustersecretstores' ||
    resourceType === 'clusterexternalsecrets' ||
    resourceType === 'clusterpushsecrets';

  const [resource, loaded, loadError] = useK8sWatchResource<any>({
    groupVersionKind: model,
    name: name,
    namespace: isClusterScoped ? undefined : namespace || 'demo',
    isList: false,
  });

  // Watch SecretProviderClassPodStatus resources when inspecting a SecretProviderClass
  const [podStatuses, podStatusesLoaded, podStatusesError] = useK8sWatchResource<
    SecretProviderClassPodStatus[]
  >({
    groupVersionKind: SecretProviderClassPodStatusModel,
    namespace: resourceType === 'secretproviderclasses' ? namespace || 'demo' : undefined,
    isList: true,
  });

  // Watch Events for this resource (involvedObject name/kind/namespace)
  const eventsNamespace = isClusterScoped ? 'default' : namespace || 'default';
  const involvedKind = getInvolvedObjectKind(resourceType);
  const eventsFieldSelector = [
    `involvedObject.name=${name}`,
    `involvedObject.kind=${involvedKind}`,
    ...(!isClusterScoped && namespace ? [`involvedObject.namespace=${namespace}`] : []),
  ].join(',');
  const [events, eventsLoaded, eventsError] = useK8sWatchResource<K8sEvent[]>({
    groupVersionKind: EventModel,
    namespace: eventsNamespace,
    isList: true,
    fieldSelector: eventsFieldSelector,
  });

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return '-';
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const renderMetadata = () => {
    if (!resource?.metadata) return null;

    return (
      <Card>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>{t('Metadata')}</CardTitle>
        <CardBody>
          <DescriptionList
            isHorizontal
            style={{
              rowGap: '0.25rem',
              background: '#1e1e1e',
              paddingTop: '16px',
              paddingLeft: '16px',
              paddingBottom: '16px',
            }}
          >
            <DescriptionListGroup
              style={{
                display: 'flex',
                flexDirection: 'row',
                alignItems: 'baseline',
                marginBottom: 0,
              }}
            >
              <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                {t('Name:')}
              </DescriptionListTerm>
              <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                {resource.metadata.name || '-'}
              </DescriptionListDescription>
            </DescriptionListGroup>
            {resource.kind && (
              <DescriptionListGroup
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {t('Kind:')}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {resource.kind}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            {resource.metadata.namespace && (
              <DescriptionListGroup
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {t('Namespace:')}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {resource.metadata.namespace}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            {resource.apiVersion && (
              <DescriptionListGroup
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {t('API version:')}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {resource.apiVersion}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            <DescriptionListGroup
              style={{
                display: 'flex',
                flexDirection: 'row',
                alignItems: 'baseline',
                marginBottom: 0,
              }}
            >
              <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                {t('Creation timestamp:')}
              </DescriptionListTerm>
              <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                {formatTimestamp(resource.metadata.creationTimestamp)}
              </DescriptionListDescription>
            </DescriptionListGroup>
            {resource.metadata.uid && (
              <DescriptionListGroup
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {t('UID:')}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {resource.metadata.uid}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
            {resource.metadata.resourceVersion && (
              <DescriptionListGroup
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {t('Resource version:')}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {resource.metadata.resourceVersion}
                </DescriptionListDescription>
              </DescriptionListGroup>
            )}
          </DescriptionList>
        </CardBody>
      </Card>
    );
  };

  const renderLabels = () => {
    const labels = resource?.metadata?.labels;
    if (!labels || Object.keys(labels).length === 0) {
      return (
        <Card>
          <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>{t('Labels')}</CardTitle>
          <CardBody>
            <em>{t('No labels')}</em>
          </CardBody>
        </Card>
      );
    }

    const cardStyle = {
      background: '#1e1e1e',
      borderRadius: '4px',
      border: '1px solid #374151',
    };
    return (
      <Card style={cardStyle}>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>{t('Labels')}</CardTitle>
        <CardBody>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {Object.entries(labels).map(([key, value]) => (
              <Label key={key} color="blue">
                {key}: {value}
              </Label>
            ))}
          </div>
        </CardBody>
      </Card>
    );
  };

  const renderAnnotations = () => {
    const annotations = resource?.metadata?.annotations;
    if (!annotations || Object.keys(annotations).length === 0) {
      return (
        <Card>
          <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
            {t('Annotations')}
          </CardTitle>
          <CardBody>
            <em>{t('No annotations')}</em>
          </CardBody>
        </Card>
      );
    }

    const cardStyle = {
      background: '#1e1e1e',
      borderRadius: '4px',
      border: '1px solid #374151',
    };
    return (
      <Card style={cardStyle}>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>{t('Annotations')}</CardTitle>
        <CardBody>
          <DescriptionList isHorizontal style={{ rowGap: '0.25rem', background: '#1e1e1e' }}>
            {Object.entries(annotations).map(([key, value]) => (
              <DescriptionListGroup
                key={key}
                style={{
                  display: 'flex',
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  marginBottom: 0,
                }}
              >
                <DescriptionListTerm style={{ minWidth: '16rem', flexShrink: 0 }}>
                  {key}
                </DescriptionListTerm>
                <DescriptionListDescription style={{ wordBreak: 'break-all', flex: 1 }}>
                  {value}
                </DescriptionListDescription>
              </DescriptionListGroup>
            ))}
          </DescriptionList>
        </CardBody>
      </Card>
    );
  };

  // Function to check if object contains sensitive data
  const containsSensitiveData = (obj: any): boolean => {
    const sensitiveKeys = [
      'password',
      'secret',
      'token',
      'key',
      'privateKey',
      'secretKey',
      'accessKey',
      'secretAccessKey',
      'clientSecret',
      'apiKey',
      'auth',
      'authentication',
      'credential',
      'cert',
      'certificate',
      'tls',
      // SecretProviderClass specific sensitive patterns
      'tenantId',
      'clientId',
      'subscriptionId',
      'resourceGroup',
      'vaultName',
      'keyVaultName',
      'servicePrincipal',
      'roleArn',
      'region',
      'vaultUrl',
      'vaultAddress',
      'vaultNamespace',
      'vaultRole',
      'vaultPath',
      'parameters',
    ];

    const checkObject = (data: any): boolean => {
      if (Array.isArray(data)) {
        return data.some(checkObject);
      }

      if (data && typeof data === 'object') {
        for (const [key, value] of Object.entries(data)) {
          const lowerKey = key.toLowerCase();
          const isSensitive = sensitiveKeys.some((sensitiveKey) =>
            lowerKey.includes(sensitiveKey.toLowerCase()),
          );

          if (isSensitive || checkObject(value)) {
            return true;
          }
        }
      }

      return false;
    };

    return checkObject(obj);
  };

  const renderSpecification = () => {
    if (!resource?.spec) return null;

    const hasSensitiveData = containsSensitiveData(resource.spec);
    const shouldHideContent = hasSensitiveData && !showSpecSensitiveData;

    return (
      <Card>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {t('Specification')}
            {hasSensitiveData && (
              <Switch
                id="spec-sensitive-toggle"
                label={showSpecSensitiveData ? t('Hide sensitive data') : t('Show sensitive data')}
                isChecked={showSpecSensitiveData}
                onChange={(event, checked) => setShowSpecSensitiveData(checked)}
                ouiaId="SpecificationSensitiveToggle"
              />
            )}
          </div>
        </CardTitle>
        <CardBody>
          <pre
            style={{
              padding: '16px',
              borderRadius: '4px',
              overflow: 'auto',
              fontSize: '13px',
              maxHeight: '400px',
              background: '#1e1e1e',
              border: '1px solid #374151',
            }}
          >
            {shouldHideContent ? (
              <span style={{ color: YAML_VALUE_COLOR }}>{HIDDEN_VALUE_PLACEHOLDER}</span>
            ) : (
              colorizeYaml(yamlDump(resource.spec, { lineWidth: -1 }))
            )}
          </pre>
        </CardBody>
      </Card>
    );
  };

  const renderStatus = () => {
    if (!resource?.status) return null;

    // For Certificates, always show the toggle when status exists (status may reference secrets/certs);
    // for other resources, only show when status contains sensitive-looking keys.
    const hasSensitiveData =
      resourceType === 'certificates' || containsSensitiveData(resource.status);
    const shouldHideContent = hasSensitiveData && !showStatusSensitiveData;

    return (
      <Card>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {t('Status')}
            {hasSensitiveData && (
              <Switch
                id="status-sensitive-toggle"
                label={
                  showStatusSensitiveData ? t('Hide sensitive data') : t('Show sensitive data')
                }
                isChecked={showStatusSensitiveData}
                onChange={(event, checked) => setShowStatusSensitiveData(checked)}
                ouiaId="StatusSensitiveToggle"
              />
            )}
          </div>
        </CardTitle>
        <CardBody>
          <pre
            style={{
              padding: '16px',
              borderRadius: '4px',
              overflow: 'auto',
              fontSize: '13px',
              maxHeight: '400px',
              background: '#1e1e1e',
              border: '1px solid #374151',
            }}
          >
            {shouldHideContent ? (
              <span style={{ color: YAML_VALUE_COLOR }}>{HIDDEN_VALUE_PLACEHOLDER}</span>
            ) : (
              colorizeYaml(yamlDump(resource.status, { lineWidth: -1 }))
            )}
          </pre>
        </CardBody>
      </Card>
    );
  };

  const renderSecretProviderClassPodStatuses = () => {
    if (resourceType !== 'secretproviderclasses' || !resource) return null;

    // Filter pod statuses that reference this SecretProviderClass
    const relevantPodStatuses = (podStatuses || []).filter(
      (podStatus) => podStatus.status.secretProviderClassName === resource.metadata.name,
    );

    if (relevantPodStatuses.length === 0) {
      return (
        <Card>
          <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
            {t('Pod Statuses')}
          </CardTitle>
          <CardBody>
            <p>{t('No pods are currently using this SecretProviderClass.')}</p>
          </CardBody>
        </Card>
      );
    }

    return (
      <Card>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
          {t('Pod Statuses')} ({relevantPodStatuses.length})
        </CardTitle>
        <CardBody>
          <div style={{ overflowX: 'auto' }}>
            <table className="pf-c-table pf-m-compact pf-m-grid-md" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('Pod Name')}</th>
                  <th>{t('Mounted')}</th>
                  <th>{t('Created')}</th>
                </tr>
              </thead>
              <tbody>
                {relevantPodStatuses.map((podStatus) => (
                  <tr key={podStatus.metadata.name}>
                    <td>{podStatus.status.podName || podStatus.metadata.name}</td>
                    <td>
                      <Label
                        color={podStatus.status.mounted ? 'green' : 'red'}
                        icon={podStatus.status.mounted ? <CheckCircleIcon /> : <TimesCircleIcon />}
                      >
                        {podStatus.status.mounted ? t('Yes') : t('No')}
                      </Label>
                    </td>
                    <td>{formatTimestamp(podStatus.metadata.creationTimestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    );
  };

  const renderEvents = () => {
    if (!resource) return null;
    const list = events ?? [];
    const sorted = [...list].sort((a, b) => {
      const tA = a.lastTimestamp || a.firstTimestamp || a.metadata?.creationTimestamp || '';
      const tB = b.lastTimestamp || b.firstTimestamp || b.metadata?.creationTimestamp || '';
      return tB.localeCompare(tA);
    });

    return (
      <Card>
        <CardTitle style={{ color: 'var(--pf-t--color--blue--30)' }}>
          {t('Events')} {eventsLoaded && `(${sorted.length})`}
        </CardTitle>
        <CardBody>
          {!eventsLoaded && <em>{t('Loading events...')}</em>}
          {eventsLoaded && eventsError && (
            <Alert variant={AlertVariant.warning} isInline title={t('Could not load events')}>
              {eventsError?.message || String(eventsError)}
            </Alert>
          )}
          {eventsLoaded && !eventsError && sorted.length === 0 && <em>{t('No events')}</em>}
          {eventsLoaded && !eventsError && sorted.length > 0 && (
            <div
              style={{
                overflowX: 'auto',
                background: '#1e1e1e',
                borderRadius: '4px',
                border: '1px solid #374151',
                paddingLeft: '16px',
                paddingTop: '16px',
              }}
            >
              <table className="pf-c-table pf-m-grid-md" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                      {t('Type')}
                    </th>
                    <th style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                      {t('Reason')}
                    </th>
                    <th style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                      {t('Message')}
                    </th>
                    <th style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                      {t('Count')}
                    </th>
                    <th style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                      {t('Last seen')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((evt) => (
                    <tr key={evt.metadata?.name ?? evt.reason ?? ''}>
                      <td style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                        <Label color={evt.type === 'Warning' ? 'orange' : 'blue'}>
                          {evt.type || 'Normal'}
                        </Label>
                      </td>
                      <td style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                        {evt.reason ?? '-'}
                      </td>
                      <td
                        style={{
                          maxWidth: '20rem',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          paddingTop: '0.75rem',
                          paddingBottom: '0.75rem',
                        }}
                        title={evt.message}
                      >
                        {evt.message ?? '-'}
                      </td>
                      <td style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                        {evt.count ?? 1}
                      </td>
                      <td style={{ paddingTop: '0.375rem', paddingBottom: '0.375rem' }}>
                        {formatTimestamp(
                          evt.lastTimestamp ||
                            evt.firstTimestamp ||
                            evt.metadata?.creationTimestamp,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    );
  };

  const getResourceTypeDisplayName = () => {
    switch (resourceType) {
      case 'certificates':
        return t('Certificate');
      case 'issuers':
        return t('Issuer');
      case 'clusterissuers':
        return t('ClusterIssuer');
      case 'externalsecrets':
        return t('ExternalSecret');
      case 'clusterexternalsecrets':
        return t('ClusterExternalSecret');
      case 'secretstores':
        return t('SecretStore');
      case 'clustersecretstores':
        return t('ClusterSecretStore');
      case 'pushsecrets':
        return t('PushSecret');
      case 'clusterpushsecrets':
        return t('ClusterPushSecret');
      case 'secretproviderclasses':
        return t('SecretProviderClass');
      default:
        return t('Resource');
    }
  };

  if (!model) {
    return (
      <div className="co-m-pane__body">
        <Alert variant={AlertVariant.danger} title={t('Invalid resource type')} isInline>
          {t('The resource type "{resourceType}" is not supported.', { resourceType })}
        </Alert>
      </div>
    );
  }

  // For SecretProviderClass, also wait for pod statuses to load
  const allLoaded = resourceType === 'secretproviderclasses' ? loaded && podStatusesLoaded : loaded;

  if (!allLoaded) {
    return (
      <div className="co-m-loader co-an-fade-in-out">
        <div className="co-m-loader-dot__one"></div>
        <div className="co-m-loader-dot__two"></div>
        <div className="co-m-loader-dot__three"></div>
      </div>
    );
  }

  // Handle errors from both resource and pod status loading
  const anyError =
    loadError || (resourceType === 'secretproviderclasses' ? podStatusesError : null);

  if (anyError) {
    return (
      <div className="co-m-pane__body">
        <Alert variant={AlertVariant.danger} title={t('Error loading resource')} isInline>
          {anyError.message}
        </Alert>
      </div>
    );
  }

  if (!resource) {
    return (
      <div className="co-m-pane__body">
        <Alert variant={AlertVariant.warning} title={t('Resource not found')} isInline>
          {t('The {resourceType} "{name}" was not found.', {
            resourceType: getResourceTypeDisplayName(),
            name,
          })}
        </Alert>
      </div>
    );
  }

  return (
    <>
      <Helmet>
        <title>{t('{resourceType} details', { resourceType: getResourceTypeDisplayName() })}</title>
      </Helmet>

      <div className="co-m-pane__body">
        <div className="co-m-pane__heading">
          <div className="co-m-pane__name co-resource-item">
            <Button variant="plain" onClick={handleBackClick} style={{ marginRight: '16px' }}>
              <ArrowLeftIcon />
            </Button>
            <KeyIcon className="co-m-resource-icon" style={{ marginRight: '8px' }} />
            <Title headingLevel="h1" size="lg">
              {getResourceTypeDisplayName()}: {name}
            </Title>
          </div>
        </div>

        <Grid hasGutter>
          <GridItem span={12} style={{ padding: '0rem 2rem' }}>
            {renderMetadata()}
          </GridItem>
          <GridItem span={6} style={{ paddingLeft: '2rem' }}>
            {renderLabels()}
          </GridItem>
          <GridItem span={6} style={{ paddingRight: '2rem' }}>
            {renderAnnotations()}
          </GridItem>
          <GridItem span={6} style={{ paddingLeft: '2rem' }}>
            {renderSpecification()}
          </GridItem>
          <GridItem span={6}>{renderStatus()}</GridItem>
          <GridItem span={12} style={{ padding: '0rem 2rem' }}>
            {renderEvents()}
          </GridItem>
          {resourceType === 'secretproviderclasses' && (
            <GridItem span={12} style={{ padding: '0rem 2rem' }}>
              {renderSecretProviderClassPodStatuses()}
            </GridItem>
          )}
        </Grid>
      </div>
    </>
  );
};