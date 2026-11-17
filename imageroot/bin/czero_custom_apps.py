# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""NS8 operator-only custom application hosting. No knowledge API bindings."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

CONTRACT = {'version': 1, 'containers_per_app': 1, 'volumes_per_app': 1, 'max_apps': 32}
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,31}\Z')
IMAGE = re.compile(r'[a-z0-9][a-z0-9.:-]*/[a-z0-9][a-z0-9_./-]*@sha256:[a-f0-9]{64}\Z')
KEY = re.compile(r'[A-Z_][A-Z0-9_]{0,127}\Z')


class HostingError(Exception):
	pass


def require(condition, reason):
	if not condition:
		raise HostingError(reason)


def identifier(value):
	require(isinstance(value, str) and IDENTIFIER.fullmatch(value), 'invalid_application_id')
	return value


def validate(manifest):
	required = {'version', 'id', 'image', 'http_port', 'readiness_path', 'data_path', 'memory_mb', 'pids_limit', 'shutdown_seconds'}
	require(isinstance(manifest, dict) and required <= manifest.keys() and not manifest.keys() - required - {'hostname', 'environment', 'secrets'}, 'invalid_manifest_fields')
	require(type(manifest['version']) is int and manifest['version'] == 1, 'unsupported_contract')
	identifier(manifest['id'])
	require(isinstance(manifest['image'], str) and IMAGE.fullmatch(manifest['image']), 'digest_required')
	for key, low, high in [('http_port', 1, 65535), ('memory_mb', 32, 1048576), ('pids_limit', 16, 65536), ('shutdown_seconds', 1, 300)]:
		require(type(manifest[key]) is int and low <= manifest[key] <= high, 'invalid_' + key)
	path = manifest['data_path']
	require(isinstance(path, str) and re.fullmatch(r'/[a-zA-Z0-9_/-]+', path) and '..' not in PurePosixPath(path).parts and str(PurePosixPath(path)) == path, 'invalid_data_path')
	require(path not in {'/', '/etc', '/proc', '/sys', '/dev', '/run', '/usr', '/bin', '/lib', '/tmp'}, 'reserved_data_path')
	require(isinstance(manifest['readiness_path'], str) and re.fullmatch(r'/(?!/)[a-zA-Z0-9_./-]*', manifest['readiness_path']) and '..' not in PurePosixPath(manifest['readiness_path']).parts, 'invalid_readiness_path')
	host = manifest.get('hostname')
	if host is not None:
		require(isinstance(host, str) and len(host) <= 253 and '.' in host and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in host.split('.')), 'invalid_hostname')
	for field in ('environment', 'secrets'):
		values = manifest.get(field, {})
		require(isinstance(values, dict) and len(values) <= 128, 'invalid_' + field)
		for key, value in values.items():
			require(KEY.fullmatch(key) and isinstance(value, str) and len(value) <= 65536 and not any(char in value for char in '\r\n\0'), 'invalid_' + field)
			if field == 'secrets':
				require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', value) and value not in {'.', '..'}, 'invalid_secret_reference')
	require(not manifest.get('environment', {}).keys() & manifest.get('secrets', {}).keys(), 'duplicate_environment_key')
	return manifest


def read_json(path):
	require(not path.is_symlink() and not path.parent.is_symlink() and path.is_file(), 'regular_configuration_required')
	require(path.stat().st_size <= 1024 * 1024, 'configuration_too_large')
	return json.loads(path.read_text())


def save(path, value):
	path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
	temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
	try:
		with temporary.open('x', encoding='utf-8') as output:
			os.chmod(temporary, 0o600)
			output.write(json.dumps(value, sort_keys=True) + '\n')
			output.flush()
			os.fsync(output.fileno())
		os.replace(temporary, path)
		directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
		try:
			os.fsync(directory)
		finally:
			os.close(directory)
	finally:
		temporary.unlink(missing_ok=True)


def run(*command, **options):
	# Neither private environment nor command output is printed on failure.
	result = subprocess.run(list(command), stdout=options.pop('stdout', subprocess.PIPE), stderr=subprocess.PIPE, timeout=options.pop('timeout', 600), **options)
	require(result.returncode == 0, 'command_failed_' + Path(command[0]).name)
	return result.stdout


def active(unit):
	return subprocess.run(['systemctl', '--user', 'is-active', '--quiet', unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def process_identity(pid):
	try:
		return Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
	except OSError:
		return None


class Host:
	def __init__(self, state=None, units=None):
		self.state = Path(state or os.environ['AGENT_STATE_DIR'])
		self.root = self.state / 'custom-apps'
		self.units = Path(units or Path.home() / '.config/systemd/user')
		self.recovery = self.state / 'custom-app-recovery.json'
		self.exports = self.state / 'custom-app-backup'
		self.module = os.environ.get('MODULE_ID', '')

	@contextmanager
	def locked(self, recovery=False):
		require(not self.root.is_symlink(), 'symlink_rejected')
		self.root.mkdir(mode=0o700, exist_ok=True)
		with (self.state / 'custom-apps.lock').open('a') as lock:
			os.chmod(lock.name, 0o600)
			fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
			require(recovery or not self.recovery.exists(), 'maintenance_recovery_required')
			yield

	def records(self):
		return [self.record(p.parent.name) for p in sorted(self.root.glob('*/record.json'))]

	def record(self, app):
		identifier(app)
		path = self.root / app
		require(not path.is_symlink(), 'symlink_rejected')
		return read_json(path / 'record.json')

	def write(self, record):
		save(self.root / identifier(record['id']) / 'record.json', record)

	def manifest(self, record):
		generation = record['generation']
		require(re.fullmatch(r'[a-f0-9]{32}', generation), 'invalid_generation')
		return validate(read_json(self.root / identifier(record['id']) / generation / 'manifest.json'))

	def name(self, app):
		return 'c0app-' + identifier(app)

	def unit(self, app):
		return self.name(app) + '.service'

	def port_pool(self):
		path = self.state / 'custom-app-ports.json'
		if path.exists():
			data = read_json(path)
			require(data.get('module') == self.module and data.get('status') == 'allocated', 'port_allocation_requires_reconciliation')
			return data['ports']
		allocation = os.environ.get('TCP_PORTS_RANGE', '')
		if allocation:
			start, end = map(int, allocation.split('-'))
			ports = [port for port in range(start, end + 1) if port != int(os.environ['TCP_PORT'])]
			require(len(ports) >= CONTRACT['max_apps'], 'insufficient_platform_ports')
		else:
			# Existing C0 installations retain their original TCP_PORT during upgrade.
			import agent
			save(path, {'module': self.module, 'status': 'allocating'})
			start, end = agent.allocate_ports(CONTRACT['max_apps'], 'tcp', keep_existing=True)
			ports = list(range(start, end + 1))
			require(len(ports) == CONTRACT['max_apps'] and int(os.environ['TCP_PORT']) not in ports, 'invalid_platform_allocation')
		save(path, {'module': self.module, 'status': 'allocated', 'ports': ports})
		return ports

	def route(self, record, manifest, remove=False):
		import agent
		require(re.fullmatch(r'[a-z][a-z0-9]*[0-9]+', self.module), 'invalid_module_identity')
		instance = self.module + '-' + self.name(record['id'])
		target = agent.resolve_agent_id('traefik@node')
		def call(action, data):
			response = agent.tasks.run(agent_id=target, action=action, data=data, extra={'isNotificationHidden': True})
			require(response['exit_code'] == 0, 'route_operation_failed')
			return response.get('output') or {}
		current = call('get-route', {'instance': instance})
		expected = 'http://127.0.0.1:' + str(record['port'])
		require(not current or current.get('url') == expected, 'route_ownership_conflict')
		if remove or not manifest.get('hostname'):
			if current:
				call('delete-route', {'instance': instance})
			return
		hostname = manifest['hostname']
		require(current.get('host') == hostname or not agent.http_route_in_use(domain=hostname), 'hostname_in_use')
		call('set-route', {'instance': instance, 'host': hostname, 'path': None, 'url': expected, 'http2https': True, 'lets_encrypt': True, 'lets_encrypt_check': True})

	def generate(self, record):
		manifest = self.manifest(record)
		self.units.mkdir(parents=True, exist_ok=True)
		unit = self.units / self.unit(record['id'])
		require(not unit.is_symlink(), 'symlink_rejected')
		# Only validated identifiers enter unit syntax; private values stay in files.
		unit.write_text('[Unit]\nDescription=C0 custom application ' + record['id'] + '\nWants=czero.service\nAfter=czero.service\n\n[Service]\nType=simple\nExecStart=/usr/local/bin/runagent czero-custom-app launch ' + record['id'] + '\nExecStop=/usr/bin/podman stop --ignore --time=' + str(manifest['shutdown_seconds']) + ' ' + self.name(record['id']) + '\nRestart=on-failure\nRestartSec=10\nTimeoutStopSec=' + str(manifest['shutdown_seconds'] + 15) + '\nSyslogIdentifier=' + self.name(record['id']) + '\n\n[Install]\nWantedBy=default.target\n')
		unit.chmod(0o600)

	def stage(self, manifest, secrets_dir):
		manifest = validate(manifest)
		generation = uuid.uuid4().hex
		require(not (self.root / manifest['id']).is_symlink(), 'symlink_rejected')
		directory = self.root / manifest['id'] / generation
		directory.mkdir(parents=True, mode=0o700)
		environment = dict(manifest.get('environment', {}))
		try:
			for key, filename in manifest.get('secrets', {}).items():
				require(secrets_dir is not None, 'secret_directory_required')
				path = Path(secrets_dir) / filename
				require(not path.is_symlink() and path.is_file() and path.stat().st_mode & 0o077 == 0 and path.stat().st_size <= 65536, 'private_secret_file_required')
				value = path.read_text().rstrip('\n')
				require(value and not any(c in value for c in '\r\n\0'), 'invalid_secret_value')
				environment[key] = value
			save(directory / 'manifest.json', manifest)
			with (directory / 'environment').open('x') as output:
				os.chmod(output.name, 0o600)
				output.write(''.join(key + '=' + value + '\n' for key, value in sorted(environment.items())))
				output.flush()
				os.fsync(output.fileno())
		except BaseException:
			shutil.rmtree(directory)
			raise
		return generation

	def deploy(self, manifest, secrets_dir=None, update=False, start=False):
		manifest = validate(manifest)
		app = manifest['id']
		path = self.root / app / 'record.json'
		previous = self.record(app) if path.exists() else None
		require(bool(previous and previous['status'] != 'removed') == update, 'application_missing' if update else 'application_already_registered')
		if previous:
			require(self.manifest(previous)['data_path'] == manifest['data_path'], 'data_mount_change_forbidden')
		else:
			require(len(self.records()) < CONTRACT['max_apps'], 'application_capacity_exceeded')
		exists = subprocess.run(['podman', 'volume', 'exists', self.name(app) + '-data'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
		require(exists == (0 if previous else 1), 'registered_volume_unavailable' if previous else 'unregistered_volume_exists')
		generation = self.stage(manifest, secrets_dir)
		run('podman', 'pull', manifest['image'])
		if not previous:
			run('podman', 'volume', 'create', self.name(app) + '-data')
		if previous:
			port = previous['port']
		else:
			used = {item['port'] for item in self.records()}
			port = next(p for p in self.port_pool() if p not in used)
		if previous:
			save(self.root / app / previous['generation'] / 'deployment.json', previous)
		record = {'id': app, 'generation': generation, 'port': port, 'enabled': previous['enabled'] if update else start, 'status': 'deploying', 'previous_generation': previous['generation'] if previous else None}
		# Stop the old image before changing the generation that launches on restart.
		if previous:
			run('systemctl', '--user', 'stop', self.unit(app))
		self.write(record)
		try:
			self.generate(record)
			run('systemctl', '--user', 'daemon-reload')
			self.route(record, manifest)
			if record['enabled']:
				self.start(record)
			else:
				record['status'] = 'stopped'
				self.write(record)
		except BaseException:
			record['status'] = 'deployment_failed'
			self.write(record)
			raise
		return self.inspect(app)

	def ready(self, record, seconds=60):
		manifest = self.manifest(record)
		deadline = time.monotonic() + seconds
		opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
		while True:
			try:
				with opener.open('http://127.0.0.1:' + str(record['port']) + manifest['readiness_path'], timeout=2) as response:
					if response.status == 200:
						return True
			except OSError:
				pass
			if time.monotonic() >= deadline:
				return False
			time.sleep(1)

	def start(self, record):
		require(record['status'] != 'removed', 'application_removed')
		self.route(record, self.manifest(record))
		run('systemctl', '--user', 'start', self.unit(record['id']))
		if not self.ready(record):
			run('systemctl', '--user', 'stop', self.unit(record['id']))
			raise HostingError('application_not_ready')
		run('systemctl', '--user', 'enable', self.unit(record['id']))
		record.update(enabled=True, status='running')
		self.write(record)

	def stop(self, record):
		require(record['status'] != 'removed', 'application_removed')
		# Persist the stop before systemd: interrupted stops cannot re-enable on upgrade.
		record.update(enabled=False, status='stopping')
		self.write(record)
		run('systemctl', '--user', 'disable', '--now', self.unit(record['id']))
		record.update(enabled=False, status='stopped')
		self.write(record)

	def remove(self, record):
		self.stop(record)
		self.route(record, self.manifest(record), remove=True)
		(self.units / self.unit(record['id'])).unlink(missing_ok=True)
		run('systemctl', '--user', 'daemon-reload')
		record['status'] = 'removed'
		self.write(record)

	def inspect(self, app):
		record = self.record(app)
		manifest = self.manifest(record)
		running = active(self.unit(app))
		return {'id': app, 'image': manifest['image'], 'status': record['status'], 'enabled': record['enabled'], 'running': running, 'ready': running and self.ready(record, seconds=0), 'port': record['port'], 'recovery_required': self.recovery.exists()}

	def quiesce(self, kind):
		require(not self.recovery.exists(), 'maintenance_recovery_required')
		records = self.records()
		journal = {'kind': kind, 'owner': os.getppid(), 'identity': process_identity(os.getppid()), 'running': [r['id'] for r in records if active(self.unit(r['id']))]}
		save(self.recovery, journal)
		for record in records:
			if record['status'] != 'removed':
				run('systemctl', '--user', 'stop', self.unit(record['id']))

	def export(self):
		require(self.recovery.exists(), 'maintenance_required')
		self.exports.mkdir(mode=0o700, exist_ok=True)
		inventory = []
		for record in self.records():
			archive = self.exports / (record['id'] + '.tar')
			with archive.open('wb') as output:
				os.chmod(archive, 0o600)
				run('podman', 'volume', 'export', self.name(record['id']) + '-data', stdout=output)
				output.flush()
				os.fsync(output.fileno())
			inventory.append({'id': record['id'], 'generation': record['generation'], 'image': self.manifest(record)['image'], 'sha256': digest(archive)})
		save(self.exports / 'inventory.json', {'version': 1, 'applications': inventory})

	def resume(self):
		if not self.recovery.exists():
			return
		journal = read_json(self.recovery)
		# Launch is allowed only for the recorded recovery set while this lock is held.
		journal['resuming'] = True
		save(self.recovery, journal)
		for app in journal['running']:
			record = self.record(app)
			if record['status'] == 'removed':
				continue
			run('systemctl', '--user', 'start', self.unit(app))
			require(self.ready(record), 'application_not_ready')
		if self.exports.exists():
			shutil.rmtree(self.exports)
		self.recovery.unlink()

	def regenerate(self):
		for record in self.records():
			if record['status'] != 'removed':
				self.generate(record)
		run('systemctl', '--user', 'daemon-reload')

	def restore(self):
		if not self.exports.exists():
			require(not self.records(), 'custom_application_archives_missing')
			return
		inventory = read_json(self.exports / 'inventory.json')
		require(inventory.get('version') == 1, 'unsupported_backup')
		records = {r['id']: r for r in self.records()}
		require(not any(active(self.unit(app)) for app in records), 'restore_application_running')
		require(set(records) == {i['id'] for i in inventory['applications']}, 'backup_inventory_mismatch')
		# Validate every archive before changing any application volume.
		for item in inventory['applications']:
			record = records[identifier(item['id'])]
			require(item['generation'] == record['generation'] and item['image'] == self.manifest(record)['image'], 'backup_manifest_mismatch')
			require(digest(self.exports / (item['id'] + '.tar')) == item['sha256'], 'backup_checksum_mismatch')
		ports = self.port_pool()
		for index, item in enumerate(inventory['applications']):
			app = item['id']
			record = records[app]
			receipt = self.state / ('custom-app-restored-' + app + '.json')
			if receipt.exists():
				require(read_json(receipt) == item, 'restore_receipt_mismatch')
			else:
				exists = subprocess.run(['podman', 'volume', 'exists', self.name(app) + '-data'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
				require(exists == 1, 'restore_volume_exists')
				run('podman', 'volume', 'create', self.name(app) + '-data')
				run('podman', 'volume', 'import', self.name(app) + '-data', str(self.exports / (app + '.tar')))
				save(receipt, item)
			removed = record['status'] == 'removed'
			record.update(port=ports[index], enabled=False, status='removed' if removed else 'restored_stopped')
			self.write(record)
			if not removed:
				self.generate(record)
				run('systemctl', '--user', 'disable', self.unit(app))
				# Removed registrations restore retained data only; no image or unit.
				# Pull failures never start a restored external writer.
				try:
					run('podman', 'pull', item['image'])
				except HostingError:
					record['status'] = 'image_unavailable'
					self.write(record)
					raise
		run('systemctl', '--user', 'daemon-reload')

	def launch(self, app):
		record = self.record(app)
		if self.recovery.exists():
			journal = read_json(self.recovery)
			require(journal.get('resuming') and app in journal['running'], 'maintenance_in_progress')
		require(record['status'] != 'removed', 'application_removed')
		manifest = self.manifest(record)
		c0 = {'id': app, 'port': int(os.environ['TCP_PORT'])}
		opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
		with opener.open('http://127.0.0.1:' + str(c0['port']) + '/api/v1/health', timeout=5) as response:
			health = json.load(response)
		require(health.get('status') == 'ok' and health.get('service') == 'czero', 'c0_not_ready')
		network = self.name(app)
		if subprocess.run(['podman', 'network', 'exists', network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
			run('podman', 'network', 'create', network)
		command = ['podman', 'run', '--rm', '--replace', '--name=' + self.name(app), '--network=' + network,
			'--log-driver=journald', '--log-opt=tag=' + self.name(app), '--cap-drop=ALL', '--security-opt=no-new-privileges',
			'--memory=' + str(manifest['memory_mb']) + 'm', '--pids-limit=' + str(manifest['pids_limit']),
			'--stop-timeout=' + str(manifest['shutdown_seconds']), '--publish=127.0.0.1:' + str(record['port']) + ':' + str(manifest['http_port']),
			'--volume=' + self.name(app) + '-data:' + manifest['data_path'] + ':Z',
			'--env-file=' + str(self.root / app / record['generation'] / 'environment'), manifest['image']]
		os.execvp(command[0], command)


class NoRedirect(urllib.request.HTTPRedirectHandler):
	def redirect_request(self, req, fp, code, msg, headers, newurl):
		return None


def digest(path):
	require(not path.is_symlink(), 'symlink_rejected')
	with path.open('rb') as source:
		checksum = hashlib.sha256()
		for chunk in iter(lambda: source.read(1024 * 1024), b''):
			checksum.update(chunk)
	return checksum.hexdigest()


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	commands = parser.add_subparsers(dest='command', required=True)
	for name in ('contract', 'list', 'regenerate', 'restore', 'maintenance-begin', 'maintenance-end', 'remove-all'):
		commands.add_parser(name)
	commands.add_parser('recover').add_argument('--automatic', action='store_true')
	for name in ('install', 'update'):
		command = commands.add_parser(name)
		command.add_argument('manifest', type=Path)
		command.add_argument('--secrets-dir', type=Path)
		if name == 'install':
			command.add_argument('--start', action='store_true')
	for name in ('start', 'stop', 'inspect', 'remove', 'launch'):
		commands.add_parser(name).add_argument('id', type=identifier)
	args = parser.parse_args()
	if args.command == 'contract':
		print(json.dumps(CONTRACT))
		return
	host = Host()
	if args.command == 'launch':
		host.launch(args.id)
		return
	with host.locked(recovery=args.command in {'recover', 'maintenance-end', 'inspect', 'list'}):
		result = None
		if args.command in {'install', 'update'}:
			result = host.deploy(read_json(args.manifest), args.secrets_dir, update=args.command == 'update', start=getattr(args, 'start', False))
		elif args.command == 'list':
			result = [host.inspect(r['id']) for r in host.records()]
		elif args.command == 'inspect':
			result = host.inspect(args.id)
		elif args.command in {'start', 'stop', 'remove'}:
			getattr(host, args.command)(host.record(args.id))
			result = host.inspect(args.id)
		elif args.command == 'recover':
			if host.recovery.exists():
				journal = read_json(host.recovery)
				if process_identity(journal['owner']) == journal['identity']:
					if args.automatic:
						return
					raise HostingError('maintenance_owner_still_running')
				# C0 writers recover before applications; cleanup retains its own journal.
				run('czero-cleanup-database')
				host.regenerate()
				host.resume()
		elif args.command == 'maintenance-begin':
			host.quiesce('update')
		elif args.command == 'maintenance-end':
			require(host.recovery.exists() and read_json(host.recovery).get('kind') == 'update', 'update_recovery_record_required')
			host.regenerate()
			host.resume()
		elif args.command == 'remove-all':
			for record in host.records():
				if record['status'] != 'removed':
					host.remove(record)
		else:
			getattr(host, args.command)()
		if result is not None:
			print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
	try:
		main()
	except (HostingError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
		print(str(error) if isinstance(error, HostingError) else type(error).__name__, file=sys.stderr)
		sys.exit(1)
