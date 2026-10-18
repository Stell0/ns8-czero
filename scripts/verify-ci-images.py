#!/usr/bin/env python3
# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Verify all published candidate images and exact sibling references."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def verify_records(records, source, owner, tag):
    expected = ['ghcr.io/'+owner+'/'+name+':'+tag for name in ('czero', 'czero-app', 'czero-postgres')]
    if (not re.fullmatch(r'[0-9a-f]{40}', source) or len(records) != 3
            or [r.get('reference') for r in records] != expected):
        raise ValueError('candidate_image_set_mismatch')
    for record in records:
        if (not re.fullmatch(r'sha256:[0-9a-f]{64}', record.get('digest', ''))
                or record.get('revision') != source):
            raise ValueError('candidate_image_identity_mismatch')
    if records[0].get('siblings') != expected[1:]:
        raise ValueError('candidate_sibling_mismatch')


def inspect(reference):
    subprocess.run(['podman', 'pull', '--quiet', reference], check=True)
    value = json.loads(subprocess.check_output(['podman', 'image', 'inspect', reference], text=True))[0]
    labels = value.get('Labels') or {}
    return {'reference': reference, 'digest': value['Digest'],
            'revision': labels.get('org.opencontainers.image.revision'),
            'siblings': labels.get('org.nethserver.images', '').split()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--owner', required=True)
    p.add_argument('--tag', required=True)
    args = p.parse_args()
    owner = args.owner.lower()
    if not re.fullmatch(r'[a-z0-9_.-]+', owner) or not re.fullmatch(r'ci-[a-z0-9-]{1,120}', args.tag):
        raise SystemExit('Invalid candidate namespace')
    records = [inspect('ghcr.io/'+owner+'/'+name+':'+args.tag) for name in ('czero', 'czero-app', 'czero-postgres')]
    verify_records(records, args.source, owner, args.tag)
    Path('candidate-images.json').write_text(json.dumps({'source': args.source, 'tag': args.tag, 'images': records}, indent=2)+'\n')
    print('All three candidate digests, source revisions and sibling references verified')


if __name__ == '__main__':
    main()
