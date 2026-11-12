// Copyright (C) 2026 C0 contributors
// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the actual supported Renovate versioning API, never a mirrored parser.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.env.RENOVATE_PACKAGE_ROOT;
assert(root,'Set RENOVATE_PACKAGE_ROOT to the installed development-only Renovate package');
const {api:Regex}=await import(pathToFileURL(resolve(root,'dist/modules/versioning/regex/index.js')));
const {api:Pep440}=await import(pathToFileURL(resolve(root,'dist/modules/versioning/pep440/index.js')));
assert.equal(Pep440.isVersion('core-v0.24.1'),false,'Reproduce the original skipped dependency');
for(const [file,project] of [
 ['renovate.json','app/pyproject.toml'],
 ['examples/fork/renovate.json','examples/fork/pyproject.toml']
]) {
 // Exercise each consumer's actual pin rather than a second version table.
 const pinned=readFileSync(project,'utf8').match(/czero-core\s*=\s*\{[^\n]*?\btag\s*=\s*"(core-v(\d+)\.(\d+)\.(\d+))"/);
 assert(pinned,'Consumer must declare a Core Git tag');
 const base=pinned[1], [major,minor,currentPatch]=pinned.slice(2).map(Number);
 const tag=(major,minor,patch)=>'core-v'+[major,minor,patch].join('.');
 const patch=tag(major,minor,currentPatch+1), next=tag(major,minor+1,0);
 const older=currentPatch>0?tag(major,minor,currentPatch-1):minor>0?tag(major,minor-1,0):tag(major-1,0,0);
 const rules=JSON.parse(readFileSync(file)).packageRules;
 const rule=rules.find(rule=>rule.matchPackageNames?.includes('Stell0/ns8-czero'));
 assert.equal(rule.automerge,false);
 assert.equal(rule.extractVersion,undefined,'Preserve the complete current tag');
 const versioning=new Regex(rule.versioning.slice('regex:'.length));
 assert(versioning.isVersion(base));
 assert(versioning.isVersion(older));
 assert(versioning.isGreaterThan(patch,base));
 assert(versioning.matches(base,rule.allowedVersions));
 assert(versioning.matches(patch,rule.allowedVersions));
 assert(!versioning.matches(next,rule.allowedVersions));
 assert(!versioning.matches(older,rule.allowedVersions));
 assert(!versioning.isVersion('0.24.2'));
 assert(!versioning.isVersion('core-v0.24.2-testing.1'));
}
console.log('Native Renovate prefix, patch, minor and prerelease bounds pass');
