/**
 * Example of using PatternFly 6 glass theme tokens in a custom component
 *
 * Glass theme activates when the .pf-v6-theme-glass class is on <html>
 */

import React from 'react';
import { Card, CardTitle, CardBody } from '@patternfly/react-core';

export const GlassCard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <Card
      style={{
        // Use glass background tokens
        backgroundColor: 'var(--pf-t--global--background--color--glass--primary--default)',
        backdropFilter: 'var(--pf-t--global--background--filter--glass--blur--primary)',
        // Optional: add subtle border for better definition
        border: '1px solid var(--pf-t--global--border--color--default)',
      }}
    >
      <CardBody>{children}</CardBody>
    </Card>
  );
};

export const GlassFloatingCard: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => {
  return (
    <Card
      style={{
        // Use glass floating context for elevated/modal content
        backgroundColor: 'var(--pf-t--global--background--color--glass--floating--default)',
        backdropFilter: 'var(--pf-t--global--background--filter--glass--blur--floating)',
        border: '1px solid var(--pf-t--global--border--color--default)',
        boxShadow: 'var(--pf-t--global--box-shadow--lg)',
      }}
    >
      <CardTitle>{title}</CardTitle>
      <CardBody>{children}</CardBody>
    </Card>
  );
};
