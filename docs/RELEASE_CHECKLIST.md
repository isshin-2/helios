# HELIOS — Release Checklist

Use this checklist before every public release. Do not skip items marked 🔴.

---

## Phase 0 — Pre-Release Gating

- [ ] 🔴 All tests pass: `pytest ai-router/tests/ -x` with 0 failures
- [ ] 🔴 `LICENSE` file exists at repository root
- [ ] 🔴 No hardcoded API keys in source (`grep -r "AIza\|sk-[A-Za-z0-9]" ai-router/ --include="*.py" --exclude-dir=venv`)
- [ ] 🔴 Anti-refusal prompt injection is absent (`grep -r "SYSTEM OVERRIDE" ai-router/ --include="*.py"`)
- [ ] 🔴 `.env` files not committed (`git status | grep ".env"` returns nothing)
- [ ] 🔴 Private signing key NOT in repository (`git log --all --full-history -- "*private*" "*_private.pem"`)

---

## Phase 1 — Security Audit

- [ ] WebSocket endpoints require authentication token
- [ ] Default bind address is `127.0.0.1` (loopback only)
- [ ] Secret redactor tests pass (14/14)
- [ ] Telemetry writes redacted output only
- [ ] Audit log does not contain raw API keys
- [ ] Permission broker tests pass
- [ ] Sandbox tests pass
- [ ] `HELIOS_BUILD_ENV=production` is set in release builds (blocks dev license)

---

## Phase 2 — License System

- [ ] Public verification key embedded in `core/license_validator.py` matches the production signing key
- [ ] Placeholder key (`AAAA...`) has been replaced with the real public key
- [ ] License validator tests pass (10/10)
- [ ] Dev license (`HELIOS_DEV_LICENSE=1`) blocked in production builds
- [ ] Sample license verified with `tools/license_keygen.py verify`
- [ ] Private signing key stored securely (HSM, password manager, or encrypted vault)

---

## Phase 3 — Entitlements

- [ ] Entitlement tests pass (21/21)
- [ ] Community features work without any license file
- [ ] Pro features blocked without valid license
- [ ] Pro features activate with valid license
- [ ] Missing premium module does not crash startup
- [ ] Invalid license file degrades gracefully to Community mode
- [ ] `helios_pro` bundle activates all three Pro modules

---

## Phase 4 — Documentation

- [ ] `README.md` updated with version number and changelog
- [ ] `docs/INSTALLATION.md` covers all supported platforms
- [ ] `docs/BYOK_BYOHW.md` is accurate for the release
- [ ] `docs/COMMUNITY_VS_PRO.md` feature matrix matches actual code
- [ ] `docs/SECURITY.md` known risks section is current
- [ ] `docs/LICENSING.md` third-party attribution is complete

---

## Phase 5 — Third-Party Licensing

- [ ] 🔴 PyQt5 GPL3 desktop app licensing resolved before binary distribution
- [ ] 🔴 VRM model (Airi, Ren) redistribution rights verified
- [ ] 🔴 Reference voice audio (`voices/airi/`) redistribution rights verified
- [ ] PyTorch CUDA license reviewed for distribution
- [ ] `pip-licenses` report generated and reviewed

---

## Phase 6 — Build and Package

- [ ] `HELIOS_BUILD_ENV=production` set in build environment
- [ ] `HELIOS_DEV_LICENSE` unset or `0` in build environment
- [ ] Requirements pinned (`pip freeze > requirements-lock.txt`)
- [ ] Checksums generated for distribution archives (SHA-256)
- [ ] Release tag created and signed (`git tag -s v1.x.y`)

---

## Phase 7 — Distribution

- [ ] Release notes published
- [ ] Download links and checksums posted
- [ ] License import instructions in release notes
- [ ] Known issues documented

---

## Rollback Plan

If a release has a critical defect:
1. Tag the broken release as `v1.x.y-retracted`
2. Push a patch release `v1.x.y+1` with the fix
3. User data (SQLite databases, `.env`, license files) is never modified by the updater
4. Users can safely roll back by reinstalling the previous release — their data is untouched
