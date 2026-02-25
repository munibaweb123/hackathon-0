# DigitalOcean DOKS — Complete CLI Reference

Source: [docs.digitalocean.com/reference/doctl/reference/kubernetes/](https://docs.digitalocean.com/reference/doctl/reference/kubernetes/)

## Installation & Authentication

```bash
# Install
brew install doctl                          # macOS
snap install doctl                          # Ubuntu/Linux
scoop install doctl                         # Windows

# Authenticate (creates ~/.config/doctl/config.yaml)
doctl auth init                             # interactive — paste API token
doctl auth init --access-token <token>      # non-interactive

# Verify
doctl account get
```

**API token**: Generate at [cloud.digitalocean.com/account/api/tokens](https://cloud.digitalocean.com/account/api/tokens). Requires read+write scope for K8s operations.

---

## doctl kubernetes cluster create

```bash
doctl kubernetes cluster create <name> [flags]
```

**Alias**: `doctl k8s cluster c`

### All Flags

| Flag | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `--region` | string | `nyc1` | Recommended | Datacenter region slug |
| `--version` | string | `latest` | No | K8s version slug (e.g., `1.29.1-do.0`) |
| `--count` | int | `3` | No | Default node pool count. Conflicts with `--node-pool` |
| `--size` | string | `s-1vcpu-2gb-intel` | No | Default node pool size. Conflicts with `--node-pool` |
| `--node-pool` | string | — | No | Custom node pool spec (repeatable for multiple pools) |
| `--ha` | bool | `false` | No | HA control plane ($40/mo extra) |
| `--auto-upgrade` | bool | `false` | No | Auto-apply patch version upgrades |
| `--surge-upgrade` | bool | `false` | No | Surge upgrade (extra nodes during upgrade) |
| `--maintenance-window` | string | `any=00:00` | No | 4-hour UTC window: `day=HH:MM` |
| `--tag` | string | — | No | Comma-separated tags |
| `--vpc-uuid` | string | — | No | Deploy into specific VPC |
| `--cluster-subnet` | CIDR | `10.244.0.0/16` | No | Pod network CIDR |
| `--service-subnet` | CIDR | `10.245.0.0/16` | No | Service network CIDR |
| `--wait` | bool | `true` | No | Wait for cluster to be ready |
| `--update-kubeconfig` | bool | `true` | No | Auto-save kubeconfig |
| `--set-current-context` | bool | `true` | No | Set as active kubectl context |

### Node Pool String Format

```
"name=<name>;size=<slug>;count=<n>;tag=<tag>;label=<key>=<value>;taint=<key>=<value>:<effect>;auto-scale=<bool>;min-nodes=<n>;max-nodes=<n>"
```

- Multiple labels: `label=key1=val1;label=key2=val2`
- Multiple taints: `taint=key1=val1:NoSchedule;taint=key2=val2:NoExecute`
- Taint effects: `NoSchedule`, `PreferNoSchedule`, `NoExecute`

### Examples

```bash
# Minimal dev cluster (uses defaults: 3 nodes, s-1vcpu-2gb-intel, nyc1)
doctl kubernetes cluster create my-dev

# Production HA with named node pools
doctl kubernetes cluster create my-prod \
  --region fra1 \
  --version 1.29.1-do.0 \
  --ha \
  --auto-upgrade \
  --surge-upgrade \
  --maintenance-window saturday=02:00 \
  --node-pool "name=app;size=s-4vcpu-8gb;count=3;auto-scale=true;min-nodes=3;max-nodes=10;label=workload=app" \
  --node-pool "name=jobs;size=s-2vcpu-4gb;count=2;auto-scale=true;min-nodes=1;max-nodes=5;label=workload=jobs;taint=dedicated=jobs:NoSchedule"

# Budget cluster
doctl kubernetes cluster create my-budget \
  --region nyc1 \
  --size s-2vcpu-4gb \
  --count 2
```

---

## Cluster Management Commands

```bash
# List all clusters
doctl kubernetes cluster list
doctl kubernetes cluster list --output json

# Get cluster details
doctl kubernetes cluster get <cluster-name-or-id>

# Update cluster config
doctl kubernetes cluster update <name> \
  --auto-upgrade=true \
  --maintenance-window sunday=04:00 \
  --surge-upgrade=true

# Check available upgrades
doctl kubernetes cluster get-upgrades <name>

# Upgrade cluster K8s version
doctl kubernetes cluster upgrade <name> --version <version-slug>

# Delete cluster
doctl kubernetes cluster delete <name>
doctl kubernetes cluster delete <name> --force          # skip confirmation
doctl kubernetes cluster delete <name> --dangerous      # also delete LBs/volumes

# Delete selectively (choose which associated resources to delete)
doctl kubernetes cluster delete-selective <name>

# List associated resources (LBs, volumes, volume snapshots)
doctl kubernetes cluster list-associated-resources <name>
```

---

## Kubeconfig Management

```bash
# Save cluster kubeconfig (merges into ~/.kube/config)
doctl kubernetes cluster kubeconfig save <name>

# Show kubeconfig YAML (stdout)
doctl kubernetes cluster kubeconfig show <name>

# Remove cluster from kubeconfig
doctl kubernetes cluster kubeconfig remove <name>
```

**Context naming**: DOKS auto-generates context names as `do-<region>-<cluster-name>` (e.g., `do-nyc1-my-prod`).

---

## Node Pool Management

```bash
# List pools
doctl kubernetes cluster node-pool list <cluster>

# Get pool details
doctl kubernetes cluster node-pool get <cluster> <pool-name-or-id>

# Create new pool
doctl kubernetes cluster node-pool create <cluster> \
  --name monitoring \
  --size s-2vcpu-4gb \
  --count 2 \
  --label purpose=monitoring \
  --taint dedicated=monitoring:NoSchedule

# Create autoscaling pool
doctl kubernetes cluster node-pool create <cluster> \
  --name autoscaled \
  --size s-4vcpu-8gb \
  --count 3 \
  --auto-scale \
  --min-nodes 2 \
  --max-nodes 20

# Update pool (resize, change autoscaling)
doctl kubernetes cluster node-pool update <cluster> <pool> \
  --count 5
doctl kubernetes cluster node-pool update <cluster> <pool> \
  --auto-scale --min-nodes 3 --max-nodes 15

# Delete pool
doctl kubernetes cluster node-pool delete <cluster> <pool>

# Delete specific node (for troubleshooting)
doctl kubernetes cluster node-pool delete-node <cluster> <pool> <node-id>

# Replace node (cordon + drain + delete + create new)
doctl kubernetes cluster node-pool replace-node <cluster> <pool> <node-id>
```

**Important**: Scale-to-zero is not supported. Minimum node count is 1.

---

## Discovery Commands

```bash
# Available K8s versions
doctl kubernetes options versions

# Available droplet sizes for K8s
doctl kubernetes options sizes

# Available regions
doctl kubernetes options regions
```

---

## Available Regions

| Slug | Location |
|------|----------|
| `nyc1`, `nyc3` | New York |
| `sfo3` | San Francisco |
| `ams3` | Amsterdam |
| `lon1` | London |
| `fra1` | Frankfurt |
| `sgp1` | Singapore |
| `blr1` | Bangalore |
| `syd1` | Sydney |
| `tor1` | Toronto |

---

## Common Node Sizes for K8s

| Slug | vCPU | RAM | Disk | $/mo |
|------|------|-----|------|------|
| `s-1vcpu-2gb` | 1 | 2 GB | 50 GB | $12 |
| `s-2vcpu-2gb` | 2 | 2 GB | 60 GB | $18 |
| `s-2vcpu-4gb` | 2 | 4 GB | 80 GB | $24 |
| `s-4vcpu-8gb` | 4 | 8 GB | 160 GB | $48 |
| `s-8vcpu-16gb` | 8 | 16 GB | 320 GB | $96 |
| `c-2` | 2 | 4 GB | 25 GB | $42 |
| `c-4` | 4 | 8 GB | 50 GB | $84 |
| `g-2vcpu-8gb` | 2 | 8 GB | 25 GB | $63 |
| `g-4vcpu-16gb` | 4 | 16 GB | 50 GB | $126 |
| `m-2vcpu-16gb` | 2 | 16 GB | 50 GB | $84 |

Use `doctl kubernetes options sizes` for the latest list.

---

## Maintenance Window Format

```
day=HH:MM    (UTC, 4-hour window)
```

| Day Value | Meaning |
|-----------|---------|
| `any` | Any day |
| `monday`–`sunday` | Specific day |

Example: `saturday=02:00` means Saturday 02:00–06:00 UTC.

---

## Container Registry Integration

```bash
# Connect registry to cluster (allows pulling private images)
doctl kubernetes cluster registry add <cluster-name>

# Remove registry from cluster
doctl kubernetes cluster registry remove <cluster-name>
```

---

## Gotchas & Notes

1. **Free control plane**: DOKS control plane is free. You only pay for worker nodes, LBs, and volumes.
2. **HA cost**: $40/mo for HA control plane — recommended for production.
3. **Context auto-naming**: Context is `do-<region>-<cluster-name>`. Rename if needed.
4. **--dangerous flag**: `delete --dangerous` also deletes associated LBs and block storage volumes.
5. **Upgrade window**: Upgrades happen in the maintenance window. Use `--surge-upgrade` to minimize downtime.
6. **VPC**: Clusters are placed in the region's default VPC unless `--vpc-uuid` is specified.
7. **CIDR conflicts**: Default pod CIDR is `10.244.0.0/16`. Change if running multiple clusters that might connect.
