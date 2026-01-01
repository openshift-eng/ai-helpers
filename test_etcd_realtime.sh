 #!/bin/bash

  # ETCD Real-time Performance Monitor
  # Simple test script for monitoring ETCD performance metrics

  set -e

  # Configuration
  INTERVAL=${1:-5}  # Default 5 seconds
  TEST_DURATION=60  # Run for 60 seconds
  WORK_DIR=".work/etcd-realtime-$(date +%Y%m%d_%H%M%S)"

  echo "ETCD Real-time Performance Monitor"
  echo "================================="
  echo "Start time: $(date)"
  echo "Update interval: ${INTERVAL} seconds"
  echo "Test duration: ${TEST_DURATION} seconds"
  echo ""

  # Create work directory
  mkdir -p "$WORK_DIR"
  CSV_FILE="$WORK_DIR/metrics.csv"
  echo "timestamp,db_size_mb,fragmentation_pct,commit_latency_ms,status" > "$CSV_FILE"

  # Get ETCD pod
  ETCD_POD=$(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  echo "Monitoring pod: $ETCD_POD"
  echo ""

  # Monitor loop
  START_TIME=$(date +%s)
  ITERATION=0

  while true; do
      CURRENT_TIME=$(date +%s)
      ELAPSED=$((CURRENT_TIME - START_TIME))

      # Check if test duration exceeded
      if [ $ELAPSED -ge $TEST_DURATION ]; then
          echo "Test duration reached. Stopping..."
          break
      fi

      ITERATION=$((ITERATION + 1))
      TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

      echo "=== Iteration $ITERATION | $(date '+%H:%M:%S') ==="

      # Collect database metrics
      DB_STATUS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- \
          etcdctl endpoint status --cluster -w json 2>/dev/null)

      if [ $? -eq 0 ] && [ -n "$DB_STATUS" ]; then
          # Parse metrics
          DB_SIZE_MB=$(echo "$DB_STATUS" | jq -r '[.[] | (.Status.dbSize / 1024 / 1024)] | max | floor')
          FRAGMENTATION=$(echo "$DB_STATUS" | jq -r '[.[] | if .Status.dbSize > 0 then ((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) else 0 end] 
  | max | floor')

          # Quick health check for latency
          HEALTH_OUTPUT=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- \
              etcdctl endpoint health --cluster 2>/dev/null)
          COMMIT_LATENCY=$(echo "$HEALTH_OUTPUT" | grep -o 'took = [0-9.]*ms' | head -1 | grep -o '[0-9.]*')

          # Determine status
          STATUS="HEALTHY"
          if [ "$FRAGMENTATION" -gt 50 ]; then
              STATUS="CRITICAL"
          elif [ "$FRAGMENTATION" -gt 30 ]; then
              STATUS="WARNING"
          fi

          # Display metrics
          printf "Database Size:     %5s MB\n" "$DB_SIZE_MB"
          printf "Fragmentation:     %5s%%\n" "$FRAGMENTATION"
          printf "Commit Latency:    %5s ms\n" "$COMMIT_LATENCY"
          printf "Status:            %s\n" "$STATUS"

          # Status indicator
          case $STATUS in
              "HEALTHY")  echo "✅ All metrics within normal range" ;;
              "WARNING")  echo "⚠️  Performance warnings detected" ;;
              "CRITICAL") echo "🔥 Critical performance issues" ;;
          esac

          # Save to CSV
          echo "$TIMESTAMP,$DB_SIZE_MB,$FRAGMENTATION,$COMMIT_LATENCY,$STATUS" >> "$CSV_FILE"

      else
          echo "❌ Failed to collect metrics from ETCD"
          echo "$TIMESTAMP,,,ERROR" >> "$CSV_FILE"
      fi

      # Progress info
      REMAINING=$((TEST_DURATION - ELAPSED))
      echo "Elapsed: ${ELAPSED}s | Remaining: ${REMAINING}s"
      echo ""

      # Wait for next iteration
      sleep "$INTERVAL"
  done

  echo ""
  echo "Monitoring Complete!"
  echo "==================="
  echo "Total iterations: $ITERATION"
  echo "Results saved to: $WORK_DIR"
  echo ""
  echo "View results:"
  echo "  cat $CSV_FILE"
  echo "  ls -la $WORK_DIR/"
  echo ""

  # Show final summary
  if [ -f "$CSV_FILE" ]; then
      echo "Final metrics summary:"
      tail -5 "$CSV_FILE"
  fi

