# Custom application hosting, contract 1

This candidate adds an **NS8 operator CLI**, separate from C0's REST/MCP knowledge
service. Release and native acceptance are tracked in [PLAN](../PLAN.md).
An installer must check `czero-custom-app contract` before changing an instance.
Contract 1 accepts one digest-pinned container and one named data volume per app.
It supports up to 32 registered applications, including removed registrations
whose data is retained. It has no sidecars, deployment hooks or marketplace.

## Trust and storage

Applications share C0's Unix account and its administrative trust boundary.
Install only trusted images. Each app has its own Podman network, loopback HTTP
port, systemd service, private environment and named volume. It receives neither
the Podman socket nor C0's files or database credentials. Supply scoped C0 API
credentials and explicit space selectors; connect to C0 using its HTTPS endpoint.
Network separation does not make mutually untrusted code safe within one account.

Persistent registration is `state/custom-apps/<id>/record.json`. Each immutable
deployment directory contains a manifest and a private `environment` file.
Updates retain the previous deployment record and image identity. Generated
`c0app-<id>.service` units and `c0app-<id>-data` volumes never reuse packaged C0
names. Inspection returns deployment and health metadata, never configuration
values. Application stdout/stderr goes to journald under `c0app-<id>`; applications
are responsible for sanitizing their own logs.

## Install and operate

Run as the NS8 administrator, replacing `czero1` with the intended instance:

```sh
runagent -m czero1 czero-custom-app contract
runagent -m czero1 czero-custom-app install /path/to/manifest.json --secrets-dir /path/to/private-files
runagent -m czero1 czero-custom-app start support-bot
runagent -m czero1 czero-custom-app inspect support-bot
runagent -m czero1 czero-custom-app list
runagent -m czero1 czero-custom-app stop support-bot
runagent -m czero1 czero-custom-app update /path/to/replacement.json --secrets-dir /path/to/private-files
runagent -m czero1 czero-custom-app remove support-bot
```

Input paths must be readable by that module account. Secret files must be regular
files, mode 0600, with one nonempty line. The manifest maps environment names to
basenames in the explicitly selected secret directory. Files are copied into the
private deployment environment; later changes to source files do not change a
running application. Pass the complete desired configuration again when updating.
Never place secrets in Git or in the NS8 shared environment/Redis store.

Installation starts stopped unless `--start` is supplied. Start verifies HTTP 200
at the readiness path before enabling reboot startup. Readiness uses loopback,
does not follow redirects, and does not use ambient HTTP proxies. A configured
hostname creates a distinct Traefik route with HTTPS redirection and verified
Let's Encrypt provisioning. DNS must already point to this node. Route identity
or hostname conflicts fail; a restore creates its route only on explicit start.
`inspect` reports running and ready independently of C0's own runtime status.

The [schema](../imageroot/etc/custom-app-v1.schema.json) and
[minimal reference manifest](../examples/custom-app/manifest.json) describe all
fields. The reference uses the upstream unprivileged nginx image, with its image
identity verified through the registry. It serves a persistent document directory
and has no external write credentials. It is a hosting demonstration, not the
support bot. Native acceptance uses two independent copies with synthetic files.

NS8 reserves 33 TCP ports on a new C0 instance: one for C0 and 32 app slots. An
upgraded instance keeps C0's original port and obtains the additional pool through
`agent.allocate_ports(..., keep_existing=True)`. The private allocation receipt is
host-specific and excluded from backups. An interrupted allocation is marked
uncertain and is never repeated automatically. An operator must reconcile the
module's actual native allocation before repairing that receipt; never deallocate
all C0 ports to repair one app. Removing an app retains its slot and data; installing
the same ID again reuses them. Module removal releases the module's native pool.

## Private registry images

Configure registry credentials in Podman under the C0 module account. C0's
`CZERO_GITHUB_TOKEN_FILE` is for the source worker's GitHub API requests and does
not authenticate image pulls.

For a private GitHub Container Registry image, create a personal access token
(classic) with only `read:packages`. The GitHub account must have read access to
the package, either directly or through inherited repository access. Authorize
the token for organization SSO when required. See [GitHub's registry authentication
guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-with-a-personal-access-token-classic).

From the NS8 node, pass the token over standard input from a private file or a
password manager. Replace `GITHUB_USERNAME` and the example path:

```sh
runagent -m czero1 sh -c '
    umask 077
    auth_dir="${XDG_CONFIG_HOME:-$HOME/.config}/containers"
    mkdir -p "$auth_dir" &&
        podman login --authfile "$auth_dir/auth.json" --username "$1" --password-stdin ghcr.io &&
        chmod 0600 "$auth_dir/auth.json"
' sh GITHUB_USERNAME < /path/to/private/ghcr-token
```

This uses Podman's persistent configuration directory. The default login file
under the runtime directory is temporary. Keep registry credentials out of
application manifests, container environments and the shared NS8 configuration.
Provision the registry login again on a clean restore destination before
restoring an app that uses a private image. See the [Podman login
options](https://docs.podman.io/en/latest/markdown/podman-login.1.html) and
[credential lookup order](https://github.com/containers/image/blob/main/docs/containers-auth.json.5.md).

## Updates and recovery

Custom image updates are independent from C0 upgrades. Install and update pull
the manifest's pinned digest before starting or replacing the app. The pull can
take up to ten minutes. An update completes the pull before stopping the old
container, then starts the replacement on the same volume. Normal systemd starts
use the pinned image in local storage when available. The readiness check after
launch has its own 60-second window. A stopped application stays stopped. A failed replacement retains its
deployment and reports failure. There is no automatic image rollback: a newer
image may already have migrated its data. Reverting requires an explicit compatible
manifest or a verified data restore chosen by the operator.

All CLI mutations take an account-local lock. Backup and C0 maintenance leave a
durable recovery record that blocks app mutations between native lifecycle steps.
C0 updates quiesce apps, preserve manifests/configuration/volumes, regenerate units
and resume the previously running set. `regenerate` recreates units without changing
image identities or starting services. App failures remain visible separately.

If a process or machine stops during maintenance, the recovery timer checks the
recorded owner PID, process start identity and boot ID. It restores C0's writer
states first, then the saved running apps. It retains the record on any recovery
failure. An active owner prevents recovery; the operator may inspect and run:

```sh
runagent -m czero1 czero-custom-app recover
```

Do not delete a recovery record merely to unblock changes. Verify the original
operation has ended and complete recovery. A failed hook or health check does not
constitute a successful backup, restore or update.

## Native backup and restore

Use NS8's encrypted off-machine backups. A local volume cannot recover a lost
machine. C0's native dump procedure records and stops custom apps, then quiesces
C0's SQL/file writers. It exports each app volume to
`state/custom-app-backup/<id>.tar`, records the exact manifest generation, digest
and SHA-256, and includes that directory plus `state/custom-apps` in the same
Restic backup. It does not change NS8 Core's backup machinery.

Allow free temporary disk space at least equal to the sum of all app volume
exports plus the C0 PostgreSQL dump, with operating headroom. App and C0 writes
are unavailable from quiescing until the native backup copy and cleanup finish.
Each app must honor its shutdown timeout; the container is terminated after the
configured grace period. An application must recover interrupted work on startup.

Cleanup restores prior service states, including pending automatic restarts, and
removes exports. Explicitly stopped applications stay stopped. Dump/export failures
attempt cleanup immediately. Some NS8 backup failures can exit before cleanup;
the durable recovery record and timer handle the abandoned operation. A failed
recovery keeps both the record and exports for inspection and retry.

Restore validates the complete inventory and archive checksums before importing
any app volume. It refuses to overwrite existing unreceipted volumes and records
completed imports for retry. An interrupted import without a receipt requires
operator investigation of that disposable destination; it is not blindly repeated.
Active registrations require their exact image; unavailable images fail explicitly.
Removed registrations restore their retained data without pulling an obsolete image
or recreating a service. The destination
gets its own port allocation and generated units; all restored apps remain disabled
and stopped. No custom route is activated until `start`, preventing external writes
from a restored copy before operator reconciliation. Choose unused destination
hostnames before activating if the original remains available.

Removing an app keeps its data and private deployment history. Removing **C0**
removes the entire shared Unix account and its app data. Export a verified native
backup before module removal. Restoring C0 also restores its registered apps, not
only the knowledge database; coordinate maintenance with their owners.

## Acceptance

Focused tests exercise validation, isolation, port uncertainty, route ownership,
update failure, cold export, failed recovery and stopped/checksummed restore.
The existing native Debian/Rocky suite now installs two synthetic apps, updates
one image, preserves both through C0 update and user-manager restart, injects an
export failure, abandons a prepared backup, then restores a native encrypted
backup into a clean module slot and verifies retained data/configuration.
Robot dry runs and mocked tests do not establish that native acceptance.

## Node Grafana dashboard

An operator can include one exported Grafana dashboard object in the optional
`grafana_dashboard` manifest field. The host registers this object in the NS8
metrics module dashboard registry on install, update and restore. Give the
dashboard a title and panels, use datasources available on the node, and keep
its serialized size within 256 KiB. The node generates a stable UID for each
module and application pair. Omitting the field on a later update or removing
the application withdraws its dashboard. Dashboard JSON is visible to Grafana
users. Keep credentials in the application's secret files.
