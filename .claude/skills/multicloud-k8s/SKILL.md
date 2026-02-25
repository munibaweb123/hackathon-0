---
name: multicloud-k8s
description: "Full Production Deployment Architect for Kubernetes across 6 providers (DO, Hetzner, AKS, GKE, EKS, Civo). Specification-first 8-phase lifecycle: Spec → Provision → Connect → Deploy → Verify → Troubleshoot → Teardown → Harden. Never generates commands without a deployment spec. Deployment is incomplete without HTTPS verification and $0 teardown confirmation."
---

# Production Deployment Architect — Multi-Cloud Kubernetes

A specification-first skill that operates as a professional cloud architect across
6 providers. It does not generate commands until a deployment specification is
complete. It treats a deployment as unfinished without HTTPS verification, cost
validation, and teardown confirmation.

## Full Deployment Lifecycle

```
PHASE 1: SPECIFICATION    Generate deployment-spec.md first. No commands without a spec.
    ↓
PHASE 2: PROVISION        Provider-specific cluster creation + auth + verification
    ↓
PHASE 3: CONNECT          Kubeconfig merge + context naming + node readiness
    ↓
PHASE 4: DEPLOY           Sequenced stack: Dapr → Traefik → cert-manager
                          → ClusterIssuer → App → Service → Ingress + TLS
    ↓
PHASE 5: VERIFY           10-point Production Readiness Checklist (mandatory)
    ↓
PHASE 6: TROUBLESHOOT     Convergence loop — diagnose by priority until all checks pass
    ↓
PHASE 7: TEARDOWN         Provider-specific deletion + $0 billing confirmation
    ↓
PHASE 8: HARDEN           (On request) Network Policies, PSS, Quotas, Monitoring
```

**Core insight:** 90% of Kubernetes operations are identical across all providers.
Only PHASE 2 (PROVISION) and PHASE 3 (CONNECT) differ by provider.
Everything from PHASE 4 onward — Helm, Dapr, Ingress, Secrets, HPA — is **the same everywhere**.

## What This Skill Does

- Generates a structured `deployment-spec.md` **before any commands are produced**
- Provisions Kubernetes clusters on **6 cloud providers**: DigitalOcean, Hetzner, Azure AKS, GKE, EKS, Civo
- Executes the correct stack deployment sequence with explicit ordering rationale
- Runs the 10-point Production Readiness Checklist — distinguishes "working" from "production-ready"
- Diagnoses failures by priority: pod status → networking → TLS → performance
- Generates provider-specific teardown commands and confirms $0 remaining cost
- Recommends Production Hardening additions when requested

## What This Skill Does NOT Do

- Generate provisioning or deployment commands before a deployment spec is approved
- Configure service mesh or multi-cluster networking (Istio, Linkerd)
- Handle application-level CI/CD pipelines (use `argocd-gitops` skill)
- Provision GPU/TPU node pools or specialized hardware beyond standard VM types

## Skill Discipline Rules

1. **Spec first.** If deployment context is missing (provider, region, domain, budget), generate clarifying questions before any command.
2. **Sequence discipline.** Never install components out of order — the dependency chain matters.
3. **Evidence-based verification.** Every check is backed by a `kubectl` command with expected output shown.
4. **Cost-aware always.** Every provisioning recommendation includes a cost estimate and hidden-cost warnings.
5. **Teardown is part of the deployment.** A lifecycle is not complete until billing shows $0.

---

## Before Generating Any Commands

Gather this context from the conversation. If any field is missing, ask before proceeding:

| Field | Why it matters |
|-------|----------------|
| **Provider** | Determines provisioning CLI, auth method, cost |
| **Region** | Latency, data residency, compliance |
| **Cluster name** | Kubeconfig context naming |
| **Domain** | TLS certificate subject, Ingress host |
| **Monthly budget** | Node size selection, provider recommendation |
| **Environment** | dev/staging/prod → HA, replicas, PDB decisions |
| **App image** | Registry type → imagePullSecrets pattern |
| **Compliance** | SOC2/HIPAA/FedRAMP → provider constraints |

---

## Specification Clarifications

If any of the following are missing from the conversation, ask these questions before generating commands:

1. **Provider**: "Which cloud provider — DigitalOcean, Hetzner, Azure, GCP, AWS, Civo?"
2. **Purpose**: "Is this dev/staging/production? What app will run on it?"
3. **Budget**: "What is the monthly budget target?"
4. **Region**: "Any geographic or compliance constraints on where data must reside?"
5. **Domain**: "Do you have a domain name for TLS? Or should we use nip.io for testing?"
6. **Existing infrastructure**: "Any existing kubeconfig, VPC, or registry to connect to?"

---

## Workflow: Provision → Connect → Deploy

```
1. PROVISION          2. CONNECT              3. DEPLOY
   DigitalOcean          Merge kubeconfig        kubectl apply
   doctl k8s create      Set context             or GitOps sync
       ─── or ───        Verify access
   Hetzner               Label contexts
   hetzner-k3s create
```

### Step 1: Provision

Choose provider based on requirements:

| Factor | DigitalOcean | Hetzner | Azure AKS | Google GKE | AWS EKS | Civo |
|--------|-------------|---------|-----------|------------|---------|------|
| **Control plane** | Managed (free) | Self-managed K3s | Managed ($0.10/hr) | Managed ($0.10/hr) | Managed ($0.10/hr) | Managed (free) |
| **Min cost (2-node 4GB)** | ~$48/mo | ~$8/mo | ~$110/mo | ~$120/mo | ~$135/mo | ~$20/mo |
| **Provisioning time** | 5–8 min | 3–5 min | 8–12 min | 5–8 min | 12–18 min | ~90 sec |
| **Best regions** | NYC, SFO, AMS, LON, SGP | EU (FSN, NBG, HEL), US, SIN | Global (60+ regions) | Global (40+ regions) | Global (30+ regions) | LON, NYC, FRA |
| **Autoscaling** | Built-in | Add-on | Built-in | Built-in | Built-in | Built-in |
| **Compliance certs** | SOC2, ISO 27001 | Limited | SOC2, HIPAA, FedRAMP | SOC2, HIPAA, FedRAMP | SOC2, HIPAA, FedRAMP | SOC2 |
| **Best for** | Simplicity, US/Asia | Cheapest, EU | Enterprise, Azure ecosystem | ML/data, GCP ecosystem | Enterprise, AWS ecosystem | Learning, fastest spin-up |

### Step 2: Connect

After provisioning, merge kubeconfigs so `kubectl` can reach all clusters:

```bash
# DigitalOcean — auto-adds to kubeconfig
doctl kubernetes cluster kubeconfig save <cluster-name>

# Hetzner — kubeconfig written to path specified in config
export KUBECONFIG=~/.kube/config:./kubeconfig
kubectl config view --merge --flatten > ~/.kube/merged-config
mv ~/.kube/merged-config ~/.kube/config

# List all contexts
kubectl config get-contexts

# Switch between clusters
kubectl config use-context do-nyc1-my-doks-cluster
kubectl config use-context my-hetzner-cluster

# Verify connectivity
kubectl --context=do-nyc1-my-doks-cluster get nodes
kubectl --context=my-hetzner-cluster get nodes
```

### Step 3: Deploy

Deploy workloads to any connected cluster:

```bash
# Deploy to specific cluster
kubectl --context=do-nyc1-my-doks-cluster apply -f k8s/

# Or set default context and deploy
kubectl config use-context my-hetzner-cluster
kubectl apply -f k8s/
```

---

## Phase 1: Deployment Specification

**Generate this specification document before any provisioning or deployment commands.**
If data is missing, ask for it. Do not skip fields — each one drives downstream decisions.

### deployment-spec.md Template

```markdown
# Deployment Specification
**Date:** YYYY-MM-DD
**Status:** DRAFT → APPROVED → ACTIVE → TORN DOWN

---

## 1. Target Environment

| Field | Value |
|-------|-------|
| Provider | e.g. DigitalOcean / Hetzner / Azure / GCP / AWS / Civo |
| Region | e.g. ams3 / fsn1 / eastus / us-central1-a / us-east-1 / LON1 |
| Cluster name | e.g. my-app-prod |
| Environment | dev / staging / production |
| Domain | e.g. app.example.com (or "use nip.io for testing") |
| Kubeconfig context | e.g. do-ams3-my-app-prod |

---

## 2. Resource Requirements

| Resource | Value |
|----------|-------|
| Node count | e.g. 2 (dev) / 3+ (prod HA) |
| Node size | e.g. cx22 / s-2vcpu-4gb / Standard_B2s |
| CPU request per pod | e.g. 50m |
| CPU limit per pod | e.g. 500m |
| Memory request per pod | e.g. 64Mi |
| Memory limit per pod | e.g. 256Mi |
| Replicas | e.g. 2 (minimum for production) |

---

## 3. Stack Components

| Component | Included? | Version / Notes |
|-----------|-----------|-----------------|
| Dapr | Yes / No | e.g. 1.14.4 |
| Traefik | Yes / No | e.g. 32.1.1 |
| cert-manager | Yes / No | e.g. v1.16.2 |
| Let's Encrypt | Staging / Prod | Start with staging |
| Application image | Yes | e.g. ghcr.io/org/app:v1.0.0 |
| PostgreSQL | Yes / No | In-cluster or external |
| Redis | Yes / No | In-cluster or external |
| Registry type | Public / Private | imagePullSecrets needed? |

---

## 4. Success Criteria

Deployment is complete ONLY when all of the following are confirmed:

- [ ] `kubectl get nodes` — all nodes `Ready`
- [ ] `kubectl get pods -n <ns>` — all pods `Running`, 0 `CrashLoopBackOff`
- [ ] `kubectl get certificate -n <ns>` — `READY=True` with prod issuer
- [ ] `curl -sf https://<domain>/health` — returns `200`
- [ ] `kubectl get hpa -n <ns>` — HPA configured (if traffic-serving)
- [ ] `kubectl get pdb -n <ns>` — PDB exists
- [ ] Monthly cost estimate documented (see Cost Constraints below)
- [ ] Teardown completed with $0 billing confirmed (if non-permanent cluster)

---

## 5. Non-Goals (Explicit Scope Boundaries)

List what this deployment does NOT cover:

- [ ] e.g. CI/CD pipeline setup
- [ ] e.g. Database backups
- [ ] e.g. Multi-cluster failover
- [ ] e.g. Custom domain email routing

---

## 6. Cost Constraints

| Item | Estimated $/mo |
|------|---------------|
| Nodes (n × size) | $__ |
| Control plane fee | $__ |
| Load balancer(s) | $__ |
| Storage volumes | $__ |
| Bandwidth (if heavy) | $__ |
| **Total estimate** | **$__** |

Maximum acceptable monthly spend: $____
Alert threshold (80%): $____

---

## 7. Risk Assumptions

List known risks accepted for this deployment:

- e.g. Single-node cluster = no HA (acceptable for dev, not prod)
- e.g. Using nip.io domain = not suitable for real end-users
- e.g. Staging TLS cert = browser warnings (acceptable before go-live)
- e.g. No PDB in dev = acceptable for cost savings

---

## 8. Rollback Strategy

| Trigger | Action |
|---------|--------|
| Health check fails after deploy | `helm rollback <release>` |
| CrashLoopBackOff after image change | `kubectl set image deployment/my-app app=<previous-tag>` |
| DNS change causes outage | Revert A-record to previous LB IP |
| Full cluster corruption | `hetzner-k3s delete` / `doctl k8s cluster delete` + re-provision from this spec |

---

## 9. Teardown Plan

| Step | Command | Verification |
|------|---------|--------------|
| 1. Delete cluster | See Phase 7 teardown commands | `kubectl get nodes` fails |
| 2. Verify LBs deleted | Check billing dashboard | No LB line item |
| 3. Verify volumes deleted | Check storage dashboard | No volume line item |
| 4. Remove kubeconfig context | `kubectl config delete-context <name>` | Context not in `kubectl config get-contexts` |
| 5. Confirm $0 running cost | Screenshot billing dashboard | Balance $0 or expected base only |

---

## Spec Approval

| Reviewer | Date | Sign-off |
|----------|------|----------|
| | | ☐ Approved to proceed to PHASE 2 |
```

### How to Use This Template

1. Fill in all fields marked with `____` or `e.g.`
2. Set **Status** to `DRAFT`
3. Review Non-Goals — anything not listed is in-scope by default
4. Review Cost Constraints — verify budget is acceptable before provisioning
5. Set **Status** to `APPROVED` before generating Phase 2 commands

> **This skill will not generate provisioning commands until the spec has:**
> - Provider and region confirmed
> - Cost estimate reviewed
> - Success Criteria acknowledged
> - Teardown Plan documented

---

## Phase 2: Provision (Provider-Specific)

*The detailed provisioning commands for each provider are in their Quick Reference sections below.
Cross-reference the spec to select the correct node size and region.*

**After provisioning, confirm:**
```bash
kubectl get nodes
# Expected: all nodes STATUS=Ready before proceeding to Phase 3
```

---

## Phase 3: Connect (Kubeconfig)

*Detailed kubeconfig merge steps are in each provider's Quick Reference and in Multi-Cloud Kubeconfig Management.*

**After connecting, confirm:**
```bash
kubectl config current-context       # must match spec Kubeconfig context field
kubectl cluster-info                 # control plane URL must respond
kubectl get nodes                    # nodes must show Ready
```

---

## Phase 4: Deploy (Stack Sequence)

**Deployment order is mandatory.** Each component is a dependency of the next.

```
1. Dapr           — must exist before app pods (sidecar injection)
2. Traefik        — must exist before Ingress rules are evaluated
3. cert-manager   — must exist before TLS resources are created
4. ClusterIssuer  — must exist before Ingress requests certificates
5. Application    — Deployment + resource limits + probes + Dapr annotations
6. Service        — ClusterIP (Traefik routes externally — no per-app LB)
7. Ingress + TLS  — references ClusterIssuer + routes through Traefik
```

*The complete per-component commands and YAML are in Full Stack Deployment Patterns below.*

---

## Phase 5: Verify

*Run the 10-point Production Readiness Checklist (see Production Readiness Verification below).*

**Gate:** All 10 checks must PASS before marking deployment complete.
Conditional checks (PostgreSQL, external APIs, load testing) must pass if applicable.

---

## Phase 6: Troubleshoot (Convergence Loop)

*If any Phase 5 check fails, diagnose using the Failure Diagnosis Playbook (Priority 1 → 4).*

**Rule:** Fix Priority 1 (pod not running) before investigating Priority 2 (networking).
Never move to teardown while checks are failing — fix the issue or document it as a known Non-Goal.

---

## Phase 7: Clean Teardown

A deployment is not complete until it is cleanly deleted and all cloud resources show $0 active charges.
**This phase is mandatory for all learning, staging, and ephemeral environments.**

### Step 1 — Pre-Teardown Resource Inventory

Before deleting anything, list every resource the cluster created. Orphaned load balancers and volumes continue billing silently after the cluster is gone.

```bash
# ── DigitalOcean ──────────────────────────────────────────────────────────────
# List LBs created by the cluster (must delete these FIRST)
doctl compute load-balancer list --format Name,IP,Status
# List volumes associated with cluster PVCs
doctl compute volume list --format Name,SizeGigaBytes,Tags

# ── Hetzner ───────────────────────────────────────────────────────────────────
# hetzner-k3s delete handles LBs and volumes automatically when configured
# To verify manually:
hcloud load-balancer list
hcloud volume list

# ── Azure ─────────────────────────────────────────────────────────────────────
az resource list --resource-group <rg-name> --output table
az network lb list --resource-group <rg-name> --output table
az disk list --resource-group <rg-name> --output table

# ── Google Cloud ───────────────────────────────────────────────────────────────
gcloud compute forwarding-rules list --project <project-id>
gcloud compute disks list --project <project-id>

# ── AWS ────────────────────────────────────────────────────────────────────────
aws elb describe-load-balancers --region <region>
aws elbv2 describe-load-balancers --region <region>
aws ec2 describe-volumes --filters Name=status,Values=in-use --region <region>

# ── Civo ───────────────────────────────────────────────────────────────────────
civo loadbalancer list
civo volume list
```

### Step 2 — Delete Kubernetes Resources First

Remove in-cluster resources so cloud controllers can deprovision external LBs and volumes gracefully before cluster deletion.

```bash
# Delete all LoadBalancer-type services (triggers LB deletion by cloud controller)
kubectl get svc -A --field-selector spec.type=LoadBalancer
kubectl delete svc <service-name> -n <namespace>

# Delete PVCs (triggers volume deletion if reclaim policy is Delete)
kubectl get pvc -A
kubectl delete pvc <pvc-name> -n <namespace>

# Wait for external resources to be deprovisioned (30–120 seconds)
sleep 60
```

### Step 3 — Delete the Cluster

```bash
# ── DigitalOcean ──────────────────────────────────────────────────────────────
doctl kubernetes cluster delete <cluster-name> --force
# Confirm cluster is gone:
doctl kubernetes cluster list

# ── Hetzner ───────────────────────────────────────────────────────────────────
hetzner-k3s delete --config cluster.yaml
# hetzner-k3s handles: servers, firewalls, networks, LBs, SSH keys

# ── Azure ─────────────────────────────────────────────────────────────────────
# Deleting the resource group removes ALL resources (AKS cluster, LBs, disks, NICs)
az group delete --name <rg-name> --yes --no-wait
# Monitor deletion:
az group show --name <rg-name> --query properties.provisioningState

# ── Google Cloud ───────────────────────────────────────────────────────────────
gcloud container clusters delete <cluster-name> \
  --zone <zone> --project <project-id> --quiet
# Delete any orphaned persistent disks:
gcloud compute disks delete <disk-name> --zone <zone> --project <project-id>

# ── AWS ────────────────────────────────────────────────────────────────────────
eksctl delete cluster --name <cluster-name> --region <region>
# eksctl handles: node groups, VPC, security groups, IAM roles
# Monitor (can take 15–25 minutes):
eksctl get cluster --name <cluster-name> --region <region>

# ── Civo ───────────────────────────────────────────────────────────────────────
civo kubernetes delete <cluster-name> --yes
```

### Step 4 — Clean Up Local Kubeconfig

```bash
# Remove the deleted cluster's context
kubectl config delete-context <context-name>
kubectl config delete-cluster <cluster-name>
kubectl config delete-user <user-name>

# Verify contexts list is clean
kubectl config get-contexts
```

### Step 5 — $0 Billing Confirmation Checklist

Do not mark a teardown as complete until every item is verified:

```
Teardown Verification
─────────────────────────────────────────────────────────────────
[ ] No active Kubernetes clusters visible in provider console
[ ] No active load balancers (check provider console, not just kubectl)
[ ] No unattached or in-use volumes from this cluster
[ ] No active node pools or VM instances
[ ] Kubeconfig context removed from ~/.kube/config
[ ] Billing dashboard checked — no unexpected charges since deletion
[ ] Billing alert confirmed still active (not deleted with the cluster)
─────────────────────────────────────────────────────────────────
All boxes checked = TEARDOWN COMPLETE / $0 CONFIRMED
```

**How to verify $0 in each provider's billing dashboard:**

| Provider | Billing Check URL |
|----------|-------------------|
| DigitalOcean | cloud.digitalocean.com → Billing → Usage |
| Hetzner | console.hetzner.cloud → Account → Billing → Current usage |
| Azure | portal.azure.com → Cost Management → Cost analysis |
| GCP | console.cloud.google.com → Billing → Reports |
| AWS | console.aws.amazon.com → Billing → Bills |
| Civo | dash.civo.com → Settings → Billing |

> **Note:** Cloud billing often has a 1–6 hour lag. If you see charges, wait and refresh.
> The goal is zero *active* resources — historical charges for the session are expected.

---

## Phase 8: Production Hardening

Apply after a deployment is stable and verified. Hardening is additive — the application must already be running before these controls are applied. Prioritized by production risk level.

### Priority 1 (Critical) — Workload Isolation

#### Network Policies

Without Network Policies, every pod can communicate with every other pod. Apply default-deny and allow only required traffic.

```yaml
# default-deny-all.yaml — block all ingress/egress by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: <your-namespace>
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# allow-app-ingress.yaml — allow only Traefik → app traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-traefik-ingress
  namespace: <your-namespace>
spec:
  podSelector:
    matchLabels:
      app: <your-app>
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: traefik
      ports:
        - port: 8080
---
# allow-app-to-db.yaml — allow app → PostgreSQL only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-to-postgres
  namespace: <your-namespace>
spec:
  podSelector:
    matchLabels:
      app: postgres
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: <your-app>
      ports:
        - port: 5432
```

```bash
# Verify policy is applied
kubectl get networkpolicy -n <your-namespace>
# Test isolation: this should timeout if policies are working
kubectl run test --image=busybox --rm -it -- wget -qO- http://<app-service>
```

#### Pod Security Standards (PSS)

```bash
# Label namespace to enforce restricted policy (blocks privileged pods, hostPath, etc.)
kubectl label namespace <your-namespace> \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=latest \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted
```

```yaml
# Ensure your pods comply — add to Deployment spec.template.spec:
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 2000
  seccompProfile:
    type: RuntimeDefault

# And to each container spec:
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

### Priority 2 (High) — Resource Governance

#### Resource Quotas

Prevents a single namespace from consuming all cluster resources (critical in multi-tenant clusters).

```yaml
# resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: namespace-quota
  namespace: <your-namespace>
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
    services: "10"
    persistentvolumeclaims: "5"
---
# LimitRange — enforces defaults so pods without requests/limits are still bounded
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: <your-namespace>
spec:
  limits:
    - type: Container
      default:
        cpu: 500m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "2"
        memory: 2Gi
```

```bash
kubectl apply -f resource-quota.yaml
kubectl describe resourcequota namespace-quota -n <your-namespace>
```

#### Horizontal Pod Autoscaler (HPA)

```yaml
# hpa.yaml — scale between 2 and 10 replicas based on CPU
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: <app>-hpa
  namespace: <your-namespace>
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <your-app>
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # wait 5 min before scaling down
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
```

#### Pod Disruption Budget (PDB)

Ensures voluntary disruptions (node upgrades, scaling) never take all replicas offline simultaneously.

```yaml
# pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: <app>-pdb
  namespace: <your-namespace>
spec:
  minAvailable: 1         # always keep at least 1 pod running
  selector:
    matchLabels:
      app: <your-app>
```

```bash
kubectl apply -f pdb.yaml
kubectl get pdb -n <your-namespace>
```

### Priority 3 (Medium) — Observability & Backup

#### Monitoring Stack (Prometheus + Grafana)

```bash
# Install kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=<your-password> \
  --set prometheus.prometheusSpec.retention=30d \
  --wait

# Access Grafana (port-forward for initial access)
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
# Open: http://localhost:3000 (admin / <your-password>)
```

**Key dashboards to import (Grafana dashboard IDs):**

| Dashboard | ID | Purpose |
|-----------|-----|---------|
| Kubernetes Cluster Overview | 7249 | Nodes, CPU, Memory, Pods |
| Kubernetes Deployments | 8588 | Deployment health, rollouts |
| Kubernetes Networking | 12125 | Network policies, traffic |
| Node Exporter Full | 1860 | Node-level metrics |

#### Backup Strategy

```bash
# Install Velero (cluster backup and restore)
helm repo add vmware-tanzu https://vmware-tanzu.github.io/helm-charts
helm upgrade --install velero vmware-tanzu/velero \
  --namespace velero --create-namespace \
  --set configuration.provider=<provider> \   # aws | gcp | azure
  --set configuration.backupStorageLocation.bucket=<bucket> \
  --set initContainers[0].name=velero-plugin-for-<provider> \
  --set initContainers[0].image=velero/velero-plugin-for-<provider>:latest \
  --wait

# Schedule daily backups at 2am UTC
velero schedule create daily-backup \
  --schedule="0 2 * * *" \
  --ttl 720h    # keep 30 days

# Verify backup schedule
velero schedule get
velero backup get
```

### Priority 4 (Recommended) — Rollback Strategy

Document the rollback path before go-live so it can be executed under pressure.

```bash
# ── Rollback Deployment to previous version ───────────────────────────────────
kubectl rollout history deployment/<app> -n <namespace>
kubectl rollout undo deployment/<app> -n <namespace>
# or to a specific revision:
kubectl rollout undo deployment/<app> --to-revision=2 -n <namespace>

# Monitor rollback:
kubectl rollout status deployment/<app> -n <namespace>

# ── Rollback Helm release to previous chart ───────────────────────────────────
helm history <release> -n <namespace>
helm rollback <release> <revision> -n <namespace>
# Example: roll back to revision 3
helm rollback my-app 3 -n production

# ── Emergency: scale to zero (if rollback fails and outage is worse) ──────────
kubectl scale deployment/<app> --replicas=0 -n <namespace>
```

**Rollback decision matrix:**

| Signal | Action | Command |
|--------|---------|---------|
| New pods crash-looping | Rollback deployment | `kubectl rollout undo deployment/<app>` |
| 5xx rate > 1% post-deploy | Rollback deployment | `kubectl rollout undo deployment/<app>` |
| Database migration failed | Scale to zero, fix migration | `kubectl scale deploy/<app> --replicas=0` |
| Helm upgrade broke config | Rollback Helm release | `helm rollback <release> <revision>` |
| Total service loss | Check nodes first | `kubectl get nodes; kubectl get pods -A` |

### Hardening Summary Table

| Priority | Control | Risk Mitigated | Applied |
|----------|---------|----------------|---------|
| 1 — Critical | Network Policies | Lateral movement after compromise | [ ] |
| 1 — Critical | Pod Security Standards | Container escape, privilege escalation | [ ] |
| 2 — High | Resource Quotas + LimitRange | Noisy neighbor, resource exhaustion | [ ] |
| 2 — High | HPA | Traffic spike → outage | [ ] |
| 2 — High | PDB | Rolling updates taking all replicas offline | [ ] |
| 3 — Medium | Prometheus + Grafana | Blind to failures until users complain | [ ] |
| 3 — Medium | Velero backups | No recovery path after data loss | [ ] |
| 4 — Recommended | Rollback runbook | Panic under pressure → wrong action | [ ] |

> **When to apply:** After Phase 5 (Verify) passes. Never block launch for hardening —
> ship first, harden within the first sprint. Priority 1 controls should be applied
> within 24 hours of any production launch.

---

## Universal Kubernetes Operations

**These commands are identical on every provider after `kubectl` is configured.**
Kubernetes expertise is fully transferable — only provisioning differs.

```bash
# ── Apply manifests ─────────────────────────────────────────────────────────
kubectl apply -f k8s/                          # deploy all manifests in a dir
kubectl apply -f deployment.yaml               # deploy single file

# ── Helm (identical on all providers) ───────────────────────────────────────
helm repo add <repo> <url>
helm upgrade --install <release> <chart> \
  --namespace <ns> --create-namespace \
  --values values.yaml --wait

# ── Dapr (identical on all providers) ───────────────────────────────────────
helm repo add dapr https://dapr.github.io/helm-charts
helm upgrade --install dapr dapr/dapr \
  --namespace dapr-system --create-namespace \
  --set global.mtls.enabled=true --wait

# ── Ingress controller (identical on all providers) ─────────────────────────
helm repo add traefik https://traefik.github.io/charts
helm upgrade --install traefik traefik/traefik \
  --namespace traefik --create-namespace \
  --set service.type=LoadBalancer --wait

# ── cert-manager (identical on all providers) ───────────────────────────────
helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true --wait

# ── Secrets (identical on all providers) ────────────────────────────────────
kubectl create secret generic my-secrets \
  --from-literal=API_KEY=value --namespace my-app
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io --docker-username=user \
  --docker-password=token --namespace my-app

# ── Scaling (identical on all providers) ────────────────────────────────────
kubectl scale deployment my-app --replicas=3 -n my-app
kubectl autoscale deployment my-app --min=2 --max=10 --cpu-percent=60

# ── Logs & Debug (identical on all providers) ───────────────────────────────
kubectl logs -f deployment/my-app -n my-app
kubectl exec -it <pod> -n my-app -- sh
kubectl describe pod <pod> -n my-app
kubectl top pods -n my-app
```

> The only provider-specific difference in STEP 3 is the **storage class name**
> used in PersistentVolumeClaims. See Migration Strategy Generator for how to
> parameterize this.

---

## Multi-Cloud Command Comparison

### Provision, Connect, Delete

| Operation | DigitalOcean | Hetzner | Azure AKS | Google GKE | AWS EKS | Civo |
|-----------|-------------|---------|-----------|------------|---------|------|
| **Install CLI** | `brew install doctl` | `brew install vitobotta/tap/hetzner_k3s` | `brew install azure-cli` | `brew install google-cloud-sdk` | `brew install eksctl awscli` | `brew install civo/tools/civo` |
| **Authenticate** | `doctl auth init` | `export HCLOUD_TOKEN=...` | `az login` | `gcloud auth login` | `aws configure` | `civo apikey save my-key <token>` |
| **Create 2-node cluster** | `doctl k8s cluster create my-cluster --region nyc1 --size s-2vcpu-4gb --count 2` | `hetzner-k3s create --config cluster.yaml` | `az aks create -g my-rg -n my-aks --node-count 2 --node-vm-size Standard_B2s` | `gcloud container clusters create my-gke --num-nodes 2 --machine-type e2-medium --zone us-central1-a` | `eksctl create cluster --name my-eks --region us-east-1 --node-type t3.medium --nodes 2` | `civo kubernetes create my-cluster --nodes 2 --size g4s.kube.medium --region LON1` |
| **Save kubeconfig** | `doctl k8s cluster kubeconfig save my-cluster` | merge `./kubeconfig` manually | `az aks get-credentials -g my-rg -n my-aks` | `gcloud container clusters get-credentials my-gke --zone us-central1-a` | `aws eks update-kubeconfig --name my-eks --region us-east-1` | `civo kubernetes config my-cluster --save --merge` |
| **List clusters** | `doctl k8s cluster list` | N/A (config-based) | `az aks list -o table` | `gcloud container clusters list` | `eksctl get cluster` | `civo kubernetes list` |
| **Delete cluster** | `doctl k8s cluster delete my-cluster` | `hetzner-k3s delete --config cluster.yaml` | `az aks delete -g my-rg -n my-aks` | `gcloud container clusters delete my-gke --zone us-central1-a` | `eksctl delete cluster --name my-eks` | `civo kubernetes delete my-cluster` |

### Universal Operations (Provider-Agnostic)

| Operation | Command (same on all providers) |
|-----------|--------------------------------|
| **Deploy manifests** | `kubectl apply -f k8s/` |
| **Install Helm chart** | `helm upgrade --install <release> <chart> --wait` |
| **Install Dapr** | `helm upgrade --install dapr dapr/dapr -n dapr-system --create-namespace` |
| **Install Traefik** | `helm upgrade --install traefik traefik/traefik -n traefik --create-namespace` |
| **Create secret** | `kubectl create secret generic my-secrets --from-literal=KEY=value` |
| **Scale deployment** | `kubectl scale deployment my-app --replicas=3` |
| **View logs** | `kubectl logs -f deployment/my-app` |
| **Exec into pod** | `kubectl exec -it <pod> -- sh` |
| **Check node status** | `kubectl get nodes -o wide` |
| **Run readiness check** | `kubectl wait --for=condition=Ready nodes --all --timeout=120s` |

### Provider-Specific Defaults to Override

| Item | DigitalOcean | Hetzner | Azure | GCP | AWS | Civo |
|------|-------------|---------|-------|-----|-----|------|
| **Storage class** | `do-block-storage` | `hcloud-volumes` | `managed-premium` | `standard-rwo` | `gp2` / `gp3` | `civo-volume` |
| **LB annotation** | `service.beta.kubernetes.io/do-loadbalancer-*` | Hetzner CCM auto | `service.beta.kubernetes.io/azure-load-balancer-*` | `cloud.google.com/neg` | `service.beta.kubernetes.io/aws-load-balancer-*` | None needed |
| **Node labels** | Pool name | Node pool name | `agentpool` label | `cloud.google.com/gke-nodepool` | nodegroup name | `kubernetes.civo.com/node-pool` |
| **Context name format** | `do-<region>-<name>` | `<cluster-name>` | `<name>` | `gke_<project>_<zone>_<name>` | `arn:aws:eks:<region>:<id>:cluster/<name>` | `<name>` |

---

## DigitalOcean DOKS Quick Reference

### Prerequisites

#### 1. Install doctl

```bash
brew install doctl                    # macOS
snap install doctl                    # Ubuntu/Linux (snapd required)
scoop install doctl                   # Windows (scoop required)

# Verify binary is on PATH
doctl version
# Expected: doctl version X.Y.Z release
```

#### 2. Generate an API Token

Go to **cloud.digitalocean.com → API → Tokens → Generate New Token**.

| Token scope | What it unlocks | Required? |
|---|---|---|
| **Read** | List clusters, nodes, regions, sizes | Yes |
| **Write** | Create/delete clusters, node pools, kubeconfigs | Yes — without this, `doctl k8s cluster create` returns 403 |

> Read-only tokens appear to authenticate successfully but fail silently when
> provisioning — always create tokens with **Full Access** or explicit
> read+write scope.

#### 3. Authenticate

```bash
# Interactive (recommended for first-time setup)
doctl auth init
# Paste your token when prompted
# Config saved to: ~/.config/doctl/config.yaml

# Non-interactive (CI/CD or scripted setup)
doctl auth init --access-token <your-token>

# Multiple accounts — use named contexts
doctl auth init --context my-startup
doctl auth switch --context my-startup
doctl auth list                        # show all saved auth contexts
```

#### 4. Verify Authentication & Account Status

```bash
doctl account get
```

Expected output (healthy account):

```
Email           Team              Droplet Limit    Email Verified    Status
you@example.com My Team           25               true              active
```

| Field | What to check |
|---|---|
| `Status` | Must be `active` — `warning` or `locked` blocks provisioning |
| `Email Verified` | Must be `true` — unverified accounts cannot create resources |
| `Droplet Limit` | Default 25; DOKS nodes count against this — request increase if needed |

If `doctl account get` returns `Unable to authenticate`:
```bash
doctl auth init          # re-run auth — token may be expired or revoked
```

### Provision Cluster

#### Common create options

| Flag | Purpose | Example |
|---|---|---|
| `--region` | Datacenter location | `--region ams3` |
| `--size` | Node droplet size slug | `--size s-4vcpu-8gb` |
| `--count` | Number of nodes (simple pool) | `--count 2` |
| `--version` | K8s version (`latest` or pinned) | `--version 1.32.0-do.0` |
| `--ha` | HA control plane (+$40/mo) | `--ha` |
| `--auto-upgrade` | Auto-apply patch upgrades | `--auto-upgrade` |
| `--surge-upgrade` | Extra node during upgrades (zero-downtime) | `--surge-upgrade` |
| `--maintenance-window` | 4-hour UTC window for upgrades | `--maintenance-window saturday=02:00` |
| `--node-pool` | Named pool with autoscaling (repeatable) | see below |
| `--tag` | Tag cluster for billing/filtering | `--tag env:prod` |
| `--vpc-uuid` | Place in specific VPC | `--vpc-uuid <uuid>` |
| `--update-kubeconfig` | Auto-merge kubeconfig (default: true) | `--update-kubeconfig=false` |

```bash
# --- Tier 1: Dev / learning (~$24/mo) ---
doctl kubernetes cluster create my-dev \
  --region ams3 \
  --size s-2vcpu-4gb \
  --count 2

# --- Tier 2: Startup / staging (~$96/mo) ---
doctl kubernetes cluster create my-staging \
  --region ams3 \
  --size s-4vcpu-8gb \
  --count 2 \
  --auto-upgrade \
  --maintenance-window saturday=02:00 \
  --tag env:staging

# --- Tier 3: Production HA with autoscaling (~$184+/mo) ---
doctl kubernetes cluster create my-prod \
  --region ams3 \
  --version latest \
  --ha \
  --auto-upgrade \
  --surge-upgrade \
  --maintenance-window saturday=02:00 \
  --node-pool "name=app-pool;size=s-4vcpu-8gb;count=3;auto-scale=true;min-nodes=3;max-nodes=10;label=workload=app" \
  --node-pool "name=worker-pool;size=s-2vcpu-4gb;count=2;auto-scale=true;min-nodes=1;max-nodes=5;label=workload=worker;taint=dedicated=worker:NoSchedule" \
  --tag env:prod
```

> Before provisioning: run `doctl kubernetes options sizes` and
> `doctl kubernetes options regions` to confirm slugs are valid.

### Kubeconfig & Cluster Switching

DOKS auto-saves kubeconfig when `--update-kubeconfig` is true (default).
After provisioning, or to connect to an existing cluster:

```bash
# Save / refresh credentials for a cluster (merges into ~/.kube/config)
doctl kubernetes cluster kubeconfig save my-prod

# Context is auto-named: do-<region>-<cluster-name>
# e.g. do-ams3-my-prod

# List all available contexts (all clouds)
kubectl config get-contexts

# Switch to this cluster
kubectl config use-context do-ams3-my-prod

# One-off command without switching default context
kubectl --context=do-ams3-my-prod get pods -A

# Remove stale cluster from kubeconfig (after delete)
doctl kubernetes cluster kubeconfig remove my-prod
```

### Verification Commands

Run these after provisioning to confirm the cluster is healthy before deploying workloads:

```bash
# 1. Confirm nodes are Ready
kubectl get nodes
# Expected:
# NAME              STATUS   ROLES    AGE   VERSION
# pool-abc-xxxx     Ready    <none>   3m    v1.32.x
# pool-abc-yyyy     Ready    <none>   3m    v1.32.x

# 2. Confirm control plane is reachable
kubectl cluster-info
# Expected:
# Kubernetes control plane is running at https://...
# CoreDNS is running at https://.../api/v1/namespaces/kube-system/...

# 3. Confirm system pods are Running
kubectl get pods -n kube-system

# 4. Check node resource capacity
kubectl get nodes -o wide

# 5. (Optional) Full readiness check
kubectl wait --for=condition=Ready nodes --all --timeout=120s
```

### Cost Awareness

```bash
# Check current node sizes and counts before provisioning
doctl kubernetes options sizes          # full size catalogue with $/mo
doctl kubernetes options regions        # confirm region supports your size

# Estimate monthly cost before creating
# Formula: node_count × droplet_$/mo  (control plane is always free on DOKS)
# Examples:
#   2 × s-2vcpu-4gb ($24) = $48/mo
#   2 × s-4vcpu-8gb ($48) = $96/mo
#   3 × s-4vcpu-8gb ($48) + HA ($40) = $184/mo

# Monitor live spend: cloud.digitalocean.com/account/billing
```

### Teardown Procedure

Always follow this order to avoid orphaned billable resources:

```bash
# 1. List associated resources first (LBs, volumes — these bill separately)
doctl kubernetes cluster list-associated-resources my-prod

# 2a. Standard delete (leaves associated LBs/volumes — you pay until manually removed)
doctl kubernetes cluster delete my-prod

# 2b. Aggressive delete — also removes associated LBs and block volumes
#     WARNING: destroys persistent data. Use only for dev/staging.
doctl kubernetes cluster delete my-prod --dangerous

# 3. Verify cluster is gone
doctl kubernetes cluster list

# 4. Remove stale kubeconfig context
doctl kubernetes cluster kubeconfig remove my-prod
# or manually:
kubectl config delete-context do-ams3-my-prod
kubectl config delete-cluster do-ams3-my-prod

# 5. Confirm no orphaned LBs or volumes remain in the DO console
#    cloud.digitalocean.com/networking/load_balancers
#    cloud.digitalocean.com/volumes
```

### Manage Cluster

```bash
doctl kubernetes cluster list                                 # list all clusters
doctl kubernetes cluster get <name>                           # cluster details + status
doctl kubernetes cluster get-upgrades <name>                  # available K8s upgrades
doctl kubernetes cluster upgrade <name> --version <slug>      # upgrade K8s version
doctl kubernetes cluster node-pool list <cluster>             # list node pools
doctl kubernetes cluster node-pool create <cluster> \         # add node pool
  --name new-pool --size s-4vcpu-8gb --count 3
doctl kubernetes cluster node-pool update <cluster> <pool> \  # resize pool
  --count 5
doctl kubernetes cluster node-pool delete <cluster> <pool>    # remove pool
doctl kubernetes options versions                             # available K8s versions
doctl kubernetes options sizes                                # available node sizes
doctl kubernetes options regions                              # available regions
```

> Full CLI reference: `references/digitalocean-doks.md`

---

## Hetzner K3s Quick Reference

### Prerequisites

#### 1. Install hetzner-k3s CLI

```bash
# macOS / Linux (Homebrew)
brew install vitobotta/tap/hetzner_k3s

# Linux amd64 (most servers and WSL2)
wget https://github.com/vitobotta/hetzner-k3s/releases/latest/download/hetzner-k3s-linux-amd64
chmod +x hetzner-k3s-linux-amd64
sudo mv hetzner-k3s-linux-amd64 /usr/local/bin/hetzner-k3s

# Linux arm64 (Raspberry Pi, ARM servers)
wget https://github.com/vitobotta/hetzner-k3s/releases/latest/download/hetzner-k3s-linux-arm64
chmod +x hetzner-k3s-linux-arm64
sudo mv hetzner-k3s-linux-arm64 /usr/local/bin/hetzner-k3s

# Verify
hetzner-k3s --version
# Expected: hetzner-k3s version X.Y.Z
```

#### 2. Generate a Hetzner Cloud API Token

Go to **console.hetzner.cloud → Your Project → Security → API Tokens → Generate API Token**.

| Token scope | What it unlocks | Required? |
|---|---|---|
| **Read** | List servers, networks, locations | Yes |
| **Write** | Create/delete servers, networks, firewalls, LBs | Yes — without this, `hetzner-k3s create` fails mid-provision |

> **Never hardcode the token in your config YAML and commit it to Git.**
> Use an environment variable and reference it at provision time:

```bash
# Set once per shell session (or add to ~/.bashrc)
export HCLOUD_TOKEN="your-hetzner-api-token"

# Then in cluster.yaml, reference the env var:
hetzner_token: "${HCLOUD_TOKEN}"    # hetzner-k3s expands this at runtime

# Or inject at provision time via envsubst
envsubst < cluster-template.yaml > cluster.yaml
hetzner-k3s create --config cluster.yaml
rm cluster.yaml   # discard the rendered file with the token
```

#### 3. Generate an SSH Key Pair

hetzner-k3s SSHs into every node during provisioning. A dedicated key keeps
cluster access separate from your personal keys:

```bash
# Generate key pair (no passphrase — hetzner-k3s needs unattended access)
ssh-keygen -t ed25519 -f ~/.ssh/hetzner_k3s -N ""

# Verify both files exist
ls ~/.ssh/hetzner_k3s*
# ~/.ssh/hetzner_k3s      ← private key (never share)
# ~/.ssh/hetzner_k3s.pub  ← public key (goes in cluster config)
```

---

### K3s vs Full Kubernetes: Decision Guide

K3s is a fully CNCF-certified, lightweight Kubernetes distribution. It removes
heavyweight components that most workloads don't need.

| Feature | K3s (Hetzner) | Full K8s (DOKS) | Impact |
|---|---|---|---|
| **API compatibility** | Full K8s API | Full K8s API | None — same `kubectl` commands |
| **Helm / Ingress / CRDs** | Fully supported | Fully supported | None |
| **Container runtime** | containerd | containerd | None |
| **etcd** | Replaced by SQLite (single node) or embedded etcd (HA) | Managed etcd | None in practice |
| **Control plane overhead** | ~512 MB RAM per master | Managed (hidden) | You pay for master nodes |
| **Cloud Controller Manager** | Optional Hetzner CCM | Built-in | Must install CCM for LBs/PVs |
| **Storage** | Must install Hetzner CSI | Built-in block storage | Must install CSI for PVCs |
| **Alpha features** | Some removed | All included | Matters only for bleeding-edge features |
| **Cluster Autoscaler** | Add-on | Built-in | Extra installation step |

**When K3s limitations matter:**
- You need alpha Kubernetes features (rare — most projects never hit this)
- You want zero ops on the control plane (choose DOKS instead)

**When K3s limitations do NOT matter (most cases):**
- Running standard workloads (APIs, web apps, background jobs, databases)
- Using Helm charts, Ingress, Dapr, cert-manager — all work identically
- HA clusters with 3+ masters use embedded etcd (production-grade)

**Rule of thumb:** If a workload runs on DOKS, it runs on K3s. The 2-4x cost
savings are real with no functional difference for 95% of use cases.

---

### Cluster Configuration Templates

#### Template 1: Single-Node Learning (~$4–5/mo)

Lowest possible cost. Master also runs workloads. For learning, demos, and CI.

```yaml
# cluster-learning.yaml
hetzner_token: "${HCLOUD_TOKEN}"
cluster_name: learning
kubeconfig_path: "./kubeconfig"
k3s_version: v1.32.0+k3s1
schedule_workloads_on_masters: true    # single node must run workloads

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh:
      - 0.0.0.0/0    # restrict to your IP in any real use
    api:
      - 0.0.0.0/0

masters_pool:
  instance_type: cx22     # 2 vCPU, 4 GB RAM, ~$4/mo — recommended for learning
  instance_count: 1       # single master (no HA)
  location: fsn1

worker_node_pools: []     # no workers — master runs everything
```

> Use `cx22` (4 GB) rather than `cpx11` (2 GB) for learning — 2 GB is too tight
> for running Traefik + cert-manager + Dapr simultaneously (~500–700 MB overhead).

#### Template 2: Dev / Staging — 3-Node Cluster (~$12/mo)

1 master + 2 workers. Simulates production topology without HA cost.

```yaml
# cluster-dev.yaml
hetzner_token: "${HCLOUD_TOKEN}"
cluster_name: my-dev
kubeconfig_path: "./kubeconfig"
k3s_version: v1.32.0+k3s1

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh:
      - 0.0.0.0/0
    api:
      - 0.0.0.0/0
  private_network:
    enabled: true          # nodes communicate on private network
    subnet: 10.0.0.0/16

masters_pool:
  instance_type: cx22      # 2 vCPU, 4 GB — ~$4/mo
  instance_count: 1
  location: fsn1

worker_node_pools:
  - name: workers
    instance_type: cx22    # 2 vCPU, 4 GB — ~$4/mo each
    instance_count: 2
    location: fsn1
```

#### Template 3: Production HA — Multi-Location (~$58/mo)

3 masters across 3 locations + dedicated worker pools. Production-ready.

```yaml
# cluster-prod.yaml
hetzner_token: "${HCLOUD_TOKEN}"
cluster_name: my-prod
kubeconfig_path: "./kubeconfig-prod"
k3s_version: v1.32.0+k3s1
schedule_workloads_on_masters: false   # dedicated masters — no workloads
protect_against_deletion: true         # prevents accidental delete from console

networking:
  ssh:
    port: 22
    use_agent: false
    public_key_path: "~/.ssh/hetzner_k3s.pub"
    private_key_path: "~/.ssh/hetzner_k3s"
  allowed_networks:
    ssh:
      - <your-ip>/32      # restrict to your IP or VPN CIDR
    api:
      - <your-ip>/32
  private_network:
    enabled: true
    subnet: 10.0.0.0/16
  cni:
    enabled: true
    mode: cilium           # cilium for production (eBPF-based, network policies)

masters_pool:
  instance_type: cpx22    # 4 vCPU, 8 GB dedicated — ~$15/mo each
  instance_count: 3       # 3 masters = HA with embedded etcd
  locations:              # spread across 3 DCs for zone fault tolerance
    - fsn1                # Falkenstein, Germany
    - nbg1                # Nuremberg, Germany
    - hel1                # Helsinki, Finland

worker_node_pools:
  - name: app             # general purpose workloads
    instance_type: cpx32  # 8 vCPU, 16 GB dedicated — ~$26/mo each
    instance_count: 3
    location: fsn1
    labels:
      - key: workload
        value: app

  - name: jobs            # ARM64 for background jobs — cheapest compute
    instance_type: cax21  # 4 vCPU, 8 GB ARM64 — ~$7/mo each
    instance_count: 1
    location: fsn1
    labels:
      - key: workload
        value: background
    autoscaling:
      enabled: true
      min_instances: 1    # scale-to-zero NOT supported (min must be ≥1)
      max_instances: 10

addons:
  csi_driver:
    enabled: true         # Hetzner block storage for PersistentVolumeClaims
  cloud_controller_manager:
    enabled: true         # required for Service type: LoadBalancer to get IPs
```

---

### hetzner-k3s CLI Usage

```bash
# Provision cluster (idempotent — safe to re-run)
hetzner-k3s create --config cluster-dev.yaml

# Delete cluster (removes all servers, networks, firewalls, LBs)
hetzner-k3s delete --config cluster-dev.yaml

# Upgrade K3s version (edit k3s_version in config first, then)
hetzner-k3s upgrade --config cluster-dev.yaml

# Add nodes (increase instance_count in config, then re-run create)
# hetzner-k3s is idempotent — running create again adds nodes without destroying existing ones
hetzner-k3s create --config cluster-dev.yaml
```

**Idempotent behavior:** Running `create` on an existing cluster only adds/modifies
resources declared in the config diff. Existing nodes are not destroyed.

### Kubeconfig Setup (Connect After Provisioning)

```bash
# kubeconfig is written to the path in kubeconfig_path (e.g. ./kubeconfig)
# Merge it into your main kubeconfig:

KUBECONFIG=~/.kube/config:./kubeconfig kubectl config view \
  --merge --flatten > ~/.kube/merged
mv ~/.kube/merged ~/.kube/config

# Rename the context to follow the provider-region-name convention
kubectl config rename-context my-prod hetzner-fsn1-prod

# Verify nodes are Ready
kubectl --context=hetzner-fsn1-prod get nodes
# Expected:
# NAME                      STATUS   ROLES                  AGE   VERSION
# my-prod-master-fsn1-1     Ready    control-plane,master   2m    v1.32.x
# my-prod-master-nbg1-1     Ready    control-plane,master   2m    v1.32.x
# my-prod-master-hel1-1     Ready    control-plane,master   2m    v1.32.x
# my-prod-pool-app-1        Ready    <none>                 1m    v1.32.x
```

> Full configuration reference: `references/hetzner-k3s.md`

---

## Azure AKS Quick Reference

### Prerequisites

```bash
# Install Azure CLI
brew install azure-cli                         # macOS / Linux
# Windows: winget install Microsoft.AzureCLI

# Authenticate (opens browser)
az login

# Set subscription (if multiple)
az account list -o table
az account set --subscription "<subscription-id>"

# Verify
az account show -o table
```

### Provision Cluster

```bash
# Create resource group (required container for AKS)
az group create --name my-rg --location eastus

# ── 2-node learning cluster (~$36/mo nodes + ~$73/mo control plane = ~$110/mo) ──
az aks create \
  --resource-group my-rg \
  --name my-aks \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --location eastus

# ── Production HA with autoscaling ──
az aks create \
  --resource-group my-rg \
  --name my-aks-prod \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --enable-cluster-autoscaler \
  --min-count 2 \
  --max-count 10 \
  --enable-managed-identity \
  --network-plugin azure \
  --location eastus
```

### Connect kubeconfig

```bash
# Merge AKS credentials into ~/.kube/config
az aks get-credentials --resource-group my-rg --name my-aks

# Context is named: <cluster-name>
# Rename to convention:
kubectl config rename-context my-aks azure-eastus-my-aks

# Verify
kubectl --context=azure-eastus-my-aks get nodes
```

### Cost (2-node, 4GB RAM) and Hidden Costs

| Item | Cost/mo |
|------|---------|
| 2× Standard_B2s nodes ($0.050/hr each) | ~$73 |
| **Control plane fee** ($0.10/hr) | **~$73** |
| Load balancer (1x) | ~$18 |
| 50 GB managed disk (LRS) | ~$2 |
| **Minimum total** | **~$166** |

> **Control plane hidden cost**: AKS charges $0.10/hr ($73/mo) for the managed control plane — this is on top of node costs and applies even to 1-node dev clusters. The first cluster in a region is free (until Dec 2025 — verify current policy).

> **Egress cost**: $0.087/GB after 5GB/mo outbound. Can dominate costs for data-heavy workloads.

### Teardown

```bash
# Delete the entire resource group (removes cluster + all associated resources)
az group delete --name my-rg --yes --no-wait

# Or delete just the cluster (keeps the resource group)
az aks delete --resource-group my-rg --name my-aks --yes
```

---

## Google Cloud GKE Quick Reference

### Prerequisites

```bash
# Install Google Cloud SDK
brew install google-cloud-sdk                  # macOS / Linux
# Or: curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth login                              # browser login
gcloud auth application-default login          # for API calls from tools

# Set project
gcloud config set project <project-id>

# Enable required APIs
gcloud services enable container.googleapis.com

# Verify
gcloud config list
```

### Provision Cluster

```bash
# ── 2-node learning cluster (~$49/mo nodes + ~$73/mo control plane = ~$122/mo) ──
gcloud container clusters create my-gke \
  --num-nodes 2 \
  --machine-type e2-medium \
  --zone us-central1-a

# ── Production HA — regional cluster (nodes spread across 3 zones) ──
gcloud container clusters create my-gke-prod \
  --num-nodes 1 \
  --machine-type e2-standard-2 \
  --region us-central1 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 5 \
  --enable-ip-alias \
  --workload-pool=<project-id>.svc.id.goog   # Workload Identity
```

### Connect kubeconfig

```bash
# Fetch credentials and merge into ~/.kube/config
gcloud container clusters get-credentials my-gke --zone us-central1-a

# Context is auto-named: gke_<project>_<zone>_<cluster>
# Rename to convention:
kubectl config rename-context \
  gke_myproject_us-central1-a_my-gke \
  gke-us-central1-my-gke

# Verify
kubectl --context=gke-us-central1-my-gke get nodes
```

### Cost (2-node, 4GB RAM) and Hidden Costs

| Item | Cost/mo |
|------|---------|
| 2× e2-medium nodes ($0.034/hr each) | ~$50 |
| **Control plane fee** ($0.10/hr standard) | **~$73** |
| Load balancer (1x) | ~$18 |
| 50 GB standard persistent disk | ~$2 |
| **Minimum total** | **~$143** |

> **Autopilot mode**: GKE Autopilot removes node management — you pay per Pod resource request. Good for variable workloads; can be cheaper or more expensive depending on density. Compare before choosing.

> **Free tier**: One Autopilot or Zonal cluster free per billing account. Standard regional clusters are not free.

### Teardown

```bash
gcloud container clusters delete my-gke --zone us-central1-a --quiet
# Regional: gcloud container clusters delete my-gke-prod --region us-central1 --quiet
```

---

## AWS EKS Quick Reference

### Prerequisites

```bash
# Install AWS CLI + eksctl
brew install awscli eksctl                     # macOS / Linux

# Configure AWS credentials
aws configure
# Prompts for: AWS Access Key ID, Secret Access Key, region, output format
# Get keys: AWS Console → IAM → Users → Security credentials → Create access key

# Verify
aws sts get-caller-identity
```

> **IAM permissions required**: `eks:*`, `ec2:*`, `iam:*`, `cloudformation:*`.
> Use an IAM user with `AdministratorAccess` for initial setup; tighten for production.

### Provision Cluster

```bash
# ── 2-node learning cluster (~$61/mo nodes + ~$73/mo control plane = ~$134/mo) ──
eksctl create cluster \
  --name my-eks \
  --region us-east-1 \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 5

# ── Production HA — managed node group with autoscaling ──
eksctl create cluster \
  --name my-eks-prod \
  --region us-east-1 \
  --managed \
  --nodegroup-name app-workers \
  --node-type m5.large \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 10 \
  --asg-access \
  --full-ecr-access \
  --with-oidc              # enables IAM roles for service accounts (IRSA)
```

### Connect kubeconfig

```bash
# Update ~/.kube/config with EKS cluster credentials
aws eks update-kubeconfig --name my-eks --region us-east-1

# Context is auto-named: arn:aws:eks:<region>:<account>:cluster/<name>
# Rename to convention:
kubectl config rename-context \
  arn:aws:eks:us-east-1:123456:cluster/my-eks \
  eks-us-east1-my-eks

# Verify
kubectl --context=eks-us-east1-my-eks get nodes
```

### Cost (2-node, 4GB RAM) and Hidden Costs

| Item | Cost/mo |
|------|---------|
| 2× t3.medium nodes ($0.042/hr each) | ~$61 |
| **Control plane fee** ($0.10/hr) | **~$73** |
| Network Load Balancer (1x) | ~$20 |
| 50 GB EBS gp3 storage | ~$4 |
| NAT Gateway (if private subnets) | ~$32 |
| **Minimum total (public subnets)** | **~$158** |
| **With NAT Gateway** | **~$190** |

> **NAT Gateway surprise**: Private subnet configurations (recommended for production) require a NAT Gateway ($0.045/hr + $0.045/GB) — this can add $32–100+/mo unexpectedly.

> **eksctl uses CloudFormation**: `eksctl create cluster` takes 15–18 minutes. Monitor with `eksctl utils describe-stacks --region us-east-1 --cluster my-eks | grep Status`.

### Teardown

```bash
# Delete cluster and all associated resources (node groups, VPC, security groups)
eksctl delete cluster --name my-eks --region us-east-1
# This takes 10-15 minutes. Monitor: eksctl delete cluster --name my-eks --wait
```

---

## Civo Quick Reference

### Prerequisites

```bash
# Install Civo CLI
brew install civo/tools/civo                   # macOS / Linux
# Or binary: https://github.com/civo/cli/releases

# Authenticate (get API key from dash.civo.com → Settings → Security)
civo apikey save my-key <your-api-key>
civo apikey use my-key

# Verify
civo quota show
```

### Provision Cluster

Civo uses K3s underneath. Provisioning takes ~90 seconds — the fastest of any managed provider.

```bash
# ── 2-node learning cluster (~$20/mo — no control plane fee) ──
civo kubernetes create my-cluster \
  --nodes 2 \
  --size g4s.kube.medium \
  --region LON1

# ── Available node sizes (Civo) ──
civo kubernetes size list

# ── Production cluster with autoscaling ──
civo kubernetes create my-cluster-prod \
  --nodes 3 \
  --size g4s.kube.large \
  --region LON1 \
  --applications traefik2-nodeport

# Watch provisioning (completes in ~90 seconds)
civo kubernetes show my-cluster
```

**Civo node sizes (common):**

| Size | vCPU | RAM | Disk | $/mo |
|------|------|-----|------|------|
| `g4s.kube.small` | 1 | 2 GB | 25 GB | $5 |
| `g4s.kube.medium` | 2 | 4 GB | 50 GB | $10 |
| `g4s.kube.large` | 4 | 8 GB | 100 GB | $20 |
| `g4s.kube.xlarge` | 8 | 16 GB | 150 GB | $40 |

### Connect kubeconfig

```bash
# Save and merge kubeconfig
civo kubernetes config my-cluster --save --merge

# Context is auto-named: <cluster-name>
# Rename to convention:
kubectl config rename-context my-cluster civo-lon1-my-cluster

# Verify
kubectl --context=civo-lon1-my-cluster get nodes
```

### Cost (2-node, 4GB RAM) and Hidden Costs

| Item | Cost/mo |
|------|---------|
| 2× g4s.kube.medium nodes | ~$20 |
| **Control plane fee** | **$0** |
| Load balancer (1x) | ~$5 |
| 50 GB volume | ~$5 |
| **Minimum total** | **~$30** |

> **Bandwidth**: 1 TB/mo included per cluster, then $0.012/GB. For most workloads, bandwidth is effectively free.

> **Common pitfall**: Civo K3s uses Traefik as the default ingress — if you install your own Traefik or nginx-ingress, you'll have two ingress controllers competing. Either use Civo's built-in or disable it at cluster creation.

### Teardown

```bash
civo kubernetes delete my-cluster
# Confirm prompt → cluster deleted in ~30 seconds
```

---

## Multi-Cloud Kubeconfig Management

### Naming Convention

Use a consistent pattern: `<provider>-<region>-<cluster-name>`

```bash
# Rename contexts for clarity
kubectl config rename-context do-nyc1-my-prod do-nyc1-prod
kubectl config rename-context my-hetzner-cluster hetzner-fsn1-prod
```

### Merge Multiple Kubeconfigs

```bash
# Temporary merge (session only)
export KUBECONFIG=~/.kube/config:./kubeconfig-hetzner:./kubeconfig-do

# Permanent merge
KUBECONFIG=~/.kube/config:./kubeconfig-hetzner kubectl config view \
  --merge --flatten > ~/.kube/merged && mv ~/.kube/merged ~/.kube/config
```

### Cross-Cluster Commands

```bash
# Run against specific cluster without switching context
kubectl --context=do-nyc1-prod get pods -A
kubectl --context=hetzner-fsn1-prod get nodes

# Compare node status across clusters
for ctx in do-nyc1-prod hetzner-fsn1-prod; do
  echo "=== $ctx ==="
  kubectl --context=$ctx get nodes -o wide
done
```

> Full reference: `references/multi-cluster-kubectl.md`

---

## Services, LoadBalancer & DNS

### Service Types Comparison

```
ClusterIP (default)       NodePort                  LoadBalancer
───────────────────       ────────────              ────────────
Internal only             NodeIP:30000–32767         Dedicated external IP
No external access        Manual firewall/DNS        Cloud LB auto-provisioned
Free                      Free                       ~$12/mo (DO) ~$5.50/mo (Hetzner)
Use for: inter-service    Use for: dev/testing       Use for: production traffic
```

| Property | ClusterIP | NodePort | LoadBalancer |
|---|---|---|---|
| External access | No | Yes (port 30000–32767) | Yes (port 80/443) |
| HA routing | N/A | No — single node SPOF | Yes — LB distributes across nodes |
| TLS termination | No | No | Yes (with annotations) |
| Cloud cost | Free | Free | ~$12/mo per service (DO) |
| Best for | Internal service mesh | Dev/testing/CI | Production internet traffic |

---

### The PENDING → External IP Transition

When you apply a `LoadBalancer` service, the cloud controller manager provisions
a real load balancer. This takes 60–90 seconds:

```bash
# Apply your service
kubectl apply -f service.yaml

# Watch the EXTERNAL-IP column transition from <pending> to a real IP
kubectl get svc my-app --watch

# Output sequence:
# NAME     TYPE           CLUSTER-IP    EXTERNAL-IP   PORT(S)        AGE
# my-app   LoadBalancer   10.245.0.42   <pending>     80:31234/TCP   5s
# my-app   LoadBalancer   10.245.0.42   134.209.1.55  80:31234/TCP   72s
#                                       ^^^^^^^^^^^^ real IP appears here

# Grab the IP programmatically once ready
kubectl get svc my-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

**Stuck on `<pending>`? Diagnose by provider:**

| Cause | How to check | Fix |
|---|---|---|
| Read-only API token | `doctl account get` → check token scope | Re-auth with read+write token |
| Cloud controller not running | `kubectl get pods -n kube-system \| grep cloud` | Reinstall cloud controller |
| LB quota exhausted | Check billing dashboard | Request quota increase |
| Wrong annotations | `kubectl describe svc my-app` | Verify provider annotation keys |
| Hetzner: no CCM installed | `kubectl get pods -n kube-system` | Install hetzner-cloud-controller-manager |

---

### LoadBalancer Cost Implications

**Each `Service type: LoadBalancer` = one cloud LB = separate monthly charge, billed from creation.**

| Provider | Cost per LB | Notes |
|---|---|---|
| DigitalOcean | ~$12/mo | Billed hourly from provisioning, not from traffic |
| Hetzner | ~$5.50/mo | Auto-created by Cloud Controller Manager |

**Anti-pattern — one LB per service:**
```yaml
# $12 × 3 = $36/mo just in load balancers
kind: Service
metadata:
  name: api        # LB #1
---
kind: Service
metadata:
  name: frontend   # LB #2
---
kind: Service
metadata:
  name: admin      # LB #3
```

**Cost-controlled pattern — one LB via Ingress controller:**
```bash
# Install once → provisions exactly one LB (~$12/mo flat)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace

# Get the single LB IP
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

```yaml
# All services routed through the one LB via host rules
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

---

### DNS A-Record Configuration

After the LB IP appears, point your domain at it:

```
LB IP: 134.209.1.55

DNS records to create (at your registrar or DNS provider):
  api.example.com     A    134.209.1.55    TTL 300
  app.example.com     A    134.209.1.55    TTL 300
  *.example.com       A    134.209.1.55    TTL 300   ← wildcard (optional)
```

**Common DNS providers — where to add A records:**

| Provider | Path |
|---|---|
| Cloudflare | Dashboard → your domain → DNS → Add record |
| DigitalOcean DNS | Networking → Domains → your domain → Add record |
| Route53 | Hosted zones → your domain → Create record |
| Namecheap | Domain list → Manage → Advanced DNS |

**Propagation timing:** TTL 300 = 5-minute propagation. Use TTL 60 during initial
setup, bump to 3600+ once stable.

---

### Wildcard DNS for Testing (No Domain Required)

Use free wildcard DNS services that resolve any IP embedded in the hostname.
No registration, no DNS changes needed — works instantly.

| Service | Pattern | Example |
|---|---|---|
| **nip.io** | `<anything>.<ip>.nip.io` | `myapp.134.209.1.55.nip.io` |
| **sslip.io** | `<anything>.<ip>.sslip.io` | `myapp.134.209.1.55.sslip.io` |

```bash
# Get your LB IP
LB_IP=$(kubectl get svc my-app -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Use immediately in Ingress — no DNS setup required
echo "Test URL: http://myapp.${LB_IP}.nip.io"

# Example Ingress using nip.io
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: myapp.${LB_IP}.nip.io
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-app
            port:
              number: 80
EOF
```

> nip.io and sslip.io are production-maintained services. nip.io is backed by
> PowerDNS; sslip.io is backed by multiple resolvers. Both are appropriate for
> staging environments but should not be used for real production traffic.

---

### DNS Verification

After setting records, verify propagation before troubleshooting your app:

```bash
# Basic A-record lookup
dig api.example.com A +short
# Expected: 134.209.1.55

# Check with nslookup (cross-platform)
nslookup api.example.com
# Expected:
# Server:   8.8.8.8
# Name:     api.example.com
# Address:  134.209.1.55

# Check against a specific nameserver (bypass local cache)
dig @8.8.8.8 api.example.com A +short    # Google DNS
dig @1.1.1.1 api.example.com A +short    # Cloudflare DNS

# Check wildcard DNS service resolves correctly
dig myapp.134.209.1.55.nip.io A +short
# Expected: 134.209.1.55

# Trace full DNS resolution path (useful for debugging)
dig api.example.com +trace

# Check TTL remaining (tells you how long cache is held)
dig api.example.com A +ttl

# HTTP-level check once DNS resolves
curl -v http://api.example.com
curl -I http://api.example.com          # headers only
```

**DNS propagation not completing:**
```bash
# Verify the A record exists at your authoritative nameserver
dig api.example.com NS +short           # find your authoritative NS
dig @<authoritative-ns> api.example.com A +short   # check there directly

# If the authoritative NS has it but public DNS doesn't → wait for TTL
# If the authoritative NS doesn't have it → check your registrar config
```

---

## Full Stack Deployment Patterns

### DOKS Stack: cert-manager + Traefik + Dapr

#### Deployment sequence and why order matters

```
1. cert-manager   ← must exist before any TLS resources are created
2. ClusterIssuers ← must exist before Ingress objects request certs
3. Traefik        ← must exist before Ingress rules are evaluated
4. Dapr           ← independent; install before app namespaces
5. Application    ← annotated Deployment + ClusterIP Service
6. Ingress        ← TLS Ingress referencing ClusterIssuer
```

Installing in any other order causes:
- Ingress objects created before cert-manager → certificate never issued
- Ingress rules active before Traefik → traffic silently dropped
- Dapr annotations on pods before Dapr is installed → pods crash-loop

---

#### Step 1: cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io --force-update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version v1.16.2 \
  --set crds.enabled=true \
  --wait                  # blocks until all cert-manager pods are Ready

# Verify
kubectl get pods -n cert-manager
# Expected: cert-manager, cert-manager-cainjector, cert-manager-webhook → Running
```

---

#### Step 2: ClusterIssuers (Let's Encrypt)

Always create staging first — LE prod has strict rate limits (5 certs/domain/week).

```yaml
# cluster-issuers.yaml
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-key
    solvers:
    - http01:
        ingress:
          ingressClassName: traefik   # must match the Ingress controller below
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          ingressClassName: traefik
```

```bash
kubectl apply -f cluster-issuers.yaml

# Verify issuers are ready
kubectl get clusterissuer
# Expected:
# NAME                   READY   AGE
# letsencrypt-staging    True    10s
# letsencrypt-prod       True    10s
```

> If `READY` is `False`, check: `kubectl describe clusterissuer letsencrypt-staging`
> Common cause: incorrect email or ACME server URL.

---

#### Step 3: Traefik (single LoadBalancer entry point)

```bash
helm repo add traefik https://traefik.github.io/charts --force-update

helm upgrade --install traefik traefik/traefik \
  --namespace traefik --create-namespace \
  --version 32.1.1 \
  --set service.type=LoadBalancer \
  --set ingressClass.enabled=true \
  --set ingressClass.isDefaultClass=true \
  --set logs.general.level=INFO \
  --wait

# Wait for LoadBalancer IP (60–90s — PENDING → real IP)
kubectl get svc -n traefik traefik --watch

# Capture IP for DNS / nip.io use
TRAEFIK_IP=$(kubectl get svc -n traefik traefik \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "Traefik LB IP: $TRAEFIK_IP"

# Verify ingressclass registered
kubectl get ingressclass
# Expected: traefik   traefik.io/ingress-traefik   <none>   true
```

---

#### Step 4: Dapr

```bash
helm repo add dapr https://dapr.github.io/helm-charts --force-update

helm upgrade --install dapr dapr/dapr \
  --namespace dapr-system --create-namespace \
  --version 1.14.4 \
  --set global.mtls.enabled=true \
  --wait

# Wait for all Dapr control plane pods
kubectl wait --for=condition=Ready pods \
  -l app.kubernetes.io/part-of=dapr \
  -n dapr-system \
  --timeout=120s

# Verify
kubectl get pods -n dapr-system
# Expected: dapr-operator, dapr-sentry, dapr-placement-server,
#           dapr-sidecar-injector → all Running
```

---

#### Step 5: Application Deployment

Label the namespace so Dapr can inject sidecars automatically:

```bash
kubectl create namespace my-app
kubectl label namespace my-app dapr-enabled=true
```

```yaml
# app-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
      annotations:
        dapr.io/enabled:    "true"      # triggers sidecar injection
        dapr.io/app-id:     "my-app"    # Dapr service discovery ID
        dapr.io/app-port:   "8080"      # port Dapr proxies to your app
    spec:
      containers:
      - name: app
        image: your-registry/your-image:tag
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-app
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP   # ClusterIP — Traefik handles all external routing
```

```bash
kubectl apply -f app-deployment.yaml

# Confirm Dapr sidecar injected (pod should have 2 containers: app + daprd)
kubectl get pods -n my-app
# Expected: my-app-xxxx   2/2   Running
```

---

#### Step 6: TLS Ingress via Traefik + cert-manager

```yaml
# app-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app-ingress
  namespace: my-app
  annotations:
    # Which ClusterIssuer to use — start with staging, swap to prod after verification
    cert-manager.io/cluster-issuer: letsencrypt-staging

    # Traefik-specific: enable both HTTP and HTTPS entrypoints
    traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
  - hosts:
    - app.example.com
    secretName: my-app-tls   # cert-manager creates this Secret automatically
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-app
            port:
              number: 80
```

```bash
kubectl apply -f app-ingress.yaml

# Watch cert-manager issue the certificate (30–120s)
kubectl get certificate -n my-app --watch
# Expected:
# NAME         READY   SECRET       AGE
# my-app-tls   True    my-app-tls   45s

# If READY stays False:
kubectl describe certificate my-app-tls -n my-app
kubectl describe certificaterequest -n my-app
# Look for: "Waiting for HTTP-01 challenge" → DNS not resolving yet
# Look for: "Rate limit" → switch to staging issuer
```

---

#### Promote to Production TLS

Once the staging cert works and HTTPS is confirmed:

```bash
# Swap to the prod ClusterIssuer (deletes old staging cert and requests a real one)
kubectl annotate ingress my-app-ingress -n my-app \
  cert-manager.io/cluster-issuer=letsencrypt-prod --overwrite

# Delete the old staging secret to force cert-manager to reissue
kubectl delete secret my-app-tls -n my-app

# Watch new prod cert issue
kubectl get certificate -n my-app --watch
```

---

#### Stack Verification Checklist

```bash
# 1. cert-manager control plane
kubectl get pods -n cert-manager

# 2. ClusterIssuers ready
kubectl get clusterissuer

# 3. Traefik running, LB IP assigned
kubectl get pods -n traefik
kubectl get svc  -n traefik traefik

# 4. Dapr control plane
kubectl get pods -n dapr-system

# 5. App pod has 2 containers (app + daprd sidecar)
kubectl get pods -n my-app

# 6. Certificate issued
kubectl get certificate -n my-app

# 7. TLS end-to-end
curl -v https://app.example.com
# Look for: SSL certificate verify ok
#           HTTP/2 200
```

---

#### Common Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Certificate stuck `READY=False` | DNS A record not propagated | `dig app.example.com` — wait for IP to resolve |
| Certificate stuck `READY=False` | Traefik not installed yet | Install Traefik before creating Ingress |
| Pod stuck `0/2 Pending` with Dapr | Dapr sidecar injector not running | `kubectl get pods -n dapr-system` — check injector |
| 404 from Traefik | Ingress host mismatch | `kubectl describe ingress my-app-ingress -n my-app` |
| `ERR_CERT_AUTHORITY_INVALID` | Staging cert in browser | Expected — swap to `letsencrypt-prod` issuer |
| ACME challenge fails | Port 80 blocked | Ensure Traefik LB allows inbound port 80 (HTTP-01 needs it) |

---

## Secrets Management

### The Three-Layer Configuration Hierarchy

Load configuration from least-sensitive to most-sensitive. Each layer overrides the previous:

```
Layer 1: Deployment defaults (baked into image or spec)
   ↓ overridden by
Layer 2: ConfigMap (non-sensitive config — safe to commit to Git)
   ↓ overridden by
Layer 3: Secret (sensitive values — NEVER commit to Git)
```

This lets you define safe defaults in code, tune per-environment in ConfigMaps,
and inject credentials via Secrets — all without rebuilding the image.

---

### Layer 1: ConfigMap (Non-Sensitive Configuration)

```bash
# From literal values
kubectl create configmap my-app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=PORT=8080 \
  --from-literal=ENVIRONMENT=production \
  --namespace my-app

# From a config file (e.g. app.properties, nginx.conf)
kubectl create configmap my-app-config \
  --from-file=app.properties \
  --namespace my-app

# Verify
kubectl get configmap my-app-config -n my-app -o yaml
```

```yaml
# configmap.yaml — safe to commit to Git
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-app-config
  namespace: my-app
data:
  LOG_LEVEL: "info"
  PORT: "8080"
  ENVIRONMENT: "production"
  DB_HOST: "postgres.my-app.svc.cluster.local"   # internal service DNS — not sensitive
  DB_PORT: "5432"
```

---

### Layer 2: Application Secrets (Sensitive Values)

```bash
# From literal values — one-liner
kubectl create secret generic my-app-secrets \
  --from-literal=DATABASE_PASSWORD="s3cr3t-db-pass" \
  --from-literal=API_KEY="sk-prod-xxxx" \
  --from-literal=JWT_SECRET="super-secret-jwt-key" \
  --namespace my-app

# From a .env file (keep file in .gitignore — never commit it)
kubectl create secret generic my-app-secrets \
  --from-env-file=.env.production \
  --namespace my-app

# Verify (values shown as base64 — never plain text)
kubectl get secret my-app-secrets -n my-app
kubectl describe secret my-app-secrets -n my-app

# Decode a specific value to confirm it's correct
kubectl get secret my-app-secrets -n my-app \
  -o jsonpath='{.data.API_KEY}' | base64 --decode
```

> **NEVER** put secrets in ConfigMaps — ConfigMaps are not encrypted at rest
> by default and are readable by anyone with `kubectl get configmap` access.

---

### Layer 3: Image Pull Secrets (Private Registry Access)

#### Option A: DigitalOcean Container Registry (zero-config)

```bash
# DOKS-native: injects credentials into every namespace automatically
doctl kubernetes cluster registry add my-prod

# Verify the secret was created in default namespace
kubectl get secret -n default | grep registry
# Also check your app namespace
kubectl get secret -n my-app | grep registry
```

No `imagePullSecrets` needed in the Deployment spec when using this method.

#### Option B: Any Private Registry (Docker Hub, GHCR, custom)

```bash
# Docker Hub
kubectl create secret docker-registry regcred \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=your-dockerhub-username \
  --docker-password=your-access-token \
  --docker-email=you@example.com \
  --namespace my-app

# GitHub Container Registry (GHCR)
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=your-github-username \
  --docker-password=ghp_your_pat_token \
  --docker-email=you@example.com \
  --namespace my-app

# Custom / self-hosted registry
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=you@example.com \
  --namespace my-app

# Verify
kubectl get secret regcred -n my-app
kubectl get secret regcred -n my-app -o jsonpath='{.data.\.dockerconfigjson}' \
  | base64 --decode | jq .   # inspect decoded auth config
```

---

### Wiring All Three Layers into a Deployment

```yaml
# app-deployment.yaml — full three-layer configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      # ── Layer 3: Image pull secret (private registry) ──────────────────
      imagePullSecrets:
      - name: regcred               # COMMON MISTAKE: forgetting this causes
                                    # ErrImagePull / ImagePullBackOff on private images

      containers:
      - name: app
        image: ghcr.io/your-org/your-image:tag

        # ── Layer 2: Secrets (injected as env vars) ─────────────────────
        envFrom:
        - secretRef:
            name: my-app-secrets    # injects ALL keys: DATABASE_PASSWORD, API_KEY, etc.

        # ── Layer 1: ConfigMap (non-sensitive config) ────────────────────
        - configMapRef:
            name: my-app-config     # injects ALL keys: LOG_LEVEL, PORT, etc.

        # ── Override: inject a single secret key by name ─────────────────
        env:
        - name: DB_PASSWORD         # explicit single-key injection
          valueFrom:
            secretKeyRef:
              name: my-app-secrets
              key: DATABASE_PASSWORD
        - name: APP_ENV
          valueFrom:
            configMapKeyRef:
              name: my-app-config
              key: ENVIRONMENT

        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
```

---

### Verification: Confirm Variables Inside the Pod

After deploying, exec into the pod to confirm all three layers are injected correctly:

```bash
# Get a pod name
POD=$(kubectl get pods -n my-app -l app=my-app -o jsonpath='{.items[0].metadata.name}')

# Check a secret value is present (don't log this in CI)
kubectl exec -n my-app "$POD" -- printenv API_KEY
# Expected: sk-prod-xxxx

# Check a configmap value
kubectl exec -n my-app "$POD" -- printenv LOG_LEVEL
# Expected: info

# List all env vars (confirm no missing vars)
kubectl exec -n my-app "$POD" -- printenv | sort

# Check image pull worked (pod Running, not ErrImagePull)
kubectl get pods -n my-app
# Expected: my-app-xxxx   1/1   Running  (or 2/2 with Dapr)
```

---

### Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Forgot `imagePullSecrets` in Deployment spec | `ErrImagePull` / `ImagePullBackOff` | Add `imagePullSecrets: [{name: regcred}]` under `spec` |
| Secret in wrong namespace | Pod starts but env var is empty | Secret and Pod must be in the **same namespace** |
| ConfigMap value used for a secret | Secret readable by any cluster user | Move sensitive values to `Secret`, not `ConfigMap` |
| Secret created with wrong key name | Pod env var missing at runtime | `kubectl describe secret` to list actual keys, fix `secretKeyRef.key` |
| `.env` file committed to Git | Credential leak | Add `.env*` to `.gitignore`; rotate all exposed credentials immediately |
| Used `envFrom` + duplicate key in `env` | Unpredictable value | `env` keys take precedence over `envFrom` — remove the duplicate |
| Deleted secret without updating Deployment | `CreateContainerConfigError` | Recreate secret before or alongside deleting the old one |

---

### GitOps-Safe Secret Patterns

Never commit plain `Secret` YAML. Use one of these instead:

```bash
# ── Option 1: Sealed Secrets (encrypt-in-cluster, commit the encrypted output) ──
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system --wait

# Install CLI
brew install kubeseal   # macOS / Linux via Homebrew

# Seal a secret — the output file IS safe to commit
kubectl create secret generic my-app-secrets \
  --from-literal=API_KEY=sk-prod-xxxx \
  --namespace my-app \
  --dry-run=client -o yaml \
  | kubeseal --format yaml > sealed-my-app-secrets.yaml

git add sealed-my-app-secrets.yaml   # safe to commit
kubectl apply -f sealed-my-app-secrets.yaml

# ── Option 2: External Secrets Operator (sync from DO/AWS/Vault) ──────────────
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace --wait

# Then create an ExternalSecret that pulls from your secrets provider
# (DigitalOcean does not have a native secrets manager — use AWS SSM or Vault)
```

---

## Production Readiness Verification

**Deployment is NOT complete until all applicable checks pass.**

Run this checklist after every deployment, on every cloud provider. A single failing check means the cluster is not production-ready.

---

### Checklist Summary Table

| # | Check | Command | Pass Criteria |
|---|-------|---------|---------------|
| 1 | Health endpoint | `curl -sf https://<host>/health` | HTTP 200 within 2s |
| 2 | Resource requests & limits | `kubectl get pod -o json \| jq` | All containers have requests + limits |
| 3 | Replica count | `kubectl get deploy` | `READY >= 2` |
| 4 | Liveness probe | `kubectl get deploy -o jsonpath` | `livenessProbe` defined |
| 5 | Readiness probe | `kubectl get deploy -o jsonpath` | `readinessProbe` defined |
| 6 | TLS certificate | `kubectl get certificate` | `READY=True`, prod issuer |
| 7 | Secrets not plain env | `kubectl get deploy -o json \| jq` | No `value:` for sensitive keys |
| 8 | PodDisruptionBudget | `kubectl get pdb` | PDB exists, `minAvailable >= 1` |
| 9 | HPA configured | `kubectl get hpa` | HPA exists, `MINPODS >= 2` |
| 10 | Cost estimate documented | Manual review | Monthly estimate on file |

---

### Check 1: Health Endpoint Returns HTTP 200

```bash
# Get the LB IP or ingress hostname
LB_IP=$(kubectl get svc -n <namespace> <svc-name> \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Test via raw IP
curl -sf http://${LB_IP}/health -o /dev/null -w "%{http_code}" && echo " PASS"

# Test via domain (TLS)
curl -sf https://app.example.com/health -o /dev/null -w "%{http_code}"
# Expected: 200
```

**PASS:** `200` returned within 2s
**FAIL symptoms:** `000` = connection refused; `502` = no healthy backend; `503` = app not ready; timeout

**Fix — 502 Bad Gateway (service routing broken):**
```bash
# Check that service Endpoints are populated (not empty)
kubectl get endpoints <svc-name> -n <namespace>
# If empty → label mismatch. Verify pod labels match service selector:
kubectl get pods -n <namespace> --show-labels
kubectl describe svc <svc-name> -n <namespace>   # check "Selector:"
```

**Fix — app has no `/health` route (add one):**
```yaml
# Wire existing route as health via readiness probe (see Check 5)
# Minimal health handler in FastAPI:   @app.get("/health") → return {"status": "ok"}
# Minimal health handler in Express:   app.get('/health', (_, res) => res.json({ status: 'ok' }))
```

---

### Check 2: Resource Requests & Limits Configured

```bash
# List containers missing requests or limits
kubectl get pods -n <namespace> -o json | \
  jq -r '.items[].spec.containers[] |
    select(.resources.requests == null or .resources.limits == null) |
    .name'
# Expected: empty output

# Inspect actual values per container
kubectl describe pod <pod-name> -n <namespace> | grep -A 6 "Limits:"
```

**PASS:** Every container has `requests.cpu`, `requests.memory`, `limits.cpu`, `limits.memory`
**FAIL symptoms:** Pod OOMKilled under load; CPU throttled; evicted by kubelet during node pressure; noisy-neighbour starvation

**YAML fix — add resource block:**
```yaml
resources:
  requests:
    cpu: 50m          # baseline reservation — what K8s guarantees on the node
    memory: 64Mi
  limits:
    cpu: 500m         # hard cap — pod throttled if exceeded (not killed)
    memory: 256Mi     # hard cap — pod OOMKilled if exceeded
```

> Measure with `kubectl top pods -n <namespace>` to baseline your `requests`.
> Set `limits` at 4–5× `requests` to allow burst without wasting reserved capacity.

---

### Check 3: Replica Count >= 2

```bash
kubectl get deployment -n <namespace>
# Expected:
# NAME     READY   UP-TO-DATE   AVAILABLE
# my-app   2/2     2            2

# Check exact spec value
kubectl get deployment my-app -n <namespace> \
  -o jsonpath='{.spec.replicas}'
# Expected: 2 or higher
```

**PASS:** `spec.replicas >= 2` AND `AVAILABLE == READY == spec.replicas`
**FAIL symptoms:** Single pod = single point of failure; one node drain or pod crash → full outage

**YAML fix:**
```yaml
spec:
  replicas: 2    # minimum for production; 3 recommended for rolling-update safety
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0    # never remove a pod before a new one is Ready
      maxSurge: 1          # allow one extra pod during the update
```

---

### Check 4: Liveness Probe Exists

```bash
kubectl get deployment my-app -n <namespace> \
  -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}'
# Expected: non-empty JSON — e.g. {"httpGet":{"path":"/health",...}...}
# Fail: empty string
```

**PASS:** `livenessProbe` defined with `initialDelaySeconds` >= app startup time
**FAIL symptoms:** Deadlocked or hung pod never restarted; pod shows `Running` but returns 5xx; only manual `kubectl delete pod` fixes it

**YAML fix:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30    # give the app time to start before first check
  periodSeconds: 10
  failureThreshold: 3        # restart pod after 3 consecutive failures
  timeoutSeconds: 5
```

---

### Check 5: Readiness Probe Exists

```bash
kubectl get deployment my-app -n <namespace> \
  -o jsonpath='{.spec.template.spec.containers[0].readinessProbe}'
# Expected: non-empty JSON
```

**PASS:** `readinessProbe` defined; pod only receives traffic when probe passes
**FAIL symptoms:** `502` errors during startup and rolling updates; traffic routed to pod before it has loaded config/warmed cache

**YAML fix:**
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10    # shorter than liveness — detect readiness fast
  periodSeconds: 5
  failureThreshold: 3        # remove from service rotation after 3 failures
  timeoutSeconds: 3
```

> **Liveness** = "is the app alive?" → restart if not
> **Readiness** = "is the app ready for traffic?" → remove from LB if not
> Both are required for zero-downtime rolling updates.

---

### Check 6: TLS Certificate Status

```bash
kubectl get certificate -n <namespace>
# Expected:
# NAME         READY   SECRET       AGE
# my-app-tls   True    my-app-tls   10m

# Verify it's the prod issuer (not staging)
kubectl get certificate my-app-tls -n <namespace> \
  -o jsonpath='{.spec.issuerRef.name}'
# Expected: letsencrypt-prod  (NOT letsencrypt-staging)

# Verify TLS handshake end-to-end
curl -v https://app.example.com 2>&1 | grep -E "issuer|SSL|expire"
```

**PASS:** `READY=True`; issuer is `letsencrypt-prod`; expiry > 30 days
**FAIL symptoms:** `ERR_CERT_AUTHORITY_INVALID` = staging cert in browser; browser padlock missing; HTTPS fails

**Fix — still on staging cert:**
```bash
kubectl annotate ingress my-app-ingress -n <namespace> \
  cert-manager.io/cluster-issuer=letsencrypt-prod --overwrite
kubectl delete secret my-app-tls -n <namespace>    # force cert-manager to reissue
kubectl get certificate -n <namespace> --watch
```

**Fix — ACME challenge stuck (DNS not resolving):**
```bash
kubectl get challenge -n <namespace>               # challenge object visible?
dig app.example.com A +short                       # must return LB IP
# Port 80 must be open inbound — HTTP-01 challenge requires it
```

---

### Check 7: Secrets Not Exposed as Plain Env Values

```bash
# List all plain-value env vars across containers
kubectl get deployment my-app -n <namespace> -o json | \
  jq -r '.spec.template.spec.containers[].env[]? |
    select(.value != null) |
    "\(.name)=\(.value)"'
# Review output — flag anything containing: PASSWORD, KEY, SECRET, TOKEN, DSN, CREDENTIALS
# Acceptable plain values: PORT, LOG_LEVEL, APP_NAME, ENV
```

**PASS:** Sensitive keys use `secretKeyRef` or `envFrom.secretRef`, NOT `value:`
**FAIL symptoms:** Credential visible in `kubectl get deployment -o yaml`; secret leaks to CI logs; rotation requires full redeploy

**YAML fix — move to secretRef:**
```yaml
# BEFORE (insecure)
env:
- name: DATABASE_PASSWORD
  value: "s3cr3t"

# AFTER (secure)
env:
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: my-app-secrets
      key: DATABASE_PASSWORD
```

---

### Check 8: PodDisruptionBudget Exists

```bash
kubectl get pdb -n <namespace>
# Expected:
# NAME        MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS
# my-app-pdb  1               N/A               1

kubectl describe pdb my-app-pdb -n <namespace>
```

**PASS:** PDB exists; `ALLOWED DISRUPTIONS >= 1`; `minAvailable >= 1`
**FAIL symptoms:** Node drain during Kubernetes version upgrade evicts all pods simultaneously → outage; cloud provider rolling node replacements cause downtime

**YAML fix — create PDB:**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-app-pdb
  namespace: <namespace>
spec:
  minAvailable: 1         # always keep at least 1 pod running during voluntary disruptions
  selector:
    matchLabels:
      app: my-app         # must match your Deployment's pod template labels
```

```bash
kubectl apply -f pdb.yaml
```

---

### Check 9: HPA Configuration (Traffic-Serving Services)

*Skip if the service has no external traffic (e.g. pure background workers, cron jobs).*

```bash
kubectl get hpa -n <namespace>
# Expected:
# NAME        REFERENCE             TARGETS    MINPODS   MAXPODS   REPLICAS
# my-app-hpa  Deployment/my-app    32%/60%    2         10        3

kubectl describe hpa my-app-hpa -n <namespace>
# Look for: "AbleToScale: True", "ScalingActive: True"
# Warning: "unable to get metrics" → metrics-server not installed
```

**PASS:** HPA exists; `MINPODS >= 2`; `MAXPODS` bounded; targets show real metrics (not `<unknown>`)
**FAIL symptoms:** No autoscaling → manual intervention during traffic spikes; over-provisioned at off-peak → wasted spend

**YAML fix — create HPA:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-app-hpa
  namespace: <namespace>
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60    # scale up when avg CPU > 60%
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0     # react immediately to spikes
    scaleDown:
      stabilizationWindowSeconds: 300   # wait 5 min before scaling down
```

> **Hetzner K3s only:** metrics-server is not pre-installed.
> Install it: `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`
> Then verify: `kubectl top pods -n <namespace>`

---

### Check 10: Monthly Cost Estimate Documented

```bash
# No automated check — requires human review before go-live

# DigitalOcean formula:
#   node_count × node_$/mo + LB_count × $12 + storage_GB × $0.10

# Hetzner formula:
#   master_count × master_$/mo + worker_count × worker_$/mo
#   + LB_count × $6 + storage_GB × $0.05
```

**PASS:** A README section, cluster config comment, or ticket contains the estimated monthly total
**FAIL:** No cost estimate → surprise cloud bills; no budget sign-off

**Template — add to cluster config or README:**
```
# Monthly Cost Estimate — my-app (prod)  — 2025-01-15
#
# Cluster (Hetzner):
#   3× CPX22 masters ($15 × 3)         = $45
#   3× CPX32 workers ($26 × 3)         = $78
#   1× Hetzner load balancer           = $6
#   50 GB block storage (2 PVCs)       = $3
# ──────────────────────────────────────────
# Total:                               ~ $132/mo
```

---

## Conditional Checks

### C1: PostgreSQL Connectivity & Readiness

*Run if your application connects to a PostgreSQL database.*

```bash
APP_POD=$(kubectl get pods -n <namespace> -l app=my-app \
  -o jsonpath='{.items[0].metadata.name}')

# 1. Verify DB is reachable on port 5432
kubectl exec -n <namespace> "$APP_POD" -- \
  nc -zv postgres.my-app.svc.cluster.local 5432
# Expected: Connection succeeded!

# 2. Verify DB pod is Running
kubectl get pods -n <namespace> -l app=postgres
# Expected: postgres-0   1/1   Running

# 3. Verify DB Service has Endpoints (not empty)
kubectl get endpoints postgres -n <namespace>
# Expected: postgres   10.244.x.x:5432

# 4. Test authentication
kubectl exec -n <namespace> "$APP_POD" -- \
  psql "$DATABASE_URL" -c "SELECT 1;"
# Expected: ?column? = 1
```

**PASS:** Pod reaches DB on 5432; `SELECT 1` returns; DB pod `1/1 Running`
**FAIL symptoms:**

| Error | Root Cause | Fix |
|---|---|---|
| `Connection refused` | Wrong host/port or DB not running | Check `kubectl get svc postgres` — port correct? |
| `Could not translate host name` | Wrong service name or wrong namespace | Use FQDN: `<svc>.<ns>.svc.cluster.local` |
| `password authentication failed` | Wrong credentials in Secret | `kubectl exec ... -- printenv DATABASE_URL` to confirm |
| `Connection timed out` | NetworkPolicy blocking | Add ingress rule allowing port 5432 from app pods |

---

### C2: External API Connectivity & Rate Limits

*Run if your application calls external APIs (OpenAI, Stripe, Twilio, etc.).*

```bash
APP_POD=$(kubectl get pods -n <namespace> -l app=my-app \
  -o jsonpath='{.items[0].metadata.name}')

# 1. DNS resolution (basic egress test)
kubectl exec -n <namespace> "$APP_POD" -- \
  nslookup api.openai.com
# Expected: Address resolved

# 2. HTTPS connectivity
kubectl exec -n <namespace> "$APP_POD" -- \
  curl -sf https://api.openai.com -o /dev/null -w "%{http_code}"
# Expected: 200 or 401 (auth required but connection works)

# 3. Authenticated call + rate limit headers
kubectl exec -n <namespace> "$APP_POD" -- \
  curl -sI https://api.openai.com/v1/models \
  -H "Authorization: Bearer $(printenv OPENAI_API_KEY)" | \
  grep -i "x-ratelimit"
# Look for: x-ratelimit-remaining-requests > 0
```

**PASS:** DNS resolves; HTTPS connects; API returns 200 (or 401 for auth-protected endpoints); rate limit remaining > 0
**FAIL symptoms:**

| Error | Root Cause | Fix |
|---|---|---|
| `Could not resolve host` | DNS blocked or no egress | Add egress NetworkPolicy for port 443 + port 53 |
| `403` | Wrong or expired API key | Verify key in Secret: `kubectl exec ... -- printenv OPENAI_API_KEY` |
| `429 Too Many Requests` | Rate limit exhausted | Add exponential backoff in code; request quota increase |
| `SSL handshake failed` | Egress TLS inspection proxy | Check if cluster has an egress proxy — may need CA bundle |

**Fix — egress NetworkPolicy blocking outbound HTTPS:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-external
  namespace: <namespace>
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
  - Egress
  egress:
  - ports:
    - port: 443
      protocol: TCP
  - ports:
    - port: 53
      protocol: UDP     # required for DNS
```

---

### C3: Load Testing & Scaling Validation (100+ RPS)

*Run if the service must handle sustained 100+ requests per second.*

```bash
# Option A: hey (simple, single binary)
# Install: go install github.com/rakyll/hey@latest
hey -n 10000 -c 100 -q 100 https://app.example.com/health
# Flags: -n total requests, -c concurrency, -q RPS cap
# Expected: 0.00% error rate, p99 < 500ms

# Option B: k6 (scripted, threshold assertions)
k6 run - <<'EOF'
import http from 'k6/http';
import { check } from 'k6';
export const options = {
  vus: 100,
  duration: '60s',
  thresholds: {
    http_req_failed:   ['rate<0.01'],    // < 1% errors
    http_req_duration: ['p(99)<500'],    // p99 < 500ms
  },
};
export default function () {
  const res = http.get('https://app.example.com/health');
  check(res, { 'status 200': (r) => r.status === 200 });
}
EOF

# Watch HPA react during test (separate terminal)
kubectl get hpa -n <namespace> --watch

# Watch pod count change
kubectl get pods -n <namespace> --watch

# Monitor resource usage at peak
kubectl top pods -n <namespace>
kubectl top nodes
```

**PASS:** Error rate < 1%; p99 < 500ms at target RPS; HPA scales pods up during load; pods scale back down after load drops
**FAIL symptoms:**

| Symptom | Root Cause | Fix |
|---|---|---|
| Rising error rate | Too few replicas or low resource limits | Increase `minReplicas`; raise `limits.cpu` |
| p99 > 1s | App too slow or DB bottleneck | Profile app; add DB connection pooling |
| HPA not scaling | Metrics-server missing or CPU target too high | Install metrics-server; lower `averageUtilization` target |
| Pods OOMKilled under load | Memory limit too low | Increase `limits.memory`; check for memory leaks |
| HPA scales but pods `Pending` | Node pool at capacity | Scale node pool or enable cluster autoscaler |

**Fix — HPA scales too slowly:**
```yaml
spec:
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0      # react to spikes immediately
      policies:
      - type: Percent
        value: 100                       # allow doubling pods per interval
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300    # wait 5 min before reducing pods
```

---

## Failure Diagnosis Playbook

Diagnose failures in this priority order. Fix Priority 1 before investigating Priority 2.

### Priority 1: Pod Not Running

```bash
# Step 1: Identify failing pods
kubectl get pods -n <namespace>
# Status to investigate: Pending, CrashLoopBackOff, Error, OOMKilled, ErrImagePull

# Step 2: Get root cause from events
kubectl describe pod <pod-name> -n <namespace>
# Look at "Events:" section at the bottom

# Step 3: Get application logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous   # logs from last crash
```

| Pod Status | Root Cause | Fix |
|---|---|---|
| `Pending` | Insufficient node resources | `kubectl describe pod` → `Insufficient cpu/memory` → scale node pool |
| `ErrImagePull` | Wrong image tag or missing imagePullSecrets | Fix image reference; add `imagePullSecrets` |
| `CrashLoopBackOff` | App crashes on startup | `kubectl logs --previous`; check env vars / DB connectivity |
| `OOMKilled` | Memory limit too low | Increase `limits.memory`; check for leaks with `kubectl top pod` |
| `CreateContainerConfigError` | Missing Secret or ConfigMap | Verify Secret/ConfigMap exists in same namespace |

---

### Priority 2: Pod Running But Not Reachable

```bash
# Step 1: Check service has Endpoints populated
kubectl get endpoints <svc-name> -n <namespace>
# Empty → label mismatch between Service selector and Pod labels

# Step 2: Confirm labels
kubectl get pods -n <namespace> --show-labels
kubectl describe svc <svc-name> -n <namespace>   # check "Selector:"

# Step 3: Bypass Service — test pod directly
kubectl port-forward pod/<pod-name> 8080:8080 -n <namespace>
curl localhost:8080/health
# If this works → Service or Ingress misconfigured, not the app
```

---

### Priority 3: TLS / Certificate Issues

```bash
# Check cert-manager pipeline
kubectl get certificate -n <namespace>
kubectl describe certificate my-app-tls -n <namespace>
# Look for "Reason:" and "Message:" in Status

# Check ACME challenge objects
kubectl get challenge -n <namespace>
# Challenge stuck → port 80 blocked or DNS not resolving

# Force reissue
kubectl delete secret <tls-secret-name> -n <namespace>
# cert-manager automatically reissues when the Secret is deleted
kubectl get certificate -n <namespace> --watch
```

---

### Priority 4: Performance & Scaling Issues

```bash
# Verify metrics-server is working (required for HPA)
kubectl top pods -n <namespace>
kubectl top nodes
# If this fails → install metrics-server (Hetzner K3s)

# Check HPA status
kubectl describe hpa <hpa-name> -n <namespace>
# "unable to get metrics" → metrics-server missing
# "DesiredReplicas" not changing → check stabilizationWindowSeconds

# Install metrics-server on Hetzner K3s
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

---

### Deployment Gate

A deployment is **NOT production-ready** if any applicable box is unchecked:

```
Core checks:
  ☐ Check 1  PASS — health endpoint returns 200
  ☐ Check 2  PASS — all containers have resource requests + limits
  ☐ Check 3  PASS — replicas >= 2
  ☐ Check 4  PASS — liveness probe defined
  ☐ Check 5  PASS — readiness probe defined
  ☐ Check 6  PASS — TLS cert READY=True with letsencrypt-prod
  ☐ Check 7  PASS — no sensitive values in plain env
  ☐ Check 8  PASS — PodDisruptionBudget exists
  ☐ Check 9  PASS — HPA configured (traffic-serving services)
  ☐ Check 10 PASS — monthly cost estimate documented

Conditional checks (mark N/A if not applicable):
  ☐ C1  PASS / N/A — PostgreSQL connectivity verified
  ☐ C2  PASS / N/A — external API connectivity + rate limits verified
  ☐ C3  PASS / N/A — load test passed at target RPS
```

Do not mark a deployment complete until every applicable box is checked.

---

## Cost-Optimized Cluster Configurations

### Tier 1: Hobby/Learning (~$6-12/mo)

| Provider | Config | Monthly Cost |
|----------|--------|:------------:|
| **Hetzner** | 1x CX22 (2vCPU/4GB) single-node | ~$3-4 |
| **Hetzner** | 1x CX22 master + 2x CX22 workers | ~$9-12 |
| **DigitalOcean** | Free CP + 1x s-1vcpu-2gb | ~$12 |

### Tier 2: Startup/Staging (~$24-60/mo)

| Provider | Config | Monthly Cost |
|----------|--------|:------------:|
| **Hetzner** | 3x CPX22 masters (HA) + 3x CPX32 workers | ~$58 |
| **DigitalOcean** | Free CP + 3x s-2vcpu-4gb | ~$72 |
| **DigitalOcean** | HA CP + 3x s-2vcpu-4gb | ~$112 |

### Tier 3: Production (~$60-200/mo)

| Provider | Config | Monthly Cost |
|----------|--------|:------------:|
| **Hetzner** | 3x CPX22 HA + 10x CPX32 + autoscaling | ~$135 |
| **Hetzner** | 3x CPX22 HA + 10x CAX21 ARM64 + autoscaling | ~$100 |
| **DigitalOcean** | HA CP + 5x s-4vcpu-8gb + autoscaling | ~$280 |

> Full cost analysis and optimization strategies: `references/cost-optimization.md`

---

## Provider Selection Guide

### By Use Case

| Use Case | Best Provider | Why |
|----------|---------------|-----|
| **Learning / hobby** | Civo | ~$20/mo, 90-second provisioning, no control plane fee |
| **Cheapest option** | Hetzner | 3–8x cheaper than big-3 clouds; EU-only; ARM64 available |
| **Fastest provisioning** | Civo | ~90 seconds vs 5–18 minutes for others |
| **Managed + simple** | DigitalOcean | Cleanest UI/API, free control plane, good docs |
| **Enterprise compliance** | Azure AKS or AWS EKS | SOC2, HIPAA, FedRAMP, PCI-DSS, FedRAMP High |
| **ML / data workloads** | Google GKE | Best GPU/TPU selection (A100, TPU v4), Vertex AI integration |
| **AWS ecosystem** | AWS EKS | IAM, S3, RDS, Lambda integration; most mature tooling |
| **Azure ecosystem** | Azure AKS | Active Directory, DevOps, GitHub Actions integration |
| **EU data residency + cost** | Hetzner | Germany/Finland DCs, GDPR-native, lowest price in EU |
| **Multi-cloud resilience** | Any 2 providers | Provision each, merge kubeconfigs, deploy identically |

### By Budget (2-node cluster, 4GB RAM per node)

```
$0–$25/mo:
  Civo ($20)  ←── best value managed K8s

$25–$75/mo:
  Hetzner cx22 ($8, self-managed)
  DigitalOcean DOKS ($48)

$75–$175/mo:
  Azure AKS (~$110–130)
  Google GKE (~$120–145)
  AWS EKS (~$135–160, +$32 if private subnets)

Note: Big-3 costs are dominated by the ~$73/mo control plane fee.
      For dev/staging, use Civo or DO to avoid that tax.
```

### Common Pitfalls per Provider

| Provider | Common Pitfall | Prevention |
|----------|----------------|------------|
| **DigitalOcean** | Orphaned LBs after cluster delete | `doctl k8s cluster list-associated-resources` before delete |
| **Hetzner** | Token hardcoded in YAML → Git commit | Always use `export HCLOUD_TOKEN=...` + env var reference |
| **Azure AKS** | Surprise control plane fee on dev clusters | Use Civo for dev; AKS for prod only |
| **GKE** | Regional cluster billed for 3 zones even with 1 node | Use zonal cluster for dev; regional for prod |
| **AWS EKS** | NAT Gateway $32+/mo surprise on private subnets | Budget for it; or use public subnets for non-sensitive dev |
| **Civo** | Duplicate Traefik controllers | Disable Civo's built-in Traefik if installing your own |
| **All providers** | Left cluster running overnight while learning | Set a calendar reminder; delete after session |

---

## Cost Analysis Mode

When given workload specs, compare costs across all 6 providers.

### Standard Reference: 2-Node Cluster (4GB RAM each)

| Provider | Nodes | Control plane | 1× LB | 50GB storage | **Total/mo** |
|----------|-------|---------------|-------|--------------|-------------|
| **Hetzner** | 2× cx22 = ~$8 | ~$0 (self) | ~$6 | ~$3 | **~$17** |
| **Civo** | 2× Medium = $20 | Free | ~$5 | ~$5 | **~$30** |
| **DigitalOcean** | 2× s-2vcpu-4gb = $48 | Free | $12 | $5 | **~$65** |
| **Azure AKS** | 2× Standard_B2s = ~$73 | ~$73 | ~$18 | ~$2 | **~$166** |
| **Google GKE** | 2× e2-medium = ~$50 | ~$73 | ~$18 | ~$2 | **~$143** |
| **AWS EKS** | 2× t3.medium = ~$61 | ~$73 | ~$20 | ~$4 | **~$158** |

### Calculate for Custom Workload

Apply this formula when given different specs:

```
DigitalOcean:
  nodes × node_$/mo                           (control plane: free)
  + LB_count × $12
  + storage_GB × $0.10

Hetzner:
  master_count × master_$/mo + worker_count × worker_$/mo   (CP: free)
  + LB_count × $6
  + storage_GB × $0.05

Azure AKS:
  node_count × vm_$/mo
  + $73 (control plane)                       ← ALWAYS add this
  + LB_count × $18
  + storage_GB × $0.04

Google GKE:
  node_count × machine_$/mo
  + $73 (standard control plane)              ← ALWAYS add this
  + LB_count × $18
  + storage_GB × $0.04

AWS EKS:
  node_count × instance_$/mo
  + $73 (control plane)                       ← ALWAYS add this
  + LB_count × $20
  + storage_GB × $0.10
  + NAT_Gateway × $32 (if private subnets)    ← common surprise

Civo:
  node_count × node_$/mo                     (control plane: free)
  + LB_count × $5
  + storage_GB × $0.10
```

### Data Transfer Costs (often overlooked)

| Provider | Included | Overage |
|----------|----------|---------|
| Hetzner | 20 TB/mo per server | ~$1/TB |
| Civo | 1 TB/mo per cluster | $0.012/GB |
| DigitalOcean | 1–2 TB/mo per node | $0.01/GB |
| Azure | 5 GB/mo outbound | $0.087/GB |
| GCP | 1 GB/mo outbound | $0.085/GB |
| AWS | 1 GB/mo outbound | $0.09/GB |

> For bandwidth-heavy workloads (video, ML training data, CDN origin), Hetzner and Civo are dramatically cheaper than the big-3.

---

## Migration Strategy Generator

**Principle: Keep Helm charts 100% identical. Parameterize only what differs.**

What actually differs between providers:
1. Storage class name in `PersistentVolumeClaim`
2. Load balancer annotations on `Service` (if using non-standard configs)
3. Node pool labels for pod affinity rules

Everything else — Deployments, ConfigMaps, Secrets, Ingress, RBAC — is identical.

### Provider-Agnostic Helm values.yaml Pattern

```yaml
# values.yaml — committed to Git, provider-agnostic defaults
app:
  image: ghcr.io/your-org/your-app:latest
  replicas: 2
  resources:
    requests: { cpu: 50m, memory: 64Mi }
    limits: { cpu: 500m, memory: 256Mi }

# Provider-specific overrides — NOT in values.yaml, injected at deploy time
storage:
  className: standard    # default; overridden per provider (see below)
  size: 10Gi

ingress:
  enabled: true
  className: traefik     # or nginx — same across providers
  host: app.example.com
```

```yaml
# values-do.yaml — DigitalOcean overrides only
storage:
  className: do-block-storage

# values-hetzner.yaml — Hetzner overrides only
storage:
  className: hcloud-volumes

# values-azure.yaml — Azure overrides only
storage:
  className: managed-premium

# values-gke.yaml — GKE overrides only
storage:
  className: standard-rwo

# values-eks.yaml — EKS overrides only
storage:
  className: gp3

# values-civo.yaml — Civo overrides only
storage:
  className: civo-volume
```

```bash
# Deploy to any provider — same chart, different values overlay
PROVIDER=hetzner   # or: do, azure, gke, eks, civo

helm upgrade --install my-app ./charts/my-app \
  --namespace my-app --create-namespace \
  --values values.yaml \
  --values values-${PROVIDER}.yaml \
  --wait
```

### CI/CD Pipeline with Provider Flag

```yaml
# .github/workflows/deploy.yaml
name: Deploy
on:
  workflow_dispatch:
    inputs:
      provider:
        type: choice
        options: [do, hetzner, azure, gke, eks, civo]
        default: do

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Configure kubeconfig
      run: |
        # Each provider writes credentials to ~/.kube/config
        case "${{ inputs.provider }}" in
          do)      doctl k8s cluster kubeconfig save $CLUSTER_NAME ;;
          hetzner) cat "$HETZNER_KUBECONFIG" > ~/.kube/config ;;
          azure)   az aks get-credentials -g $RG -n $CLUSTER_NAME ;;
          gke)     gcloud container clusters get-credentials $CLUSTER_NAME --zone $GKE_ZONE ;;
          eks)     aws eks update-kubeconfig --name $CLUSTER_NAME --region $AWS_REGION ;;
          civo)    civo k8s config $CLUSTER_NAME --save --merge ;;
        esac

    - name: Deploy with Helm
      run: |
        # Identical deploy command — only values overlay differs
        helm upgrade --install my-app ./charts/my-app \
          --namespace my-app --create-namespace \
          --values values.yaml \
          --values values-${{ inputs.provider }}.yaml \
          --wait
```

### Migration Checklist (Provider A → Provider B)

```
Before migration:
  ☐ Export all Secrets: kubectl get secrets -n my-app -o yaml > secrets-backup.yaml
  ☐ Export all PVC data (if stateful): use velero or manual volume snapshots
  ☐ Document current cluster context: kubectl config current-context
  ☐ Note StorageClass name on source cluster: kubectl get sc

During migration:
  ☐ Provision new cluster on provider B (Step 1)
  ☐ Connect kubeconfig (Step 2)
  ☐ Create Secrets on new cluster: kubectl apply -f secrets-backup.yaml
  ☐ Update values-<provider>.yaml with new StorageClass name
  ☐ Deploy with Helm --values overlay (Step 3 — identical chart)
  ☐ Run Production Readiness Checklist on new cluster

After migration:
  ☐ Verify health endpoint on new cluster
  ☐ Shift DNS A-record to new LB IP (low TTL first)
  ☐ Monitor for 24h before decommissioning old cluster
  ☐ Delete old cluster (verify LBs and volumes cleaned up)
```

---

## Output Checklist

Before delivering, verify:

- [ ] Correct CLI installed and authenticated (`doctl auth init` / Hetzner token set)
- [ ] SSH key exists for Hetzner clusters
- [ ] Cluster provisioned successfully (nodes in `Ready` state)
- [ ] Kubeconfig saved and merged into `~/.kube/config`
- [ ] Context named with `<provider>-<region>-<name>` convention
- [ ] `kubectl get nodes` returns expected nodes on correct context
- [ ] Node pool sizing matches budget target
- [ ] Autoscaling configured if production workload
- [ ] Network access restricted (`allowed_networks` for Hetzner, VPC for DO)

---

## Safety & Billing Controls

### NEVER

| Action | Why | Safe alternative |
|--------|-----|-----------------|
| Store API tokens in Git | Token exposed → attacker can spin up servers in your account | `export TOKEN=...` env var or secrets manager |
| Provision prod without HA | Single master → single point of failure | 3 masters minimum for production |
| Use `0.0.0.0/0` for SSH in production | Open SSH to the internet → brute force attacks | Restrict to your IP/VPN CIDR |
| Delete cluster without checking LBs/volumes | Orphaned resources continue billing silently | List associated resources first (see teardown steps) |
| Mix cluster CIDRs across multi-cluster setups | CIDR conflict breaks cross-cluster routing | Change pod/service CIDR at provisioning time |
| Commit `.env` or `kubeconfig` to Git | Credentials leaked to all repo readers | `.gitignore` both; use sealed secrets or SOPS |
| Leave learning clusters running overnight | Idle cluster costs $4–$73+/mo overnight for nothing | Delete after session; recreate from config |

### ALWAYS

| Action | Why |
|--------|-----|
| Set `protect_against_deletion: true` (Hetzner prod) | Prevents accidental console delete |
| Set `--maintenance-window` (DOKS, AKS) | Controls when K8s upgrades happen |
| Back up kubeconfig before merging | Merge is destructive if you make a mistake |
| Verify node count before creating | Cloud bills start immediately at provisioning |
| Document monthly cost estimate before go-live | Prevents budget surprises |
| Set billing alerts on every cloud account | Catch runaway costs before they compound |
| Run Production Readiness Checklist before launch | Ensures cluster is actually production-ready |

### Billing Alert Setup (Per Provider)

```bash
# ── DigitalOcean ──────────────────────────────────────────────────────────────
# cloud.digitalocean.com → Billing → Billing Alerts → Create Alert
# Set alert at 80% of monthly budget

# ── Azure ─────────────────────────────────────────────────────────────────────
az consumption budget create \
  --budget-name my-budget \
  --amount 200 \
  --time-grain Monthly \
  --category Cost \
  --notifications '[{"enabled":true,"operator":"GreaterThan","threshold":80,"contactEmails":["you@example.com"]}]'

# ── Google Cloud ───────────────────────────────────────────────────────────────
# console.cloud.google.com → Billing → Budgets & alerts → Create Budget
# Set threshold at 80% of monthly estimate

# ── AWS ────────────────────────────────────────────────────────────────────────
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget '{"BudgetName":"my-budget","BudgetLimit":{"Amount":"200","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
  --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]}]'

# ── Hetzner ────────────────────────────────────────────────────────────────────
# console.hetzner.cloud → Account → Billing → Budget notification
# Set monthly budget; Hetzner emails at 80% and 100%

# ── Civo ──────────────────────────────────────────────────────────────────────
# dash.civo.com → Settings → Billing → Create billing alert
```

### Smallest Viable Node Sizes for Labs

| Provider | Minimum viable size | vCPU | RAM | Cost/mo |
|----------|--------------------|----|-----|---------|
| Hetzner | `cx22` | 2 | 4 GB | ~$4 |
| Civo | `g4s.kube.medium` | 2 | 4 GB | $10 |
| DigitalOcean | `s-2vcpu-4gb` | 2 | 4 GB | $24 |
| Azure | `Standard_B2s` | 2 | 4 GB | ~$18/node |
| GCP | `e2-medium` | 2 | 4 GB | ~$25/node |
| AWS | `t3.medium` | 2 | 4 GB | ~$30/node |

> 2 GB RAM nodes are insufficient for running Traefik + cert-manager + Dapr simultaneously.
> Always use 4 GB minimum for any multi-component stack.

### Overnight Running Cost Warning

When learning or experimenting, always delete clusters after your session:

```bash
# DigitalOcean
doctl kubernetes cluster delete my-cluster --force

# Hetzner
hetzner-k3s delete --config cluster.yaml

# Azure
az group delete --name my-rg --yes --no-wait

# GCP
gcloud container clusters delete my-cluster --zone us-central1-a --quiet

# AWS
eksctl delete cluster --name my-cluster --region us-east-1

# Civo
civo kubernetes delete my-cluster
```

**Cost of forgetting to delete (24h):**

| Provider | 2-node 4GB cluster left overnight |
|----------|----------------------------------|
| Hetzner | ~$0.25 |
| Civo | ~$0.65 |
| DigitalOcean | ~$1.60 |
| Azure AKS | ~$4.60 (incl. control plane) |
| GCP GKE | ~$4.30 (incl. control plane) |
| AWS EKS | ~$4.80 (incl. control plane) |

---

## Reference Files

| File | When to Read |
|------|--------------|
| `references/digitalocean-doks.md` | Full doctl CLI reference, all flags, node pool management |
| `references/hetzner-k3s.md` | Complete hetzner-k3s config spec, all fields, add-ons |
| `references/multi-cluster-kubectl.md` | Kubeconfig merge, context management, cross-cluster patterns |
| `references/cost-optimization.md` | Detailed pricing, comparison tables, optimization strategies |
