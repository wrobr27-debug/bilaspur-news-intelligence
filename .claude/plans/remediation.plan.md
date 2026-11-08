# Bilaspur News Intelligence — Remediation Plan

**Date:** Sun Nov 08 2026  
**Status:** PLANNING MODE — No code changes yet  
**Scope:** Fix GitHub Actions workflow failures and dashboard data collection

---

## 1. Current State Summary

### What Works ✅
- Dashboard is live at `https://wrobr27-debug.github.io/bilaspur-news-intelligence/`
- Dashboard shows 1 news item (CMO Chhattisgarh YouTube), 2 active sources
- Last successful dashboard update: 7 Nov 2026, 07:10:00 am
- All 35 sources are `active=true` in Neon PostgreSQL database
- Database schema: `source_health.source_id` is TEXT type
- `instagram` collection method registered in DB enum and factory

### What's Broken ❌
- GitHub Actions runs #37 through #42 have all **failed**
- Run #42 (currently running, 8+ min) is using old code and will likely fail same as previous
- Run #43 (queued, commit 46552fb) is blocked waiting for #42 due to concurrency lock
- Most government websites fail collection:
  - Timeouts: `cmo.cg.gov.in`, `cgstate.gov.in`, `cgpolice.gov.in`, `forest.cg.gov.in`, `jansampark.cg.gov.in`
  - SSL errors: `icccbilaspur.in` (ERR_SSL_VERSION_OR_CIPHER_MISMATCH)
  - HTTP 301 redirects: `cpcb.nic.in`, `cghealth.nic.in`, `bilaspuruniversity.ac.in/`
  - HTTP 403: `irctc.co.in`
  - HTTP 302: `instagram.com`
- Dashboard data is stale (only 1 item collected from YouTube)

---

## 2. Root Cause Analysis

### Root Cause A: Playwright Timeout Too Short (15s)
**File:** `src/collectors/website.py`, line 139  
**Impact:** JS-heavy government sites (CMO, CG State Gov, CG Police, Forest) time out before page loads  
**Evidence:** Run #42 logs show `Page.goto: Timeout 15000ms exceeded` repeatedly  
**Fix needed:** Increase Playwright `page.goto` timeout from 15000ms to 30000ms

### Root Cause B: Non-200 Responses Discarded
**File:** `src/collectors/base.py`, lines 113-119  
**Impact:** HTTP 301/302 redirects (cpcb.nic.in, cghealth.nic.in, bilaspuruniversity.ac.in, instagram.com) return responses but code only accepts status 200. The response content after redirect is never parsed.  
**Evidence:** Run #42 logs show `HTTP 301 from ... (attempt 1/2/3)` — all retried but never processed  
**Fix needed:** Return non-200 responses so HTML can be parsed even after redirects

### Root Cause C: Social Media Disabled in Workflow
**File:** `.github/workflows/collect_sources.yml`, line 17  
**Impact:** `social` input default is `'false'`, so Twitter/Instagram collectors never run  
**Evidence:** Run #42 shows `bilaspur_police_instagram (social_media) error: Failed to fetch Instagram page` because social=False means the instagram collector path isn't reached properly  
**Fix needed:** Change default from `'false'` to `'true'`

### Root Cause D: SSL Certificate Errors on Government Sites
**Impact:** `icccbilaspur.in` fails with `ERR_SSL_VERSION_OR_CIPHER_MISMATCH` — bad/expired SSL certificate  
**Evidence:** Run #42 logs show SSL handshake failure on all 3 attempts, then Playwright SSL error  
**Fix needed:** Configure httpx to ignore SSL verification for specific sources or globally

### Root Cause E: HTTP 403 on irctc.co.in
**Impact:** irctc.co.in blocks the scraper with HTTP 403  
**Evidence:** Run #42 logs show `HTTP 403 from https://www.irctc.co.in/ (attempt 1/2/3)`  
**Fix needed:** Add browser-like headers (User-Agent, Accept, Referer) to httpx requests

---

## 3. Prioritized Fix Plan

### Phase 1: Quick Wins (Code Changes Already Committed)
| Fix | File | Change | Status |
|-----|------|--------|--------|
| Playwright timeout | `src/collectors/website.py` | 15000ms → 30000ms | ✅ Committed (46552fb) |
| Non-200 responses | `src/collectors/base.py` | Return response for status != 200 | ✅ Committed (46552fb) |
| Social media default | `.github/workflows/collect_sources.yml` | `'false'` → `'true'` | ✅ Committed (46552fb) |

### Phase 2: Additional Code Fixes (Not Yet Done)
| Fix | File | Change | Priority |
|-----|------|--------|----------|
| SSL verification disable | `src/collectors/base.py` | Add `verify=False` to httpx client config for government sites with bad certs | High |
| Custom headers for 403 | `src/collectors/base.py` | Add browser-like headers (Accept-Language, Referer, etc.) to bypass bot detection | High |
| Instagram redirect handling | `src/collectors/website.py` or InstagramCollector | Follow 302 redirects to login wall, capture OG meta tags | Medium |
| Per-source timeout config | `src/collectors/base.py` | Allow different timeout per source type (govt sites slower) | Medium |
| YouTube API key | Secrets config | Ensure `YOUTUBE_API_KEY` is set in GitHub Secrets | High |

### Phase 3: GitHub Actions Workflow Fixes
| Fix | Change | Priority |
|-----|--------|----------|
| Concurrency lock | Review `concurrency.group` setting — run #43 blocked by #42 | Medium |
| Workflow timeout | Current 30 min may not be enough for 35 sources with retries | Medium |
| Secret validation | Verify `DATABASE_URL`, `YOUTUBE_API_KEY`, `INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD` are set | High |

### Phase 4: Database & Source Config
| Fix | Change | Priority |
|-----|--------|----------|
| YouTube channel ID | Fix `ibc24_youtube` source — URL returns 404, need correct channel ID | High |
| Source URLs | Verify all source URLs are correct and reachable | Medium |
| next_collection_at | Reset to NULL for all sources after fixes applied | Medium |

---

## 4. Implementation Order

1. **Wait for run #42 to finish** (currently running, blocked by concurrency)
2. **Run #43 will auto-start** with Phase 1 fixes already committed
3. **Monitor run #43 results** — check which sources still fail
4. **Apply Phase 2 fixes** based on run #43 output:
   - Add `verify=False` for SSL sites
   - Add custom headers for 403 sites
   - Add Instagram authentication or OG tag scraping
5. **Commit and push** Phase 2 fixes
6. **Trigger manual workflow run** with social=true
7. **Verify dashboard** at `https://wrobr27-debug.github.io/bilaspur-news-intelligence/`
8. **Iterate** until dashboard shows news items from multiple sources

---

## 5. Success Criteria

- [ ] GitHub Actions workflow runs successfully (exit code 0)
- [ ] Dashboard shows news items from at least 3-5 different sources
- [ ] YouTube, Instagram, and at least 2 government sources collect items
- [ ] Dashboard data JSON at `docs/data/news-data.json` has >10 items
- [ ] Last collection timestamp on dashboard is current (within last 2 hours)

---

## 6. Next Steps (Planning Only)

The user will review this plan and either:
- **Approve** → proceed to implement Phase 2 fixes
- **Request changes** → revise the plan before implementing

No code has been written or modified beyond the Phase 1 commits already pushed (46552fb).
