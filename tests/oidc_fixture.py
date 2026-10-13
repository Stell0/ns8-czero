# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable-QEMU only: provision private SSO fixtures and trusted test TLS."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

IDP_HOST = "idp.czero.test"
DOMAIN = "users.czero.test"
IDP_IMAGE = "ghcr.io/nethserver/idp:main@sha256:fb33441753aba1f7df20df8511cf992dd21202e527a5cd983707a36876ec5976"
KEYCLOAK_IMAGE = "ghcr.io/nethserver/idp-keycloak:main@sha256:c9327906f63fe03e0571bf94cbdd0839033e6b56cd14604b72a9100b223a833a"
LDAPROXY_IMAGE = "ghcr.io/nethserver/ldapproxy:1.4.0-dev.1@sha256:c06ad303d81596a50c5aef84f3220fdd0ef5e3af7e85ce8c252fe4f0ca36219e"
STATE = Path("/tmp/czero-oidc-fixture")
PHASE = "initialization"


def task(action, data):
    result = subprocess.run(["api-cli", "run", action, "--data=-"], input=json.dumps(data),
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        raise RuntimeError("Disposable SSO action failed: " + action)
    return json.loads(result.stdout) if result.stdout.strip() else None


def command(arguments):
    result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
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
    for username in ("c0member", "c0administrator"):
        task("module/" + ldap + "/add-user", {"user": username, "display_name": username,
                                             "password": payload["password"]})
    PHASE = "IdP installation"
    result = command(["add-module", IDP_IMAGE, "1"])
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
    # Test-only drop-ins: no DNS/CA testing flags or tools enter runtime images.
    base = Path(command(["runagent", "-m", module_id, "python3", "-c",
                        "import os; print(os.environ['AGENT_INSTALL_DIR'])"]).strip())
    public_ca = base / "czero-test-ca.pem"
    shutil.copyfile(STATE / "ca.pem", public_ca)
    public_ca.chmod(0o644)
    vpn = command(["runagent", "-m", "node", "python3", "-c",
        "import agent,os; print(agent.redis_connect().hget('node/'+os.environ['NODE_ID']+'/vpn','ip_address'))"]).strip()
    install = base / "systemd/user"
    for name in ("czero-pod.service", "czero.service"):
        text = command(["runagent", "-m", module_id, "systemctl", "--user", "cat", name])
        # Normalize systemd continuations and retain only the relevant Exec line.
        text = text.replace("\\\n", " ")
        if name == "czero-pod.service":
            original = next(line for line in text.splitlines() if line.startswith("ExecStartPre=") and "pod create" in line)
            amended = original.replace(" pod create ", " pod create --add-host=" + IDP_HOST + ":" + vpn + " ")
            contents = "[Service]\nExecStartPre=\nExecStartPre=/bin/rm -f %t/czero-pod.pid %t/czero.pod-id\n" + amended + "\n"
        else:
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


def cleanup():
    global PHASE
    PHASE = "fixture cleanup"
    if not (STATE / "resources.json").exists():
        return
    resources = json.loads((STATE / "resources.json").read_text())
    for key in ("idp", "ldap"):
        if resources.get(key):
            command(["remove-module", "--no-preserve", resources[key]])
    shutil.rmtree(STATE)


if __name__ == "__main__":
    try:
        operation = sys.argv[1]
        if operation == "setup":
            result = setup(json.loads(Path(sys.argv[2]).read_text()))
            print(json.dumps(result))
        elif operation == "network":
            apply_czero_network(sys.argv[2])
        elif operation == "cleanup":
            cleanup()
    except Exception as error:
        # Never echo native action outputs, certificates/keys or credentials.
        print("Disposable SSO fixture failed: " + PHASE + " (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
