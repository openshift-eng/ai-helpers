---
name: HyperShift AWS Provider
description: Use this skill when you need to deploy HyperShift clusters on AWS infrastructure with proper STS credentials, IAM roles, and VPC configuration
---

# HyperShift AWS Provider

This skill provides implementation guidance for creating HyperShift clusters on AWS, handling AWS-specific requirements including STS credentials, IAM roles, VPC configuration, and regional best practices.

## When to Use This Skill

This skill is automatically invoked by the `/hcp:generate aws` command to guide the AWS provider cluster creation process.

## Prerequisites

- AWS CLI configured with appropriate credentials
- HyperShift operator installed and configured
- STS credentials file for the target AWS account
- IAM role with required permissions for HyperShift
- Pull secret for accessing OpenShift images

## AWS Provider Overview

### AWS Provider Peculiarities

- **Requires AWS credentials (STS):** Must have valid STS credentials file
- **Region selection affects availability zones:** Different regions have different AZ availability
- **Instance types vary by region:** Not all instance types available in all regions
- **VPC CIDR must not conflict:** Must not overlap with existing infrastructure
- **IAM roles:** Can be auto-created or use pre-existing roles

### Common AWS Configurations

**Development Environment:**
- Single replica control plane (cost-effective)
- m5.large instances (balanced performance/cost)
- 2 availability zones (basic redundancy)
- Basic networking (public endpoints)

**Production Environment:**
- Highly available control plane
- m5.xlarge+ instances (better performance)
- 3+ availability zones (high availability)
- Custom VPC configuration
- KMS encryption enabled

**Cost-Optimized Environment:**
- Single NAT gateway
- Smaller instance types
- Minimal replicas
- Spot instances (where applicable)

## Implementation Steps

### Step 1: Analyze Cluster Description

Parse the natural language description for AWS-specific requirements:

**Environment Type Detection:**
- **Development**: "dev", "development", "testing", "demo", "sandbox"
- **Production**: "prod", "production", "critical", "enterprise"
- **Cost-Optimized**: "cheap", "cost", "minimal", "budget", "demo"

**Performance Indicators:**
- **High Performance**: "performance", "fast", "high-compute", "intensive"
- **Standard**: Default moderate configuration
- **Minimal**: "small", "minimal", "basic", "simple"

**Security/Compliance:**
- **FIPS**: "fips", "compliance", "security", "regulated"
- **Private**: "private", "isolated", "secure", "internal"

**Special Requirements:**
- **Multi-AZ**: "highly available", "ha", "multi-zone", "resilient"
- **Single-AZ**: "single zone", "simple", "minimal"

### Step 2: Apply AWS Provider Defaults

**Required Parameters:**
- `--region`: AWS region (default: us-east-1)
- `--pull-secret`: Path to pull secret file
- `--release-image`: OpenShift release image
- `--sts-creds`: **REQUIRED** - Path to STS credentials file
- `--role-arn`: **REQUIRED** - ARN of the IAM role to assume
- `--base-domain`: **REQUIRED** - Base domain for the cluster

**Smart Defaults by Environment:**

**Development Environment:**
```bash
--instance-type m5.large
--node-pool-replicas 2
--control-plane-availability-policy SingleReplica
--endpoint-access Public
--root-volume-size 120
--zones auto-select 2 zones based on region
```

**Production Environment:**
```bash
--instance-type m5.xlarge
--node-pool-replicas 3
--control-plane-availability-policy HighlyAvailable
--endpoint-access PublicAndPrivate
--root-volume-size 120
--auto-repair true
--zones auto-select 3+ zones based on region
```

**Cost-Optimized Environment:**
```bash
--instance-type m5.large
--node-pool-replicas 2
--control-plane-availability-policy SingleReplica
--endpoint-access Public
--root-volume-size 120
--zones auto-select 2 zones (minimal redundancy)
```

### Step 3: Interactive Parameter Collection

**Required Information Collection:**

1. **Cluster Name**
   ```
   🔹 **Cluster Name**: What would you like to name your cluster?
      - Must be DNS-compatible (lowercase, hyphens allowed)
      - Used for AWS resource naming
      - Example: dev-cluster, prod-app, demo-env
   ```

2. **AWS Region**
   ```
   🔹 **AWS Region**: Which AWS region should host your cluster?
      - Consider latency to your users
      - Verify desired instance types are available
      - [Press Enter for default: us-east-1]

      Popular regions:
      - us-east-1 (N. Virginia) - Largest service availability
      - us-west-2 (Oregon) - West coast, latest services
      - eu-west-1 (Ireland) - Europe
      - ap-southeast-1 (Singapore) - Asia Pacific
   ```

3. **STS Credentials**
   ```
   🔹 **STS Credentials**: Path to your AWS STS credentials file?
      - Required for AWS authentication
      - Generate using: aws sts get-session-token
      - Example: /home/user/.aws/sts-creds.json
      - Format: {"AccessKeyId": "...", "SecretAccessKey": "...", "SessionToken": "..."}
   ```

4. **IAM Role ARN**
   ```
   🔹 **IAM Role ARN**: ARN of the IAM role for HyperShift?
      - Role must have required HyperShift permissions
      - Example: arn:aws:iam::123456789012:role/hypershift-operator-role
      - See: https://hypershift.openshift.io/aws-setup/
   ```

5. **Base Domain**
   ```
   🔹 **Base Domain**: What base domain should be used for cluster DNS?
      - Must be a domain you control in Route53
      - Used for cluster API and application routes
      - Example: example.com, clusters.mycompany.com
   ```

6. **Pull Secret**
   ```
   🔹 **Pull Secret**: Path to your OpenShift pull secret file?
      - Required for accessing OpenShift container images
      - Download from: https://console.redhat.com/openshift/install/pull-secret
      - Example: /home/user/pull-secret.json
   ```

7. **OpenShift Version**
   ```
   🔹 **OpenShift Version**: Which OpenShift version do you want to use?

      📋 **Check supported versions**: https://amd64.ocp.releases.ci.openshift.org/

      - Enter release image URL: quay.io/openshift-release-dev/ocp-release:X.Y.Z-multi
      - [Press Enter for default: quay.io/openshift-release-dev/ocp-release:4.18.0-multi]
   ```

**Optional Configuration (based on description analysis):**

8. **Instance Type** (if performance requirements detected)
   ```
   🔹 **Instance Type**: Select instance type based on your performance needs:
      - m5.large (2 vCPU, 8GB RAM) - Development, light workloads
      - m5.xlarge (4 vCPU, 16GB RAM) - Production, balanced workloads
      - m5.2xlarge (8 vCPU, 32GB RAM) - High-performance workloads
      - c5.xlarge (4 vCPU, 8GB RAM) - Compute-optimized
      - [Press Enter for default based on environment type]
   ```

9. **Node Pool Replicas**
   ```
   🔹 **Node Pool Replicas**: How many worker nodes do you need?
      - Minimum: 2 (for basic redundancy)
      - Production recommended: 3+
      - [Press Enter for default based on environment type]
   ```

10. **Availability Zones** (auto-selected, but confirmed)
    ```
    🔹 **Availability Zones**: Detected region: us-east-1
       Auto-selecting zones for optimal distribution:
       - Development: us-east-1a, us-east-1b (2 zones)
       - Production: us-east-1a, us-east-1b, us-east-1c (3 zones)

       Modify zone selection? [y/N]
    ```

### Step 4: Advanced Configuration (Conditional)

**For FIPS Compliance** (if detected):
```
🔹 **FIPS Mode**: Enable FIPS mode for compliance?
   - Required for government/regulated workloads
   - May impact performance
   - [yes/no] [Press Enter for default: no]
```

**For High-Performance Workloads**:
```
🔹 **Root Volume Size**: Increase root volume size?
   - Default: 120GB
   - High-performance workloads: 200GB+
   - [Press Enter for default: 120]
```

**For Production Environments**:
```
🔹 **Auto-Repair**: Enable automatic node repair?
   - Automatically replaces unhealthy nodes
   - Recommended for production
   - [yes/no] [Press Enter for default: yes for production]
```

### Step 5: Generate Command

**Basic AWS Cluster Command:**
```bash
hypershift create cluster aws \
  --name <cluster-name> \
  --namespace <cluster-name>-ns \
  --region <region> \
  --instance-type <instance-type> \
  --pull-secret <pull-secret-path> \
  --node-pool-replicas <replica-count> \
  --zones <zone-list> \
  --control-plane-availability-policy <policy> \
  --sts-creds <sts-creds-path> \
  --role-arn <role-arn> \
  --base-domain <base-domain> \
  --release-image <release-image>
```

**Development Configuration Example:**
```bash
hypershift create cluster aws \
  --name dev-cluster \
  --namespace dev-cluster-ns \
  --region us-east-1 \
  --instance-type m5.large \
  --pull-secret /path/to/pull-secret.json \
  --node-pool-replicas 2 \
  --zones us-east-1a,us-east-1b \
  --control-plane-availability-policy SingleReplica \
  --endpoint-access Public \
  --root-volume-size 120 \
  --sts-creds /path/to/sts-creds.json \
  --role-arn arn:aws:iam::123456789012:role/hypershift-role \
  --base-domain example.com \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi
```

**Production Configuration Example:**
```bash
hypershift create cluster aws \
  --name production-cluster \
  --namespace production-cluster-ns \
  --region us-west-2 \
  --instance-type m5.xlarge \
  --pull-secret /path/to/pull-secret.json \
  --node-pool-replicas 3 \
  --zones us-west-2a,us-west-2b,us-west-2c \
  --control-plane-availability-policy HighlyAvailable \
  --endpoint-access PublicAndPrivate \
  --root-volume-size 120 \
  --auto-repair \
  --sts-creds /path/to/sts-creds.json \
  --role-arn arn:aws:iam::123456789012:role/hypershift-prod-role \
  --base-domain clusters.company.com \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi
```

**FIPS-Enabled Configuration:**
```bash
hypershift create cluster aws \
  --name compliance-cluster \
  --namespace compliance-cluster-ns \
  --region us-gov-east-1 \
  --instance-type m5.xlarge \
  --pull-secret /path/to/pull-secret.json \
  --node-pool-replicas 3 \
  --zones us-gov-east-1a,us-gov-east-1b,us-gov-east-1c \
  --control-plane-availability-policy HighlyAvailable \
  --fips \
  --sts-creds /path/to/sts-creds.json \
  --role-arn arn:aws-us-gov:iam::123456789012:role/hypershift-fips-role \
  --base-domain secure.gov.example.com \
  --release-image quay.io/openshift-release-dev/ocp-release:4.18.0-multi
```

### Step 6: Pre-Flight Validation

**Provide validation commands:**
```
## Pre-Flight Checks

Before creating the cluster, verify your setup:

1. **AWS Credentials:**
   aws sts get-caller-identity

2. **STS Credentials File:**
   cat /path/to/sts-creds.json | jq .

3. **IAM Role Access:**
   aws iam get-role --role-name hypershift-role

4. **Route53 Domain:**
   aws route53 list-hosted-zones --query "HostedZones[?Name=='example.com.']"

5. **Region Availability:**
   aws ec2 describe-availability-zones --region us-east-1

6. **Instance Type Availability:**
   aws ec2 describe-instance-type-offerings --location-type availability-zone --filters Name=instance-type,Values=m5.large --region us-east-1
```

### Step 7: Post-Generation Instructions

**Next Steps:**
```
## Next Steps

1. **Verify prerequisites are met:**
   - AWS credentials configured
   - STS credentials file exists and is valid
   - IAM role has required permissions
   - Base domain exists in Route53

2. **Run the generated command:**
   Copy and paste the command above

3. **Monitor cluster creation:**
   kubectl get hostedcluster -n <cluster-namespace>
   kubectl get nodepool -n <cluster-namespace>

4. **Check AWS resources:**
   - EC2 instances in AWS console
   - Load balancers created
   - VPC and networking resources

5. **Access cluster when ready:**
   hypershift create kubeconfig --name <cluster-name> --namespace <cluster-namespace>
   export KUBECONFIG=<cluster-name>-kubeconfig
   oc get nodes
```

## Error Handling

### Invalid AWS Credentials

**Scenario:** AWS credentials are invalid or expired.

**Action:**
```
AWS credentials validation failed.

Please check:
1. AWS CLI configuration: aws configure list
2. STS credentials file validity
3. IAM permissions

Regenerate STS credentials:
  aws sts get-session-token --duration-seconds 3600
```

### IAM Role Not Found

**Scenario:** Specified IAM role doesn't exist or can't be assumed.

**Action:**
```
IAM role "arn:aws:iam::123456789012:role/hypershift-role" not found or inaccessible.

Please verify:
1. Role exists: aws iam get-role --role-name hypershift-role
2. Role has required permissions
3. Trust relationship allows your account to assume the role

See HyperShift AWS setup guide: https://hypershift.openshift.io/aws-setup/
```

### Region/Zone Issues

**Scenario:** Instance type not available in selected region/zones.

**Action:**
```
Instance type "m5.large" not available in zone "us-east-1f".

Checking alternative zones in us-east-1:
✅ us-east-1a (available)
✅ us-east-1b (available)
❌ us-east-1f (not available)

Suggested zones: us-east-1a,us-east-1b

Would you like me to update the command?
```

### Route53 Domain Issues

**Scenario:** Base domain not found in Route53 or not accessible.

**Action:**
```
Base domain "example.com" not found in Route53.

Please ensure:
1. Domain exists in Route53: aws route53 list-hosted-zones
2. Account has access to the hosted zone
3. Domain spelling is correct

Alternative: Use a subdomain you control (e.g., clusters.mydomain.com)
```

### Resource Limits

**Scenario:** AWS account limits would be exceeded.

**Action:**
```
AWS service limits may be exceeded:
- EC2 instances: Current: 18/20, Requested: 5 more
- Elastic IPs: Current: 4/5, Requested: 2 more

Consider:
1. Request limit increases via AWS Support
2. Choose smaller instance types
3. Reduce node count
4. Clean up unused resources
```

## Best Practices

### Cost Optimization

1. **Right-size instances:** Don't over-provision for development
2. **Use Spot instances:** Where appropriate for non-critical workloads
3. **Monitor resource usage:** Regularly review AWS costs
4. **Clean up unused clusters:** Delete development clusters when not needed

### Security

1. **Least privilege IAM:** Use minimal required permissions
2. **STS credentials:** Use short-lived credentials when possible
3. **Private networking:** Use PrivateAndPublic endpoints for production
4. **KMS encryption:** Enable for sensitive workloads

### High Availability

1. **Multi-AZ deployment:** Use 3+ availability zones for production
2. **Instance distribution:** Spread nodes across zones
3. **Auto-repair:** Enable for automatic recovery
4. **Monitoring:** Set up CloudWatch monitoring

### Network Planning

1. **VPC design:** Plan CIDR ranges carefully
2. **Subnet strategy:** Use public/private subnet design
3. **Load balancer:** Configure appropriate load balancer types
4. **DNS:** Ensure proper Route53 configuration

## Anti-Patterns to Avoid

❌ **Using root AWS credentials**
```
Never use root account credentials for HyperShift
```
✅ Use IAM roles and STS credentials

❌ **Single availability zone for production**
```
--zones us-east-1a  # Single point of failure
```
✅ Use multiple zones: `--zones us-east-1a,us-east-1b,us-east-1c`

❌ **Over-provisioning for development**
```
--instance-type m5.8xlarge --node-pool-replicas 10  # Expensive for dev
```
✅ Use appropriate sizing: `--instance-type m5.large --node-pool-replicas 2`

❌ **Ignoring region-specific limitations**
```
Choosing regions without checking instance type availability
```
✅ Verify instance types and services are available in target region

## Example Workflows

### Startup Development Environment
```
Input: "cheap AWS cluster for testing our new microservice"

Analysis:
- Environment: Development
- Cost focus: High priority
- Scale: Minimal

Generated Command:
hypershift create cluster aws \
  --name dev-microservice \
  --namespace dev-microservice-ns \
  --region us-east-1 \
  --instance-type m5.large \
  --node-pool-replicas 2 \
  --control-plane-availability-policy SingleReplica \
  --endpoint-access Public
```

### Enterprise Production
```
Input: "highly available AWS production cluster for customer-facing applications"

Analysis:
- Environment: Production
- Availability: High priority
- Scale: Enterprise

Generated Command:
hypershift create cluster aws \
  --name prod-customer-apps \
  --namespace prod-customer-apps-ns \
  --region us-west-2 \
  --instance-type m5.xlarge \
  --node-pool-replicas 5 \
  --zones us-west-2a,us-west-2b,us-west-2c \
  --control-plane-availability-policy HighlyAvailable \
  --endpoint-access PublicAndPrivate \
  --auto-repair
```

## See Also

- [HyperShift AWS Provider Documentation](https://hypershift.openshift.io/aws-setup/)
- [AWS IAM Roles for HyperShift](https://hypershift.openshift.io/aws-setup/#_prerequisites)
- [AWS CLI Configuration Guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [OpenShift on AWS Best Practices](https://docs.openshift.com/container-platform/latest/installing/installing_aws/)