# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('czero_custom_apps', ROOT / 'imageroot/bin/czero_custom_apps.py')
hosting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosting)


def manifest(app='first', **changes):
	return dict(version=1, id=app, image='registry.example.test/apps/demo@sha256:' + 'a' * 64,
		http_port=8080, readiness_path='/ready', data_path='/data', memory_mb=256,
		pids_limit=128, shutdown_seconds=30, **changes)


@pytest.fixture
def platform(monkeypatch, tmp_path):
	state = tmp_path / 'state'
	state.mkdir()
	monkeypatch.setenv('AGENT_STATE_DIR', str(state))
	monkeypatch.setenv('MODULE_ID', 'czero9')
	monkeypatch.setenv('TCP_PORT', '20000')
	monkeypatch.setenv('TCP_PORTS_RANGE', '20000-20032')
	host = hosting.Host(state, tmp_path / 'units')
	volumes, running, enabled, routes, calls = {}, set(), set(), {}, []
	fail, activating = set(), set()
	def run(command, **options):
		calls.append(command)
		if tuple(command) in fail:
			return SimpleNamespace(returncode=1, stdout=b'private-error', stderr=b'secret')
		if command[:3] == ['systemctl', '--user', 'is-active']:
			return SimpleNamespace(returncode=0 if command[-1] in running else 3)
		if command[:3] == ['systemctl', '--user', 'show']:
			state = b'activating' if command[-1] in activating else b'active' if command[-1] in running else b'inactive'
			return SimpleNamespace(returncode=0, stdout=state + b'\n')
		if command[:3] == ['systemctl', '--user', 'start']:
			activating.discard(command[-1])
			running.add(command[-1])
		if command[:3] == ['systemctl', '--user', 'stop']:
			activating.discard(command[-1])
			running.discard(command[-1])
		if command[:3] == ['systemctl', '--user', 'enable']:
			enabled.add(command[-1])
		if command[:3] == ['systemctl', '--user', 'disable']:
			enabled.discard(command[-1])
			if '--now' in command:
				running.discard(command[-1])
		if command[:3] == ['podman', 'volume', 'create']:
			if command[-1] in volumes:
				return SimpleNamespace(returncode=125, stdout=b'', stderr=b'volume already exists')
			volumes[command[-1]] = b''
		if command[:3] == ['podman', 'volume', 'export']:
			options['stdout'].write(volumes[command[-1]])
		if command[:3] == ['podman', 'volume', 'import']:
			volumes[command[-2]] = Path(command[-1]).read_bytes()
		if command[:3] == ['podman', 'volume', 'exists']:
			return SimpleNamespace(returncode=0 if command[-1] in volumes else 1)
		return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
	def task(*, action, data, **kw):
		instance = data['instance']
		if action == 'set-route':
			routes[instance] = data
		elif action == 'delete-route':
			routes.pop(instance, None)
		return {'exit_code': 0, 'output': routes.get(instance, {})}
	agent = SimpleNamespace(resolve_agent_id=lambda value: 'module/traefik1', tasks=SimpleNamespace(run=task),
		http_route_in_use=lambda domain: any(r.get('host') == domain for r in routes.values()))
	monkeypatch.setitem(sys.modules, 'agent', agent)
	monkeypatch.setattr(subprocess, 'run', run)
	monkeypatch.setattr(host, 'ready', lambda record, seconds=60: host.unit(record['id']) in running)
	return SimpleNamespace(host=host, volumes=volumes, running=running, enabled=enabled, routes=routes, calls=calls, fail=fail, activating=activating, agent=agent)


@pytest.mark.parametrize('field,value', [
	('id', '../other'), ('id', 'czero\nExecStart=evil'), ('image', 'registry.test/app:latest'),
	('image', '--privileged'), ('http_port', True), ('version', True), ('pids_limit', 0),
	('shutdown_seconds', 7200), ('data_path', '/data/../etc'), ('data_path', '/etc'),
	('readiness_path', '//evil.test/'), ('hostname', 'example.test\nInjected'),
	('environment', {'TOKEN': 'first\nNEXT=bad'}), ('secrets', {'TOKEN': '../key'}),
])
def test_manifest_rejects_unsafe_or_unsupported_values(field, value):
	data = manifest()
	data[field] = value
	with pytest.raises(hosting.HostingError):
		hosting.validate(data)


def test_two_applications_have_independent_configuration_units_ports_and_volumes(platform, tmp_path):
	p = platform
	secret = tmp_path / 'key'
	secret.write_text('never-report-this-value\n')
	secret.chmod(0o600)
	with p.host.locked():
		first = p.host.deploy(manifest(secrets={'TOKEN': 'key'}, hostname='one.example.test'), tmp_path, start=True)
		second = p.host.deploy(manifest('second', environment={'MODE': 'other'}, hostname='two.example.test'), start=True)
	assert first['ready'] and second['ready'] and first['port'] != second['port']
	assert set(p.volumes) == {'c0app-first-data', 'c0app-second-data'}
	assert len(p.routes) == 2
	assert 'never-report-this-value' not in json.dumps(first) + json.dumps(second) + json.dumps(p.calls)
	for record in p.host.records():
		unit = (p.host.units / p.host.unit(record['id'])).read_text()
		assert 'runagent czero-custom-app launch ' + record['id'] in unit
		assert 'never-report-this-value' not in unit
		assert (p.host.root / record['id'] / record['generation'] / 'environment').stat().st_mode & 0o777 == 0o600


def test_update_stops_old_image_before_replacement_and_preserves_data(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	previous = p.host.record('first')
	p.volumes['c0app-first-data'] = b'durable sqlite data'
	new = manifest()
	new['image'] = new['image'].replace('a' * 64, 'b' * 64)
	p.host.deploy(new, update=True)
	current = p.host.record('first')
	assert current['generation'] != previous['generation']
	assert current['previous_generation'] == previous['generation']
	assert hosting.read_json(p.host.root / 'first' / previous['generation'] / 'deployment.json') == previous
	assert p.volumes['c0app-first-data'] == b'durable sqlite data'
	assert current['enabled'] and current['port'] == previous['port']
	stop = p.calls.index(['systemctl', '--user', 'stop', 'c0app-first.service'])
	assert ['systemctl', '--user', 'start', 'c0app-first.service'] in p.calls[stop + 1:]


def test_failed_update_remains_visible_without_automatic_image_rollback(platform, monkeypatch):
	p = platform
	p.host.deploy(manifest(), start=True)
	new = manifest()
	new['image'] = new['image'].replace('a' * 64, 'b' * 64)
	monkeypatch.setattr(p.host, 'ready', lambda *a, **kw: False)
	with pytest.raises(hosting.HostingError, match='not_ready'):
		p.host.deploy(new, update=True)
	assert p.host.inspect('first')['status'] == 'deployment_failed'
	assert p.host.inspect('first')['image'] == new['image']
	assert 'c0app-first.service' not in p.running


def test_stopped_application_stays_stopped_across_update(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.stop(p.host.record('first'))
	p.host.deploy(manifest(), update=True)
	assert not p.host.inspect('first')['enabled']
	assert not p.host.inspect('first')['running']


def test_remove_preserves_data_and_can_reinstall(platform):
	p = platform
	p.host.deploy(manifest(hostname='one.example.test'), start=True)
	p.volumes['c0app-first-data'] = b'retained'
	p.host.remove(p.host.record('first'))
	assert not p.routes and not p.running
	assert p.volumes['c0app-first-data'] == b'retained'
	assert not (p.host.units / 'c0app-first.service').exists()
	p.host.deploy(manifest())
	assert p.volumes['c0app-first-data'] == b'retained'


def test_cold_backup_blocks_changes_until_cleanup_and_restores_running_set(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.deploy(manifest('second'))
	p.volumes.update({'c0app-first-data': b'first-data', 'c0app-second-data': b'second-data'})
	with p.host.locked():
		p.host.quiesce('backup')
		p.host.export()
	assert not p.running
	with pytest.raises(hosting.HostingError, match='recovery_required'):
		with p.host.locked():
			pytest.fail('mutation admitted during backup')
	assert (p.host.exports / 'first.tar').read_bytes() == b'first-data'
	assert (p.host.exports / 'second.tar').read_bytes() == b'second-data'
	with p.host.locked(recovery=True):
		p.host.resume()
	assert p.running == {'c0app-first.service'}
	assert not p.host.recovery.exists() and not p.host.exports.exists()


@pytest.mark.parametrize('kind', ['backup', 'update'])
def test_maintenance_resumes_pending_restart_and_preserves_stopped_app(platform, kind):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.deploy(manifest('second'))
	p.running.remove('c0app-first.service')
	p.activating.add('c0app-first.service')
	p.host.quiesce(kind)
	assert not p.running and not p.activating
	assert hosting.read_json(p.host.recovery)['running'] == ['first']
	p.host.resume()
	assert p.running == {'c0app-first.service'}
	assert p.host.inspect('first')['ready']
	assert not p.host.inspect('second')['enabled']
	assert not p.host.recovery.exists()


def test_failed_recovery_retains_intent_for_retry(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.quiesce('backup')
	p.fail.add(('systemctl', '--user', 'start', 'c0app-first.service'))
	with pytest.raises(hosting.HostingError):
		p.host.resume()
	assert p.host.recovery.exists()
	p.fail.clear()
	p.host.resume()
	assert not p.host.recovery.exists()


def test_restore_verifies_archive_and_never_activates_external_writers(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.deploy(manifest('second'), start=True)
	p.volumes.update({'c0app-first-data': b'first-data', 'c0app-second-data': b'second-data'})
	p.host.quiesce('backup')
	p.host.export()
	p.host.recovery.unlink()
	p.volumes.clear()
	p.calls.clear()
	p.host.restore()
	assert p.volumes == {'c0app-first-data': b'first-data', 'c0app-second-data': b'second-data'}
	assert not p.running and not p.enabled
	assert all(r['status'] == 'restored_stopped' for r in p.host.records())
	assert not any(c[:3] == ['systemctl', '--user', 'start'] for c in p.calls)
	# Same completed restoration is a readback, never a second import.
	p.calls.clear()
	p.host.restore()
	assert not any(c[:3] == ['podman', 'volume', 'import'] for c in p.calls)


def test_corrupt_archive_rejected_before_any_volume_change(platform):
	p = platform
	p.host.deploy(manifest())
	p.host.quiesce('backup')
	p.host.export()
	(p.host.exports / 'first.tar').write_bytes(b'tampered')
	p.calls.clear()
	with pytest.raises(hosting.HostingError, match='checksum'):
		p.host.restore()
	assert not any(c[0] == 'podman' for c in p.calls)


def test_restore_never_overwrites_existing_unreceipted_volume(platform):
	p = platform
	p.host.deploy(manifest())
	p.host.quiesce('backup')
	p.host.export()
	with pytest.raises(hosting.HostingError, match='volume_exists'):
		p.host.restore()


def test_upgrade_allocates_extra_ports_without_replacing_c0_port(platform, monkeypatch):
	p = platform
	monkeypatch.delenv('TCP_PORTS_RANGE')
	calls = []
	p.agent.allocate_ports = lambda *a, **kw: calls.append((a, kw)) or (21000, 21031)
	assert p.host.port_pool() == list(range(21000, 21032))
	assert p.host.port_pool() == list(range(21000, 21032))
	assert calls == [((32, 'tcp'), {'keep_existing': True})]


def test_uncertain_port_allocation_cannot_blindly_allocate_again(platform, monkeypatch):
	p = platform
	monkeypatch.delenv('TCP_PORTS_RANGE')
	def allocate(*a, **kw):
		raise OSError('connection lost after allocation')
	p.agent.allocate_ports = allocate
	with pytest.raises(OSError):
		p.host.port_pool()
	with pytest.raises(hosting.HostingError, match='reconciliation'):
		p.host.port_pool()


def test_route_ownership_and_hostname_conflicts_do_not_overwrite(platform):
	p = platform
	p.host.deploy(manifest(hostname='one.example.test'))
	with pytest.raises(hosting.HostingError, match='hostname_in_use'):
		p.host.deploy(manifest('second', hostname='one.example.test'))
	p.routes['czero9-c0app-first']['url'] = 'http://127.0.0.1:9999'
	with pytest.raises(hosting.HostingError, match='ownership'):
		p.host.remove(p.host.record('first'))
	assert p.routes['czero9-c0app-first']['url'] == 'http://127.0.0.1:9999'


def test_private_secret_symlink_and_world_readable_file_rejected(platform, tmp_path):
	path = tmp_path / 'key'
	path.write_text('secret')
	path.chmod(0o644)
	with pytest.raises(hosting.HostingError, match='private_secret'):
		platform.host.stage(manifest(secrets={'TOKEN': 'key'}), tmp_path)
	path.chmod(0o600)
	(tmp_path / 'alias').symlink_to(path)
	with pytest.raises(hosting.HostingError, match='private_secret'):
		platform.host.stage(manifest(secrets={'TOKEN': 'alias'}), tmp_path)


def test_backup_fixed_paths_exclude_host_allocations_and_recovery_journal():
	paths = (ROOT / 'imageroot/etc/state-include.conf').read_text().splitlines()
	assert 'state/custom-apps' in paths and 'state/custom-app-backup' in paths
	assert 'state/custom-app-ports.json' not in paths
	assert 'state/custom-app-recovery.json' not in paths


def test_install_refuses_unregistered_volume(platform):
	p = platform
	p.volumes['c0app-first-data'] = b'unrelated data'
	with pytest.raises(hosting.HostingError, match='unregistered_volume'):
		p.host.deploy(manifest())
	assert p.volumes['c0app-first-data'] == b'unrelated data'
	assert not p.host.records()


def test_launcher_limits_mounts_and_keeps_private_values_out_of_arguments(platform, monkeypatch):
	from io import BytesIO
	p = platform
	p.host.deploy(manifest(environment={'PRIVATE_VALUE': 'synthetic-private-data'}))
	monkeypatch.setattr(hosting.urllib.request, 'build_opener', lambda *args: SimpleNamespace(open=lambda *a, **kw: BytesIO(b'{"status":"ok","service":"czero"}')))
	commands = []
	monkeypatch.setattr(hosting.os, 'execvp', lambda executable, command: commands.append(command))
	p.host.launch('first')
	command = commands[0]
	assert '--publish=127.0.0.1:20001:8080' in command
	assert '--network=c0app-first' in command
	assert '--cap-drop=ALL' in command and '--pids-limit=128' in command
	assert [v for v in command if v.startswith('--volume=')] == ['--volume=c0app-first-data:/data:Z']
	assert 'synthetic-private-data' not in ' '.join(command)
	assert not any(v in command for v in ('--privileged', '--network=host', '--env-host'))
	p.host.quiesce('backup')
	with pytest.raises(hosting.HostingError, match='maintenance_in_progress'):
		p.host.launch('first')


def test_recovery_waits_for_owner_then_restores_after_owner_exit(platform, monkeypatch):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.host.quiesce('backup')
	monkeypatch.setattr(hosting, 'Host', lambda: p.host)
	monkeypatch.setattr(sys, 'argv', ['czero-custom-app', 'recover', '--automatic'])
	hosting.main()
	assert p.host.recovery.exists() and not p.running
	journal = hosting.read_json(p.host.recovery)
	journal['identity'] = 'previous-boot'
	hosting.save(p.host.recovery, journal)
	hosting.main()
	assert not p.host.recovery.exists() and p.host.inspect('first')['ready']


def test_removed_application_restore_needs_no_image_and_keeps_data(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	p.volumes['c0app-first-data'] = b'retained after removal'
	p.host.remove(p.host.record('first'))
	p.fail.add(('systemctl', '--user', 'show', '--property=ActiveState', '--value', 'c0app-first.service'))
	p.host.quiesce('backup')
	p.host.export()
	p.host.recovery.unlink()
	p.volumes.clear()
	p.fail.add(('podman', 'pull', manifest()['image']))
	p.calls.clear()
	p.host.restore()
	assert p.volumes['c0app-first-data'] == b'retained after removal'
	assert p.host.inspect('first')['status'] == 'removed'
	assert not p.running and not p.enabled
	assert not (p.host.units / 'c0app-first.service').exists()
	assert not any(c[:2] == ['podman', 'pull'] for c in p.calls)


def test_update_never_recreates_missing_registered_data(platform):
	p = platform
	p.host.deploy(manifest(), start=True)
	before = p.host.record('first')
	p.volumes.clear()
	p.calls.clear()
	with pytest.raises(hosting.HostingError, match='registered_volume_unavailable'):
		p.host.deploy(manifest(), update=True)
	assert p.host.record('first') == before
	assert not p.volumes
	assert not any(c[:3] in (['podman', 'volume', 'create'], ['systemctl', '--user', 'stop']) for c in p.calls)
