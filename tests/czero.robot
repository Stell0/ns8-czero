*** Settings ***
Library    SSHLibrary
Library    CzeroActions.py
Library    CzeroBrowser.py
Library    CzeroBackup.py
Library    CzeroSso.py
Suite Teardown    Cleanup disposable Czero resources

*** Variables ***
${SCENARIO}    install
${module_id}    ${EMPTY}
${other_id}    ${EMPTY}
${host}    ${EMPTY}
${backup_repository}    ${EMPTY}
${health_run_count}    0

*** Keywords ***
Remove disposable module
    IF    $other_id
        ${rc} =    Execute Command    remove-module --no-preserve ${other_id}
        ...    return_rc=True    return_stdout=False    timeout=180s
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${other_id}    ${EMPTY}
    END
    IF    $module_id
        ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
        ...    return_rc=True    return_stdout=False    timeout=180s
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${module_id}    ${EMPTY}
    END

Remove disposable backup resources
    IF    $backup_repository
        ${rc} =    Execute Command    api-cli run remove-backup-repository --data '{"id":"${backup_repository}"}'
        ...    return_rc=True    return_stdout=False    timeout=180s
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${backup_repository}    ${EMPTY}
    END

Cleanup disposable Czero resources
    Remove disposable module
    Remove disposable backup resources
    Cleanup Disposable Sso

Check legacy route
    ${output}    ${rc} =    Execute Command
    ...    curl --fail --silent --show-error --max-time 10 http://127.0.0.1/czero/${module_id}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${health} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${health}[status]    ok
    Should Be Equal    ${health}[database][status]    ok

Check application route
    ${output}    ${rc} =    Execute Command
    ...    curl --fail --silent --show-error --max-time 10 https://${host}/api/v1/health --insecure --resolve ${host}:443:127.0.0.1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${health} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${health}[status]    ok
    Should Be Equal    ${health}[database][status]    ok
    Should Contain    ${output}    "core_version":"0.29.0"
    Should Contain    ${output}    "app_version":"0.44.0"

Check worker timer recovered
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${scheduler}[timer_active]
    Should Be True    ${scheduler}[timer_enabled]
    Should Not Be True    ${scheduler}[worker_failed]
    Should Not Be True    ${scheduler}[worker_running]
    ${result}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} systemctl --user show --property=Result --value czero-worker.service
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${result}    success

*** Test Cases ***
Install Czero with its own identity
    ${install_image} =    Set Variable    ${IMAGE_URL}
    IF    $SCENARIO == 'update'
        ${install_image} =    Set Variable    ghcr.io/stell0/czero@sha256:6b24869832ce1277a951c081b5058b27b559fb01a5e262f58cd27b63d1852e34
    END
    ${output}    ${rc} =    Execute Command    add-module ${install_image} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${installed_id} =    Installed Module Id    ${output}
    Set Global Variable    ${module_id}    ${installed_id}
    Should Start With    ${module_id}    czero
    Set Global Variable    ${host}    ${module_id}.test
    IF    $SCENARIO == 'update'
        # Freeze all three actually deployed 878978d AM4 predecessor images.
        ${rc} =    Execute Command
        ...    runagent -m ${module_id} python3 -c "import agent; agent.mset_env({'CZERO_APP_IMAGE':'ghcr.io/stell0/czero-app@sha256:fdfb6de553118c2ddbd6439330659f3883f1aacc258c0b75ebbd70969e34b436','CZERO_POSTGRES_IMAGE':'ghcr.io/stell0/czero-postgres@sha256:6321d506400581e9ab37b9c12a7748fccfcf99d2774911f74203835557b26399'})"
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        # Seed a real predecessor database before running current lifecycle hooks.
        ${rc} =    Execute Command
        ...    api-cli run module/${module_id}/configure-module --data '{"host":"${host}","lets_encrypt":false}'
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        ${rc} =    Execute Command
        ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -v ON_ERROR_STOP=1 -c "CREATE TABLE czero_upgrade_probe (id int PRIMARY KEY); INSERT INTO czero_upgrade_probe VALUES (7);"
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        ${rc} =    Execute Command
        ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        ${output}    ${rc} =    Execute Command
        ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT id FROM czero_upgrade_probe;"
        ...    return_rc=True
        Should Be Equal As Integers    ${rc}    0
        Should Be Equal    ${output}    7
        # Return to a clean unconfigured fixture for the inherited preservation check.
        ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-pod.service
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        ${rc} =    Execute Command
        ...    runagent -m ${module_id} python3 -c "import agent; agent.mset_env({'CZERO_HOST':'','CZERO_BASE_PATH':'/czero/${module_id}'})"
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
    END

Update an unconfigured instance without starting it
    Skip If    $SCENARIO != 'update'    Clean install scenario
    ${rc} =    Execute Command
    ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active czero.service
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Not Be True    ${scheduler}[timer_active]
    Should Not Be True    ${scheduler}[worker_running]

Preserve a legacy prefix during native upgrade
    Skip If    $SCENARIO != 'update'    Clean install scenario
    # Disposable M01 fixture: prefix route and no persisted base-path setting.
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} python3 -c "import agent,os; m=os.environ['MODULE_ID']; agent.mset_env({'CZERO_MODULE_ID':m,'CZERO_BASE_PATH':'/czero/'+m}); agent.set_route({'instance':m,'url':'http://127.0.0.1:'+os.environ['TCP_PORT'],'path':'/czero/'+m,'host':None,'http2https':False,'lets_encrypt':False})"
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    runagent -m ${module_id} python3 -c "import agent; agent.unset_env('CZERO_BASE_PATH')"
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command
    ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check legacy route

Configure and reconfigure the hostname service
    FOR    ${attempt}    IN RANGE    2
        ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/configure-module --data '{"host":"${host}","lets_encrypt":false}'
        ...    return_rc=True
        Should Be Equal As Integers    ${rc}    0    msg=${output}
    END
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${config}[host]    ${host}
    Should Be Equal    ${config}[lets_encrypt]    ${False}
    Should Be Equal    ${config}[retrieval][embedding][enabled]    ${False}
    Should Be Equal    ${config}[retrieval][scorer][mode]    off
    Should Be Equal    ${config}[retrieval][embedding][api_key_configured]    ${False}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} stat -c '%a' /home/${module_id}/.config/state/retrieval.env
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    600
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-status
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${status} =    Evaluate    json.loads($output)    modules=json
    ${service} =    Evaluate    next(s for s in $status['services'] if s['name'] == 'czero')
    Should Be Equal    ${service}[active]    ${True}
    Should Be Equal    ${service}[enabled]    ${True}
    Should Be Equal    ${service}[failed]    ${False}

Verify HTTPS redirect and replace the hostname route
    ${code}    ${rc} =    Execute Command
    ...    curl --silent --max-time 10 --output /dev/null --write-out '\%{http_code}' --resolve ${host}:80:127.0.0.1 http://${host}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${code}    301
    ${old_host} =    Set Variable    ${host}
    Set Global Variable    ${host}    changed-${module_id}.test
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${host}","lets_encrypt":false}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Check application route
    ${code}    ${rc} =    Execute Command
    ...    curl --silent --insecure --max-time 10 --output /dev/null --write-out '\%{http_code}' --resolve ${old_host}:443:127.0.0.1 https://${old_host}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${code}    404
    ${code}    ${rc} =    Execute Command
    ...    curl --silent --max-time 10 --output /dev/null --write-out '\%{http_code}' http://127.0.0.1/czero/${module_id}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${code}    404

Reject a competing instance without changing the owner
    ${output}    ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${installed_id} =    Installed Module Id    ${output}
    Set Global Variable    ${other_id}    ${installed_id}
    ${rc} =    Execute Command
    ...    api-cli run module/${other_id}/configure-module --data '{"host":"${host}","lets_encrypt":false}'
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command    api-cli run module/${other_id}/get-configuration
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Be Empty    ${config}[host]
    Check application route
    ${rc} =    Execute Command    remove-module --no-preserve ${other_id}
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Set Global Variable    ${other_id}    ${EMPTY}

Verify durable isolated PostgreSQL and indexed vectors
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -v ON_ERROR_STOP=1 -c "CREATE TABLE czero_persistence_probe (id integer PRIMARY KEY, embedding vector(3)); INSERT INTO czero_persistence_probe VALUES (1,'[1,0,0]'),(2,'[0,1,0]'); CREATE INDEX czero_probe_hnsw ON czero_persistence_probe USING hnsw (embedding vector_l2_ops);"
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -v ON_ERROR_STOP=1 -c "SET enable_seqscan=off; EXPLAIN SELECT id FROM czero_persistence_probe ORDER BY embedding <-> '[1,0,0]' LIMIT 1;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${output}    czero_probe_hnsw
    ${output}    ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${installed_id} =    Installed Module Id    ${output}
    Set Global Variable    ${other_id}    ${installed_id}
    ${rc} =    Execute Command
    ...    api-cli run module/${other_id}/configure-module --data '{"host":"${other_id}.test","lets_encrypt":false}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${other_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT to_regclass('czero_persistence_probe') IS NULL;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    t
    ${rc} =    Execute Command
    ...    cmp --quiet /home/${module_id}/.config/state/passwords.env /home/${other_id}/.config/state/passwords.env
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    1
    ${mode}    ${rc} =    Execute Command    stat -c '%a' /home/${module_id}/.config/state/passwords.env
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${mode}    600
    ${safe}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} python3 -c "import agent,os; e=agent.read_envfile(os.environ['AGENT_STATE_DIR']+'/environment'); print('POSTGRES_PASSWORD' not in e and 'CZERO_DATABASE_URL' not in e)"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${safe}    True
    ${ports}    ${rc} =    Execute Command    runagent -m ${module_id} podman port czero-postgres
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Contain    ${ports}    5432
    ${rc} =    Execute Command    remove-module --no-preserve ${other_id}
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Set Global Variable    ${other_id}    ${EMPTY}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Check application route
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero python -m czero_core.migrate
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT id FROM czero_persistence_probe ORDER BY embedding <-> '[1,0,0]' LIMIT 1;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    1
    # Infrastructure restart must recover both active children, not leave them stopped.
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero-pod.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM czero_persistence_probe;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    2

Report database outage and recover the application
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command
    ...    curl --silent --show-error --max-time 10 --insecure --resolve ${host}:443:127.0.0.1 https://${host}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${health} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${health}[status]    degraded
    Should Be Equal    ${health}[database][reason]    database_unavailable
    # Force a genuine failed wake during the outage; do not mask its state.
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-worker.service
    ...    return_rc=True    return_stdout=False    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-worker.service
    ...    return_rc=True    return_stdout=False    timeout=30s
    Should Not Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${scheduler}[worker_failed]
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Check application route
    # Retain the real timer and wait for its next successful completed wake.
    # Never reset-failed or start the worker manually after restoring the DB.
    Wait Until Keyword Succeeds    95s    2s    Check worker timer recovered

Verify application requests are logged
    Check application route
    # systemd expands %N in czero.service to the container name "czero".
    ${logs}    ${rc} =    Execute Command    runagent -m ${module_id} podman logs czero
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${logs}    /api/v1/health

Reject invalid settings without changing configuration
    FOR    ${data}    IN    {"unknown":true}    {"host":"localhost"}    {"host":"valid.test","lets_encrypt":"false"}
        ${rc} =    Execute Command
        ...    api-cli run module/${module_id}/configure-module --data '${data}'
        ...    return_rc=True    return_stdout=False
        Should Not Be Equal As Integers    ${rc}    0
    END
    ${config_output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($config_output)    modules=json
    Should Be Equal    ${config}[host]    ${host}
    Check application route

Restart the installed service
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route

Exercise the native module update
    Skip If    $SCENARIO != 'update'    Clean install scenario
    ${before}    ${rc} =    Execute Command    runagent -m ${module_id} podman inspect --format '{{.Id}}' czero
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    # M00 did not store this identity. The running process is unaffected until
    # update replaces it, so this fixture detects both reconciliation/restart.
    ${rc} =    Execute Command    runagent -m ${module_id} python3 -c "import agent; agent.unset_env('CZERO_MODULE_ID')"
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command
    ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${after}    ${rc} =    Execute Command    runagent -m ${module_id} podman inspect --format '{{.Id}}' czero
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Be Equal    ${before}    ${after}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM czero_persistence_probe;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    2
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

Verify protected Core spaces in the installed runtime
    [Timeout]    90 seconds
    # Owned trusted Core fixtures are separate from real SSO/SDK acceptance.
    Put File    ${CURDIR}/packaging/core_spaces_probe.py    /tmp/czero-core-spaces-probe.py    mode=0644
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec -i -e CZERO_DISPOSABLE_TEST=1 czero python - < /tmp/czero-core-spaces-probe.py
    ...    return_rc=True    timeout=80s
    Should Be Equal As Integers    ${rc}    0
    ${result} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${result}[spaces]
    Should Be True    ${result}[scoped_names]
    Should Be True    ${result}[immutable_evidence]
    Should Be True    ${result}[typed_references]
    Should Be True    ${result}[grant_revocation]
    Should Be True    ${result}[annotations]
    Should Be True    ${result}[structured_retrieval]
    Should Be True    ${result}[atomic_consolidation]
    Should Be True    ${result}[maintenance_annotations]

Verify effective container hardening and memory targets
    Put File    ${CURDIR}/hardening_probe.py    /tmp/czero-hardening-probe.py    mode=0644
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} python3 /tmp/czero-hardening-probe.py
    ...    return_rc=True    timeout=45s
    Should Be Equal As Integers    ${rc}    0
    Log    ${output}

Verify deterministic worker and native timer
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${scheduler}[timer_active]
    Should Be True    ${scheduler}[timer_enabled]
    Should Not Be True    ${scheduler}[worker_failed]
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-worker.timer czero-worker.service
    ...    return_rc=True    return_stdout=False    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${before}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM c0_task_runs t JOIN c0_scheduled_tasks s ON s.id=t.schedule_id WHERE s.name='health-hourly';"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -v ON_ERROR_STOP=1 -c "UPDATE c0_scheduled_tasks SET next_run_at=now()-interval '1 second' WHERE name='health-hourly';"
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-worker.service
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${state}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT j.state FROM c0_task_runs t JOIN c0_jobs j ON j.id=t.job_id JOIN c0_scheduled_tasks s ON s.id=t.schedule_id WHERE s.name='health-hourly' ORDER BY t.due_at DESC LIMIT 1;"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${state}    succeeded
    ${expected} =    Evaluate    int($before)+1
    Set Global Variable    ${health_run_count}    ${expected}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-worker.service
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${after}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM c0_task_runs t JOIN c0_scheduled_tasks s ON s.id=t.schedule_id WHERE s.name='health-hourly';"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal As Integers    ${after}    ${expected}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero.service
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${scheduler}[timer_active]
    Should Not Be True    ${scheduler}[worker_failed]

    # Core restart-module restarts the whole rootless user manager, not merely
    # the app service. Verify this distinct startup path as used live.
    ${rc} =    Execute Command
    ...    api-cli run node/1/restart-module --data '{"module_id":"${module_id}"}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-scheduler-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${scheduler} =    Evaluate    json.loads($output)    modules=json
    Should Be True    ${scheduler}[timer_active]
    Should Not Be True    ${scheduler}[worker_failed]

Backup and restore into a clean disposable instance
    [Timeout]    10 minutes
    Log To Console    Backup phase: seed retained fixture
    ${before_identity}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT knowledge_space_id FROM instance_metadata;"
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero sh -c "printf retained-fixture > /var/lib/czero/sources/retained.txt"
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Log To Console    Backup phase: create native destination and schedule
    ${backup} =    Create Disposable Backup    ${module_id}
    Set Global Variable    ${backup_repository}    ${backup}[repository]
    Log To Console    Backup phase: run native encrypted backup
    ${rc} =    Execute Command    api-cli run run-backup --data '{"id":${backup}[backup_id]}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} test ! -e /home/${module_id}/.config/state/czero.pg_dump
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Log To Console    Backup phase: verify native snapshot
    Verify Disposable Snapshot    ${module_id}    ${backup}[repository]    ${backup}[path]
    # Only the disposable Czero module is destroyed; native backup data remains.
    Log To Console    Restore phase: remove donor
    Remove disposable module
    Log To Console    Restore phase: restore clean slot
    ${output}    ${rc} =    Execute Command
    ...    api-cli run restore-module --data '{"repository":"${backup}[repository]","path":"${backup}[path]","snapshot":"latest","node":1}'
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0    msg=${output}
    ${restored_id} =    Installed Module Id    ${output}
    Set Global Variable    ${module_id}    ${restored_id}
    Log To Console    Restore phase: verify health and data
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${identity}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT knowledge_space_id FROM instance_metadata;"
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${identity}    ${before_identity}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM czero_persistence_probe;"
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    2
    ${output}    ${rc} =    Execute Command    runagent -m ${module_id} podman exec czero cat /var/lib/czero/sources/retained.txt
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    retained-fixture
    ${count}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM c0_task_runs t JOIN c0_scheduled_tasks s ON s.id=t.schedule_id WHERE s.name='health-hourly';"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal As Integers    ${count}    ${health_run_count}
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${config}[host]    ${host}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} stat -c '%a' /home/${module_id}/.config/state/passwords.env
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    600
    # Re-delivering a completed archive preserves later database changes.
    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -v ON_ERROR_STOP=1 -c "INSERT INTO czero_persistence_probe VALUES (3, '[3,0,0]');"
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Log To Console    Restore phase: replay completed archive
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/restore-module --data '{"repository":"${backup}[repository]","path":"${backup}[path]","snapshot":"latest","environment":{"IMAGE_URL":"${IMAGE_URL}","CZERO_HOST":"${host}","CZERO_LETS_ENCRYPT":"false","CZERO_USER_DOMAIN":"${config}[user_domain]","CZERO_IDP_UUID":"${config}[idp]","CZERO_OWNER_USERNAME":"${config}[owner]","CZERO_OWNER_LDAP_UUID":"${config}[owner_ldap_uuid]"}}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Log To Console    Restore phase: verify health and data
    Wait Until Keyword Succeeds    30s    2s    Check application route
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec czero-postgres psql -U czero -d czero -At -c "SELECT count(*) FROM czero_persistence_probe;"
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    3
    ${rc} =    Execute Command    api-cli run module/${module_id}/configure-module --data '{"host":"${host}","lets_encrypt":false}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Check application route

Check saved settings and application HTTPS in a browser
    [Tags]    ui
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    Login To Disposable Cluster    ${NODE_ADDR}
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}
    Wait For Elements State    iframe >>> h2 >> text="Status"    visible    timeout=30s
    Get Text    iframe >>> text="czero"    contains    czero
    Wait For Elements State    iframe >>> \#runtime-database >> text="Database ready"    visible    timeout=30s
    Wait For Elements State    iframe >>> \#runtime-authentication >> text="Sign-in not configured"    visible    timeout=30s
    Wait For Elements State    iframe >>> \#runtime-retrieval >> text="Text search configured"    visible    timeout=30s
    Get Text    iframe >>> \#runtime-scheduler    matches    (?s).*Worker (timer ready|running).*
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=settings
    Wait For Elements State    iframe >>> h2 >> text="Settings"    visible    timeout=30s
    Wait For Elements State    iframe >>> .ns-text-input input >> nth=0    enabled    timeout=30s
    Get Property    iframe >>> .ns-text-input input >> nth=0    value    ==    ${host}
    Fill Text    iframe >>> .ns-text-input input >> nth=0    localhost
    Click    iframe >>> button >> text="Save"
    Wait For Elements State    iframe >>> text="Enter a valid fully qualified DNS hostname."    visible    timeout=30s
    Fill Text    iframe >>> .ns-text-input input >> nth=0    ${host}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    curl --fail --silent --max-time 10 https://${host}/api/v1/health --insecure --resolve ${host}:443:127.0.0.1
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
    Click    iframe >>> button >> text="Save"
    Wait For Elements State    iframe >>> .progress-bar-container    visible    timeout=5s
    Wait For Elements State    iframe >>> button >> text="Save"    enabled    timeout=30s
    Wait For Elements State    iframe >>> .progress-bar-container    detached    timeout=30s
    Wait Until Keyword Succeeds    30s    2s    Check application route
    Reload
    Wait For Elements State    iframe >>> .ns-text-input input >> nth=0    enabled    timeout=30s
    Get Property    iframe >>> .ns-text-input input >> nth=0    value    ==    ${host}
    Get Attribute    iframe >>> a:has-text("Open C0 application")    href    ==    https://${host}/
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=about
    Wait For Elements State    iframe >>> h3 >> text="czero"    visible    timeout=30s
    Go To    https://${host}/
    Get Text    h1    ==    A place to find what we know.
    Get Element Count    nav[aria-label="C0 navigation"] a    ==    10
    Get Element Count    nav a[aria-current="page"]    ==    1
    Press Keys    body    Tab
    Wait For Elements State    .skip-link    focused
    Get Attribute    .skip-link    href    ==    \#main-content
    Go To    https://${host}/?view=account
    Get Text    \#database-status    ==    Workspace ready
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Click    \#refresh-status
    Get Text    \#database-status    ==    Workspace unavailable. Ask an administrator to check the service.
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Click    \#refresh-status
    Get Text    \#database-status    ==    Workspace ready
    Go To    https://${host}/api/v1/health
    Get Text    body    contains    "core_version":"0.29.0"
    Get Text    body    contains    "app_version":"0.44.0"
    Go To    https://${host}/openapi.json
    Get Text    body    contains    /api/v1/health
    Go To    https://${host}/agents
    Get Text    h1    ==    Use with AI
    Go To    https://${host}/agents?view=tools
    Get Text    body    contains    search source text.
    Get Text    body    contains    sourced claims and bounded graph queries are available.
    Get Text    body    contains    MCP is unavailable until NS8 sign-in and hostname-root routing are configured.
    Go To    https://${host}/agents/capabilities.json
    Get Text    body    contains    "authenticated":false
    Get Text    body    contains    "operations":[]
    Close Browser
    Assert Disposable Browser Password Is Private

Verify exact installed candidate images
    Verify Installed Candidate Images    ${module_id}

Verify real native SSO and application-wide membership
    [Timeout]    15 minutes
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-authentication-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${diagnostic} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${diagnostic}    ${{ {'configured': False, 'status': 'disabled'} }}
    Provision Disposable Sso    ${module_id}    ${host}
    Wait Until Keyword Succeeds    30s    2s    Check application route
    Verify Disposable Sso    ${module_id}
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-authentication-status
    ...    return_rc=True    timeout=30s
    Should Be Equal As Integers    ${rc}    0
    ${diagnostic} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${diagnostic}    ${{ {'configured': True, 'status': 'ok'} }}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero.service
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    Verify Disposable Sso    ${module_id}

Preserve admitted identities through update and clean restore
    [Timeout]    15 minutes
    Prepare Disposable Identity Persistence
    Prepare Disposable Retrieval Persistence    ${module_id}
    Log To Console    SSO persistence: native configured update
    ${rc} =    Execute Command
    ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Verify Disposable Identity Persistence    ${module_id}
    # Core restore preserves logical UUID/path: keep its encryption key too.
    ${backup} =    Create Disposable Backup    ${module_id}    ${backup_repository}
    Set Global Variable    ${backup_repository}    ${backup}[repository]
    Log To Console    SSO persistence: native encrypted backup
    ${observer} =    Begin Disposable Backup Observer    ${module_id}
    ${rc} =    Execute Command    api-cli run run-backup --data '{"id":${backup}[backup_id]}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Verify Disposable Backup Observer    ${observer}
    Verify Disposable Snapshot    ${module_id}    ${backup}[repository]    ${backup}[path]
    ${donor_id} =    Set Variable    ${module_id}
    Remove disposable module
    Log To Console    SSO persistence: restore a new module identity
    ${output}    ${rc} =    Execute Command
    ...    api-cli run restore-module --data '{"repository":"${backup}[repository]","path":"${backup}[path]","snapshot":"latest","node":1}'
    ...    return_rc=True    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    ${restored_id} =    Installed Module Id    ${output}
    Set Global Variable    ${module_id}    ${restored_id}
    Should Not Be Equal    ${module_id}    ${donor_id}
    Verify Disposable Identity Persistence    ${module_id}
    Wait Until Keyword Succeeds    30s    2s    Check application route

Measure restored HTTPS latency and resident-memory targets
    [Timeout]    3 minutes
    ${output}    ${errors}    ${rc} =    Execute Command    python3 /tmp/oidc_probe.py performance
    ...    return_stderr=True    return_rc=True    timeout=150s
    Should Be Equal As Integers    ${rc}    0    msg=${errors}
    Log    ${output}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} python3 /tmp/czero-hardening-probe.py
    ...    return_rc=True    timeout=45s
    Should Be Equal As Integers    ${rc}    0
    Log    ${output}

Check rejected sign-in can switch accounts in a browser
    [Tags]    ui
    [Timeout]    4 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Account Switch Browser    ${module_id}    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check OAuth consent, delegated scopes and SDK calls in a browser
    [Tags]    ui
    [Timeout]    8 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Oauth Browser    ${module_id}    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check object CRUD and Reader controls in a browser
    [Tags]    ui
    [Timeout]    5 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Objects Browser    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check source ingestion, history, search and Reader controls in a browser
    [Tags]    ui
    [Timeout]    8 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Sources Browser    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check Wiki revisions, provenance, graph and Reader controls in a browser
    [Tags]    ui
    [Timeout]    5 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Wiki Browser    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check hybrid search, citations and Reader behavior in a browser
    [Tags]    ui
    [Timeout]    5 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Search Browser    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Check protected spaces, grants and revocation in a browser
    [Tags]    ui
    [Timeout]    8 minutes
    Import Library    Browser
    New Browser    chromium    headless=True    args=["--host-resolver-rules=MAP *.test ${NODE_ADDR}", "--no-proxy-server"]
    New Context    ignoreHTTPSErrors=True
    New Page
    Verify Disposable Spaces Browser    ${module_id}    ${host}
    Close Browser
    Assert Disposable Sso Browser Password Is Private

Uninstall only the disposable Czero module
    Should Not Be Empty    ${module_id}
    ${removed_id} =    Set Variable    ${module_id}
    Remove disposable module
    ${output}    ${rc} =    Execute Command    api-cli run list-installed-modules
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Contain    ${output}    "${removed_id}"
    ${rc} =    Execute Command    curl --fail --silent --max-time 10 https://${host}/api/v1/health --insecure --resolve ${host}:443:127.0.0.1
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
