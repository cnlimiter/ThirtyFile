# ThirtyFile for Windows AMD64

Extract the entire artifact into a writable folder. It contains `thirtyfile-windows-amd64.exe`, `SHA256SUMS`, this guide, `LICENSE`, and `THIRD-PARTY-NOTICES`. Keep the license files when redistributing the executable. Application resources, including the browser interface and SQLite migrations, are embedded in the executable. Writable data is created at runtime.

In PowerShell, from the extracted folder:

```powershell
.\thirtyfile-windows-amd64.exe --addr 127.0.0.1:8080 --data .\data
```

Open `http://127.0.0.1:8080` in a browser. Sign in as `admin`; on first startup a random administrator credential is printed in the terminal. Stop normally with Ctrl+C in that terminal. Start again with the same command and preserve the entire `data` folder: it contains the database, encryption key, settings, thumbnails, temporary uploads, and file storage (`data\blobs` by default). Use an absolute `--data` path if starting from different working directories. Double-clicking the executable uses its default listen address `0.0.0.0:8080`; use the command above to bind to loopback explicitly.

Node, Rust, Python and Docker are not required to run the program. The build targets `x86_64-pc-windows-msvc` with a static C runtime. CI inspects PE architecture and imported DLLs and rejects imports of VC++ runtime DLLs. Windows system DLLs and the Windows certificate store remain operating-system dependencies. CI runs on Windows Server 2022 with developer tools installed; it does not constitute a test on a clean Windows 10/11 machine without those tools. The binary is unsigned, so Windows may display a publisher or SmartScreen prompt. Local folder safety and external integrations need additional validation before exposing arbitrary existing folders or making the service available to other machines.

Check SHA-256 from PowerShell:

```powershell
Get-Content .\SHA256SUMS | ForEach-Object {
    $expected, $name = $_ -split '  ', 2
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $name).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "Checksum mismatch: $name" }
    Write-Output "$name`: OK"
}
```

The `Windows AMD64 single file` GitHub Actions workflow builds the frontend first, then compiles the release executable and generates notices for the Windows target. It verifies AMD64 PE32+, imports, direct startup in a fresh directory containing Chinese characters and spaces, embedded web resources, authentication, Chinese file upload/download bytes, graceful Ctrl+C shutdown and persistence after restart. A helper attaches to the server's independent console to send Ctrl+C; force termination is only used to clean up failed checks. The smoke uses temporary data, not an existing installation.

Re-run the workflow on the desired commit to rebuild. The successful executable and a separate evidence artifact are retained for 14 days. The evidence includes Windows version, source commit, PE checks, imports, startup/restart logs, and the tested executable's SHA-256. Downloaded executable checksums must agree with both `SHA256SUMS` and `smoke-result.json`.
