# Research: Gold Tier — Autonomous Employee

**Feature Branch**: `004-gold-tier-autonomous`
**Date**: 2026-02-08
**Status**: Complete

---

## Research Topics

### 1. Xero API Integration Patterns

**Decision**: Use Xero's OAuth 2.0 with PKCE flow via `xero-python` SDK

**Rationale**:
- Official SDK handles token refresh automatically
- PKCE flow is more secure than authorization code flow
- SDK provides typed models for all Xero entities
- Rate limiting (60 calls/min) is built into SDK

**Alternatives Considered**:
- Raw REST API: More control but requires manual token management and model definitions
- Third-party libraries: Less maintained, potential security concerns

**Key Implementation Notes**:
- Tokens stored encrypted via `python-dotenv` + `cryptography` library
- Token refresh happens automatically; store refresh token securely
- Use tenant_id to scope all API calls to correct organization
- Implement request queue for rate limit compliance

---

### 2. Meta Business API (Facebook/Instagram)

**Decision**: Use Meta Graph API v19.0 with long-lived page tokens

**Rationale**:
- Graph API is the only official way to access Facebook Pages and Instagram Business
- Long-lived tokens (60 days) reduce re-authentication frequency
- Webhook subscriptions available for real-time updates (future enhancement)
- Unified API for both Facebook and Instagram Business accounts

**Alternatives Considered**:
- Instagram Basic Display API: Personal accounts only, not suitable for business
- Third-party SDKs: Outdated, less secure
- Webhook-first approach: More complex, overkill for 5-minute polling

**Key Implementation Notes**:
- Require Facebook Page connected to Instagram Business account
- Permissions needed: `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`
- Store page_id and instagram_account_id separately
- Engagement metrics: Use `/insights` endpoint with `day` period

---

### 3. Twitter/X API v2 Integration

**Decision**: Use Twitter API v2 with OAuth 2.0 (PKCE) via `tweepy` library

**Rationale**:
- v2 API is the current supported version
- `tweepy` provides async support and handles rate limits
- OAuth 2.0 PKCE is required for public clients
- Access levels: Free tier allows 1,500 tweets/month (sufficient for business use)

**Alternatives Considered**:
- Twitter API v1.1: Deprecated for most endpoints
- Raw REST: More work, no rate limit handling
- Twitter Ads API: Overkill, requires elevated access

**Key Implementation Notes**:
- Rate limits: 300 tweets/3 hours, 900 DM lookups/15 min
- Use app-only auth for read operations, user auth for writes
- Store bearer token (app) and access token (user) separately
- Implement tweet queue with exponential backoff

---

### 4. Multi-MCP Server Architecture

**Decision**: Domain-based server separation with coordinator pattern

**Rationale**:
- Security isolation: Financial operations separated from social
- Independent scaling: Each domain has different load patterns
- Clear audit boundaries: Each server logs its own actions
- Fault isolation: One server failure doesn't affect others

**Architecture**:
```
                    ┌──────────────────┐
                    │   Coordinator    │
                    │   (Port 8000)    │
                    └────────┬─────────┘
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼─────┐    ┌──────▼─────┐    ┌──────▼─────┐
    │  Financial │    │   Social   │    │   Comms    │
    │ (Port 8001)│    │ (Port 8002)│    │ (Port 8003)│
    │   - Xero   │    │ - Facebook │    │  - Email   │
    └────────────┘    │ - Instagram│    │  - WhatsApp│
                      │ - Twitter  │    │  - LinkedIn│
                      └────────────┘    └────────────┘
```

**Alternatives Considered**:
- Single monolithic server: Simpler but violates security isolation principle
- Microservices per platform: Too granular, operational overhead
- Serverless functions: Cold start latency, not suitable for real-time actions

**Key Implementation Notes**:
- Coordinator handles routing and health checks
- Each domain server validates its own approvals
- Inter-server communication via HTTP (internal network)
- Shared audit log writer with hash chaining

---

### 5. Audit Log Hash Chain Implementation

**Decision**: SHA-256 hash chain with JSON-serialized entries

**Rationale**:
- SHA-256 is cryptographically secure and widely supported
- JSON serialization ensures consistent hashing across entries
- Chain integrity verifiable without external dependencies
- Compatible with future blockchain anchoring if needed

**Implementation Pattern**:
```python
entry = {
    "id": uuid4(),
    "timestamp": datetime.utcnow().isoformat(),
    "action": action_type,
    "actor": actor_id,
    "details": details,
    "result": result,
    "prev_hash": previous_entry_hash
}
entry["hash"] = sha256(json.dumps(entry, sort_keys=True)).hexdigest()
```

**Alternatives Considered**:
- Merkle tree: More complex, unnecessary for single-chain audit
- External timestamping service: Adds dependency, latency
- Database triggers: Less portable, harder to verify

**Key Implementation Notes**:
- Store entries in append-only log file (one per day)
- Archive files older than 90 days to cold storage
- Verify chain on startup and after each append
- Export format: JSON Lines (.jsonl) for streaming reads

---

### 6. CEO Briefing Generation

**Decision**: Template-based Markdown generation with AI summarization

**Rationale**:
- Markdown is human-readable and Obsidian-native
- Template ensures consistent structure
- AI summarization provides insights beyond raw data
- Scheduled via existing APScheduler infrastructure

**Template Structure**:
```markdown
# CEO Briefing — Week of {date}

## Executive Summary
{ai_generated_summary}

## Financial Health
- Revenue: {revenue}
- Expenses: {expenses}
- Outstanding Invoices: {count} totaling {amount}
- Cash Flow: {cashflow}

## Social Media Performance
### Facebook/Instagram
- Posts: {count}, Reach: {reach}, Engagement: {rate}%

### Twitter
- Tweets: {count}, Impressions: {impressions}, Followers: +{delta}

## Pending Actions
{pending_approvals_list}

## AI Recommendations
{ai_recommendations}

## Data Sources
{availability_status}
```

**Alternatives Considered**:
- PDF generation: Less integrated with Obsidian workflow
- HTML dashboard: Separate from vault, harder to archive
- Raw JSON: Not human-readable

---

### 7. Contact Matching Strategy

**Decision**: Email-based primary key with manual linking fallback

**Rationale**:
- Email is present in Xero (invoices) and often in social DMs
- Unique identifier across platforms
- Manual linking handles edge cases without complex fuzzy matching
- Unified profile aggregates data from all sources

**Data Model**:
```python
class UnifiedContact:
    id: str  # Internal UUID
    primary_email: str
    linked_identities: List[PlatformIdentity]
    # PlatformIdentity = {platform, platform_id, display_name}
```

**Alternatives Considered**:
- AI fuzzy matching: High false positive risk, requires training data
- Phone number matching: Less reliable, privacy concerns
- No matching: Loses cross-domain intelligence value

---

### 8. Credential Storage

**Decision**: Encrypted environment variables with `python-dotenv` and `cryptography`

**Rationale**:
- Aligns with file-based architecture (no database)
- Industry standard for secret management
- `cryptography` library provides Fernet symmetric encryption
- `.env` files excluded from git via `.gitignore`

**Implementation**:
- Master key stored in `GOLD_MASTER_KEY` env var (set at runtime)
- OAuth tokens encrypted before writing to `.env`
- Decryption happens on-demand in memory only
- Key rotation supported via re-encryption script

**Alternatives Considered**:
- HashiCorp Vault: Overkill for single-user system
- AWS Secrets Manager: Cloud dependency, cost
- Plain text: Security risk, violates constitution

---

### 9. Observability Stack

**Decision**: Structured JSON logs + Prometheus-compatible metrics

**Rationale**:
- JSON logs are parseable by any log aggregator
- Prometheus format is industry standard for metrics
- No external dependencies required (file-based)
- Dashboard can expose `/metrics` endpoint

**Metrics to Track**:
- `api_call_latency_seconds` (histogram): p50, p95, p99 per integration
- `api_error_total` (counter): Error count per integration, error type
- `retry_queue_depth` (gauge): Current items in retry queue
- `mcp_server_health` (gauge): 1=healthy, 0=unhealthy per server

**Alternatives Considered**:
- OpenTelemetry tracing: Too complex for single-process system
- Custom metrics format: Less tooling support
- No metrics: Violates observability requirement

---

### 10. Error Recovery Strategy

**Decision**: Exponential backoff with 5 retries, max 4-hour delay

**Rationale**:
- Exponential backoff prevents thundering herd on recovery
- 5 retries provides sufficient recovery opportunity
- 4-hour max delay aligns with success criteria (SC-004)
- User notification after permanent failure

**Backoff Schedule**:
| Retry | Delay |
|-------|-------|
| 1 | 1 min |
| 2 | 5 min |
| 3 | 30 min |
| 4 | 2 hours |
| 5 | 4 hours |

**Alternatives Considered**:
- Fixed delay: Doesn't adapt to outage duration
- Immediate retry: Wastes API quota
- Infinite retry: Actions could queue indefinitely

---

## Dependencies to Add

```text
# Gold Tier dependencies (add to requirements.txt)
xero-python>=3.0.0         # Xero API SDK
tweepy>=4.14.0             # Twitter API v2
cryptography>=42.0.0       # Token encryption
prometheus-client>=0.19.0  # Metrics export
httpx>=0.27.0              # Async HTTP for multi-MCP communication
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limit exhaustion | Medium | High | Pre-emptive queue management, metrics alerting |
| OAuth token expiry during briefing | Low | Medium | Token refresh before scheduled jobs |
| Hash chain corruption | Very Low | High | Chain verification on write, daily backups |
| Multi-MCP coordination failure | Low | Medium | Health checks, circuit breaker pattern |
| Cross-domain matching false positives | Medium | Low | Manual review option, conservative matching |

---

## Conclusion

All technical unknowns have been resolved. The architecture extends the existing Silver Tier foundation with:
- Domain-separated MCP servers for security isolation
- Industry-standard OAuth flows for external integrations
- File-based audit logging with cryptographic integrity
- Email-based contact unification for cross-domain intelligence

Ready to proceed to Phase 1: Data Model and Contracts.
