#!/bin/bash

#
# Copyright (C) 2023 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Terminate on error
set -euo pipefail

# Prepare variables for later use
images=()
# The image will be pushed to GitHub container registry
repobase="${REPOBASE:-ghcr.io/stell0}"
repobase="${repobase,,}"
# Configure the image name
reponame="czero"
imagetag="${IMAGETAG:-latest}"
imagetag="${imagetag//\//-}"
revision="${GITHUB_SHA:-$(git rev-parse HEAD)}"

# Build the versioned C0 application separately so the NS8 module image stays
# a small shell containing actions, metadata and its administrator UI.
buildah build \
    --file containers/czero-app/Containerfile \
    --force-rm \
    --layers \
    --jobs "$(nproc)" \
    --tag "${repobase}/czero-app" \
    --tag "${repobase}/czero-app:${imagetag}" \
    --label="org.opencontainers.image.source=https://github.com/${GITHUB_REPOSITORY:-Stell0/ns8-czero}" \
    --label="org.opencontainers.image.revision=${revision}" \
    --label="org.opencontainers.image.licenses=GPL-3.0-or-later" \
    --label="org.opencontainers.image.title=C0 application runtime" \
    .

# Small derived image: upstream PostgreSQL/vector runtime without PGXS tools.
buildah build --file containers/czero-postgres/Containerfile --force-rm --layers \
    --tag "${repobase}/czero-postgres" --tag "${repobase}/czero-postgres:${imagetag}" \
    --label="org.opencontainers.image.source=https://github.com/${GITHUB_REPOSITORY:-Stell0/ns8-czero}" \
    --label="org.opencontainers.image.revision=${revision}" \
    --label="org.opencontainers.image.licenses=GPL-3.0-or-later" \
    --label="org.opencontainers.image.title=C0 PostgreSQL and pgvector runtime" \
    .

# Create a new empty container image
container=$(buildah from scratch)

# Reuse existing nodebuilder-czero container, to speed up builds
if ! buildah containers --format "{{.ContainerName}}" | grep -q nodebuilder-czero; then
    echo "Pulling NodeJS runtime..."
    buildah from --name nodebuilder-czero -v "${PWD}:/usr/src:Z" docker.io/library/node:24.21.0-slim
fi

echo "Build static UI files with node..."
buildah run \
    --workingdir=/usr/src/ui \
    --env="NODE_OPTIONS=--openssl-legacy-provider" \
    nodebuilder-czero \
    sh -c "corepack enable && yarn install --immutable && yarn build"

# Add imageroot directory to the container image
buildah add "${container}" imageroot /imageroot
buildah add "${container}" ui/dist /ui
# Setup the entrypoint, ask to reserve one TCP port with the label and set a rootless container
buildah config --entrypoint=/ \
    --label="org.opencontainers.image.source=https://github.com/${GITHUB_REPOSITORY:-Stell0/ns8-czero}" \
    --label="org.opencontainers.image.revision=${revision}" \
    --label="org.opencontainers.image.licenses=GPL-3.0-or-later" \
    --label="org.opencontainers.image.title=C0 (Czero) NS8 module" \
    --label="org.nethserver.authorizations=traefik@node:routeadm cluster:accountconsumer idp@any:clientadm" \
    --label="org.nethserver.tcp-ports-demand=1" \
    --label="org.nethserver.rootfull=0" \
    --label="org.nethserver.volumes=czero-db-data czero-sources" \
    --label="org.nethserver.images=${repobase}/czero-app:${imagetag} ${repobase}/czero-postgres:${imagetag}" \
    "${container}"
# Commit the image
buildah commit "${container}" "${repobase}/${reponame}"

# Append the image URL to the images array
images+=("${repobase}/czero-app" "${repobase}/czero-postgres" "${repobase}/${reponame}")

#
# NOTICE:
#
# It is possible to build and publish multiple images.
#
# 1. create another buildah container
# 2. add things to it and commit it
# 3. append the image url to the images array
#

#
# Setup CI when pushing to Github. 
# Warning! docker::// protocol expects lowercase letters (,,)
if [[ -n "${CI:-}" ]]; then
    # Set output value for Github Actions
    printf "images=%s\n" "${images[*],,}" >> "${GITHUB_OUTPUT}"
else
    # Just print info for manual push
    printf "Publish the images with:\n\n"
    for image in "${images[@],,}"; do printf "  buildah push %s docker://%s:%s\n" "${image}" "${image}" "${imagetag}" ; done
    printf "\n"
fi
