# CLAUDE.md - Home Kubernetes Cluster Guide

## Overview

This is a **production home Kubernetes cluster** running on **Talos Linux** with **Flux GitOps**. Every push to this repository automatically updates the live cluster - exercise caution with all changes.

- **Repository:** https://github.com/DavidIlie/home-cluster
- **Cluster OS:** Talos Linux v1.10.x
- **Kubernetes Version:** v1.33.x
- **GitOps:** Flux v2 (operator + instance pattern)
- **Secrets:** SOPS with Age encryption
- **Updates:** Renovate bot

## Critical Rules

### NEVER Touch Automatically
- **Talos OS version** - Manual updates only
- **Kubernetes version** - Manual updates only
- If a package update requires a newer Kubernetes version, **do not proceed** - flag it for manual review

### Before Any Change
1. This is a **LIVE cluster** - every merge affects production
2. Validate YAML syntax before committing
3. Check for breaking changes in release notes
4. Ensure secrets are properly encrypted (`.sops.yaml` suffix)

## Project Structure

```
home-cluster/
├── kubernetes/
│   ├── apps/                    # Application deployments by namespace
│   │   ├── flux-system/         # Flux operator & instance
│   │   ├── kube-system/         # Core services (Cilium, CoreDNS, etc.)
│   │   ├── cert-manager/        # TLS certificates
│   │   ├── network/             # Ingress (internal/external)
│   │   ├── observability/       # Prometheus, Grafana, exporters
│   │   ├── databases/           # PostgreSQL, Dragonfly, ClickHouse
│   │   ├── media/               # Plex, Radarr, Sonarr, etc.
│   │   ├── downloads/           # qBittorrent, SABnzbd, Prowlarr
│   │   ├── ai/                  # Ollama, Open WebUI
│   │   ├── default/             # Personal apps
│   │   ├── infastructure/       # Portainer, Scrypted
│   │   └── external-services/   # External service monitors
│   ├── bootstrap/
│   │   ├── talos/               # Talos configuration
│   │   └── flux/                # Initial Flux setup
│   └── flux/
│       ├── cluster/             # Main Kustomizations
│       ├── meta/                # Helm/OCI repositories
│       └── components/          # Reusable components
├── .github/
│   ├── renovate.json5           # Renovate configuration
│   └── workflows/               # CI/CD pipelines
├── .taskfiles/                  # Task automation
├── config.yaml                  # Cluster configuration (IPs, secrets refs)
├── .sops.yaml                   # SOPS encryption rules
└── age.key                      # Age public key
```

## App Structure Pattern

Each application follows this structure:
```
app-name/
├── ks.yaml                      # Flux Kustomization
└── app/
    ├── kustomization.yaml       # Resource aggregator
    ├── helmrelease.yaml         # Helm deployment
    ├── helm-values.yaml         # Helm values (optional)
    └── secret.sops.yaml         # Encrypted secrets (optional)
```

## Common Tasks

### IMPORTANT: Always Ask for Consent

**Before performing ANY action that modifies the cluster or repository, ALWAYS ask for user consent first.** This includes:
- Merging PRs
- Making config changes
- Creating new files
- Modifying existing files
- Running kubectl commands that change state (scale, restart, delete)

Present findings and recommendations, then wait for explicit approval before proceeding.

---

### Task 1: Check Renovate Updates

When asked to review pending updates:

#### Step 1: Fetch and List All Open PRs
```bash
gh pr list --repo DavidIlie/home-cluster --state open --limit 100
```

#### Step 2: For Each PR, Gather Information
```bash
# View PR details
gh pr view <PR_NUMBER> --repo DavidIlie/home-cluster

# View changed files
gh pr diff <PR_NUMBER> --repo DavidIlie/home-cluster
```

#### Step 3: Analyze Each Update
For each PR, investigate:

1. **Identify the app and location:**
   - Find the app in `kubernetes/apps/<namespace>/<app>/`
   - Read the current `helmrelease.yaml` and `helm-values.yaml`

2. **Check for breaking changes:**
   - Fetch release notes/changelog from the project's GitHub
   - Look for migration guides, deprecations, or breaking changes
   - Check if new required config options were added

3. **Check secrets if applicable:**
   ```bash
   sops -d kubernetes/apps/<namespace>/<app>/app/secret.sops.yaml
   ```
   - Verify secret format still matches what the new version expects
   - Check if new secrets are required

4. **Check Kubernetes version requirements:**
   - If the update requires a newer K8s version than v1.33.x → **FLAG AS BLOCKED**
   - Do NOT recommend merging

#### Step 4: Present Findings and Ask for Consent

Present a summary table for all PRs:

| PR | Package | Current → New | Status | Notes |
|----|---------|---------------|--------|-------|
| #123 | sonarr | 4.0.0 → 4.1.0 | ✅ Safe | No config changes needed |
| #124 | radarr | 5.0.0 → 6.0.0 | ⚠️ Config needed | New env var required |
| #125 | cilium | 1.15 → 1.16 | 🚫 Blocked | Requires K8s 1.34 |

Then ask: **"Which PRs would you like me to process? Do you want me to make the necessary config changes for PR #124?"**

#### Step 5: Only After Approval
- Make config changes if approved
- Merge PRs only when explicitly told to

---

### Task 2: Install New Applications

The user may provide various input formats:
- **Just an app name:** "install jellyfin"
- **GitHub project link:** "install https://github.com/jellyfin/jellyfin"
- **KubeSearch link:** "use this https://kubesearch.dev/?search=jellyfin"
- **Other home cluster links:** "use this as reference https://github.com/someone/home-cluster/tree/main/kubernetes/apps/media/jellyfin"
- **Multiple references:** Combination of the above

#### Step 1: Research Phase

**If given just an app name:**
1. Search https://kubesearch.dev/ for the app to find community implementations
2. Find the official project GitHub/docs
3. Look for official Helm charts

**If given a GitHub project link:**
1. Check if they have an official Helm chart
2. Search kubesearch.dev for community implementations
3. Review their documentation for Kubernetes deployment

**If given a KubeSearch link:**
1. Open the link and review the community implementations shown
2. Pick well-structured examples that match this cluster's patterns
3. Cross-reference with official documentation

**If given another home cluster reference:**
1. Fetch and analyze their implementation
2. Adapt to match this cluster's conventions
3. Verify chart versions and values are current

#### Step 2: Ask Required Questions (Unless Already Provided)

**ALWAYS ask these questions before proceeding (skip if user already specified):**

1. **Namespace:** "Which namespace should this go in?"
   - Suggest based on app type (media, downloads, observability, default, etc.)
   - List existing namespaces as options

2. **Ingress/Access:** "Do you want this publicly accessible or internal only?"
   - `external` = Public via Cloudflare tunnel (accessible from internet)
   - `internal` = Internal network only (home network access)
   - Or no ingress at all

3. **Hostname:** "What hostname/subdomain do you want?"
   - e.g., `jellyfin.davidhome.ro` for external
   - e.g., `jellyfin.internal` for internal

Example questions:
```
Before I set up Jellyfin, I need to know:

1. Namespace: Where should this live?
   - media (recommended, alongside Plex/Sonarr/Radarr)
   - default
   - Other?

2. Access: Public or private?
   - External (public via Cloudflare - accessible from anywhere)
   - Internal (home network only)

3. Hostname: What subdomain?
   - e.g., jellyfin.davidhome.ro
```

**If the user provided these details upfront, skip the questions and proceed.**

#### Step 3: Present Implementation Plan

After getting answers (or if already provided), present the full plan:

1. **Namespace:** Confirmed choice
2. **Helm chart:** Which chart and version to use
3. **Ingress configuration:** Class and hostname
4. **Storage:** What volumes/mounts are needed
5. **Secrets:** What secrets are required (if any)
6. **Dependencies:** Other apps or resources required
7. **Reference sources:** What implementations were used as reference

Example:
```
Here's the plan for Jellyfin:

- Namespace: media
- Helm chart: bjw-s/app-template v3.x
- Ingress: internal class, hostname jellyfin.internal
- Storage: NFS mount for media library at /media
- Secrets: None required for basic setup
- GPU: Will enable NVIDIA transcoding

References used:
- kubesearch.dev example from user X
- Official Jellyfin docs

Should I proceed with creating the files?
```

**Wait for approval before creating any files.**

#### Step 3: Implementation (After Approval)

1. Create app directory: `kubernetes/apps/<namespace>/<app-name>/`
2. Create `ks.yaml` (Flux Kustomization)
3. Create `app/kustomization.yaml`
4. Create `app/helmrelease.yaml`
5. Create `app/helm-values.yaml` if needed
6. Create `app/secret.sops.yaml` if secrets required

#### Step 4: Encrypt Secrets (if any)
```bash
sops -e -i kubernetes/apps/<namespace>/<app>/app/secret.sops.yaml
```

#### Step 5: Validate
- YAML syntax is correct
- Helm repository exists in `kubernetes/flux/meta/repositories/`
- Namespace exists or add to parent kustomization
- All referenced secrets/configmaps exist

#### Step 6: Final Review
Present the created files for review before committing. Ask: **"Here are the files I've created. Should I commit these changes?"**

## Key Configuration

### Network
- **Node IP:** 192.168.100.180
- **Pod CIDR:** 10.42.0.0/16
- **Service CIDR:** 10.24.0.0/16
- **Ingress External:** 192.168.100.91
- **Ingress Internal:** Uses internal DNS

### Ingress Classes
- `external` - Public-facing via Cloudflare tunnel
- `internal` - Internal network only

### Ingress Requirements (IMPORTANT)

**Every app with an ingress MUST have:**

1. **Gatus Health Check** - Add this annotation to the ingress:
```yaml
ingress:
  app:
    annotations:
      gatus.home-operations.com/endpoint: |-
        name: App Name
        group: Category  # Media, Utilities, Downloads, Monitoring, etc.
        url: https://hostname.davidhome.ro
        interval: 1m
        conditions: ["[STATUS] == 200"]
```

2. **Homepage Entry** - Add to `kubernetes/apps/default/homepage/app/services.yaml`:
```yaml
- Category:
    - App Name:
        icon: app-icon.png  # or mdi-icon-name
        href: https://hostname.davidhome.ro
        description: Brief description
        widget:  # Optional - only if the app supports homepage widgets
          type: widget-type
          url: http://service.namespace.svc.cluster.local:port
          key: "{{HOMEPAGE_VAR_APP_API_KEY}}"
```

**Widget API keys** go in `kubernetes/apps/default/homepage/app/secret.sops.yaml`

### Storage
- **OpenEBS** - Local provisioner for stateful apps
- **NFS** - Media storage mounted from TrueNAS

### Backups (VolSync)

Apps with PVCs use VolSync to backup data to MinIO S3 (`192.168.100.63:9000/volsync`).

**To enable VolSync backups for an app:**

1. Add to `ks.yaml`:
```yaml
spec:
  dependsOn:
    - name: volsync
      namespace: volsync-system
  postBuild:
    substitute:
      APP: *app
      APP_PVC: *app  # Or custom PVC name if different
    substituteFrom:
      - kind: Secret
        name: volsync-secret
        namespace: volsync-system
```

2. Add to `app/kustomization.yaml`:
```yaml
components:
  - ../../../../flux/components/volsync
```

**Backup schedule:** Every 6 hours
**Retention:** 6 hourly, 7 daily, 4 weekly, 3 monthly

### Common Helm Repositories
- `bjw-s` - app-template charts (most apps use this)
- `prometheus-community` - Monitoring stack
- `jetstack` - cert-manager
- `ingress-nginx` - Ingress controllers

## Available CLI Tools

All tools are managed via `mise` and available in the project environment:

| Tool | Version | Purpose |
|------|---------|---------|
| `kubectl` | 1.32.1 | Kubernetes cluster management |
| `flux` | 2.6.4 | GitOps operations |
| `helm` | 4.0.5 | Helm chart management |
| `helmfile` | 1.2.3 | Declarative Helm deployments |
| `sops` | 3.11.0 | Secret encryption/decryption |
| `age` | 1.3.1 | Encryption backend for SOPS |
| `talosctl` | 1.10.7 | Talos node management |
| `talhelper` | 3.1.2 | Talos config generation |
| `kustomize` | 5.6.0 | Kustomization builds |
| `kubeconform` | 0.7.0 | YAML validation |
| `task` | 3.46.4 | Task runner |
| `yq` | 4.50.1 | YAML processing |
| `jq` | 1.7.1 | JSON processing |
| `cloudflared` | 2026.1.1 | Cloudflare tunnel CLI |

## Common Operations

### Kubectl Commands
```bash
# Get all pods in a namespace
kubectl get pods -n <namespace>

# Restart a deployment (rollout restart)
kubectl rollout restart deployment/<name> -n <namespace>

# Scale a deployment down/up
kubectl scale deployment/<name> --replicas=0 -n <namespace>
kubectl scale deployment/<name> --replicas=1 -n <namespace>

# View logs
kubectl logs -n <namespace> <pod-name> -f

# Describe a resource
kubectl describe pod/<name> -n <namespace>

# Get events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Execute into a pod
kubectl exec -it -n <namespace> <pod-name> -- /bin/sh
```

### Flux Commands
```bash
# Check all Flux resources
flux get all -A

# Reconcile a kustomization
flux reconcile kustomization <name> --with-source

# Reconcile a helmrelease
flux reconcile helmrelease <name> -n <namespace>

# Suspend a helmrelease (pause updates)
flux suspend helmrelease <name> -n <namespace>

# Resume a helmrelease
flux resume helmrelease <name> -n <namespace>

# View Flux logs
flux logs -A --follow

# Check source status
flux get sources all -A
```

### SOPS Commands
```bash
# Decrypt a secret (view only)
sops -d <file.sops.yaml>

# Encrypt a new secret file
sops -e -i <file.sops.yaml>

# Edit encrypted file in place
sops <file.sops.yaml>
```

### Helm Commands
```bash
# List releases
helm list -A

# Get values from a release
helm get values <release> -n <namespace>

# Show chart values
helm show values <chart>
```

### Task Commands
```bash
# Force Flux reconciliation
task reconcile

# Generate Talos config
task talos:generate-config

# Bootstrap apps
task bootstrap:apps
```

## Useful Commands (Quick Reference)

```bash
# Decrypt a secret
sops -d <file.sops.yaml>

# Encrypt a secret
sops -e -i <file.sops.yaml>

# Force Flux reconciliation
task reconcile

# Check Flux status
flux get all -A

# View Talos config
task talos:generate-config

# List open PRs
gh pr list --state open

# Restart a stuck deployment
kubectl rollout restart deployment/<name> -n <namespace>

# Check why a pod is failing
kubectl describe pod/<name> -n <namespace>
kubectl logs -n <namespace> <pod-name>
```

## File Naming Conventions

- `ks.yaml` - Flux Kustomization resource
- `helmrelease.yaml` - HelmRelease resource
- `helm-values.yaml` - Helm chart values
- `secret.sops.yaml` - SOPS-encrypted Secret
- `configmap.sops.yaml` - SOPS-encrypted ConfigMap
- `kustomization.yaml` - Kustomize aggregator

## Renovate Labels

PRs are labeled by type:
- `type/major` - Major version bumps (review carefully)
- `type/minor` - Minor version bumps
- `type/patch` - Patch version bumps
- `renovate/container` - Container image updates
- `renovate/helm` - Helm chart updates

## Resources

- **KubeSearch:** https://kubesearch.dev/ - Search other home clusters
- **Flux Docs:** https://fluxcd.io/docs/
- **Talos Docs:** https://www.talos.dev/docs/
- **SOPS:** https://github.com/getsops/sops

## Namespace Reference

| Namespace | Purpose |
|-----------|---------|
| `flux-system` | Flux GitOps operator |
| `kube-system` | Core cluster services |
| `cert-manager` | TLS certificate management |
| `network` | Ingress controllers, DNS |
| `observability` | Monitoring, Grafana, Prometheus |
| `databases` | PostgreSQL, Dragonfly, ClickHouse |
| `media` | Plex, *arr stack |
| `downloads` | qBittorrent, SABnzbd |
| `ai` | Ollama, Open WebUI |
| `default` | Personal applications |
| `infastructure` | Infrastructure tools |
| `external-services` | External service monitors |
| `openebs-system` | Storage provisioner |
| `volsync-system` | PVC backup/restore with VolSync |
| `actions-runner-system` | GitHub Actions self-hosted runners |
