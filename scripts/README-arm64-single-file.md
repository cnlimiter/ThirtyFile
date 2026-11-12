# ARM64 standalone verification

The `ARM64 single file` workflow builds the existing Dockerfile with its release profile on the standard `ubuntu-24.04-arm` runner. It extracts the static executable and license notices without publishing an image or a GitHub Release. Pushes to `ci/kylin-arm64-single-file` run it automatically; `workflow_dispatch` permits manual runs once GitHub has registered the workflow.

The job checks AArch64 ELF architecture, absence of an ELF interpreter and shared-library dependencies, and the program version. It copies only the executable into a fresh temporary working directory and starts it directly on the runner. The Python standard-library smoke script verifies health, embedded HTML/JavaScript/CSS and Chinese language resources, authentication failures, invalid names, missing files, Chinese filenames, file upload/download bytes, configuration updates, and persistence after a graceful stop and restart. The executable's SHA-256 is recorded in the evidence and must match the delivered artifact.

The successful artifact contains `thirtyfile-linux-arm64`, `SHA256SUMS`, this guide, `LICENSE` and `THIRD-PARTY-NOTICES`. Keep the license notices when redistributing the program. GitHub artifact downloads may discard executable permissions, so restore them before starting:

```sh
sha256sum -c SHA256SUMS
chmod 755 thirtyfile-linux-arm64
./thirtyfile-linux-arm64 --addr 127.0.0.1:8080 --data ./data
```

Open `http://127.0.0.1:8080` in a browser. On a new data directory, the administrator credential is generated and printed in the terminal. The program creates writable data beside the chosen data path, including the SQLite database, encryption key, thumbnails, temporary uploads and file storage (`data/blobs` by default). Preserve the entire data directory across restarts. Use an absolute `--data` path when starting from different working directories. A browser remains required for the interface; Node, Rust and Docker are build tools and are not needed to run the executable.

For an existing executable, the same smoke can be run with Python 3 on its matching Linux architecture:

```sh
python3 scripts/smoke-single-file.py /path/to/thirtyfile --evidence .dsh/evidence/single-file
```

A successful Ubuntu ARM64 run does not certify Galaxy Kylin. Record the exact Kylin edition/version, `uname -a`, CPU architecture, security policy and filesystem before target validation. Check direct startup, browser interaction, file operations and persistence there. Local folder spaces use `/proc/self/fd`, `openat` and inotify. Data storage needs filesystem locking and SQLite WAL support. Outbound HTTPS, FTPS, SMTP TLS and SSO use system trust certificates, and local time formatting may use system time-zone data. These OS resources are separate from the executable. The smoke uses loopback HTTP and does not validate external TLS or integrations.

The workflow uploads environment details, ELF reports, startup/restart logs and `smoke-result.json` as a separate evidence artifact, including on failure. Artifacts are retained for 14 days. No target-system claim should be based solely on the Ubuntu evidence.
