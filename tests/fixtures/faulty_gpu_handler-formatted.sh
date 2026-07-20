#!/bin/bash -e

get_node_label() {
    local label=$(echo $1 | sed 's/[.]/\\./g')

    kubectl get node $NODE_NAME -o jsonpath="{.metadata.labels.$label}"
}

get_node_annotation() {
    local annotation=$(echo $1 | sed 's/[.]/\\./g')

    kubectl get node $NODE_NAME -o jsonpath="{.metadata.annotations.$annotation}"
}

log_error() {
    local message=$1

    # Using instance id from node annotation for logging and GCP troubleshooting purposes
    local instance_id=$(get_node_annotation "container.googleapis.com/instance_id")

    shift
    echo "ERROR: $message node=$NODE_NAME instance_id=$instance_id ${@}" > /dev/stderr
}

slack_handler() {
    local alertname=$1
    local summary=$2

    local json_payload='[{
      "labels": {
        "alertname": "'"${alertname}"'",
        "node": "'"${NODE_NAME}"'",
        "sendResolved": "false",
        "severity": "error",
        "slack": "'"${SLACK_CHANNEL}"'"
      },
      "annotations": {
        "summary": "'"${summary}"'",
        "description": "Faulty GPU handler encountered an error. Manual intervention and investigation is required.",
        "logs_url": "'"${GRAFANA_URL}"'?panes=%7B%22aOE%22:%7B%22datasource%22:%22P8E80F9AEF21F6940%22,%22queries%22:%5B%7B%22refId%22:%22D%22,%22datasource%22:%7B%22type%22:%22loki%22,%22uid%22:%22P8E80F9AEF21F6940%22%7D,%22editorMode%22:%22code%22,%22expr%22:%22%7Bcontainer%3D%5C%22faulty-gpu-handler%5C%22%7D%20%7C%3D%20%5C%22'"${NODE_NAME}"'%5C%22%22,%22queryType%22:%22range%22,%22hide%22:false%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&schemaVersion=1&orgId=1"
      },
      "startsAt": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'",
      "endsAt": "'"$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ)"'"
    }]'

    curl -s -X POST -H 'Content-Type: application/json' \
        -d "${json_payload}" \
        http://prom-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/alerts
}

# https://cloud.google.com/ai-hypercomputer/docs/manage/manage-gke-clusters#report-faulty-hosts-how-to
report_faulty_host() {
    local label_fault_behavior="cloud.google.com/fault-behavior"
    local label_replacement_status="cloud.google.com/report-and-replace-status"
    local label_topology_host="cloud.google.com/gce-topology-host"
    local label_fault_epoch="ai21.com/fault-detected-epoch"

    local epoch=$(get_node_label $label_fault_epoch)

    # Using instance id from node annotation for logging and GCP troubleshooting purposes
    local physical_host_before=$(get_node_label $label_topology_host)

    if [[ "$epoch" =~ ^[0-9]+$ ]]; then
        if [ $epoch -gt $(date +%s -d "-1 hour") ]; then
            echo not reporting faulty node that was already reported in the last hour
            return 0
        fi
    fi

    echo "Reporting faulty node by labeling it. node=$NODE_NAME physical_host=$physical_host_before"
    if ! kubectl label node $NODE_NAME $label_fault_behavior=XID; then
        log_error "Failed to apply fault-behavior label"
        slack_handler "FaultyGpuHandlerFailed" \
            "Failed to apply fault-behavior label on node $NODE_NAME"
        return 0
    fi

    kubectl label node $NODE_NAME $label_fault_epoch=$(date +%s) --overwrite

    # Poll for GKE node to be ready to be moved to a new host
    echo "Waiting for GKE replacement"
    while true; do
        local status=$(get_node_label $label_replacement_status)
        local fault_behavior=$(get_node_label $label_fault_behavior)
        echo "$NODE_NAME replacement status: $status"

        if [[ $status == 'ERROR' || $status == 'Error' ]]; then
            log_error "GKE replacement failed" "physical_host=$physical_host_before status=$status"
            slack_handler "FaultyGpuReplacementError" \
                "GKE replacement failed for node $NODE_NAME"
            return 0
        fi

        if [ -z $fault_behavior ]; then
            echo "Fault-behavior label was removed - node has been repaired by GKE. node=$NODE_NAME physical_host=$physical_host_before"
            break
        fi

        sleep 120
    done

    local physical_host_after=$(get_node_label $label_topology_host)

    if [ "$physical_host_before" == "$physical_host_after" ]; then
        log_error "Physical host unchanged" "physical_host_before=$physical_host_before physical_host_after=$physical_host_after"
        slack_handler "FaultyGpuSamePhysicalHost" \
            "Physical host unchanged for node $NODE_NAME"
        return 0
    fi

    echo "SUCCESS: Physical host changed for node $NODE_NAME from $physical_host_before to $physical_host_after"

    kubectl uncordon $NODE_NAME
}

for i in $(seq 1 "$AMX_ALERT_LEN"); do
    NODE_NAME=""
    declare NODE_LABEL="AMX_ALERT_${i}_LABEL_node"
    declare NODE_NAME_LABEL="AMX_ALERT_${i}_LABEL_node_name"
    declare POD_LABEL="AMX_ALERT_${i}_LABEL_pod"
    declare NAMESPACE_LABEL="AMX_ALERT_${i}_LABEL_namespace"

    if [ -n "${!NODE_LABEL}" ]; then
        NODE_NAME=${!NODE_LABEL}
    elif [ -n "${!NODE_NAME_LABEL}" ]; then
        NODE_NAME=${!NODE_NAME_LABEL}
    elif [ -n "${!POD_LABEL}" ]; then
        POD=${!POD_LABEL}
        NAMESPACE=${!NAMESPACE_LABEL}
        [ -z $NAMESPACE ] && {
            log_error "Found 'pod' label but not 'namespace' label"
            exit 1
        }
        NODE_NAME=$(kubectl -n $NAMESPACE get pod $POD -o jsonpath="{.spec.nodeName}")
        [ -z $NODE_NAME ] && {
            echo Warning: pod $POD no longer exists. skipping
            continue
        }
    else
        log_error "Could not find relevant labels for locating faulty machine"
        exit 1
    fi

    if ! kubectl get node $NODE_NAME &> /dev/null; then
        echo Node $NODE_NAME no longer exists. skipping
        continue
    fi

    kubectl drain $NODE_NAME \
        --delete-emptydir-data \
        --force \
        --ignore-daemonsets \
        --timeout=360s \
    || kubectl drain $NODE_NAME \
        --delete-emptydir-data \
        --disable-eviction \
        --force \
        --grace-period 1 \
        --ignore-daemonsets \
        --timeout=60s \
    || { # Final fallback: force delete any remaining pods
        echo Force deleting remaining pods on node $NODE_NAME
        kubectl get pods --all-namespaces --field-selector "spec.nodeName=$NODE_NAME" \
            -o jsonpath='{range .items[*]}{.metadata.namespace} {.metadata.name}{"\n"}{end}' \
        | while read namespace pod; do
            kubectl delete pod $pod -n $namespace --force --grace-period=0 --timeout=5s
        done
    }

    # GKE fault-behavior is available for reserved and calendar A3/A4 GPU node pools
    if [[ $NODE_NAME == *"reserved"* ]] || [[ $NODE_NAME == *"calendar"* ]]; then
        report_faulty_host
    fi
done
