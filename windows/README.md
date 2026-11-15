# Windows tooling

- `build.ps1`: validates arguments and prerequisites, runs PSScriptAnalyzer (any finding fails), runs Pester (any failure fails), builds the zip atomically, verifies its contents and writes a `sha256sum`-compatible `SHA256SUMS`.
- `build.bat`: process-scoped `-ExecutionPolicy Bypass`, prefers pwsh, propagates the exit code. No administrator rights.
- `BastionBuild.psm1`: testable functions used by `build.ps1`.
- `Get-BuildInfo.ps1`: version, build number, timestamp, branch and commit. No absolute paths.
- Tests: `windows/tests/build.tests.ps1` (31 Pester tests: paths with spaces, missing prerequisites and inputs, invalid arguments, interrupted packaging, temp cleanup, unexpected working directory, checksum tamper and traversal, exit codes). PASS on 2026-11-15 with Pester 6.2.0.

```powershell
windows\build.bat -Version 0.2.0 -BuildNumber 1
```
