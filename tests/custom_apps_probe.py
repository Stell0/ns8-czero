#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic native fixture, called only inside the disposable Robot module."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(os.environ['AGENT_INSTALL_DIR']) / 'bin'))
import czero_custom_apps as hosting

OLD = 'docker.io/nginxinc/nginx-unprivileged@sha256:c97ff0bf7cbae369953c6da1232ec14ad9f971d66360c5698db0856a4cd657a0'
NEW = 'docker.io/nginxinc/nginx-unprivileged@sha256:5aea7cc516b419e3526f47dd1531be31a56a046cfe44754d94f9383e13e2ee99'
APPS = ('acceptance-one', 'acceptance-two')
host = hosting.Host()


def verify(restored=False):
	results = [host.inspect(app) for app in APPS]
	assert results[0]['port'] != results[1]['port']
	assert results[0]['image'] == NEW and results[1]['image'] == OLD
	assert results[0]['ready'] == (not restored)
	assert not results[1]['running']
	if restored:
		assert not any(result['enabled'] for result in results)
		for app in APPS:
			host.start(host.record(app))
	for app in APPS:
		if not hosting.active(host.unit(app)):
			host.start(host.record(app))
		assert hosting.run('podman', 'exec', host.name(app), 'cat', '/usr/share/nginx/html/retained.txt').strip() == app.encode()
		assert hosting.run('podman', 'exec', host.name(app), 'printenv', 'SYNTHETIC_NAME').strip() == app.encode()
		host.stop(host.record(app))
	if not restored:
		host.start(host.record(APPS[0]))


phase = sys.argv[1]
if phase == 'seed':
	with host.locked():
		assert not host.records(), 'fixture requires a clean disposable registry'
		for app in APPS:
			manifest = {'version': 1, 'id': app, 'image': OLD, 'http_port': 8080,
				'readiness_path': '/', 'data_path': '/usr/share/nginx/html', 'memory_mb': 128,
				'pids_limit': 128, 'shutdown_seconds': 15, 'environment': {'SYNTHETIC_NAME': app}}
			host.deploy(manifest, start=True)
			hosting.run('podman', 'exec', '--user=0', host.name(app), 'sh', '-c', 'printf "%s" "$SYNTHETIC_NAME" > /usr/share/nginx/html/retained.txt')
		host.stop(host.record(APPS[1]))
		manifest = host.manifest(host.record(APPS[0]))
		manifest['image'] = NEW
		host.deploy(manifest, update=True)
		verify()
elif phase == 'verify':
	with host.locked():
		verify()
elif phase == 'restored':
	with host.locked():
		verify(restored=True)
elif phase == 'backup-failure':
	original = subprocess.run
	def fail_export(command, **options):
		if command[:3] == ['podman', 'volume', 'export']:
			raise OSError('synthetic full backup filesystem')
		return original(command, **options)
	subprocess.run = fail_export
	try:
		try:
			runpy.run_path(str(Path(os.environ['AGENT_INSTALL_DIR']) / 'bin/module-dump-state'))
		except OSError:
			pass
		else:
			raise AssertionError('expected synthetic backup failure')
	finally:
		subprocess.run = original
	assert not host.recovery.exists()
	assert host.inspect(APPS[0])['ready']
elif phase == 'interrupt':
	# Returning before cleanup simulates loss of the native backup parent process.
	runpy.run_path(str(Path(os.environ['AGENT_INSTALL_DIR']) / 'bin/module-dump-state'))
	assert host.recovery.exists()
	assert not any(host.inspect(app)['running'] for app in APPS)
else:
	raise ValueError('unknown fixture phase')
print(json.dumps({'phase': phase, 'verified': True}))
