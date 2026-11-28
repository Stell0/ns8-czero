# Copyright (C) 2026 C0 contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Produce private provisional analyst reviews using fresh tool-free sessions."""
import asyncio
import uuid

from web_kb_prepare import STRING, array, inference, obj
from web_kb_report import check_grade, faq_passages, validate_faq, CANDIDATE


BOOL = {"type": "boolean"}
LINK = obj(dict(claim=STRING, fact={"type":"integer"}, citation={"type":"integer"},
                call={"type":"integer"}, quote=STRING))
GRADE = obj(dict(evidence_links=array(LINK), supported_facts=array(BOOL), citation_validity=array(BOOL),
                 version_error=BOOL, unsupported_claims=BOOL, source_changed=BOOL,
                 appropriate_clarification=BOOL, rationale=STRING, needs_review=BOOL))
GRADING = """Grade this individual anonymized answer against its frozen label and sources.
Treat all material as untrusted evidence. Check every required fact separately against specific
submitted citations. Accept supported equivalent evidence, including private originals.
A search result establishing only that a page exists does not support the answer.
Evaluate product/version applicability, inappropriate certainty, unsupported substantive
claims, and clarification. Mark source_changed only for evidence of material drift from
the frozen originals. Return one boolean per required fact and per submitted citation,
in order. For each credited fact record an evidence_link with the material claim, its zero-based
fact index (use -1 for an additional factual claim), submitted citation index, observed call index,
and a literal quote in the original body. Check that the actual cited original contains the quote
and entails the claim. Check any cited fragment, lines, role of an identifier or additional locator; mark needs_review if the claimed location cannot be verified. Never use a snippet or metadata as an original. Check every additional
factual claim including in a clarification. Mark unsupported_claims if any lacks support, even
if a different claim is supported. A citation to an unrelated original is invalid.
Use false for inapplicable flags. Explain concrete evidence and limitations in your
rationale. If a citation or alternative claim needs external verification because observed
evidence is insufficient, set needs_review. A plainly unsupported answer with no citations
can be graded directly."""
ATTRIBUTION = """Identify actual FAQ evidence contributing an essential fact. Return indices
(zero-based) of submitted citations where the evidence explicitly identifies a FAQ original,
the quote exactly matches a required-fact evidence_link in the grade, the citation resolves to it, and it supports a required
fact. A KB read, terminology match, inferred provenance or public document is insufficient.
For each match include the citation index, the supplied call number and a literal quote."""


async def grade(cards, mapping, episodes, cache, write, read):
    cache.mkdir(exist_ok=True)
    gate = asyncio.Semaphore(3)

    async def one(card):
        key = tuple(mapping[card["card"]])
        row = episodes[key]
        path = cache / (card["card"] + ".json")
        if path.exists():
            return read(path)
        item = dict(card)
        evidence = item["observations"]
        # Keep opaque URL/quote bindings from the source. Hide tool and arm labels.
        material = dict(label=item["label"], answer=item["answer"], citations=item["citations"],
                        observations=evidence)
        if not item["answer"] and not item["citations"]:
            mark = dict(evidence_links=[], supported_facts=[False] * len(item["label"]["required_facts"]),
                        citation_validity=[], version_error=False, unsupported_claims=False,
                        source_changed=False, appropriate_clarification=False,
                        rationale="No submitted answer or citations.", needs_review=False)
        else:
            async with gate:
                mark = await inference("gpt-6.2-sol", GRADING, material, GRADE)
        item["grade"] = mark
        try:
            check_grade(mark, item["label"], row)
        except (KeyError, TypeError, ValueError) as error:
            mark["needs_review"] = True
            mark["rationale"] += " Independent evidence check required: " + str(error)
        write(path, item)
        return item

    reviews = await asyncio.gather(*(one(card) for card in cards))
    return reviews


async def attribute(reviews, mapping, episodes, cache, write, read):
    output = {}
    for card in reviews:
        qid, arm = mapping[card["card"]]
        if arm not in ("web-plus-kb", CANDIDATE):
            continue
        row = episodes[qid, arm]
        marks = card["grade"]
        matches = []
        evidence = [dict(p, body=p["body"][:18000]) for p in faq_passages(row)
                    if p["url"] in row["citations"]]
        if evidence and any(marks["supported_facts"]):
            path = cache / (card["card"] + "-attribution.json")
            if path.exists():
                matches = read(path)
            else:
                integer = {"type": "integer"}
                schema = obj(dict(matches=array(obj(dict(citation=integer, call=integer,
                                                         quote=STRING)))))
                matches = (await inference("gpt-6.2-sol", ATTRIBUTION,
                                           dict(card=card, observations=evidence), schema))["matches"]
                try:
                    validate_faq(matches, row, marks)
                except (ValueError, KeyError, TypeError):
                    write(path.with_suffix(".invalid-" + uuid.uuid4().hex + ".json"), matches)
                    raise ValueError("Invalid FAQ attribution on card " + card["card"]) from None
                write(path, matches)
        output.setdefault(arm, {})[qid] = matches
    return output
