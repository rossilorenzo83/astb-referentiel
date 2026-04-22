# 40 — Merge & enrichment

Two distinct code paths, both in `src/merge.py`. They are NOT interchangeable.

## Generation mode: `merge_all(doctors)`

Used when the user imports files without providing an existing annuaire. Deduplicates a flat list coming from any number of sources:

- Doctors with empty `nom` pass through unchanged (they may carry useful notes).
- For each doctor with a `nom`, look for a matching record already in the accumulator using `find_match` (same ville + same normalized nom + same specialty).
- On match, merge field-by-field, preferring the more complete value.
- On no match, append.

## Enrichment mode: `enrich(existing, new_doctors)`

Used when the user provides an existing annuaire. The **no-delete invariant** applies: every record in `existing` must appear in the output.

For each new doctor:

1. **Same-city match** (ville + nom + specialty): update empty fields on the existing record with new values; don't overwrite populated fields unless the new one is strictly more complete.
2. **Cross-city match** (same nom + same specialty, different ville): treated as a **transfer** only when the incoming source explicitly signals one (see "Transfer vs dual affiliation" below). Otherwise treated as a hospital conflict requiring human review.
3. **Same-city / different-hospital match** (same nom + prenom + specialty + ville, different `hopital`): treated as a hospital conflict (see below).
4. **No match**: append as a new record.

## Invariants

- No existing record is ever removed by enrichment.
- A `source` field is stamped on new records from the "Origine" input; it becomes the traceability trail.
- `date_import` is stamped at creation, not at merge; it identifies when the record first entered the annuaire.
- Inferred field values (see below) are always annotated in `notes` so they can be distinguished from values that came directly from a source file.

## Field inference from siblings *(new)*

When a new doctor arrives with incomplete contact info, fill empty fields by inferring from **sibling records** — existing doctors practicing at the same establishment — rather than leaving the columns blank.

### When it runs

- In **enrichment mode**, after match resolution, before writing. Runs on records that ended up either appended as new or merged with an existing record still missing fields.
- Also in **generation mode** after `merge_all`, so multi-file imports benefit from the same inference within the batch.

### Sibling definition

Two records are siblings when **all** of these hold:
- Same `ville` (accent-stripped, case-insensitive).
- Same normalized `hopital` (accent- and punctuation-stripped, case-insensitive; `CHU de Bordeaux` == `CHU Bordeaux`).
- Non-empty `hopital` on both sides (we don't infer across records that lack a hospital).

### Fields eligible for inference

Only **shared-context** fields, never personally identifying ones:

| Field | Inferable from siblings? | Notes |
|---|---|---|
| `adresse` | yes | The hospital address is the same for everyone there. |
| `telephone` | yes | Only if the sibling phone looks like a secretariat line (labeled `secretariat` in notes, or present on ≥ 2 siblings). Personal lines are not propagated. |
| `email` | yes | Same rule as phone: only secretariat-style emails (common domain already shared by ≥ 2 siblings, or explicitly labeled). |
| `hopital` | no | That's the join key. |
| `nom`, `prenom`, `titre`, `specialite`, `secteur`, `notes` | no | Personal / per-record. |

### Resolution rules

- If exactly one sibling has a value for the eligible field, copy it verbatim.
- If multiple siblings agree (same value), copy it.
- If siblings disagree, **do not infer** — leave the field empty and emit a Journal warning: `[Inference] Ambiguous <field> for Dr X at <hopital>: values {a, b, ...} — left empty`.
- Inferred values are stamped with `(inferé)` suffix in the `notes` field, e.g. `notes += "email inferé depuis secretariat <hopital>"`, so downstream users can audit what was guessed vs. what was provided.

### Non-goals

- No inference across different hospitals, even in the same city.
- No inference of `specialite` or `secteur` — these are per-doctor.
- No "best guess" when siblings disagree: the tool logs the ambiguity and leaves the field empty.

## Transfer vs dual affiliation *(new — replaces the silent transfer rule)*

When the same doctor (same `nom` + `prenom` + `specialite`) is observed at **two different hospitals** — whether in the same ville or different villes — the tool cannot reliably decide between:

- a **transfer** (the doctor moved; the old affiliation is stale), or
- a **dual affiliation** (the doctor practices at both hospitals).

Silently collapsing the two records loses information either way (a real dual practice is destroyed; a stale affiliation lingers). Silently keeping both pollutes the annuaire with near-duplicates and confuses families searching by hospital.

### Default: keep both + flag for human review

Default policy when a hospital conflict is detected:

1. **Keep both records.** Hospital is a filter axis users rely on; merging it away is destructive.
2. **Cross-link them** via `notes`: append `Affiliation multiple possible — voir aussi <other hopital>` to each of the two records.
3. **Highlight the `Hopital` cells** on both rows in the `Annuaire Complet` sheet (see `specs/50-output.md` — yellow fill, `IMPORTANT` tag in cell comment).
4. **Log in the Journal**: `[Conflit hopital] Dr X <specialite>: <hopital A> et <hopital B> — revue manuelle requise`.
5. Preserve both records' `source` and `date_import` as-is so the reviewer can see which came from where.

### Explicit transfer override

The tool treats the situation as a transfer (collapses into a single updated record, as before) only when the incoming doctor **explicitly signals one**. Signals, in priority order:

1. The doctor's `notes` on import contain a phrase matching `transfer(é|e)\s+(de|depuis)` or `muté` / `ancienne?\s+affect` (case-insensitive, accent-insensitive).
2. The scanner flags a whole-file-level "Transfer" marker set by the user via a future "Nature de l'import" dropdown (NOT in scope yet, but the spec leaves room).

When the transfer override applies: update the existing record with the new hospital/address/phone/email, append `Transfere de <old hopital>` to notes, log the transfer in the Journal, and do NOT highlight.

### Manual resolution workflow

The reviewer opens the annuaire, looks at the highlighted `Hopital` cells, and either:

- **Keeps both rows** (real dual affiliation): removes the `Affiliation multiple possible` note from both; highlight can be cleared manually. On the next import, the conflict re-surfaces only if a *third* hospital appears.
- **Drops the stale row** (was a transfer): deletes the obsolete row from the annuaire. The `no-delete invariant` does not apply to manual edits — only the tool is forbidden from deleting.
- **Merges manually** (keeps one row with a combined `Hopital` value like `CHU A / CHU B`): up to the reviewer; the tool does not force this.

On the next run, the tool re-evaluates based on the current state of the annuaire and does not re-introduce the dropped row.

### Non-goals

- No automated tie-breaking ("most recent date wins", "most complete wins"). Any automatic rule would silently hide real transfers or real dual practices.
- No attempt to detect "probable transfer" from contextual hints (e.g. different `date_import`). A transfer is claimed only via an explicit in-source signal.

## Conflict reporting

Conflicts (different values on populated fields) are logged in the Journal with the doctor's name and both values. The merge decision still proceeds per completeness-score; conflicts are informational, not blockers.
