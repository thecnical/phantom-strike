# 📋 Changelog

All notable changes to PhantomStrike will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced AI engine with multi-provider failover
- Real-time WebSocket dashboard
- Cloud security scanning (AWS S3, Azure Blob, GCP)
- Blind SQL injection detection
- CSRF/XXE/IDOR vulnerability testing
- Scan locking mechanism to prevent duplicates

### Fixed
- httpx HTTP2 support for AI providers
- Dockerfile using enhanced_server instead of old server
- Unclosed aiohttp client sessions

## [2.0.0] - 2024-04-27

### 🎉 Major Release - "The AI Revolution"

#### Added
- **Enhanced Phantom Engine v2.0**
  - Multi-provider AI integration (Groq, OpenRouter, Gemini, Cerebras)
  - Intelligent failover system
  - Rate limiting and caching
  
- **Web Dashboard v2.0**
  - Real-time WebSocket updates
  - Live vulnerability alerts
  - AI Attack Assistant chat
  - Payload Generator UI
  - C2 Agent Management panel
  - Scan history viewer

- **Enhanced Web Module**
  - Blind SQL injection detection (time-based)
  - Stored XSS testing
  - XXE (XML External Entity) detection
  - CSRF token validation
  - IDOR (Insecure Direct Object Reference) testing
  - JWT security analysis
  - Security header checks

- **Enhanced Cloud Module**
  - AWS S3 bucket enumeration
  - Azure Blob Storage scanning
  - GCP Storage bucket detection
  - Metadata SSRF testing
  - IAM misconfiguration checks
  - CDN security analysis

- **New API Endpoints**
  - `/api/scan/quick` - Synchronous quick scan
  - `/api/ai/query` - AI attack planning
  - `/api/ai/status` - AI provider status
  - `/api/payload/generate` - Payload generation
  - `/api/c2/agents` - C2 agent management
  - `/ws` - WebSocket for live updates

- **Infrastructure**
  - Docker support with multi-stage builds
  - Render.com deployment ready
  - GitHub Actions CI/CD
  - Comprehensive test suite

#### Changed
- Upgraded to FastAPI 0.110+
- Migrated to Pydantic v2
- Improved async performance with uvloop
- Enhanced module loading system

#### Fixed
- Memory leaks in aiohttp sessions
- Race conditions in concurrent scans
- API timeout handling
- Error handling in AI providers

#### Security
- Added scan locking to prevent resource exhaustion
- Isolated scan sessions
- Secure API key handling

## [1.0.0-alpha] - 2024-03-15

### 🚀 Initial Release

#### Added
- Core PhantomStrike engine
- 11 offensive security modules:
  - phantom-osint (OSINT reconnaissance)
  - phantom-network (Network scanning)
  - phantom-web (Web vulnerability scanning)
  - phantom-cloud (Cloud security)
  - phantom-identity (Identity attacks)
  - phantom-cred (Credential attacks)
  - phantom-stealth (Evasion techniques)
  - phantom-exploit (Exploitation)
  - phantom-c2 (Command & Control)
  - phantom-post (Post-exploitation)
  - phantom-report (Report generation)

- Basic AI integration with Groq
- CLI interface with Rich
- REST API server
- Report generation (HTML)
- MITRE ATT&CK mapping

#### Features
- Async port scanning
- SQL injection detection
- XSS vulnerability scanning
- Subdomain enumeration
- Technology detection
- Banner grabbing
- Service fingerprinting

---

## Release Notes Format

Each release includes:
- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

## Versioning Strategy

- **MAJOR**: Incompatible API changes, major architecture updates
- **MINOR**: New functionality, backwards compatible
- **PATCH**: Bug fixes, security patches

---

**Full Changelog**: [https://github.com/thecnical/phantom-strike/commits/main](https://github.com/thecnical/phantom-strike/commits/main)
