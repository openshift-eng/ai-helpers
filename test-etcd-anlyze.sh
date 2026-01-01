 #!/bin/bash

  # Set up environment
  DURATION=5
  VERBOSE=false
  EXPORT_HTML=false
  WORK_DIR=".work/etcd-analysis/$(date +%Y%m%d_%H%M%S)"

  # Parse basic arguments
  while [[ $# -gt 0 ]]; do
      case $1 in
          --duration)
              DURATION="$2"
              shift 2
              ;;
          --verbose)
              VERBOSE=true
              shift
              ;;
          --export-html)
              EXPORT_HTML=true
              shift
              ;;
          *)
              echo "Unknown option: $1"
              exit 1
              ;;
      esac
  done

  # Create working directory
  mkdir -p "$WORK_DIR"
  echo "Analysis workspace: $WORK_DIR"

  # Verify prerequisites
  if ! command -v oc &> /dev/null; then
      echo "Error: oc CLI not found"
      exit 1
  fi

  if ! command -v jq &> /dev/null; then
      echo "Error: jq not found"
      exit 1
  fi

  if ! oc whoami &> /dev/null; then
      echo "Error: Not connected to cluster"
      exit 1
  fi

  echo "Starting ETCD performance analysis (${DURATION}m window)..."
  echo "Timestamp: $(date)"
  echo ""

  # Get etcd pods
  ETCD_PODS=($(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'))

  if [ ${#ETCD_PODS[@]} -eq 0 ]; then
      echo "Error: No running etcd pods found"
      exit 1
  fi

  echo "Found ${#ETCD_PODS[@]} running etcd pods:"
  for pod in "${ETCD_PODS[@]}"; do
      echo "  - $pod"
  done
  echo ""

  # Select primary pod
  PRIMARY_POD="${ETCD_PODS[0]}"
  echo "Using primary pod: $PRIMARY_POD"
  echo ""

  echo "==============================================="
  echo "DATABASE PERFORMANCE ANALYSIS"
  echo "==============================================="
  echo ""

  # Get database status
  DB_STATUS=$(oc exec -n openshift-etcd "$PRIMARY_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json 2>/dev/null)

  if [ -z "$DB_STATUS" ]; then
      echo "Failed to collect etcd metrics"
      exit 1
  fi

  echo "Database Statistics:"
  echo "$DB_STATUS" | jq -r '.[] |
      "Endpoint: \(.Endpoint)
    Version: \(.Status.version)  
    DB Size: \(.Status.dbSize) bytes (\((.Status.dbSize / 1024 / 1024) | floor)MB)
    DB In Use: \(.Status.dbSizeInUse) bytes (\((.Status.dbSizeInUse / 1024 / 1024) | floor)MB)
    Leader: \(if .Status.leader == .Status.header.member_id then "YES" else "NO" end)
  "'

  echo ""
  echo "Fragmentation Analysis:"
  echo "$DB_STATUS" | jq -r '.[] |
      if .Status.dbSize > 0 then
          ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) as $frag |
          "Endpoint: \(.Endpoint)
    Fragmentation: \($frag | floor)%" +
          if $frag > 50 then
              " - WARNING: High fragmentation detected"
          elif $frag > 30 then
              " - NOTICE: Moderate fragmentation"  
          else
              " - OK"
          end
      else
          "Endpoint: \(.Endpoint)
    Fragmentation: N/A"
      end'

  echo ""
  echo "==============================================="
  echo "CLUSTER HEALTH CHECK"
  echo "==============================================="
  echo ""

  oc exec -n openshift-etcd "$PRIMARY_POD" -c etcdctl -- etcdctl endpoint health --cluster 2>/dev/null || echo "Health check failed"

  echo ""
  echo "==============================================="
  echo "PERFORMANCE LOG ANALYSIS"
  echo "==============================================="
  echo ""

  # Get recent logs
  LOGS=$(oc logs -n openshift-etcd "$PRIMARY_POD" -c etcd --since="${DURATION}m" 2>/dev/null)

  # Analyze slow operations
  SLOW_OPS=$(echo "$LOGS" | grep -i "slow" | wc -l)
  echo "Slow operations in last ${DURATION}m: $SLOW_OPS"

  if [ "$SLOW_OPS" -gt 0 ]; then
      echo "Recent slow operations:"
      echo "$LOGS" | grep -i "slow" | tail -5
  fi

  echo ""
  echo "Analysis complete!"
  echo "Results saved to: $WORK_DIR"

