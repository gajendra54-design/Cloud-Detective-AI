# Publication security review — 2026-10-20

## Scope and findings

Reviewed the project source, scripts, configuration, documentation, generated reports and local artifacts for known local credential values, common provider-key/private-key patterns, embedded credential URLs and private-network URLs. Initial traversal covered 443 files, excluding installed .venv and node_modules dependency trees. These third-party dependency directories are excluded from publication; this review is not a third-party source audit or a guarantee that every possible secret format is detected.

- Actual local credentials belong in ignored .env only. No real provider API keys or private-key files were identified in publishable first-party source.
- POSTGRES_PASSWORD and DEMO_CONTROL_TOKEN were still using public example placeholders locally. Both were privately replaced, including the PostgreSQL role password, without deleting its volume. No credential values are recorded here. Prior environment recovery material remains in ignored .local-backups.
- setup_env.py now generates missing, empty and placeholder credentials while preserving valid existing values. Regression coverage verifies replacement and repeat-run preservation.
- .env.example contains placeholder values and non-secret service configuration only.
- Hardcoded unit-test tokens/passwords are synthetic fixtures used with isolated test databases. They are not production credentials and should not be used to configure a running system.
- The Compose database URL obtains its password through environment substitution. Localhost, Docker service hostnames and host.docker.internal URLs are intentional local routing, not private remote endpoints.
- Credential-URL pattern matches in retained SARIF reports occur inside upstream vulnerability advisory examples (CVE-2026-81870), not application credentials.

If you previously copied the old example values to any other installation, replace them there too. If any real credential has already been shared or committed elsewhere, rotate it with its issuer; ignoring a file does not remove it from existing Git history. No .git history existed in this project at preparation time, and no remote history was inspected.

## Publication exclusions and cleanup

.gitignore excludes all .env variants except .env.example, private keys, database files/dumps, local backups, uploads/logs, Python environments/caches, node_modules/vendor, build outputs and IDE/OS files. Docker build exclusions also protect private local files.

Removed generated Python bytecode, pytest/Ruff caches and TypeScript incremental metadata. Installed dependencies and private backups were preserved and ignored. Tests, historical verification records, scans and screenshots were retained as engineering evidence. No ambiguous user-authored files were deleted. No leftover debugger statements were found in application code.

Before publishing, inspect screenshots yourself for personal information and review the staged file list as described in publishing.md. Automated text searches do not inspect pixels in screenshots or encrypted/compressed backup contents; backups and local data must remain excluded. Container vulnerability findings are separately documented in container-security.md and remain unresolved.

## Preparation validation

A clean copy containing only the publication file selection was tested with newly generated credentials and empty PostgreSQL/Grafana volumes. README setup/build/start instructions passed, followed by the real scenario, lifecycle and trace/Grafana checks. The isolated test containers/volumes were removed and the original local stack was restored. This used the same computer and cached build dependencies, not an independent-machine test.

57 Python tests passed (one existing Starlette/httpx deprecation warning); Ruff, frontend ESLint and TypeScript/Vite build passed. Final publishable-file checks found no current local credential values or excluded private paths. Results: publishing-verification.json. No Git repository was initialized in the project root, and no commit, remote creation or push was performed. A temporary isolated Git directory used only to verify ignore rules was removed after validation.
