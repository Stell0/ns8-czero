*** Settings ***
Library    SSHLibrary
Library    CzeroActions.py
Library    CzeroBrowser.py
Suite Teardown    Remove disposable module

*** Variables ***
${SCENARIO}    install
${module_id}    ${EMPTY}
${other_id}    ${EMPTY}
${host}    ${EMPTY}

*** Keywords ***
Remove disposable module
    IF    $other_id
        ${rc} =    Execute Command    remove-module --no-preserve ${other_id}
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${other_id}    ${EMPTY}
    END
    IF    $module_id
        ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${module_id}    ${EMPTY}
    END

Check legacy route
    ${output}    ${rc} =    Execute Command
    ...    curl --fail --silent --show-error --max-time 10 http://127.0.0.1/czero/${module_id}/api/v1/health
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${output}    "status":"ok"

Check application route
    ${output}    ${rc} =    Execute Command
    ...    curl --fail --silent --show-error --max-time 10 https://${host}/api/v1/health --insecure --resolve ${host}:443:127.0.0.1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${output}    "status":"ok"
    Should Contain    ${output}    "core_version":"0.1.0"

*** Test Cases ***
Install Czero with its own identity
    ${output}    ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${installed_id} =    Installed Module Id    ${output}
    Set Global Variable    ${module_id}    ${installed_id}
    Should Start With    ${module_id}    czero
    Set Global Variable    ${host}    ${module_id}.test

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
    ...    runagent -m ${module_id} python3 -c "import agent,os; m=os.environ['MODULE_ID']; agent.mset_env({'CZERO_MODULE_ID':m,'CZERO_BASE_PATH':'/czero/'+m}); agent.set_route({'instance':m,'url':'http://127.0.0.1:'+os.environ['TCP_PORT'],'path':'/czero/'+m,'http2https':False,'lets_encrypt':False})"
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
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

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
    Go To    https://${host}/api/v1/health
    Get Text    body    contains    "core_version":"0.1.0"
    Go To    https://${host}/openapi.json
    Get Text    body    contains    /api/v1/health
    Go To    https://${host}/agents
    Get Text    body    contains    Authentication, storage, search and MCP are planned milestones.
    Close Browser

Uninstall only the disposable Czero module
    ${removed_id} =    Set Variable    ${module_id}
    Remove disposable module
    ${output}    ${rc} =    Execute Command    api-cli run list-installed-modules
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Contain    ${output}    "${removed_id}"
    ${rc} =    Execute Command    curl --fail --silent --max-time 10 https://${host}/api/v1/health --insecure --resolve ${host}:443:127.0.0.1
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
