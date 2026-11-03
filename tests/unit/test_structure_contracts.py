# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from czero_core.extraction import Extracted,ExtractionError
from czero_core.structure import derive,section_chunks

BODY='# Required setup\n\nInstall the safety key.\n\n## Procedure\n\nSee [setup](#required-setup).\n\n> [!WARNING]\n> Disconnect power.\n\n- Check the key\n- Turn the switch\n\n| Part | State |\n| --- | --- |\n| Key | Ready |\n\n```text\n# Fake heading\n\n[ignore](#procedure)\n```\n\n## Confirmation\n\nStatus café 東京.\n'


def test_markdown_tree_types_links_and_exact_spans():
    evidence=Extracted(BODY,[]); structure=derive(evidence,'text/markdown')
    assert [BODY[s['heading']['start']:s['heading']['end']] for s in structure['sections'][1:]]==['# Required setup','## Procedure','## Confirmation']
    assert [s['parent'] for s in structure['sections']]==[None,'s0','s1','s1']
    assert {'heading','warning','list','table','code'}<=set(b['kind'] for b in structure['blocks'])
    assert len(structure['references'])==1 and structure['references'][0]['section']=='s1'
    chunks=section_chunks(evidence,structure,size=256,overlap=32)
    assert set().union(*(set(range(c['start'],c['end'])) for c in chunks))==set(range(len(BODY)))
    for chunk in chunks:
        assert chunk['text']==BODY[chunk['start']:chunk['end']] and len(chunk['text'])<=256
        assert all(section in {'s1','s2','s3'} for section in chunk['context'])
        assert not any(chunk['start']<s['start']<chunk['end'] for s in structure['sections'][1:])


def test_oversized_code_is_bounded_without_inventing_ancestor_text():
    body='# Parent\n\n```\n'+('café 東京\n'*3000)+'```\n'
    evidence=Extracted(body,[]); structure=derive(evidence,'text/markdown')
    chunks=section_chunks(evidence,structure)
    assert len(chunks)>20 and all(c['text']==body[c['start']:c['end']] and len(c['text'])<=1200 for c in chunks)
    assert chunks[-1]['context']==['s1']
    assert not chunks[2]['text'].startswith('# Parent')
    with pytest.raises(ValueError): section_chunks(evidence,structure,profile='request-import')
    with pytest.raises(ExtractionError): section_chunks(Extracted('different',[]),structure)


def test_duplicate_anchor_stays_unresolved():
    body='# Repeat\n\n# Repeat\n\n[ambiguous](#repeat)\n'
    assert derive(Extracted(body,[]),'text/markdown')['references'][0]['section'] is None
