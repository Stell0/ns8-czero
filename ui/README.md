# Native NS8 settings UI

This directory contains C0's Vue 2/Carbon settings UI for the NS8 cluster manager. It configures the module and shows its operational status. The knowledge-reading website is the separate Vue 3/Nebula application in [app/frontend](../app/frontend/package.json).

Use the committed Yarn lock and pinned CI Node version. From this directory:

```sh
corepack yarn install --immutable
NODE_OPTIONS=--openssl-legacy-provider corepack yarn build
```

See [C0 development](../docs/development.md) for the full validation workflow and [the NS8 developer manual](https://nethserver.github.io/ns8-core/ui/modules/#module-ui-development) for native module UI development. Keep settings and knowledge-reader behavior on their existing surfaces.
