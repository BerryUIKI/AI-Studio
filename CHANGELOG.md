# Changelog

All notable changes to Berry AI Studio are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- Credentials: enforce 0600 permissions on the non-Windows credential file and
  abort the save when the mode cannot be restricted, instead of silently
  storing a world-readable secret (`#101`).
- Settings: make the agent API key field write-only — the stored secret is
  never re-displayed, an empty submission keeps the stored key, and the
  placeholder hints at the redacted value (`#101`).
- Session: require the per-launch session token on sensitive reads and
  mutations (execution, engine lifecycle, downloads, credentials, shutdown)
  and on the workflow websocket, stop publishing the token through
  `/api/v1/info`, deliver it to the packaged app via the served index page
  and to the dev server through an origin-gated endpoint (`#102`).
