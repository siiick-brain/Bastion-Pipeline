<#
.SYNOPSIS
    Checks that the admission policy (infra/kyverno/require-signed-images.yaml) admits signed
    release images and rejects the rest.
.DESCRIPTION
    Each case sends a pod to the API server with a server-side dry run, so the admission
    webhooks decide and nothing is created. Every pod meets Pod Security "restricted", so only the
    signature policies can reject it. Requires a cluster set up with scripts/kind-up.ps1 -WithAdmission.
    Prints PASS or FAIL per case and exits 1 when any case does not behave as expected.
.EXAMPLE
    pwsh -File scripts/verify-admission.ps1
#>
[CmdletBinding()]
param(
    [string]$Context = 'kind-bastion',
    [string]$Namespace = 'bastion'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repo = 'ghcr.io/siiick-brain/bastion-pipeline'
$cases = @(
    @{ Name = 'Signed release v0.2.1 by digest'; Image = "$repo@sha256:dbba11b288a6a0b8d0a556b89fa331a21fdd312ef2d5f77212859a058a6c7916"; Admit = $true },
    @{ Name = 'Signed release v0.2.0 by digest'; Image = "$repo@sha256:706f6b48b24903b5b8e97bcc70e3619a682acd41ab0fb9667a2be9ac52ec3c00"; Admit = $true },
    @{ Name = 'Same release by tag instead of digest'; Image = "${repo}:v0.2.1"; Admit = $false },
    @{ Name = 'Image from another registry'; Image = 'localhost:5001/bastion-pipeline@sha256:030bad5d18c3eef96d2ead338cc5c651ed64f1981750413ec837dd2c5fe1dc43'; Admit = $false },
    @{ Name = 'Unsigned object in the project repository (signature artifact of v0.2.1)'; Image = "$repo@sha256:0405a19a7f6767435d450b8d267aefc38ec82b2b232b0e81bfef4d184c1a5546"; Admit = $false }
)

$failed = 0
foreach ($case in $cases) {
    $pod = @"
apiVersion: v1
kind: Pod
metadata:
  name: admission-check
  namespace: $Namespace
spec:
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: $($case.Image)
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: [ALL]
"@
    $out = $pod | & kubectl --context $Context apply --dry-run=server -f - 2>&1
    $admitted = $LASTEXITCODE -eq 0
    $ok = $admitted -eq $case.Admit
    if (-not $ok) { $failed++ }
    $detail = if ($admitted) { 'admitted' } else { 'rejected: ' + (($out | Out-String).Trim() -replace '\s+', ' ').Substring(0, [Math]::Min(160, (($out | Out-String).Trim() -replace '\s+', ' ').Length)) }
    $expected = if ($case.Admit) { 'admit' } else { 'reject' }
    '{0,-5} {1} (expected {2}): {3}' -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $case.Name, $expected, $detail
}
exit $(if ($failed) { 1 } else { 0 })
