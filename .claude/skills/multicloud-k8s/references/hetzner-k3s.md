# Hetzner K3s — Complete Configuration Reference

Source: [github.com/vitobotta/hetzner-k3s](https://github.com/vitobotta/hetzner-k3s) and [vitobotta.github.io/hetzner-k3s](https://vitobotta.github.io/hetzner-k3s)

## Installation

```bash
# Homebrew (macOS/Linux)
brew install vitobotta/tap/hetzner_k3s

# Linux amd64 binary
wget https://github.com/vitobotta/hetzner-k3s/releases/latest/download/hetzner-k3s-linux-amd64
chmod +x hetzner-k3s-linux-amd64
sudo mv hetzner-k3s-linux-amd64 /usr/local/bin/hetzner-k3s

# Linux arm64 binary
wget https://github.com/vitobotta/hetzner-k3s/releases/latest/download/hetzner-k3s-linux-arm64
chmod +x hetzner-k3s-linux-arm64
sudo mv hetzner-k3s-linux-arm64 /usr/local/bin/hetzner-k3s

# Verify
hetzner-k3s --version
```

---

## CLI Commands

```bash
# Create cluster
hetzner-k3s create --config <path-to-config.yaml>

# Delete cluster (removes all servers, networks, firewalls, load balancers)
hetzner-k3s delete --config <path-to-config.yaml>

# Upgrade K3s version (edit k3s_version in config first)
hetzner-k3s upgrade --config <path-to-config.yaml>

# Add nodes (increase instance_count in config, then re-run create)
hetzner-k3s create --config <path-to-config.yaml>
```

The process is **idempotent** — running `create` again with modified config adds/adjusts nodes without destroying existing ones.

---

## Prerequisites

1. **Hetzner Cloud API token**: Generate at [console.hetzner.cloud](https://console.hetzner.cloud) → Project → Security → API Tokens (read+write)
2. **SSH key pair**: `ssh-keygen -t ed25519 -f ~/.ssh/hetzner_k3s -N ""`
3. **hetzner-k3s binary**: See installation above

---

## Complete Configuration Reference

### Root-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `hetzner_token` | string | Yes | — | Hetzner Cloud API token |
| `cluster_name` | string | Yes | — | Unique cluster identifier |
| `kubeconfig_path` | string | Yes | — | Where to write kubeconfig |
| `k3s_version` | string | Yes | — | K3s version (e.g., `v1.32.0+k3s1`) |
| `image` | string | No | `ubuntu-24.04` | OS image for nodes |
| `snapshot_os` | string | No | `microos` | Snapshot-based OS option |
| `autoscaling_image` | string | No | — | Image ID for autoscaled nodes |
| `schedule_workloads_on_masters` | bool | No | `false` | Allow pods on master nodes |
| `protect_against_deletion` | bool | No | `false` | Hetzner deletion protection |
| `create_load_balancer_for_the_kubernetes_api` | bool | No | `false` | LB for K8s API |
| `api_server_hostname` | string | No | — | Custom hostname for API server |
| `k3s_upgrade_concurrency` | int | No | `1` | Nodes upgraded simultaneously |

### Networking Section

```yaml
networking:
  ssh:
    port: 22                                    # SSH port (default: 22)
    use_agent: false                            # Use SSH agent (default: false)
    public_key_path: "~/.ssh/id_ed25519.pub"    # Required
    private_key_path: "~/.ssh/id_ed25519"       # Required

  allowed_networks:
    ssh:                                         # IPs allowed to SSH
      - 0.0.0.0/0                               # Use your IP/32 in production
    api:                                         # IPs allowed to access K8s API
      - 0.0.0.0/0                               # Use your IP/32 in production
    custom_firewall_rules:                       # Optional additional rules
      - description: "Allow HTTP"
        direction: in                            # in or out
        protocol: tcp                            # tcp, udp, icmp, esp, gre
        port: "80"                               # port number, range, or "any"
        source_ips:
          - 0.0.0.0/0

  public_network:
    ipv4: true                                   # Enable public IPv4
    ipv6: true                                   # Enable public IPv6
    use_local_firewall: false                    # iptables-based firewall

  private_network:
    enabled: true                                # Use private networking (recommended)
    subnet: 10.0.0.0/16                         # Private subnet CIDR
    existing_network_name: ""                    # Use existing Hetzner network

  cni:
    enabled: true                                # Install CNI (default: true)
    mode: flannel                                # flannel or cilium
    encryption: false                            # WireGuard encryption (flannel)
    cilium:                                      # Cilium-specific options
      helm_values_path: "./cilium-values.yaml"
      chart_version: "v1.17.2"

  cluster_cidr: 10.244.0.0/16                   # Pod CIDR
  service_cidr: 10.43.0.0/16                    # Service CIDR
  cluster_dns: 10.43.0.10                       # CoreDNS IP
```

### Masters Pool

```yaml
masters_pool:
  instance_type: cpx22                          # Required: server type
  instance_count: 3                             # Required: 1 or 3+ for HA
  location: fsn1                                # Single location
  # OR multi-location for HA:
  locations:
    - fsn1                                      # Falkenstein, Germany
    - nbg1                                      # Nuremberg, Germany
    - hel1                                      # Helsinki, Finland
  image: ubuntu-24.04                           # Override global image
  labels:                                       # K8s node labels
    - key: role
      value: master
```

### Worker Node Pools

```yaml
worker_node_pools:
  - name: general                               # Required: pool name
    instance_type: cpx32                        # Required: server type
    instance_count: 3                           # Required (unless autoscaling)
    location: fsn1                              # Required: single location
    image: ubuntu-24.04                         # Override global image
    labels:                                     # K8s node labels
      - key: workload
        value: general
    taints:                                     # K8s taints
      - key: dedicated
        value: gpu:NoSchedule
    autoscaling:                                # Optional autoscaling
      enabled: true
      min_instances: 1                          # Scale-to-zero NOT supported
      max_instances: 10

  - name: arm-workers                           # ARM64 pool (cost savings)
    instance_type: cax21                        # Ampere ARM server
    instance_count: 3
    location: fsn1
    labels:
      - key: arch
        value: arm64
```

### Datastore Configuration

```yaml
datastore:
  mode: etcd                                    # etcd (default) or external
  # External datastore (PostgreSQL/MySQL):
  # mode: external
  # external_datastore_endpoint: "postgres://user:pass@host:5432/k3s"
  etcd:
    snapshot_retention: 24                      # Keep 24 snapshots
    snapshot_schedule_cron: "0 * * * *"         # Hourly snapshots
    s3_enabled: false                           # Backup to S3
    s3_endpoint: ""
    s3_region: ""
    s3_bucket: ""
    s3_access_key: ""
    s3_secret_key: ""
    s3_folder: ""
    s3_force_path_style: false
```

### Add-ons Configuration

```yaml
addons:
  csi_driver:
    enabled: true                               # Hetzner CSI for persistent volumes
    manifest_url: "https://..."                 # Custom manifest URL

  cloud_controller_manager:
    enabled: true                               # Hetzner CCM for LBs, node info
    manifest_url: "https://..."

  system_upgrade_controller:
    enabled: true                               # Zero-downtime K3s upgrades
    deployment_manifest_url: "https://..."
    crd_manifest_url: "https://..."

  cluster_autoscaler:
    enabled: false                              # Enable per-pool autoscaling
    manifest_url: "https://..."
    container_image_tag: "v1.34.2"
    scan_interval: "10s"
    scale_down_delay_after_add: "10m"
    scale_down_delay_after_delete: "10s"
    scale_down_delay_after_failure: "3m"
    max_node_provision_time: "15m"

  traefik:
    enabled: false                              # K3s bundled Traefik ingress

  servicelb:
    enabled: false                              # K3s bundled ServiceLB

  metrics_server:
    enabled: false                              # K3s bundled metrics-server

  embedded_registry_mirror:
    enabled: false                              # Registry mirror for image caching
```

### Custom Commands & Arguments

```yaml
# System packages to install on all nodes
additional_packages:
  - jq
  - htop

# Commands before K3s install
additional_pre_k3s_commands:
  - apt update && apt upgrade -y

# Commands after K3s install
additional_post_k3s_commands:
  - apt autoremove -y

# Kubernetes component arguments
kube_api_server_args:
  - "--audit-log-maxage=30"
kube_scheduler_args: []
kube_controller_manager_args: []
kube_cloud_controller_manager_args: []
kubelet_args:
  - "--max-pods=110"
kube_proxy_args: []
```

---

## Available Server Types

### Shared vCPU (CX — Intel/AMD)

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| `cx22` | 2 | 4 GB | 40 GB | ~$4 |
| `cx32` | 4 | 8 GB | 80 GB | ~$7 |
| `cx42` | 8 | 16 GB | 160 GB | ~$14 |
| `cx52` | 16 | 32 GB | 320 GB | ~$29 |

### Shared vCPU ARM64 (CAX — Ampere)

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| `cax11` | 2 | 4 GB | 40 GB | ~$4 |
| `cax21` | 4 | 8 GB | 80 GB | ~$7 |
| `cax31` | 8 | 16 GB | 160 GB | ~$13 |
| `cax41` | 16 | 32 GB | 320 GB | ~$25 |

### Dedicated vCPU (CPX — AMD)

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| `cpx11` | 2 | 2 GB | 40 GB | ~$5 |
| `cpx21` | 3 | 4 GB | 80 GB | ~$9 |
| `cpx22` | 4 | 8 GB | 160 GB | ~$15 |
| `cpx31` | 4 | 8 GB | 160 GB | ~$15 |
| `cpx32` | 8 | 16 GB | 240 GB | ~$26 |
| `cpx41` | 8 | 16 GB | 240 GB | ~$30 |
| `cpx42` | 16 | 32 GB | 360 GB | ~$56 |

### Dedicated vCPU (CCX — Intel)

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| `ccx13` | 2 | 8 GB | 80 GB | ~$13 |
| `ccx23` | 4 | 16 GB | 160 GB | ~$25 |
| `ccx33` | 8 | 32 GB | 240 GB | ~$48 |
| `ccx43` | 16 | 64 GB | 360 GB | ~$95 |
| `ccx53` | 32 | 128 GB | 600 GB | ~$189 |
| `ccx63` | 48 | 192 GB | 960 GB | ~$358 |

---

## Available Locations

| Slug | City | Country |
|------|------|---------|
| `fsn1` | Falkenstein | Germany |
| `nbg1` | Nuremberg | Germany |
| `hel1` | Helsinki | Finland |
| `ash` | Ashburn | USA |
| `hil` | Hillsboro | USA |
| `sin` | Singapore | Singapore |

---

## Complete Example Configs

### Dev/Learning — Single Node (~$4/mo)

```yaml
hetzner_token: <token>
cluster_name: dev
kubeconfig_path: "./kubeconfig"
k3s_version: v1.32.0+k3s1
schedule_workloads_on_masters: true

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh: [0.0.0.0/0]
    api: [0.0.0.0/0]

masters_pool:
  instance_type: cx22
  instance_count: 1
  location: fsn1

worker_node_pools: []
```

### Staging — 3-Node Cluster (~$12/mo)

```yaml
hetzner_token: <token>
cluster_name: staging
kubeconfig_path: "./kubeconfig"
k3s_version: v1.32.0+k3s1

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh: [<your-ip>/32]
    api: [<your-ip>/32]
  private_network:
    enabled: true
    subnet: 10.0.0.0/16

masters_pool:
  instance_type: cx22
  instance_count: 1
  location: fsn1

worker_node_pools:
  - name: workers
    instance_type: cx22
    instance_count: 2
    location: fsn1
```

### Production HA — Multi-Location (~$58/mo)

```yaml
hetzner_token: <token>
cluster_name: prod
kubeconfig_path: "./kubeconfig-prod"
k3s_version: v1.32.0+k3s1
schedule_workloads_on_masters: false
protect_against_deletion: true

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh: [<vpn-cidr>/24]
    api: [<vpn-cidr>/24]
  private_network:
    enabled: true
    subnet: 10.0.0.0/16
  cni:
    enabled: true
    mode: cilium

masters_pool:
  instance_type: cpx22
  instance_count: 3
  locations: [fsn1, nbg1, hel1]

worker_node_pools:
  - name: app
    instance_type: cpx32
    instance_count: 3
    location: fsn1
    labels:
      - key: workload
        value: app
  - name: jobs
    instance_type: cax21
    instance_count: 2
    location: fsn1
    labels:
      - key: workload
        value: background
    autoscaling:
      enabled: true
      min_instances: 1
      max_instances: 10

datastore:
  mode: etcd
  etcd:
    snapshot_retention: 48
    snapshot_schedule_cron: "0 */6 * * *"
```

---

## Gotchas & Notes

1. **Idempotent**: Running `create` again modifies the cluster (adds nodes, changes config) without destroying it.
2. **CIDR conflicts**: Default pod CIDR `10.244.0.0/16` — change if running multiple clusters.
3. **Autoscaling images**: Autoscaled pools may need `autoscaling_image` set to a snapshot ID for faster provisioning.
4. **Large clusters (100+ nodes)**: Adjust K3s args per the official large cluster guidelines.
5. **ARM64 nodes**: CAX instances run ARM64 — ensure your container images are multi-arch.
6. **No managed control plane**: You own the master nodes. They're just Hetzner servers running K3s.
7. **Token security**: The Hetzner token never leaves your machine — it's used locally by the CLI.
8. **Bandwidth**: Hetzner includes 20TB/mo outbound traffic per server at no extra cost.
9. **Load balancers**: Hetzner LBs are auto-provisioned by the Cloud Controller Manager when you create `Service type: LoadBalancer` (~$5.50/mo each).
10. **Persistent volumes**: Hetzner CSI driver creates block storage volumes on `PersistentVolumeClaim` creation (~$0.05/GB/mo).
