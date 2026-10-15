<!-- Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later -->
<template>
  <section aria-labelledby="runtime-heading">
    <h3 id="runtime-heading">{{ $t("status.runtime") }}</h3>
    <NsButton kind="tertiary" :disabled="busy" @click="refresh">
      {{ $t("status.refresh") }}
    </NsButton>
    <cv-row>
      <cv-column v-for="card in cards" :key="card.key" :md="4" :max="4">
        <div :id="'runtime-' + card.key">
          <NsInfoCard
            light
            :title="card.title"
            :description="card.description"
            :loading="loading[card.action]"
          />
          <NsInlineNotification
            v-if="errors[card.action]"
            kind="error"
            :title="$t('action.' + card.action)"
            :description="$t('status.check_failed')"
            :showCloseButton="false"
          />
        </div>
      </cv-column>
    </cv-row>
  </section>
</template>
<script>
import { mapState } from "vuex";
import { TaskService, UtilService } from "@nethserver/ns8-ui-lib";

const actions = [
  "get-runtime-status",
  "get-authentication-status",
  "get-scheduler-status",
];
export default {
  name: "RuntimeStatus",
  mixins: [TaskService, UtilService],
  data() {
    return {
      values: {},
      loading: {},
      errors: {},
      listeners: [],
      generation: 0,
      destroyed: false,
    };
  },
  computed: {
    ...mapState(["instanceName", "core"]),
    busy() {
      return actions.some((action) => this.loading[action]);
    },
    cards() {
      const runtime = this.values[actions[0]],
        auth = this.values[actions[1]],
        scheduler = this.values[actions[2]];
      const t = (key) => this.$t("status." + key);
      const db = runtime && runtime.database,
        retrieval = runtime && runtime.retrieval;
      const schedulerState = !scheduler
        ? "unknown"
        : scheduler.worker_failed
        ? "worker_failed"
        : scheduler.worker_running
        ? "worker_running"
        : scheduler.timer_active_state === "failed"
        ? "timer_failed"
        : scheduler.timer_active
        ? "timer_ready"
        : "timer_paused";
      return [
        {
          key: "database",
          action: actions[0],
          title: t(
            db
              ? db.status === "ok"
                ? "database_ready"
                : "database_unavailable"
              : "unknown"
          ),
          description:
            db && db.status === "ok"
              ? t("database") +
                " · " +
                db.schema_revision +
                " · pgvector " +
                db.vector_version
              : t("database"),
        },
        {
          key: "authentication",
          action: actions[1],
          title: t(
            auth
              ? auth.status === "ok"
                ? "authentication_ready"
                : auth.status === "disabled"
                ? "authentication_disabled"
                : "authentication_unavailable"
              : "unknown"
          ),
          description: t("authentication"),
        },
        {
          key: "scheduler",
          action: actions[2],
          title: t(schedulerState),
          description: t("worker_help"),
        },
        {
          key: "retrieval",
          action: actions[0],
          title: t(
            !retrieval
              ? "unknown"
              : !retrieval.configuration_valid
              ? "retrieval_invalid"
              : retrieval.embeddings_configured
              ? "embeddings_configured"
              : "text_search"
          ),
          description: t(
            retrieval && retrieval.scorer_mode !== "off"
              ? "scorer_configured"
              : "text_fallback"
          ),
        },
      ];
    },
  },
  created() {
    this.refresh();
  },
  beforeDestroy() {
    this.destroyed = true;
    this.generation++;
    this.clearListeners();
  },
  methods: {
    clearListeners(action = "") {
      this.listeners = this.listeners.filter((item) => {
        if (!action || item.action === action) {
          this.core.$root.$off(item.event, item.callback);
          return false;
        }
        return true;
      });
    },
    refresh() {
      if (this.destroyed) return;
      this.generation++;
      this.clearListeners();
      for (const action of actions) this.check(action, this.generation);
    },
    async check(action, generation) {
      this.$set(this.loading, action, true);
      this.$set(this.errors, action, false);
      this.$delete(this.values, action);
      const eventId = this.getUuid();
      let settled = false;
      const current = () => !this.destroyed && generation === this.generation;
      const finish = (ok, result) => {
        if (!current() || settled) return;
        settled = true;
        this.clearListeners(action);
        this.$set(this.loading, action, false);
        this.$set(this.errors, action, !ok);
        if (ok) this.$set(this.values, action, result.output);
      };
      for (const [kind, callback] of [
        ["completed", (context, result) => finish(true, result)],
        ["aborted", () => finish(false)],
      ]) {
        const event = action + "-" + kind + "-" + eventId;
        this.listeners.push({ action, event, callback });
        this.core.$root.$once(event, callback);
      }
      try {
        await this.createModuleTaskForApp(this.instanceName, {
          action,
          extra: {
            eventId,
            isNotificationHidden: true,
            title: this.$t("action." + action),
          },
        });
      } catch (_) {
        finish(false);
      }
    },
  },
};
</script>
