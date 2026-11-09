# Retrieval evidence improvements

This producer candidate starts from original main `6bb8cea`. It changes query
whitespace handling, preserves a second exact passage during hybrid document
fusion, and adds opt-in contextual embedding inputs. It does not change RRF
weights, chunk boundaries, published Core artifacts or the released consumer lock.
An app using an older released Core retains that Core's advertised query bound;
native settings omit the optional input-format field unless explicitly selected.

Search accepts at most 8192 raw characters and 512 characters after whitespace
normalization. Newlines and tabs become spaces; unexpected controls, empty and
oversized normalized queries fail. Identifiers, punctuation and explicit operators
are preserved. Clients must shorten long requests explicitly, before measurement.

Hybrid keeps its document ordering and primary fields. One distinct supporting
passage may accompany each hit, with its own exact offsets and citation. Identical
or fully covered excerpts add no passage; a unique tail is preserved even when
most of its window overlaps. Scoring sees bounded evidence from both passages;
authorization and current-generation checks cover both. Clients budget the whole
context and read supporting passages before concluding that evidence is absent.

Embedding `input_format=legacy` remains the default and retains existing profile
identities. Explicit `context-v1` uses a distinct profile and a bounded prefix of
recorded product/version, title and original ancestor headings. The provider's
4096-character input bound remains; the prefix uses at most 256 characters.
Prefixes are derivatives, never quotations. Future formatter changes require a
new input-format identity rather than changing context-v1 in place.
Schema0037 records input format and invalidates contextual vectors transactionally
when their source/Wiki labels change. Ordinary source replacement still retires
all old derivatives. Index workers reject inputs changed during provider I/O.

Evaluate old/new formats in disposable instances, with full source/Wiki coverage,
fixed models, source hashes, normalized queries and context budgets. Capture actual
modes and fallbacks, measure useful evidence and complete subquestion coverage,
and retain every attempt. Existing ticket grades are diagnostic development data;
an untouched sample is required for a general quality claim. Activation/reindex,
Core publication, consumer adoption and live deployment are separate operations.
