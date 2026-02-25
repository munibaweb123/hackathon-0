# Multi-Cluster kubectl Management

Source: [kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/](https://kubernetes.io/docs/tasks/access-application-cluster/configure-access-multiple-clusters/)

## Kubeconfig File Structure

The kubeconfig file (`~/.kube/config`) contains three key sections:

```yaml
apiVersion: v1
kind: Config
current-context: do-nyc1-prod         # active context

clusters:                              # cluster API endpoints
- cluster:
    server: https://api.do-k8s.example.com
    certificate-authority-data: <base64-ca>
  name: do-nyc1-prod

- cluster:
    server: https://hetzner-k8s.example.com:6443
    certificate-authority-data: <base64-ca>
  name: hetzner-fsn1-staging

users:                                 # authentication credentials
- name: do-nyc1-prod-admin
  user:
    token: <bearer-token>

- name: hetzner-fsn1-staging-admin
  user:
    client-certificate-data: <base64-cert>
    client-key-data: <base64-key>

contexts:                              # cluster + user + namespace combos
- context:
    cluster: do-nyc1-prod
    user: do-nyc1-prod-admin
    namespace: default
  name: do-nyc1-prod

- context:
    cluster: hetzner-fsn1-staging
    user: hetzner-fsn1-staging-admin
    namespace: default
  name: hetzner-fsn1-staging
```

---

## kubectl config Commands

### View Configuration

```bash
# Show merged kubeconfig
kubectl config view

# Show specific kubeconfig file
kubectl config view --kubeconfig=./kubeconfig

# Show only contexts
kubectl config get-contexts

# Show current context
kubectl config current-context
```

### Manage Contexts

```bash
# Switch active context
kubectl config use-context do-nyc1-prod

# Rename a context
kubectl config rename-context old-name new-name

# Delete a context
kubectl config delete-context old-context

# Set default namespace for a context
kubectl config set-context do-nyc1-prod --namespace=my-app
kubectl config set-context --current --namespace=my-app
```

### Manage Clusters

```bash
# Add a cluster entry
kubectl config set-cluster hetzner-prod \
  --server=https://hetzner-k8s.example.com:6443 \
  --certificate-authority=/path/to/ca.crt

# Add with embedded cert
kubectl config set-cluster hetzner-prod \
  --server=https://hetzner-k8s.example.com:6443 \
  --certificate-authority=/path/to/ca.crt \
  --embed-certs=true

# Delete a cluster entry
kubectl config delete-cluster old-cluster
```

### Manage Users

```bash
# Add token-based user
kubectl config set-credentials do-admin \
  --token=<bearer-token>

# Add cert-based user
kubectl config set-credentials hetzner-admin \
  --client-certificate=/path/to/cert.crt \
  --client-key=/path/to/key.key \
  --embed-certs=true

# Delete a user
kubectl config delete-user old-user
```

### Create Context

```bash
# Create context linking cluster + user + namespace
kubectl config set-context hetzner-fsn1-prod \
  --cluster=hetzner-prod \
  --user=hetzner-admin \
  --namespace=default
```

---

## Merging Multiple Kubeconfigs

### Method 1: KUBECONFIG Environment Variable

```bash
# Merge temporarily (current shell session only)
export KUBECONFIG=~/.kube/config:./kubeconfig-hetzner:./kubeconfig-do

# Now kubectl sees all clusters
kubectl config get-contexts
```

### Method 2: Permanent Merge

```bash
# Merge and flatten into single file
KUBECONFIG=~/.kube/config:./kubeconfig-hetzner:./kubeconfig-do \
  kubectl config view --merge --flatten > ~/.kube/config-merged

# Backup original
cp ~/.kube/config ~/.kube/config.bak

# Replace with merged
mv ~/.kube/config-merged ~/.kube/config
```

### Method 3: Per-Provider Kubeconfig Save

```bash
# DigitalOcean auto-merges into ~/.kube/config
doctl kubernetes cluster kubeconfig save my-doks-cluster

# Hetzner writes to path in config YAML — merge manually
KUBECONFIG=~/.kube/config:./kubeconfig \
  kubectl config view --merge --flatten > ~/.kube/config-new
mv ~/.kube/config-new ~/.kube/config
```

---

## Context Naming Convention

Use a consistent pattern for multi-cloud:

```
<provider>-<region>-<purpose>
```

| Context Name | Provider | Region | Purpose |
|--------------|----------|--------|---------|
| `do-nyc1-prod` | DigitalOcean | NYC | Production |
| `do-fra1-staging` | DigitalOcean | Frankfurt | Staging |
| `hetzner-fsn1-prod` | Hetzner | Falkenstein | Production |
| `hetzner-hel1-dev` | Hetzner | Helsinki | Development |

```bash
# DigitalOcean auto-names as: do-<region>-<cluster-name>
# Rename if needed:
kubectl config rename-context do-nyc1-my-cluster do-nyc1-prod

# Hetzner uses cluster_name from config:
kubectl config rename-context my-cluster hetzner-fsn1-prod
```

---

## Cross-Cluster Operations

### Run Commands Against Specific Cluster

```bash
# Without switching context
kubectl --context=do-nyc1-prod get nodes
kubectl --context=hetzner-fsn1-prod get pods -A

# Apply manifests to specific cluster
kubectl --context=do-nyc1-prod apply -f k8s/prod/
kubectl --context=hetzner-fsn1-prod apply -f k8s/staging/
```

### Multi-Cluster Status Script

```bash
#!/bin/bash
# check-all-clusters.sh
CONTEXTS=$(kubectl config get-contexts -o name)

for ctx in $CONTEXTS; do
  echo "=========================================="
  echo "Cluster: $ctx"
  echo "=========================================="

  echo "--- Nodes ---"
  kubectl --context="$ctx" get nodes -o wide 2>/dev/null || echo "  UNREACHABLE"

  echo "--- Pods (non-running) ---"
  kubectl --context="$ctx" get pods -A --field-selector=status.phase!=Running 2>/dev/null

  echo "--- Resource Usage ---"
  kubectl --context="$ctx" top nodes 2>/dev/null || echo "  metrics-server not available"

  echo ""
done
```

### Verify Cluster Connectivity

```bash
# Quick health check for all contexts
for ctx in $(kubectl config get-contexts -o name); do
  echo -n "$ctx: "
  kubectl --context="$ctx" cluster-info 2>/dev/null | head -1 || echo "UNREACHABLE"
done
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `error: no context exists with the name` | Check `kubectl config get-contexts` — name may differ |
| `Unable to connect to the server` | Cluster may be down or IP not in `allowed_networks` |
| `certificate signed by unknown authority` | CA cert missing — re-save kubeconfig |
| `You must be logged in to the server` | Token expired — re-auth (`doctl k8s kubeconfig save` or regenerate) |
| Duplicate context names after merge | Rename before merging: `kubectl config rename-context` |
| Wrong default namespace | Set it: `kubectl config set-context --current --namespace=my-app` |

---

## Best Practices

1. **Always name contexts consistently**: `<provider>-<region>-<purpose>`
2. **Back up kubeconfig before merging**: `cp ~/.kube/config ~/.kube/config.bak`
3. **Use `--context` flag** in scripts instead of `use-context` (avoids global state mutation)
4. **Set default namespace per context** to avoid `--namespace` on every command
5. **Don't store kubeconfig in Git** — it contains credentials
6. **Check `current-context`** before destructive operations (`delete`, `apply`)
7. **Use separate kubeconfig files** for CI/CD (don't merge into personal config)
