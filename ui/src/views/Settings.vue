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
import {
  QueryParamService,
  UtilService,
  TaskService,
  IconService,
  PageTitleService,
} from "@nethserver/ns8-ui-lib";

export default {
  name: "Settings",
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
      progress: 0,
      taskListeners: [],
      loading: {
        getConfiguration: false,
        configureModule: false,
      },
      error: {
        getConfiguration: "",
        configureModule: "",
        host: "",
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
    clearInterval(this.urlCheckInterval);
    this.clearTaskListeners();
  },
  created() {
    this.getConfiguration();
  },
  methods: {
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
          this.error.host =
            validationError.error === "domain_already_used_in_traefik"
              ? this.$t("settings.domain_already_used_in_traefik")
              : this.$t("settings.host_invalid");
          this.focusElement("host");
        } else {
          this.error.configureModule = this.$t("error.validation_error");
        }
      }
    },
    configureModuleProgressUpdated(progress) {
      this.progress = progress;
    },
    async configureModule() {
      this.error.host = "";
      this.error.configureModule = "";
      if (!this.host) {
        this.error.host = this.$t("common.required");
        this.focusElement("host");
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
        console.error(`error creating task ${taskAction}`, err);
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
