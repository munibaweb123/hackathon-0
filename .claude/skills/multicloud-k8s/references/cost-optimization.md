# Cost Optimization — DigitalOcean vs Hetzner

Sources: [digitalocean.com/pricing](https://www.digitalocean.com/pricing/kubernetes), [hetzner.com/cloud](https://www.hetzner.com/cloud/)

Prices are approximate and may change. Always verify on provider pricing pages.

---

## Head-to-Head: Equivalent Configurations

### Minimal Dev Cluster (1 master + 2 workers)

| Component | DigitalOcean | Hetzner |
|-----------|:------------:|:-------:|
| Control plane | Free (managed) | Self-managed (1x CX22 ~$4) |
| 2x worker nodes (2vCPU/4GB) | 2x s-2vcpu-4gb = $48 | 2x CX22 = ~$8 |
| **Total** | **$48/mo** | **~$12/mo** |
| **Savings** | — | **75% cheaper** |

### Production HA Cluster (3 masters + 5 workers)

| Component | DigitalOcean | Hetzner |
|-----------|:------------:|:-------:|
| Control plane (HA) | $40 (HA add-on) | 3x CPX22 = ~$45 |
| 5x worker nodes (4vCPU/8GB) | 5x s-4vcpu-8gb = $240 | 5x CPX32 = ~$130 |
| Load balancer | $12 | ~$6 |
| **Total** | **$292/mo** | **~$181/mo** |
| **Savings** | — | **38% cheaper** |

### Budget Production (3 masters + 3 workers ARM64)

| Component | DigitalOcean | Hetzner |
|-----------|:------------:|:-------:|
| Control plane (HA) | $40 | 3x CX22 = ~$12 |
| 3x worker nodes (4vCPU/8GB) | 3x s-4vcpu-8gb = $144 | 3x CAX21 (ARM) = ~$21 |
| Load balancer | $12 | ~$6 |
| **Total** | **$196/mo** | **~$39/mo** |
| **Savings** | — | **80% cheaper** |

---

## DigitalOcean Pricing Details

### Control Plane
- **Standard**: Free (single control plane, DigitalOcean manages it)
- **HA**: $40/mo (multi-master, recommended for production)

### Worker Nodes (Monthly)

| Size Slug | vCPU | RAM | Disk | $/mo |
|-----------|------|-----|------|------|
| `s-1vcpu-2gb` | 1 | 2 GB | 50 GB | $12 |
| `s-2vcpu-2gb` | 2 | 2 GB | 60 GB | $18 |
| `s-2vcpu-4gb` | 2 | 4 GB | 80 GB | $24 |
| `s-4vcpu-8gb` | 4 | 8 GB | 160 GB | $48 |
| `s-8vcpu-16gb` | 8 | 16 GB | 320 GB | $96 |
| `c-2` (CPU-optimized) | 2 | 4 GB | 25 GB | $42 |
| `c-4` | 4 | 8 GB | 50 GB | $84 |
| `g-2vcpu-8gb` (General) | 2 | 8 GB | 25 GB | $63 |
| `m-2vcpu-16gb` (Memory) | 2 | 16 GB | 50 GB | $84 |

### Additional Costs

| Service | Cost |
|---------|------|
| Load Balancer | $12/mo |
| Block Storage | From $10/mo (100 GB) |
| Bandwidth (outbound) | 2 TB free/node, then $0.01/GB |
| Snapshots | $0.06/GB/mo |

---

## Hetzner Pricing Details

### No Platform Fee
Hetzner has no managed K8s service — you pay only for VMs, and hetzner-k3s provisions K3s on them. **No markup for Kubernetes.**

### Server Types (Monthly, approximate EUR→USD)

**Shared vCPU (CX — best value for light workloads)**

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| CX22 | 2 | 4 GB | 40 GB | $4 |
| CX32 | 4 | 8 GB | 80 GB | $7 |
| CX42 | 8 | 16 GB | 160 GB | $14 |
| CX52 | 16 | 32 GB | 320 GB | $29 |

**ARM64 (CAX — cheapest compute, ideal for stateless workers)**

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| CAX11 | 2 | 4 GB | 40 GB | $4 |
| CAX21 | 4 | 8 GB | 80 GB | $7 |
| CAX31 | 8 | 16 GB | 160 GB | $13 |
| CAX41 | 16 | 32 GB | 320 GB | $25 |

**Dedicated vCPU (CPX — consistent performance for production)**

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| CPX11 | 2 | 2 GB | 40 GB | $5 |
| CPX21 | 3 | 4 GB | 80 GB | $9 |
| CPX22 | 4 | 8 GB | 160 GB | $15 |
| CPX32 | 8 | 16 GB | 240 GB | $26 |
| CPX42 | 16 | 32 GB | 360 GB | $56 |

**Dedicated High-Performance (CCX — guaranteed resources)**

| Type | vCPU | RAM | Disk | ~$/mo |
|------|------|-----|------|-------|
| CCX13 | 2 | 8 GB | 80 GB | $13 |
| CCX23 | 4 | 16 GB | 160 GB | $25 |
| CCX33 | 8 | 32 GB | 240 GB | $48 |
| CCX43 | 16 | 64 GB | 360 GB | $95 |

### Additional Costs

| Service | Cost |
|---------|------|
| Load Balancer | ~$6/mo |
| Block Storage (Volume) | ~$0.05/GB/mo |
| Bandwidth (outbound) | 20 TB/mo included per server, then ~$1/TB |
| Snapshots | ~$0.01/GB/mo |
| Floating IP | ~$3/mo |
| Private Network | Free |

---

## Cost Optimization Strategies

### 1. Right-Size Your Nodes

| Workload Type | Recommended Series | Why |
|---------------|--------------------| --- |
| Stateless APIs, web servers | Hetzner CX / CAX (shared vCPU) | Cheapest, burst-friendly |
| Background jobs, queues | Hetzner CAX ARM64 | ARM = most $/vCPU value |
| Databases, stateful workloads | Hetzner CPX / CCX (dedicated) | Consistent CPU, no noisy neighbor |
| General purpose (DO) | `s-2vcpu-4gb` or `s-4vcpu-8gb` | Best price/resource on DO |
| CPU-intensive (DO) | `c-2` or `c-4` | Optimized compute |
| Memory-intensive (DO) | `m-2vcpu-16gb` | High RAM-to-CPU ratio |

### 2. Use Autoscaling

Scale down during low-traffic periods:

**DigitalOcean:**
```bash
doctl kubernetes cluster node-pool create my-cluster \
  --name autoscaled \
  --size s-2vcpu-4gb \
  --count 2 \
  --auto-scale \
  --min-nodes 1 \
  --max-nodes 10
```

**Hetzner:**
```yaml
worker_node_pools:
  - name: autoscaled
    instance_type: cax21
    location: fsn1
    autoscaling:
      enabled: true
      min_instances: 1
      max_instances: 10
```

### 3. ARM64 Nodes (Hetzner Only)

ARM64 (CAX series) offers ~20-30% cost savings vs x86 at equivalent specs. Requirements:
- Container images must be multi-arch (`linux/amd64,linux/arm64`)
- Build with: `docker buildx build --platform linux/amd64,linux/arm64`
- Most popular images (nginx, node, python, postgres) already support ARM64

### 4. Separate Node Pools by Workload

Avoid paying for over-provisioned nodes by matching pool sizes to workload needs:

```yaml
# Hetzner example — 3 purpose-specific pools
worker_node_pools:
  - name: web          # Light: API servers, Nginx
    instance_type: cx22         # 2 vCPU, 4 GB — ~$4/mo
    instance_count: 2
    labels:
      - key: workload
        value: web

  - name: compute      # Heavy: data processing, ML
    instance_type: cpx32        # 8 vCPU, 16 GB — ~$26/mo
    instance_count: 1
    labels:
      - key: workload
        value: compute
    autoscaling:
      enabled: true
      min_instances: 0
      max_instances: 5

  - name: storage      # Stateful: databases
    instance_type: ccx23        # 4 vCPU, 16 GB — ~$25/mo
    instance_count: 1
    labels:
      - key: workload
        value: storage
```

### 5. Dev/Staging Cost Reduction

| Strategy | How | Savings |
|----------|-----|---------|
| Single-node K3s | 1x CX22, `schedule_workloads_on_masters: true` | ~$4/mo total |
| Smallest DO cluster | Free CP + 1x s-1vcpu-2gb | $12/mo total |
| Shutdown dev overnight | Delete cluster, recreate from config | ~50% |
| Use Hetzner for dev, DO for prod | Cheapest dev, managed prod | Best of both |

### 6. Bandwidth Savings

- **Hetzner**: 20 TB/mo included per server — virtually free for most workloads
- **DigitalOcean**: 2 TB/mo per node included, $0.01/GB overage
- **Tip**: Put bandwidth-heavy workloads (CDN origin, video processing) on Hetzner

### 7. Storage Optimization

- **Hetzner volumes**: ~$0.05/GB/mo (use for PersistentVolumeClaims)
- **DO block storage**: From $0.10/GB/mo (2x Hetzner)
- **Tip**: Use node local storage for ephemeral data, volumes only for persistent

---

## When to Choose Each Provider

| Scenario | Recommendation | Monthly Cost |
|----------|----------------|:------------:|
| Learning K8s | Hetzner 1x CX22 | ~$4 |
| Side project / indie hacker | Hetzner 3x CX22 | ~$12 |
| Startup staging | Hetzner 1+3 CX22 | ~$16 |
| Startup production (EU) | Hetzner 3+3 CPX (HA) | ~$58 |
| Startup production (US/Asia) | DO Free CP + 3x s-2vcpu-4gb | ~$72 |
| Production (needs managed CP) | DO HA CP + 3-5 workers | ~$112-280 |
| Multi-cloud (EU + US) | Hetzner EU + DO US | Varies |
| Maximum cost savings | Hetzner CAX ARM64 | Lowest |

---

## Monthly Budget Calculator

```
DigitalOcean:
  Control plane:    $0 (standard) or $40 (HA)
  + Workers:        count × size_price
  + Load balancers: count × $12
  + Storage:        GB × $0.10
  ─────────────────────────────────────
  Total = CP + Workers + LBs + Storage

Hetzner:
  Masters:          count × instance_price
  + Workers:        count × instance_price (per pool)
  + Load balancers: count × $6
  + Storage:        GB × $0.05
  ─────────────────────────────────────
  Total = Masters + Workers + LBs + Storage
```

### Quick Estimate Examples

| Config | DO Cost | Hetzner Cost |
|--------|:-------:|:------------:|
| 2-node dev | $48 | $8 |
| 3-node staging | $72 | $12 |
| HA + 3 workers (4vCPU/8GB) | $184 | $81 |
| HA + 5 workers (4vCPU/8GB) | $280 | $111 |
| HA + 10 workers (8vCPU/16GB) | $1000 | $305 |
