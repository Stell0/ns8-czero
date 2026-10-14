<!-- Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later -->
<template>
  <section>
    <h3>{{ $t("settings.retrieval_title") }}</h3>
    <p>{{ $t("settings.retrieval_privacy") }}</p>
    <NsInlineNotification
      v-if="error"
      kind="error"
      :description="error"
      :showCloseButton="false"
    />
    <NsToggle
      v-model="value.embedding.enabled"
      :label="$t('settings.embedding_enable')"
      :disabled="disabled"
    />
    <NsComboBox
      v-model="value.scorer.mode"
      :options="scorerModes"
      :title="$t('settings.scorer_mode')"
      :label="$t('settings.scorer_mode')"
      :disabled="disabled"
    />
    <div v-for="section in ['embedding', 'scorer']" :key="section">
      <h4>{{ $t("settings." + section) }}</h4>
      <NsTextInput
        v-model.trim="value[section].endpoint"
        :label="$t('settings.provider_endpoint')"
        :disabled="disabled"
      />
      <NsTextInput
        v-model.trim="value[section].model"
        :label="$t('settings.provider_model')"
        :disabled="disabled"
      />
      <NsTextInput
        v-model="value[section].api_key"
        type="password"
        autocomplete="new-password"
        :label="$t('settings.provider_key')"
        :helper-text="
          $t(
            value[section].api_key_configured
              ? 'settings.key_saved'
              : 'settings.key_empty'
          )
        "
        :disabled="disabled"
      />
      <NsToggle
        v-model="value[section].clear_api_key"
        :label="$t('settings.key_clear')"
        :disabled="disabled"
      />
      <NsTextInput
        v-model="value[section].timeout"
        type="number"
        min="0.05"
        max="5"
        step="0.05"
        :label="$t('settings.provider_timeout')"
        :disabled="disabled"
      />
    </div>
    <NsTextInput
      v-model="value.embedding.dimensions"
      type="number"
      min="1"
      max="2000"
      :label="$t('settings.embedding_dimensions')"
      :disabled="disabled"
    />
    <NsToggle
      v-model="value.embedding.send_dimensions"
      :label="$t('settings.embedding_send_dimensions')"
      :disabled="disabled"
    />
    <NsTextInput
      v-model="value.scorer.threshold"
      type="number"
      min="0"
      max="1"
      step="0.01"
      :label="$t('settings.scorer_threshold')"
      :helper-text="$t('settings.threshold_help')"
      :disabled="disabled"
    />
    <h4>{{ $t("settings.retrieval_limits") }}</h4>
    <NsTextInput
      v-for="limit in caps"
      :key="limit.name"
      v-model="value.limits[limit.name]"
      type="number"
      :min="limit.min"
      :max="limit.max"
      :label="$t('settings.limit_' + limit.name)"
      :disabled="disabled"
    />
  </section>
</template>
<script>
export default {
  name: "RetrievalSettings",
  props: {
    value: { type: Object, required: true },
    disabled: Boolean,
    error: String,
  },
  computed: {
    scorerModes() {
      return ["off", "rerank", "filter"].map((mode) => ({
        name: mode,
        value: mode,
        label: this.$t("settings.scorer_" + mode),
      }));
    },
  },
  data() {
    return {
      caps: [
        { name: "max_limit", min: 1, max: 50 },
        { name: "candidates", min: 1, max: 64 },
        { name: "graph_depth", min: 0, max: 3 },
        { name: "scorer_candidates", min: 1, max: 16 },
      ],
    };
  },
};
</script>
