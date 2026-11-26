# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Allowlisted source diagnostics shared by HTTP and MCP; never echo input."""
from fastapi import HTTPException


AUTOMATIC_SOURCE_OPERATIONS = frozenset({
    'automatic_sources_list', 'automatic_sources_preview', 'automatic_sources_save',
    'automatic_sources_command', 'automatic_source_runs_list', 'automatic_source_documents_list',
})

# Field paths describe the request, not values supplied by a caller or remote host.
ERRORS = {
    'invalid_drive_folder': ('folder_url', 'Enter a folder link from your own My Drive.'),
    'drive_preview_busy': (None, 'Another folder preview is in progress. Try again shortly.'),
    'drive_unavailable': (None, 'Google Drive is unavailable on this instance.'),
    'drive_reconnect_required': (None, 'Reconnect your Google account.'),
    'drive_offline_required': (None, 'Connect Google with background access before enabling updates.'),
    'drive_preview_required': ('preview_token', 'Preview the selected folder again before saving.'),
    'drive_item_unavailable': ('folder_url', 'Check access to the selected Google Drive folder.'),
    'drive_provider_error': (None, 'Google Drive could not complete this request.'),
    'drive_scope_mismatch': (None, 'Reconnect with the requested Google Drive permission.'),
    'invalid_automatic_source': (None, 'Check the source configuration and try again.'),
    'invalid_github_repositories': ('config.repositories', 'Enter 1–100 distinct repositories as owner/repository_name. An organization name alone is not supported.'),
    'invalid_github_selection': ('config.include', 'Select at least one GitHub content type: files, issues, pull_requests or releases.'),
    'invalid_github_ref': ('config.ref', 'Enter a branch, tag or commit reference using letters, numbers, dots, underscores, hyphens or slashes. Empty, . and .. path segments are not allowed.'),
    'invalid_source_configuration': ('config', 'Use the supported source settings only, without credentials or commands. Configuration must be at most 16 KiB.'),
    'invalid_source_selection': ('config', 'Include, exclude and path selections must be lists of at most 100 nonempty patterns, each at most 512 characters.'),
    'invalid_source_limit': ('config', 'Use whole-number limits: max_items 1–20, max_requests 4–30, max_bytes 1–2097152 and timeout 1–10 seconds.'),
    'invalid_source_name': ('name', 'Enter a title of 1–256 characters without control characters.'),
    'invalid_source_kind': ('kind', 'Choose GitHub or Website as the source type.'),
    'invalid_source_interval': ('interval_seconds', 'Enter a whole number from 300 to 2678400 seconds, or leave the interval empty for manual updates.'),
    'invalid_source_enabled': ('enabled', 'Set enabled to true or false.'),
    'invalid_revision': ('expected_revision', 'To edit a source, provide its identifier and current revision together. Reload the configuration before trying again.'),
    'invalid_source_replay_key': ('idempotency_key', 'Provide an idempotency key of 1–128 characters for this change.'),
    'invalid_source_action': ('action', 'Choose run, pause or remove.'),
    'invalid_website_attachments': ('config.attachments.allowed_roots', 'Enter approved HTTPS prefixes and valid PDF selection options.'),
    'invalid_website_configuration': ('config.website', 'Provide website settings with starting URLs and allowed URL prefixes, using supported settings only.'),
    'invalid_website_selection': ('config.website', 'Website URL and selector lists must contain at most 100 nonempty strings, each at most 4096 characters.'),
    'explicit_documentation_roots_required': ('config.website', 'Enter at least one starting URL and allowed URL prefix. Use a supported website profile: generic, docusaurus or sphinx.'),
    'website_destination_not_approved': ('config.website.allowed_roots', 'Every starting URL and sitemap must use an allowed website host. Starting URLs must also be within an allowed URL prefix.'),
    'invalid_public_url': ('config', 'Enter a public HTTP or HTTPS URL without credentials.'),
    'github_repository_unavailable': ('config.repositories', 'The GitHub repository is unavailable. Check owner/repository_name and that the repository is public.'),
    'source_http_403': (None, 'The source refused access. For GitHub, the API request limit may have been reached. Try again later.'),
    'source_http_429': (None, 'The source request limit has been reached. Try again later.'),
    'source_http_404': (None, 'The selected source or reference was not found. Check its address and branch or reference.'),
    'source_transport_failed': (None, 'Cannot connect to the source. Check its address and try again later.'),
    'automatic_source_conflict': (None, 'This source configuration has changed. Reload it before trying again.'),
    'automatic_source_not_found': (None, 'This automatic source is unavailable in the selected space.'),
}


def source_error_payload(reason='invalid_automatic_source'):
    if reason not in ERRORS:
        reason = 'invalid_automatic_source'
    field, message = ERRORS[reason]
    # Preserve the existing detail code; diagnostics are additive.
    detail = reason if reason in ('automatic_source_conflict', 'automatic_source_not_found') else 'invalid_automatic_source'
    return {'detail': detail, 'reason': reason, 'message': message, 'field': field}


class AutomaticSourceError(HTTPException):
    def __init__(self, reason='invalid_automatic_source', status=422):
        self.payload = source_error_payload(reason)
        super().__init__(status, self.payload['detail'], headers={'Cache-Control': 'no-store'})
