# Container security scan — 2026-10-19

All seven Compose runtime images were scanned using Docker Scout 1.25.0. Machine-readable SARIF reports are in image-scans/ and image-scan-summary.json records the exact image IDs, counts and scan status. Run `.venv\Scripts\python.exe scripts/scan_images.py` to refresh them. Scout may require Docker/network access and account authentication in a different environment.

A completed scan is not a clean bill of health. The initial scan reported findings in every image, including high-severity findings in application base images and observability/database images. Many are OS or bundled-tool dependencies rather than application Python/npm dependencies. Some reports list no fixed version. Findings must be triaged for affected versions, available fixes and runtime exposure; they are not silently suppressed.

The initial Python runtime images included pip 25.0.1 with six fixable findings. Dockerfiles now use pip 26.2.1 to install runtime dependencies, then uninstall pip from the final runtime. This version is published by [PyPA on PyPI](https://pypi.org/project/pip/). An intermediate rescan cleared the old pip findings but found vulnerabilities in the newer installer's bundled packages. Their report locations were inside pip/_vendor/bom.cdx.json. Pip is unnecessary at runtime, so it is removed after installation. Consult the final rebuilt-image summary rather than assuming an upgrade alone is sufficient.

Remaining work includes reviewing and updating the Nginx, PostgreSQL, Prometheus and Grafana images, testing compatibility, and rescanning. The Python Debian base also has an unfixed high-severity zlib finding according to this scan. Do not describe the project as vulnerability-free or production-ready.

The application remains loopback-bound, containers remain unprivileged, and no Docker socket is mounted. These constraints limit exposure but do not erase vulnerability findings. Package audits and image scans cover different layers; passing pip/npm audits does not mean the images are clean.

Final rescan: each of the backend, checkout and payment images decreased from 34 findings initially to 28, with no PyPI-package findings remaining. OS findings remain, including the reported unfixed zlib issue. Frontend: 165 findings; PostgreSQL: 72; Prometheus: 128; Grafana: 263. Counts describe this scanner run, not unique exploitable weaknesses. Final image IDs are recorded in image-scan-summary.json.

## Verified runtime upgrades — 2026-10-19

Updated Nginx to 1.30.6, Prometheus to 3.13.4 LTS and Grafana to 13.2.4. PostgreSQL is pinned to 17.11-alpine; it was already running 17.11, so this pin did not reduce findings. Version references: [Nginx changes](https://nginx.org/en/CHANGES-1.30), [Prometheus downloads](https://prometheus.io/download/), [Grafana release](https://github.com/grafana/grafana/releases/tag/v13.2.4), [PostgreSQL release](https://www.postgresql.org/docs/release/17.11/).

The new completed scan supersedes the counts above. Frontend findings decreased from 165 to 36, Prometheus from 128 to 31 and Grafana from 263 to 93. PostgreSQL remains at 72 and each Python image at 28. The prior summary is preserved in image-scan-before-upgrades.json; current image IDs and SARIF paths are in image-scan-summary.json. SARIF result counts can differ from unique rule counts. High and critical findings remain, including findings with known fixes; these require further package-level triage. Image scanning does not cover Grafana plugins stored in its persistent volume.

Before replacing containers, PostgreSQL was dumped in custom format and its archive listing verified; Grafana was stopped and its database/plugins backed up. Local backups are under .local-backups/pre-image-upgrade/ and excluded from Git and Docker build contexts. They contain private application data and must not be published. Grafana data was restored into the new grafanadata named volume; do not restore its upgraded database into an older Grafana release. Use the pre-upgrade backup for a downgrade. PostgreSQL's pgdata volume was retained.

Validation passed: frontend build and HTTP 200, all demo scenarios and expiry/auth checks, both Prometheus targets, full incident lifecycle including failed verification and replay, real cross-service traces, and the four-panel Grafana dashboard. All seven containers are running; services with configured health checks are healthy. Grafana reports 13.2.4 and Nginx reports 1.30.6. The monitoring smoke check now waits at most 30 seconds for initial scrapes. Ruff check/format passed for the changed verification scripts. No application logic changed in this increment; the previous 55-test regression result was not rerun or relabeled as a new run.

## Frontend package remediation — 2026-10-19

The frontend runtime now upgrades zlib from Alpine's configured 3.24 repository and removes unused curl (including its automatically removed libcurl dependencies). The build installed zlib 1.3.2-r1. The scanner-listed curl fix was unavailable from the configured repository; curl was not referenced by the frontend configuration or startup scripts and had no reverse dependencies. Root is used only during image construction; the final Dockerfile restores USER 101.

The rebuilt frontend passed TypeScript/Vite build, HTTP 200 for its page and referenced JS/CSS assets, proxied backend readiness, nginx -t and runtime UID 101 verification. Docker Scout findings decreased from 36 to 11. Remaining frontend findings concern libxml2 and have no fixed version listed in this scan. Current SARIF and image identity are recorded in image-scan-summary.json. This change does not resolve vulnerabilities in other containers or establish production readiness.

## Unused XML module removal — 2026-10-19

Inspection of the effective Nginx configuration showed no dynamic module loading; this dashboard serves static files and proxies HTTP. Alpine reverse-dependency checks showed libxml2 was required by the optional nginx-module-xslt/nginx-module-njs packages and libxslt. Removing those two unused modules automatically removed libxml2, libxslt and other orphaned dependencies. The Dockerfile documents the runtime scope and retains USER 101.

The final rebuilt frontend image has zero Docker Scout findings in this scan, down from 11. This is a point-in-time image result, not proof of vulnerability absence or project-wide security completion. The remaining runtime images still have findings. The image identity and scan timestamp are recorded in image-scan-summary.json.

Validation: TypeScript/Vite build passed; page and referenced JS/CSS assets returned HTTP 200; proxied backend readiness returned HTTP 200; nginx -t passed; runtime UID was 101; package checks confirmed libxml2 and both optional modules are absent. Application source code was unchanged, so the Python regression suite was not rerun for this frontend packaging change.

## PostgreSQL OS patch — 2026-10-19

Compose now builds cloud-detective-ai-postgres from observability/postgres/Dockerfile, retaining postgres:17.11-alpine and its upstream entrypoint while upgrading zlib from the configured Alpine repository. The running container reports PostgreSQL 17.11 and zlib 1.3.2-r1. The scanner now targets this derived runtime image rather than the unpatched upstream image.

A fresh custom-format database dump was copied to the ignored .local-backups/pre-image-upgrade/postgres-pre-os-patch.dump before replacement. The existing pgdata volume was retained. Compose reported PostgreSQL healthy. verify_lifecycle.py passed real incident detection, role separation, failed dependency verification, successful independent recovery, idempotent replay and persistent timeline/audit checks. Ruff check/format passed for the scanner change.

All seven runtime image scans completed. PostgreSQL findings decreased from 72 to 71; the frontend remains at zero. The remaining PostgreSQL findings include required XML dependencies and Go dependencies bundled with the upstream gosu privilege-switch helper. These were retained: removing a required library or startup helper merely to change a scan count would break supported behavior. They remain unresolved and are not suppressed. Current identities and results are in image-scan-summary.json. No production security clearance is claimed.
