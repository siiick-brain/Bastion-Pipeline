# Screenshots

Captures of real runs, taken 2026-11-17 from the public pages with headless Microsoft Edge.

| Image | Shows | Source |
| --- | --- | --- |
| [release-job-graph](images/release-job-graph.png) | Release `v0.2.0`: every job green, the job graph and the `production` approval by the required reviewer | GitHub release run 43983071969 |
| [release-assets](images/release-assets.png) | Release `v0.2.0` page with the image digest and its nine assets | `releases/tag/v0.2.0` |
| [actions-overview](images/actions-overview.png) | Workflow runs on `main`, the tag and a Dependabot pull request | `actions` |

Pages that need a signed-in browser (job logs, code scanning, rulesets) and the SonarCloud dashboard, which does not render headless, are not captured. Their results are recorded with run IDs in the [control matrix](control-matrix.md).
