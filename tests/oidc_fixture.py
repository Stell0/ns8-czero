# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable-QEMU only: provision private SSO fixtures and trusted test TLS."""
import base64
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

IDP_HOST = "idp.czero.test"
DOMAIN = "users.czero.test"
IDP_IMAGE = "ghcr.io/nethserver/idp:0.3.1@sha256:1c6ee1b6b393e20b4e8fcd1bf3733058a5b86409f12a4288e83a26d17bc0631f"
KEYCLOAK_IMAGE = "ghcr.io/nethserver/idp-keycloak:0.3.1@sha256:175bddd31f8ed3fa47a92a85e607655d0e752db5dee19ff04c3011d1baf3826d"
LDAPROXY_IMAGE = "ghcr.io/nethserver/ldapproxy:1.4.0@sha256:3dc6fc3a2bc4ae3d7775bdbd934f6f1295b80933d6fd11b2bf2301897b4cd16d"
STATE = Path("/tmp/czero-oidc-fixture")
PHASE = "initialization"


def task(action, data):
    result = subprocess.run(["api-cli", "run", action, "--data=-"], input=json.dumps(data),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError("Disposable SSO action failed: " + action)
    return json.loads(result.stdout) if result.stdout.strip() else None


def command(arguments, *, merge_stderr=False, timeout=180):
    result = subprocess.run(arguments, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Disposable SSO fixture command failed")
    return result.stdout.decode()


def setup(payload):
    global PHASE
    PHASE = "disposable ldapproxy prerequisite"
    STATE.mkdir(mode=0o700, exist_ok=True)
    (STATE / "personas.json").write_text(json.dumps(payload))
    (STATE / "personas.json").chmod(0o600)
    # Match maintained IdP QEMU: Keycloak's pod needs a non-loopback listener.
    # This prerequisite update is confined to this disposable VM.
    proxy = command(["runagent", "-m", "node", "python3", "-c",
        "import agent,os; print(agent.redis_connect().get('node/'+os.environ['NODE_ID']+'/default_instance/ldapproxy'))"]).strip()
    task("update-module", {"force": True, "module_url": LDAPROXY_IMAGE, "instances": [proxy]})
    PHASE = "LDAP provisioning"
    ldap = task("add-internal-provider", {"image": "openldap", "node": 1})["module_id"]
    (STATE / "resources.json").write_text(json.dumps({"ldap": ldap}))
    task("module/" + ldap + "/configure-module", {"domain": DOMAIN, "admuser": "c0owner",
         "admpass": payload["password"], "provision": "new-domain"})
    for username in ("c0member", "c0administrator", "c0denied"):
        task("module/" + ldap + "/add-user", {"user": username, "display_name": username,
                                             "password": payload["password"]})
    PHASE = "IdP installation"
    result = command(["add-module", IDP_IMAGE, "1"], timeout=480)
    import ast
    try:
        installed = json.loads(result)
    except json.JSONDecodeError:
        installed = ast.literal_eval(result)
    idp = installed["module_id"]
    (STATE / "resources.json").write_text(json.dumps({"ldap": ldap, "idp": idp}))
    command(["runagent", "-m", idp, "python3", "-c",
             "import agent; agent.set_env('IDP_KEYCLOAK_IMAGE'," + repr(KEYCLOAK_IMAGE) + ")"])
    PHASE = "trusted test certificate"
    ca = STATE / "ca.pem"
    key = STATE / "ca.key"
    leaf_key = STATE / "leaf.key"
    leaf = STATE / "leaf.pem"
    csr = STATE / "leaf.csr"
    extension = STATE / "leaf.ext"
    extension.write_text("subjectAltName=DNS:" + IDP_HOST + ",DNS:" + payload["host"] +
                         "\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n")
    command(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
             "-subj", "/CN=Czero disposable test CA", "-keyout", str(key), "-out", str(ca),
             "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
    command(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=" + IDP_HOST,
             "-keyout", str(leaf_key), "-out", str(csr)])
    command(["openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(key),
             "-CAcreateserial", "-days", "2", "-extfile", str(extension), "-out", str(leaf)])
    key.chmod(0o600)
    leaf_key.chmod(0o600)
    if shutil.which("update-ca-trust"):
        target = Path("/etc/pki/ca-trust/source/anchors/czero-test-ca.crt")
        shutil.copyfile(ca, target)
        command(["update-ca-trust"])
    else:
        target = Path("/usr/local/share/ca-certificates/czero-test-ca.crt")
        shutil.copyfile(ca, target)
        command(["update-ca-certificates"])
    with Path("/etc/hosts").open("a") as output:
        output.write("\n127.0.0.1 " + IDP_HOST + " " + payload["host"] + "\n")
    # Chain verification is enabled; the private CA is trusted only in this VM.
    chain = leaf.read_bytes() + ca.read_bytes()
    task("module/traefik1/upload-certificate", {"certFile": base64.b64encode(chain).decode(),
          "keyFile": base64.b64encode(leaf_key.read_bytes()).decode()})
    # Current Traefik has no native access-log settings action. Disable its
    # default query-bearing access log only in this disposable SSO fixture.
    code = ("import agent,os,pathlib,yaml\n"
            "p=pathlib.Path(os.environ['AGENT_STATE_DIR'])/'traefik.yaml'\n"
            "config=yaml.safe_load(p.read_text())\n"
            "config.pop('accessLog',None)\n"
            "with agent.safe_open(str(p)) as output: yaml.safe_dump(config,output)\n")
    command(["runagent", "-m", "traefik1", "python3", "-c", code])
    command(["runagent", "-m", "traefik1", "systemctl", "--user", "restart", "traefik.service"])
    PHASE = "IdP configuration"
    task("module/" + idp + "/configure-module", {"host": IDP_HOST, "lets_encrypt": False})
    # Use the SDK rather than depend on the cluster action output shape.
    PHASE = "IdP discovery"
    provider = command(["runagent", "-m", "node", "python3", "-c",
        "import agent; p=agent.list_service_providers(agent.redis_connect(),'oidc','http'); print(next(x['module_uuid'] for x in p if x['module_id']==" + repr(idp) + "))"])
    (STATE / "resources.json").write_text(json.dumps({"ldap": ldap, "idp": idp, "provider": provider.strip()}))
    return {"domain": DOMAIN, "idp": provider.strip(), "owner": "c0owner"}


def apply_czero_network(module_id):
    global PHASE
    PHASE = "application test network"
    # Native configuration owns local-provider routing. Only a trusted test CA
    # needs a disposable drop-in; no fixture DNS override may mask regressions.
    base = Path(command(["runagent", "-m", module_id, "python3", "-c",
                        "import os; print(os.environ['AGENT_INSTALL_DIR'])"]).strip())
    public_ca = base / "czero-test-ca.pem"
    shutil.copyfile(STATE / "ca.pem", public_ca)
    public_ca.chmod(0o644)
    # Rootless Podman must own the bind source to apply SELinux's :z label.
    shutil.chown(public_ca, user=module_id, group=module_id)
    install = base / "systemd/user"
    for name in ("czero.service", "czero-worker.service"):
        text = command(["runagent", "-m", module_id, "systemctl", "--user", "cat", name])
        # Normalize systemd continuations and retain only the relevant Exec line.
        text = text.replace("\\\n", " ")
        original = next(line for line in text.splitlines() if line.startswith("ExecStart=") and "podman run" in line)
        amended = original.replace(" run ", " run --volume=" + str(public_ca) + ":/czero-test-ca.pem:ro,z --env=SSL_CERT_FILE=/czero-test-ca.pem ")
        contents = "[Service]\nExecStart=\n" + amended + "\n"
        directory = install / (name + ".d")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "90-test-oidc.conf").write_text(contents)
        shutil.chown(directory, user=module_id, group=module_id)
        shutil.chown(directory / "90-test-oidc.conf", user=module_id, group=module_id)
    command(["runagent", "-m", module_id, "systemctl", "--user", "daemon-reload"])
    command(["runagent", "-m", module_id, "systemctl", "--user", "try-restart",
             "czero-pod.service", "czero-postgres.service", "czero.service"])


def reuse(host):
    """Reuse only this VM's exact existing provider and TLS/persona fixture."""
    global PHASE
    PHASE = 'existing disposable SSO fixture'
    personas = json.loads((STATE / 'personas.json').read_text())
    resources = json.loads((STATE / 'resources.json').read_text())
    if host != personas['host'] or not host.endswith('.test'):
        raise RuntimeError('Disposable SSO host changed')
    provider = command(['runagent', '-m', 'node', 'python3', '-c',
        "import agent; p=agent.list_service_providers(agent.redis_connect(),'oidc','http'); "
        "print(next(x['module_uuid'] for x in p if x['module_id']==" + repr(resources['idp']) + "))"]).strip()
    if provider != resources['provider']:
        raise RuntimeError('Disposable SSO provider changed')
    command(['openssl', 'x509', '-in', str(STATE / 'leaf.pem'), '-noout', '-checkend', '0'])
    return {'domain': DOMAIN, 'idp': provider, 'owner': 'c0owner'}


def cleanup():
    global PHASE
    PHASE = "fixture cleanup"
    if (STATE / 'retrieval-pid').exists():
        import signal
        pid = int((STATE / 'retrieval-pid').read_text())
        cmdline = Path('/proc') / str(pid) / 'cmdline'
        if cmdline.exists() and b'retrieval_fixture.py\x00serve' in cmdline.read_bytes():
            os.kill(pid, signal.SIGTERM)
    if not (STATE / "resources.json").exists():
        return
    resources = json.loads((STATE / "resources.json").read_text())
    for key in ("idp", "ldap"):
        if resources.get(key):
            command(["remove-module", "--no-preserve", resources[key]])
    shutil.rmtree(STATE)


def check_private_logs(module_id):
    global PHASE
    PHASE = 'access log privacy'
    for module, container in ((module_id, 'czero'), ('traefik1', 'traefik')):
        output = command(['runagent', '-m', module, 'podman', 'logs', container], merge_stderr=True)
        if re.search(r'[?&](?:code|state|session_code)=', output):
            raise RuntimeError('OAuth query values found in disposable access logs')


if __name__ == "__main__":
    try:
        operation = sys.argv[1]
        if operation == "setup":
            result = setup(json.loads(Path(sys.argv[2]).read_text()))
            print(json.dumps(result))
        elif operation == 'reuse':
            print(json.dumps(reuse(sys.argv[2])))
        elif operation == "network":
            apply_czero_network(sys.argv[2])
        elif operation == "cleanup":
            cleanup()
        elif operation == "check-logs":
            check_private_logs(sys.argv[2])
    except Exception as error:
        # Never echo native action outputs, certificates/keys or credentials.
        print("Disposable SSO fixture failed: " + PHASE + " (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
