# Migration History Notes — Core / Careers

This document explains legacy migrations in `apps/core` that relate to hiring/Careers,
why they must remain in the repository, and how to recover safely when deploying to
databases that were created before Careers became a separate app.

**Do not delete, squash, or rewrite these migrations.** They are historical records for
already-applied production and staging databases.

---

## Background

Career applications were originally implemented as `core.CareerApplication`. The feature
was later moved to a dedicated `careers` app with a new schema (`careers_careerapplication`).

The move left two legacy migrations in `core`:

| Migration | File | What it does |
|-----------|------|--------------|
| `core.0001_background_tasks` | `0001_background_tasks.py` | Creates `BackgroundTaskLog` (still in use) |
| `core.0002_career_application` | `0002_career_application.py` | Creates `core_careerapplication` **and** renames two `BackgroundTaskLog` indexes |
| `core.0003_delete_careerapplication` | `0003_delete_careerapplication.py` | Deletes `core.CareerApplication` / drops `core_careerapplication` |

Current hiring data lives in:

| App | Model | Table |
|-----|-------|-------|
| `careers` | `CareerApplication` | `careers_careerapplication` |

The active Django model registry must **not** include `core.CareerApplication`.

---

## Why these migrations must stay

1. **Already-applied databases** record `core.0002` and/or `core.0003` in
   `django_migrations`. Removing or editing those files breaks Django’s migration graph
   and blocks future `migrate` runs.

2. **`core.0002` is not only Careers.** It also applies index renames on
   `BackgroundTaskLog`. Skipping the entire migration on a fresh database can leave index
   names out of sync with history.

3. **`careers.0001+` is independent.** The careers app creates its own table. Legacy
   `core_careerapplication` rows are **not** migrated automatically by these files; any
   one-off data move was operational, not part of the current migration chain.

---

## Expected state on a new database

On a clean database, Django should apply migrations in order:

1. `core.0001_background_tasks`
2. `core.0002_career_application` (creates then-legacy table + index renames)
3. `core.0003_delete_careerapplication` (drops legacy table)
4. `careers.0001_initial` through `careers.0007_positions_and_required_email`

After migrate completes:

- Table `core_careerapplication` should **not** exist.
- Table `careers_careerapplication` **should** exist.
- `django_migrations` should list all core and careers migrations above.

Run the safety check:

```bash
python manage.py check_migration_history
```

---

## When schema already matches (fake apply)

If a database **never** had `core_careerapplication` but migration state is inconsistent
(e.g. local-prod dry-run, manual repair, restored backup), **do not** run destructive
SQL. Verify first, then fake-apply only the migration that would fail because the object
is already absent.

### Preconditions

1. Confirm the legacy table is missing:

   ```bash
   python manage.py dbshell
   ```

   PostgreSQL:

   ```sql
   SELECT to_regclass('public.core_careerapplication');
   ```

   Expected: `NULL` (table absent).

2. Confirm `careers_careerapplication` exists if the site is already serving Careers
   (or will be created by normal `careers` migrations).

3. Inspect recorded migration state:

   ```bash
   python manage.py showmigrations core careers
   ```

### Safe recovery: `core.0003` fails because table is already gone

Typical error: applying `core.0003_delete_careerapplication` tries to drop
`core_careerapplication`, but the table does not exist.

**Only after verifying the table is absent:**

```bash
python manage.py migrate core 0003 --fake
```

Then continue normally:

```bash
python manage.py migrate
python manage.py check_migration_history
```

### If `core.0002` is unapplied but the legacy table never existed

This is uncommon. Prefer a forward fix with a DBA review:

1. Ensure `BackgroundTaskLog` index rename operations from `0002` are not needed on
   this database (compare indexes on `core_backgroundtasklog`).
2. If the legacy table is absent and you only need to advance migration state, you may
   fake `0002` then `0003` **only after** documenting why index renames are skipped or
   already applied manually.

**Never fake migrations on production without a backup and a written plan.**

---

## Operational checklist before deploy

```bash
python manage.py showmigrations core careers
python manage.py check_migration_history
python manage.py migrate --plan
python manage.py migrate
```

After deploy, `/ready/` should report `"migrations": "ok"`.

---

## Verification in CI / tests

Unit tests in `tests/unit/test_migration_history.py` assert:

- `core.CareerApplication` is not in the app registry
- `careers.CareerApplication` exists
- Legacy migration files remain on disk
- Django’s migration graph includes `core.0001`–`0003` and `careers.0001`–`0007`

---

## Related files

- `apps/core/migrations/0002_career_application.py`
- `apps/core/migrations/0003_delete_careerapplication.py`
- `apps/careers/migrations/`
- `apps/core/migration_history_checks.py`
- `apps/core/management/commands/check_migration_history.py`
