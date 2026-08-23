# Hermes friends public-code runner

This tree is intentionally inert and is **not referenced** by
`kubernetes/apps/kustomization.yaml`. Merging it creates no Namespace, Flux
Kustomization, PVC, Pod, broker rollout, or other live cluster object. The
three child Flux Kustomizations are also suspended and every long-running
Deployment has zero replicas. A separate activation pull request must first
add the root reference, then advance the three children in order.

The namespaces split authority as follows:

- `hermes-friends-control`: dispatcher and its narrow Job-creation identity;
- `hermes-friends-sandbox`: disposable generator and tester Jobs, with no
  Secrets, PVCs, GitHub access, or reusable Kubernetes token;
- `hermes-friends-runtime`: one tokenless, networkless Kata validation Job;
- `hermes-friends-artifact`: the only persistent artifact store;
- `hermes-friends-creator`: the repository-creation GitHub App only;
- `hermes-friends-publisher`: the content-and-draft-PR GitHub App only.

No owner/private GitHub credential, Workspace identity, SOPS key, Fleet token,
media token, observability credential, host mount, or owner Hermes PVC belongs
in any of these namespaces. Secret names and required keys are contracts only;
the public repository never contains plaintext or invented credential values.

The encrypted provisioning file creates exactly these independent Secrets in
their stated namespaces:

| Namespace | Secret | Required key | Consumer |
| --- | --- | --- | --- |
| `default` | future broker runner contract | runner token SHA-256 and approval private key | Broker dispatch signing only |
| `hermes-friends-control` | `hermes-friend-dispatcher-auth` | `runner-token` | Broker runner API only |
| `hermes-friends-control` | `hermes-friend-trust` | `approval-public-key` | Approval verification |
| `hermes-friends-artifact` | `hermes-friend-trust` | `approval-public-key` | Approval verification |
| `hermes-friends-artifact` | `hermes-friend-artifact-signer` | `collector-private-key` | Artifact receipts only |
| `hermes-friends-creator` | `hermes-friend-trust` | `approval-public-key` | Approval verification |
| `hermes-friends-creator` | `hermes-friend-creator-github-app` | `private-key.pem` | Empty sandbox organization creation App |
| `hermes-friends-publisher` | `hermes-friend-trust` | `approval-public-key` | Approval verification |
| `hermes-friends-publisher` | `hermes-friend-publisher-github-app` | `private-key.pem` | Exact-repository publisher App |

The creator and publisher keys must be different GitHub Apps. Neither may be
installed on David's personal account or any organization that contains a
private repository. Generator and tester Jobs cannot reference any Secret;
the admission policy rejects such a Job before it is created.

The dispatcher receives Kubernetes authority through an explicitly projected,
one-hour ServiceAccount token that the client rereads for every API call. The
token omits an invented audience so the kubelet uses the API server's configured
audience. `automountServiceAccountToken`
stays false for every Pod. The dispatcher may create/get only the bounded
request ConfigMaps and create/observe Jobs in `hermes-friends-sandbox`; it may
not read Secrets, logs, exec, update Job specs, delete resources, or access any
other namespace. It creates the Job first, reads back and verifies its UID, then
creates the immutable input ConfigMap with that Job as its controller owner.
Crashing before the ConfigMap exists leaves only a deadline-bounded Job;
crashing after it exists leaves a garbage-collectable dependent. The Job TTL
controller removes the Job and garbage collection removes its input ConfigMap.

Prometheus reaches each daemon through a Cilium L7 rule that permits only
`GET /metrics`. Monitoring therefore cannot call the creator, publisher, or
artifact write APIs merely because those roles expose metrics on the same
listener.

The existing broker's runner API remains disabled by its fail-closed source
default. This pull request does not modify its HelmRelease or NetworkPolicy, so
merge cannot restart or widen the live broker. The default-namespace row above
is only a contract because the final broker secret names and file environment
variables must come from the reviewed runner API implementation. No placeholder
Secret is safe to commit for it.

Activation must be a later pull request and proceeds in this exact order:

1. Install and independently accept `RuntimeClass/kata-clh` on the selected
   sandbox nodes. The class is absent from the live cluster as of staging.
2. Pin the dedicated runtime validator to a reviewed non-inert digest and set
   the same non-`UNSET` activation revision on the Job and Pod template.
3. Pin distinct generator and tester repositories and digests, every control
   image digest, the model relay, test catalog, policy revision, organization,
   and independent GitHub App identities. Provision only the encrypted secret
   contracts below. Prove the sandbox organization contains no private
   repositories or Actions secrets.
4. Add this directory to `kubernetes/apps/kustomization.yaml`. Keep all three
   children suspended. Merge and prove only the namespaces and suspended Flux
   objects appeared.
5. Unsuspend `hermes-friends-code-boundary` alone. Prove default-deny,
   DNS-restricted egress, quotas, RBAC, and all three admission policies are
   Ready.
6. Unsuspend `hermes-friends-code-runtime-validation` alone. It cannot become
   Ready unless a Pod starts under `kata-clh` and the one-shot validator exits
   successfully. The workload child depends on this Ready condition.
7. Use a fresh David approval bound to the final policy hash. Old approvals
   must never be grandfathered. Only then change required replicas and
   unsuspend `hermes-friends-code`.
8. In a separate reviewed broker change, add the exact runner API contract,
   network ingress, and secrets, then enable execution. This staged pull
   request deliberately does not touch the live broker.

The admission policy pins `runtimeClassName: kata-clh`, distinct generator and
tester images, exact commands, tokenless identity, bounded resources and
volumes, `ndots: 1`, and automatic Job TTL. Dispatcher RBAC permits only
create/get on sandbox Jobs and ConfigMaps plus get on the named `kata-clh`
RuntimeClass. The workload child cannot race ahead of either the deny boundary
or runtime proof because its Flux dependency is fail-closed.

Broad DNS egress is forbidden. Cilium DNS rules allow only the exact internal
service names each component needs and `api.github.com` for the creator and
publisher. `ndots: 1` prevents resolver search-suffix probes from becoming an
accidental alternate DNS channel. The generator network policy reserves one
path to a future
`hermes-friend-model-relay` on port 8084. No relay workload or provider secret
is included here because no reviewed public-only model relay image/account
exists yet. Consequently generation remains impossible even if someone were
to remove only one of the other safety latches.
