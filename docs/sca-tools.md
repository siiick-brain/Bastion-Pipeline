# Software composition analysis tools

Pull request gate: OSV-Scanner on every lock file, plus dependency review on pull requests. Trivy gates the built image.

Scheduled deep scans (weekly, `.github/workflows/scheduled-scans.yml`): OWASP Dependency-Check, OSV-Scanner full source and image scan, ZAP full scan.

Each finding class has one blocking owner so findings are not duplicated. The full table with versions, inputs, outputs and external data flows is in [tool ownership](tool-ownership.md). The reasoning is in [ADR 0002](adr/0002-scanner-split.md).
