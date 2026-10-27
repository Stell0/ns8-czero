# External scheduler installation and verification handoff

Read the exact project binding and desired schedule. This archive installs no task and changes no C0 schedule. Keep disabled projects disabled. Obtain a separate explicit installation/activation request for the intended project before changing its host schedule.

1. Verify that the connected C0 app points to the bound canonical URL and that the intended account can read this exact protected project. Complete the existing OAuth flow with the required role-eligible scopes. Verify the host can retain/renew that connection without an interactive fallback; do not invent client-credentials or API-key authentication.
2. Install/attach this project's skill in the intended host and test the daily/weekly prompts manually against an authorized disposable project. Web tasks need durable prompt/skill context and accessible C0 content, not a local worktree.
3. Using the host's supported Scheduled interface/API, create exactly one daily and one weekly task for this project. Copy the complete respective prompt, bind the exact skill/connection and use the binding's IANA timezone/local times. Read the saved task settings back. Verify DST behavior against project_schedule_get; fixed UTC recurrence alone does not establish local-time correctness.
4. Record actual host task IDs, prompt/skill version, saved timezone/occurrences and observed authentication result. Store project_runner_observe reports with their true source (operator_report, runner_report or sdk_simulation). A reported installation does not verify execution.
5. Observe an actual scheduled run and retrieve its C0 run/checkpoints, coverage and saved report independently. Record actual external result publication and any observed notification separately. A manual run, local fake agent, configuration, HTTP 200 or unread indicator does not prove unattended research, delivery or human reading.

If the host lacks the required installation API or cannot retain the necessary authorized connection, preserve these complete prompts/settings and record that capability as unverified/blocked. Do not substitute C0 deterministic jobs or create unrelated Page/Site automations. No external task has been installed by package generation.

Official host references: [Scheduled tasks](https://learn.chatgpt.com/docs/automations), [MCP authentication](https://developers.openai.com/plugins/build/auth). Availability and host behavior require verification in the intended account. Local-project desktop tasks additionally depend on the machine/app remaining available.
