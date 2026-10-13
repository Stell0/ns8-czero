*** Settings ***
Library    SSHLibrary
Library    CzeroActions.py
Library    CzeroBrowser.py
Suite Teardown    Remove disposable module

*** Variables ***
${SCENARIO}    install
${module_id}    ${EMPTY}

*** Keywords ***
Remove disposable module
    IF    $module_id
        ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
        Set Global Variable    ${module_id}    ${EMPTY}
    END

Check smoke route
    ${output}    ${rc} =    Execute Command
    ...    curl --fail --silent --show-error --max-time 10 http://127.0.0.1/czero/${module_id}/api/v1/health
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

Configure and reconfigure the smoke service
    FOR    ${attempt}    IN RANGE    2
        ${rc} =    Execute Command    api-cli run module/${module_id}/configure-module --data '{}'
        ...    return_rc=True    return_stdout=False
        Should Be Equal As Integers    ${rc}    0
    END
    Wait Until Keyword Succeeds    30s    2s    Check smoke route
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Be Empty    ${config}

Verify application requests are logged
    Check smoke route
    # systemd expands %N in czero.service to the container name "czero".
    ${logs}    ${rc} =    Execute Command    runagent -m ${module_id} podman logs czero
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${logs}    /api/v1/health

Reject unknown settings
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"unknown":true}'
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
    Check smoke route

Restart the installed service
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user restart czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check smoke route

Exercise the native module update
    Skip If    $SCENARIO != 'update'    Clean install scenario
    # M00 has no stable predecessor: force a real Core update of this image.
    ${rc} =    Execute Command
    ...    api-cli run update-module --data '{"force":true,"module_url":"${IMAGE_URL}","instances":["${module_id}"]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    30s    2s    Check smoke route
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

Check administration and smoke HTTP in a browser
    [Tags]    ui
    Import Library    Browser
    New Browser    chromium    headless=True
    New Context    ignoreHTTPSErrors=True
    Login To Disposable Cluster    ${NODE_ADDR}
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}
    Wait For Elements State    iframe >>> h2 >> text="Status"    visible    timeout=30s
    Get Text    iframe >>> text="czero"    contains    czero
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=settings
    Wait For Elements State    iframe >>> h2 >> text="Settings"    visible    timeout=30s
    Get Text    iframe >>> p:has-text("FastAPI health endpoint")    contains    FastAPI health endpoint
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user stop czero.service
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    curl --fail --silent --max-time 10 http://127.0.0.1/czero/${module_id}/api/v1/health
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
    Click    iframe >>> button >> text="Save"
    Wait For Elements State    iframe >>> button >> text="Save"    enabled    timeout=30s
    Wait Until Keyword Succeeds    30s    2s    Check smoke route
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=about
    Wait For Elements State    iframe >>> h3 >> text="czero"    visible    timeout=30s
    Go To    https://${NODE_ADDR}/czero/${module_id}/
    Get Text    h1    contains    useful applications
    Go To    https://${NODE_ADDR}/czero/${module_id}/api/v1/health
    Get Text    body    contains    "core_version":"0.1.0"
    Go To    https://${NODE_ADDR}/czero/${module_id}/openapi.json
    Get Text    body    contains    /api/v1/health
    Go To    https://${NODE_ADDR}/czero/${module_id}/agents
    Get Text    body    contains    Authentication, storage, search and MCP are planned milestones.
    Close Browser

Uninstall only the disposable Czero module
    ${removed_id} =    Set Variable    ${module_id}
    Remove disposable module
    ${output}    ${rc} =    Execute Command    api-cli run list-installed-modules
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Contain    ${output}    "${removed_id}"
    ${rc} =    Execute Command    curl --fail --silent --max-time 10 http://127.0.0.1/czero/${removed_id}/api/v1/health
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0
