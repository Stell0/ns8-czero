<!--
  Copyright (C) 2023 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <cv-grid fullWidth>
    <cv-row>
      <cv-column class="page-title">
        <h2>{{ $t("settings.title") }}</h2>
      </cv-column>
    </cv-row>
    <cv-row v-if="error.getConfiguration">
      <cv-column>
        <NsInlineNotification
          kind="error"
          :title="$t('action.get-configuration')"
          :description="error.getConfiguration"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <cv-tile light>
          <cv-form @submit.prevent="configureModule">
            <p>{{ $t("settings.description") }}</p>
            <NsTextInput
              v-model.trim="host"
              ref="host"
              :label="$t('settings.host')"
              :helper-text="$t('settings.host_help')"
              :invalid-message="error.host"
              :disabled="loading.getConfiguration || loading.configureModule"
            />
            <NsToggle
              v-model="letsEncrypt"
              :label="$t('settings.lets_encrypt')"
              :disabled="loading.getConfiguration || loading.configureModule"
            />
            <p>{{ $t("settings.certificate_help") }}</p>
            <NsToggle
              v-model="ssoEnabled"
              data-c0-sso-switch="true"
              :label="$t('settings.enable_sso')"
              :disabled="loading.getConfiguration || loading.configureModule"
            />
            <div v-if="ssoEnabled">
              <NsComboBox
                v-model="idp"
                ref="idp"
                :title="$t('settings.idp')"
                :label="$t('settings.choose_idp')"
                :options="identityProviders"
                :invalid-message="error.idp"
                :disabled="loading.authOptions || loading.configureModule"
              />
              <NsComboBox
                v-model="userDomain"
                ref="userDomain"
                :title="$t('settings.user_domain')"
                :label="$t('settings.choose_domain')"
                :options="userDomains"
                :invalid-message="error.user_domain"
                :disabled="loading.authOptions || loading.configureModule"
              />
              <NsTextInput
                v-model.trim="owner"
                ref="owner"
                :label="$t('settings.owner')"
                :helper-text="$t('settings.owner_help')"
                :invalid-message="error.owner"
                :disabled="loading.getConfiguration || loading.configureModule"
              />
              <p>{{ $t("settings.sharing_help") }}</p>
              <h3>{{ $t("settings.cimd_title") }}</h3>
              <NsToggle
                v-model="cimdEnabled"
                data-c0-cimd-switch="true"
                :label="$t('settings.cimd_enabled')"
                :disabled="loading.getConfiguration || loading.configureModule"
              />
              <p>{{ $t("settings.cimd_help") }}</p>
              <NsInlineNotification
                v-if="error.cimd_enabled"
                kind="error"
                :description="error.cimd_enabled"
                :showCloseButton="false"
              />
              <h3>{{ $t("settings.session_policy_title") }}</h3>
              <p>{{ $t("settings.session_policy_help") }}</p>
              <NsTextInput
                v-model="sessionPolicy.absolute_seconds"
                ref="sessionPolicyAbsolute"
                type="number"
                min="60"
                max="86400"
                step="1"
                :label="$t('settings.session_absolute')"
                :disabled="loading.getConfiguration || loading.configureModule"
              />
              <NsTextInput
                v-model="sessionPolicy.idle_seconds"
                type="number"
                min="60"
                max="86400"
                step="1"
                :label="$t('settings.session_idle')"
                :disabled="loading.getConfiguration || loading.configureModule"
              />
              <NsInlineNotification
                v-if="error.session_policy"
                kind="error"
                :description="error.session_policy"
                :showCloseButton="false"
              />
              <NsInlineNotification
                v-if="error.authOptions"
                kind="warning"
                :description="error.authOptions"
                :showCloseButton="false"
              />
              <h3>{{ $t("settings.connection_policy_title") }}</h3>
              <p>{{ $t("settings.connection_policy_help") }}</p>
              <NsTextInput
                v-model="connectionIdleDays"
                ref="connectionIdleDays"
                type="number"
                min="1"
                max="365"
                step="1"
                :label="$t('settings.connection_idle_days')"
                :disabled="loading.getConfiguration || loading.configureModule"
              />
              <NsInlineNotification
                v-if="error.connection_idle_seconds"
                kind="error"
                :description="error.connection_idle_seconds"
                :showCloseButton="false"
              />
            </div>
            <RetrievalSettings
              :value="retrieval"
              :error="error.retrieval"
              :disabled="loading.getConfiguration || loading.configureModule"
            />
            <p v-if="savedHost">
              <a
                :href="'https://' + savedHost + '/'"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ $t("settings.open_application") }}
              </a>
            </p>
            <NsProgressBar
              v-if="loading.configureModule"
              :value="progress"
              :indeterminate="!progress"
            />
            <cv-row v-if="error.configureModule">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="$t('action.configure-module')"
                  :description="error.configureModule"
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <NsButton
              kind="primary"
              :icon="Save20"
              :loading="loading.configureModule"
              :disabled="loading.getConfiguration || loading.configureModule"
              >{{ $t("settings.save") }}</NsButton
            >
          </cv-form>
        </cv-tile>
      </cv-column>
    </cv-row>
  </cv-grid>
</template>

<script>
import to from "await-to-js";
import { mapState } from "vuex";
import RetrievalSettings from "../components/RetrievalSettings.vue";
import { sessionPolicyForm, sessionPolicyPayload } from "../session-policy.mjs";
import { connectionPolicyForm, connectionPolicyPayload } from "../connection-policy.mjs";
import {
  retrievalForm,
  retrievalPayload,
  clearRetrievalKeys,
} from "../retrieval-settings.mjs";
import {
  QueryParamService,
  UtilService,
  TaskService,
  IconService,
  PageTitleService,
} from "@nethserver/ns8-ui-lib";

export default {
  name: "Settings",
  components: { RetrievalSettings },
  mixins: [
    TaskService,
    IconService,
    UtilService,
    QueryParamService,
    PageTitleService,
  ],
  pageTitle() {
    return this.$t("settings.title") + " - " + this.appName;
  },
  data() {
    return {
      q: {
        page: "settings",
      },
      urlCheckInterval: null,
      host: "",
      savedHost: "",
      letsEncrypt: false,
      ssoEnabled: false,
      cimdEnabled: false,
      idp: "",
      userDomain: "",
      owner: "",
      retrieval: retrievalForm(),
      sessionPolicy: sessionPolicyForm(),
      connectionIdleDays: connectionPolicyForm(),
      identityProviders: [],
      userDomains: [],
      pendingIdentity: null,
      progress: 0,
      taskListeners: [],
      loading: {
        getConfiguration: false,
        configureModule: false,
        authOptions: false,
      },
      error: {
        getConfiguration: "",
        configureModule: "",
        host: "",
        idp: "",
        user_domain: "",
        owner: "",
        authOptions: "",
        retrieval: "",
        session_policy: "",
        connection_idle_seconds: "",
        cimd_enabled: "",
      },
    };
  },
  computed: {
    ...mapState(["instanceName", "core", "appName"]),
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      vm.watchQueryData(vm);
      vm.urlCheckInterval = vm.initUrlBindingForApp(vm, vm.q.page);
    });
  },
  beforeRouteLeave(to, from, next) {
    clearInterval(this.urlCheckInterval);
    next();
  },
  beforeDestroy() {
    clearRetrievalKeys(this.retrieval);
    clearInterval(this.urlCheckInterval);
    this.clearTaskListeners();
  },
  created() {
    this.getAuthOptions();
    this.getConfiguration();
  },
  methods: {
    async getAuthOptions() {
      this.loading.authOptions = true;
      const action = "get-auth-options";
      const eventId = this.getUuid();
      this.listenTask(`${action}-aborted-${eventId}`, () => {
        this.clearTaskListeners(action);
        this.loading.authOptions = false;
        this.error.authOptions = this.$t("settings.auth_options_failed");
      });
      this.listenTask(`${action}-completed-${eventId}`, (context, result) => {
        this.clearTaskListeners(action);
        this.identityProviders = result.output.providers.map((provider) => ({
          name: provider.id,
          value: provider.id,
          label: provider.label,
        }));
        this.userDomains = result.output.domains.map((domain) => ({
          name: domain,
          value: domain,
          label: domain,
        }));
        this.loading.authOptions = false;
        this.applyIdentitySelection();
      });
      const [error] = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action,
          extra: {
            eventId,
            isNotificationHidden: true,
            title: this.$t("action." + action),
          },
        })
      );
      if (error) {
        this.clearTaskListeners(action);
        this.loading.authOptions = false;
        this.error.authOptions = this.$t("settings.auth_options_failed");
      }
    },
    applyIdentitySelection() {
      if (!this.pendingIdentity || this.loading.authOptions) return;
      const selection = this.pendingIdentity;
      this.pendingIdentity = null;
      this.$nextTick(() => {
        this.idp = selection.idp;
        this.userDomain = selection.user_domain;
      });
    },
    listenTask(event, handler, repeated = false) {
      this.taskListeners.push({ event, handler });
      this.core.$root[repeated ? "$on" : "$once"](event, handler);
    },
    clearTaskListeners(action = "") {
      this.taskListeners = this.taskListeners.filter(({ event, handler }) => {
        if (!action || event.startsWith(action + "-")) {
          this.core.$root.$off(event, handler);
          return false;
        }
        return true;
      });
    },
    async getConfiguration() {
      this.loading.getConfiguration = true;
      this.error.getConfiguration = "";
      const taskAction = "get-configuration";
      const eventId = this.getUuid();

      // register to task error
      this.listenTask(
        `${taskAction}-aborted-${eventId}`,
        this.getConfigurationAborted
      );

      // register to task completion
      this.listenTask(
        `${taskAction}-completed-${eventId}`,
        this.getConfigurationCompleted
      );

      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.getConfiguration = this.getErrorMessage(err);
        this.loading.getConfiguration = false;
        this.clearTaskListeners(taskAction);
        return;
      }
    },
    getConfigurationAborted() {
      this.clearTaskListeners("get-configuration");
      this.error.getConfiguration = this.$t("error.generic_error");
      this.loading.getConfiguration = false;
    },
    getConfigurationCompleted(taskContext, taskResult) {
      this.clearTaskListeners("get-configuration");
      this.host = taskResult.output.host;
      this.savedHost = this.host;
      this.letsEncrypt = taskResult.output.lets_encrypt;
      this.cimdEnabled = taskResult.output.cimd_enabled === true;
      this.owner = taskResult.output.owner;
      this.retrieval = retrievalForm(taskResult.output.retrieval);
      this.sessionPolicy = sessionPolicyForm(taskResult.output.session_policy);
      this.connectionIdleDays = connectionPolicyForm(taskResult.output.connection_idle_seconds);
      this.ssoEnabled = Boolean(taskResult.output.user_domain);
      this.pendingIdentity = taskResult.output;
      this.applyIdentitySelection();
      this.loading.getConfiguration = false;
    },
    configureModuleValidationFailed(validationErrors) {
      this.clearTaskListeners("configure-module");
      this.loading.configureModule = false;
      for (const validationError of validationErrors) {
        if (
          validationError.parameter === "host" ||
          validationError.field === "host"
        ) {
          const messages = {
            domain_already_used_in_traefik:
              "settings.domain_already_used_in_traefik",
            newcert_acme_error: "settings.certificate_failed",
          };
          this.error.host = this.$t(
            messages[validationError.error] || "settings.host_invalid"
          );
          this.focusElement("host");
        } else {
          const field = validationError.parameter || validationError.field;
          if (field === "retrieval") {
            this.error.retrieval = this.$t("settings.retrieval_invalid");
          } else if (field === "cimd_enabled") {
            this.error.cimd_enabled = this.$t("settings.cimd_invalid");
          } else if (field === "session_policy") {
            this.error.session_policy = this.$t(
              "settings.session_policy_invalid"
            );
          } else if (field === "connection_idle_seconds") {
            this.error.connection_idle_seconds = this.$t("settings.connection_policy_invalid");
          } else if (["idp", "user_domain", "owner"].includes(field)) {
            this.error[field] = this.$t("settings.identity_invalid");
          } else {
            this.error.configureModule = this.$t("error.validation_error");
          }
        }
      }
    },
    configureModuleProgressUpdated(progress) {
      this.progress = progress;
    },
    async configureModule() {
      this.error.host = "";
      this.error.configureModule = "";
      this.error.idp = "";
      this.error.user_domain = "";
      this.error.owner = "";
      this.error.retrieval = "";
      this.error.session_policy = "";
      this.error.connection_idle_seconds = "";
      this.error.cimd_enabled = "";
      let sessionPolicy;
      let connectionIdleSeconds;
      try {
        connectionIdleSeconds = connectionPolicyPayload(this.connectionIdleDays);
      } catch (_) {
        this.error.connection_idle_seconds = this.$t("settings.connection_policy_invalid");
        this.focusElement("connectionIdleDays");
        return;
      }
      try {
        sessionPolicy = sessionPolicyPayload(this.sessionPolicy);
      } catch (_) {
        this.error.session_policy = this.$t("settings.session_policy_invalid");
        this.focusElement("sessionPolicyAbsolute");
        return;
      }
      if (!this.host) {
        this.error.host = this.$t("common.required");
        this.focusElement("host");
        return;
      }
      if (this.ssoEnabled && (!this.idp || !this.userDomain || !this.owner)) {
        this.error.configureModule = this.$t("settings.identity_required");
        return;
      }
      this.progress = 0;
      this.loading.configureModule = true;
      const taskAction = "configure-module";
      const eventId = this.getUuid();

      // register to task error
      this.listenTask(
        `${taskAction}-aborted-${eventId}`,
        this.configureModuleAborted
      );

      this.listenTask(
        `${taskAction}-progress-${eventId}`,
        this.configureModuleProgressUpdated,
        true
      );

      // register to task validation
      this.listenTask(
        `${taskAction}-validation-failed-${eventId}`,
        this.configureModuleValidationFailed
      );

      // register to task completion
      this.listenTask(
        `${taskAction}-completed-${eventId}`,
        this.configureModuleCompleted
      );

      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data: {
            host: this.host.toLowerCase(),
            lets_encrypt: this.letsEncrypt,
            idp: this.ssoEnabled ? this.idp : "",
            user_domain: this.ssoEnabled ? this.userDomain : "",
            owner: this.ssoEnabled ? this.owner : "",
            retrieval: retrievalPayload(this.retrieval),
            session_policy: sessionPolicy,
            connection_idle_seconds: connectionIdleSeconds,
            cimd_enabled: this.cimdEnabled,
          },
          extra: {
            title: this.$t("settings.configure_instance", {
              instance: this.instanceName,
            }),
            description: this.$t("common.processing"),
            isProgressNotified: true,
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        clearRetrievalKeys(this.retrieval);
        this.error.configureModule = this.getErrorMessage(err);
        this.loading.configureModule = false;
        this.clearTaskListeners(taskAction);
        return;
      }
    },
    configureModuleAborted() {
      this.clearTaskListeners("configure-module");
      this.error.configureModule = this.$t("error.generic_error");
      this.loading.configureModule = false;
    },
    configureModuleCompleted() {
      clearRetrievalKeys(this.retrieval);
      this.clearTaskListeners("configure-module");
      this.loading.configureModule = false;

      // reload configuration
      this.getConfiguration();
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
</style>
