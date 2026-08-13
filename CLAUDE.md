# Particle Man — Claude Code Context

## MANDATORY SESSION STARTUP

Run ALL of these before responding to any user message.

1. `git -C /home/ataraxia/code/particle-man status`
2. `git -C /home/ataraxia/code/particle-man log --oneline -5`
3. Read `custom_components/particle_man/manifest.json` → note version
4. Read memory file `memory/particle_man_audit.md` → note quality tier and any unverified items

**Output before anything else:**
```
STARTUP OK | branch: <name> | version: <x.y.z> | quality: Platinum (code-complete, docs partially unverified) | audit: <YYYY-MM-DD>
```
This checklist is not optional. "Resume directly" does not skip it.

---

## Repo Structure

| Path | Role |
|------|------|
| `custom_components/particle_man/__init__.py` | Entry setup/unload, PLATFORMS, stale device cleanup |
| `custom_components/particle_man/coordinator.py` | DataUpdateCoordinator, all API calls |
| `custom_components/particle_man/config_flow.py` | ConfigFlow, OptionsFlow, reauth, reconfigure |
| `custom_components/particle_man/const.py` | All constants and defaults |
| `custom_components/particle_man/strings.json` | UI strings, exception translation keys |
| `custom_components/particle_man/translations/en.json` | Mirrors strings.json (required by HA) |
| `custom_components/particle_man/icons.json` | Icon translations — never use _attr_icon on translated entities |
| `custom_components/particle_man/diagnostics.py` | Diagnostics endpoint (Gold rule) |
| `tests/conftest.py` | Mock payloads, PHCC fixtures |
| `tests/test_*.py` | One file per source module |
| `.github/workflows/validate.yml` | CI: HACS, hassfest, ruff, mypy, pytest |
| `.github/workflows/docs.yml` | Deploy docs to GitHub Pages on main push |

Platforms: `SENSOR, SWITCH, WEATHER` | Min HA: `2025.1.0` | Repo: `https://github.com/mnestrud/particle-man`

Ruff is **pinned** in `validate.yml` — an unpinned linter turns every upstream
release into a CI break with no code change. Install it locally with
`.venv/bin/pip install ruff==0.16.2` to match CI.

---

## Running Tests Locally

**Working directory: `/home/ataraxia/code/particle-man`**

```bash
# First time — create venv
python -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pip install mypy

# Type check (strict — config in pyproject.toml)
.venv/bin/mypy custom_components/particle_man

# All tests
.venv/bin/pytest tests/ -q

# With coverage
.venv/bin/pytest tests/ --cov=custom_components/particle_man --cov-report=term-missing -q

# Stop on first failure
.venv/bin/pytest tests/ -x --tb=short -q
```

Target: ≥95% coverage overall; 100% on config_flow. Any PR to main must hit this.
Current baseline: 523 tests, 98% overall, 100% config_flow (2026-08-12).

---

## PHCC Gotchas

- `AiohttpClientMockResponse` has **no `.ok`** — source uses `resp.status < 400` throughout; never add `resp.ok`
- `MockConfigEntry.options` is **read-only** — pass all options at construction time
- `DataUpdateCoordinator` requires `config_entry=` kwarg (HA 2026.x)
- `Store` must be patched: `patch("custom_components.particle_man.coordinator.Store", autospec=True)`
- `auto_enable_custom_integrations` must be `autouse=True` in conftest — required for config entry setup to find the integration
- Windows: add `event_loop_policy` fixture to set `WindowsSelectorEventLoopPolicy`
- `aioclient_mock` URL matching is case-sensitive — use `re.compile(..., re.IGNORECASE)` for mixed-case paths
- Add `-p no:socket` to `addopts` in pyproject.toml to catch missed mocks

---

## Branch and PR Workflow

- **`dev`** — all development. Never commit directly to main.
- **`main`** — merged from dev via PR only; always tagged with a release.
- Feature branches: from dev, PR back to dev.

**PR checklist before merging dev → main:**
- [ ] All CI checks pass (validate workflow)
- [ ] ≥95% test coverage, 0 mypy strict errors
- [ ] `manifest.json` version bumped (semver)
- [ ] Docs updated if behavior or config changed
- [ ] `memory/particle_man_audit.md` updated if any rule status changed

---

## CI/CD Workflows

| Workflow | Trigger | What it checks |
|----------|---------|----------------|
| `validate.yml` | Every push + PR | HACS → hassfest → ruff → mypy → pytest |
| `docs.yml` | Push to main (docs/** or mkdocs.yml) | Deploys GitHub Pages |

**Common CI failures:**
- `hassfest`: manifest.json version format wrong, or missing required field
- `HACS`: missing `hacs.json`, brand assets in wrong path, or missing README
- `mypy`: untyped dict access, missing `from __future__ import annotations`, wrong return type
- `pytest passes locally, fails CI`: PHCC version drift — pin `requirements_test.txt` to a specific version

---

## Quality Scale

**Current tier: Platinum (code-complete, docs partially unverified)**

Score as of 2026-04-23: Bronze 16/18 · Silver 10/10 · Gold 13/21 · Platinum 3/3
Remaining gap: docs audit at mnestrud.github.io/particle-man (B9–B11, S3–S4, G5–G11 — 9 docs rules unverified)

Full per-rule status: `memory/particle_man_audit.md`
Quality scale rules: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules

---

## Common Task Patterns

### Add a new sensor
1. Add constant to `const.py`
2. Add sensor class — inherit from existing base, set `_attr_translation_key`, `_attr_entity_category`, `_attr_device_class`, `_attr_entity_registry_enabled_default`
3. Add translation key to `strings.json` and `translations/en.json` under `entity.sensor.<key>`
4. Add to `icons.json` under `entity.sensor.<key>` if custom icon needed — do **not** use `_attr_icon` on translated entities
5. Update coordinator to populate the data field
6. Write test covering entity properties and state
7. Run: `.venv/bin/pytest tests/test_sensor.py -q --tb=short`

### Modify config/options flow
1. Edit `config_flow.py` — all four flows live here (user, reauth, reconfigure, options)
2. Update `strings.json` step schema and error keys; mirror to `translations/en.json`
3. If adding config key: add to `const.py` with default, update `_opt()` helper in `__init__.py`
4. Run: `.venv/bin/pytest tests/test_config_flow.py -q`

### Add an API endpoint
1. Add URL/constants to `const.py`
2. Add fetch method to `coordinator.py` — use `resp.status < 400` not `resp.ok`
3. Add mock response in `conftest.py` `register_api_mocks()`
4. Write coordinator tests for success, HTTP error (4xx/5xx), and quota-block paths

### Fix a mypy error
- Run: `.venv/bin/mypy custom_components/particle_man --strict --ignore-missing-imports`
- Do not add `# type: ignore` without an explanatory comment
- Common causes: dict access without guard, missing `| None`, no `from __future__ import annotations`

---

## Agent Usage

| When | Use |
|------|-----|
| HA entity API signatures, coordinator/flow patterns, HA breaking changes | `ha-dev` agent |
| Google Environmental API (Air Quality, Pollen, Weather, Solar) field names, response structure, quota | `google-env-api` agent |
| After rsync deploy + restart confirmed | `ha-integration-validator` agent |
| General Python/testing questions | Answer directly — no agent |

Invoke agents with the Agent tool (`subagent_type: ha-dev` or `subagent_type: google-env-api`). Don't answer HA API questions from training data — HA APIs change frequently.

---

## Development and Deploy Workflow

**Source of truth: git repo. Test target: live HA via the /mnt/ha-config mount. These are two separate steps.**

### Step 1 — Edit and test locally
1. Edit files in `/home/ataraxia/code/particle-man/custom_components/particle_man/`
2. Run `.venv/bin/pytest tests/ -q --tb=short` to catch regressions

### Step 2 — Deploy to live HA for integration testing
```bash
rsync -a --delete --inplace --exclude='__pycache__' \
  /home/ataraxia/code/particle-man/custom_components/particle_man/ \
  /mnt/ha-config/custom_components/particle_man/

# ALWAYS verify — see below
diff -r --exclude=__pycache__ \
  /home/ataraxia/code/particle-man/custom_components/particle_man/ \
  /mnt/ha-config/custom_components/particle_man/
rm -rf /mnt/ha-config/custom_components/particle_man/__pycache__
```

**`--inplace` is mandatory.** The mount is CIFS, where rsync's write-temp-then-rename
strategy fails intermittently with `mkstemp ... No such file or directory`. It has
silently skipped individual files (observed: `__init__.py`) while reporting success
for the rest — leaving a half-deployed integration that will not load. Always follow
the rsync with the `diff -r` above; a non-zero exit means the deploy is incomplete.
Clear `__pycache__` too: CIFS mtime granularity can defeat Python's cache invalidation.
- **Python changes** (any `.py` file): full HA restart required — use `ha_restart` MCP call. Verify recovery yourself via a read-only MCP call (e.g. `ha_get_entity_state` on a particle_man sensor) after ~60s — do NOT ask the user to confirm uptime
- **Non-Python changes** (strings.json, translations, icons): reload only — `ha_reload_config component=core`
- the mount is deploy target only — never edit `/mnt/ha-config/custom_components/particle_man/` directly
- **particle_man is also registered in HACS** (custom repository), which manages the *same* deploy directory. A HACS update overwrites it with the latest GitHub release — harmless when deploy == release, but it silently rolls back any dev build deployed ahead of a release. Never run `ha_hacs_update_all`; after any HACS update of particle_man, re-run the rsync deploy if dev is ahead.

### Step 2b — Validate on live HA (after user confirms restart complete)
Invoke `ha-integration-validator` agent: "Validate particle_man on live HA"

- PASS → proceed to commit
- WARN → confirm with user whether unavailable entities are expected, then commit
- FAIL → investigate errors before committing; do not push to git until resolved

### Step 3 — Commit and push
```bash
git add <changed files>
git commit -m "..."
git push origin dev
```
Never commit to main directly. Open a PR (dev → main) when ready for release.

### What NOT to do
- Do not edit /mnt/ha-config directly — git repo is source of truth; the mount is deploy target only
- No `ha_write_file`, no patch subagents, no MCP file writes to the mount
