# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Check the assembled application filesystem, including dependency wheels."""

import importlib.util
import sys
from pathlib import Path


def audit(root: Path) -> None:
    if not root.is_dir():
        raise SystemExit(f"Runtime directory is missing: {root}")
    forbidden_names = {
        ".agents", ".codex", ".git", ".github", "tests", "testing",
        "AGENTS.md", "PLAN.md", "SKILL.md", "pyproject.toml", "uv.lock",
    }
    product = root / 'agent-packages'
    product_files = {'plugin.json', 'memory-skill.md', 'LICENSE',
        'skills/c0-setup/SKILL.md', 'skills/c0-research/SKILL.md',
        'skills/c0-maintain-knowledge/SKILL.md', 'skills/c0-projects/SKILL.md',
        'references/connection.md', 'references/maintenance.md', 'references/projects.md'}
    product_files |= {'project/'+name+'.md' for name in ('skill','workflows','daily','weekly','recovery','scheduler')}
    allowed_skills = {product / path for path in product_files if path.endswith('/SKILL.md')}
    if product.exists():
        actual = {str(path.relative_to(product)) for path in product.rglob('*') if path.is_file()}
        if actual != product_files or any(path.is_symlink() for path in product.rglob('*')):
            raise SystemExit('Product workflow assets are missing or outside the explicit allowlist')
    unexpected = sorted(str(p) for p in root.rglob("*") if p.name in forbidden_names
                        and p not in allowed_skills
                        or p.suffix in {".h", ".pxd", ".pxi", ".pyx"}
                        or (p.name == "templates" and p.parent.name == "alembic")
                        or (p.name == "alembic" and p.parent.name == "bin"))
    tools = [name for name in ("pip", "setuptools", "uv", "pytest", "robot")
             if importlib.util.find_spec(name) is not None]
    if unexpected or tools:
        raise SystemExit(f"Development files: {unexpected}; build/test tools: {tools}")
    print("Application runtime contains no development files or build/test tools; product workflows are explicitly allowlisted")


def audit_core_distribution(root: Path) -> None:
    licenses=list(root.glob('.venv/lib/python*/site-packages/czero_core-*.dist-info/licenses/LICENSE'))
    if len(licenses)!=1:
        raise SystemExit('Core runtime license is missing or ambiguous')
    license=licenses[0]
    metadata=(license.parent.parent/'METADATA').read_text()
    if ('License-Expression: GPL-3.0-or-later' not in metadata
            or 'GNU GENERAL PUBLIC LICENSE' not in license.read_text()
            or 'Version 3, 29 June 2007' not in license.read_text()):
        raise SystemExit('Core runtime license metadata is incomplete')
    print('Core runtime includes its declared GPL license')


if __name__ == "__main__":
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/opt/czero')
    audit(root)
    audit_core_distribution(root)
