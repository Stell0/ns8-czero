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
    Should Contain    ${output}    "core_version":"0.6.0"

*** Test Cases ***
Install Czero with its own identity
    ${install_image} =    Set Variable    ${IMAGE_URL}
    IF    $SCENARIO == 'update'
        ${install_image} =    Set Variable    ghcr.io/stell0/czero@sha256:2543268f93026d1a4a992174f63375181437ae3dd9eec37ec46deb142034f9ad
    END
    ${output}    ${rc} =    Execute Command    add-module ${install_image} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${installed_id} =    Installed Module Id    ${output}
    Set Global Variable    ${module_id}    ${installed_id}
    Should Start With    ${module_id}    czero
    Set Global Variable    ${host}    ${module_id}.test
    IF    $SCENARIO == 'update'
        # Freeze the older component images too, not just the module shell.
        ${rc} =    Execute Command
        ...    runagent -m ${module_id} python3 -c "import agent; agent.mset_env({'CZERO_APP_IMAGE':'ghcr.io/stell0/czero-app@sha256:4f8c20c670bf67223660af01f7ef19526a2eff68d15cb8b4c6df9b3880e62d8e','CZERO_POSTGRES_IMAGE':'ghcr.io/stell0/czero-postgres@sha256:a459ab2bc7f1bb37d87e13927efe2dcb6d2108ba92c810ec2c8eee1f15485320'})"
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
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Check application route

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
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=settings
    Wait For Elements State    iframe >>> h2 >> text="Settings"    visible    timeout=30s
    Wait For Elements State    iframe >>> .ns-text-input input    enabled    timeout=30s
    Get Property    iframe >>> .ns-text-input input    value    ==    ${host}
    Fill Text    iframe >>> .ns-text-input input    localhost
    Click    iframe >>> button >> text="Save"
    Wait For Elements State    iframe >>> text="Enter a valid fully qualified DNS hostname."    visible    timeout=30s
    Fill Text    iframe >>> .ns-text-input input    ${host}
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
    Wait For Elements State    iframe >>> .ns-text-input input    enabled    timeout=30s
    Get Property    iframe >>> .ns-text-input input    value    ==    ${host}
    Get Attribute    iframe >>> a:has-text("Open C0 application")    href    ==    https://${host}/
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=about
    Wait For Elements State    iframe >>> h3 >> text="czero"    visible    timeout=30s
    Go To    https://${host}/
    Get Text    h1    contains    useful applications
    Get Text    \#database-status    ==    Database ready
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Click    \#refresh-status
    Get Text    \#database-status    ==    Database unavailable
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user start czero-postgres.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Click    \#refresh-status
    Get Text    \#database-status    ==    Database ready
    Go To    https://${host}/api/v1/health
    Get Text    body    contains    "core_version":"0.6.0"
    Go To    https://${host}/openapi.json
    Get Text    body    contains    /api/v1/health
    Go To    https://${host}/agents
    Get Text    body    contains    Objects, search and MCP are planned milestones.
    Close Browser
    Assert Disposable Browser Password Is Private

Verify real native SSO and application-wide membership
    [Timeout]    15 minutes
    Provision Disposable Sso    ${module_id}    ${host}
    Wait Until Keyword Succeeds    30s    2s    Check application route
    Verify Disposable Sso    ${module_id}
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero.service
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check application route
    Verify Disposable Sso    ${module_id}

Preserve admitted identities through update and clean restore
    [Timeout]    15 minutes
    Prepare Disposable Identity Persistence
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
    ${rc} =    Execute Command    api-cli run run-backup --data '{"id":${backup}[backup_id]}'
    ...    return_rc=True    return_stdout=False    timeout=180s
    Should Be Equal As Integers    ${rc}    0
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
