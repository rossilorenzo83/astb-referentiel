# 21 — Name parsing

## Goal

Given a raw name string from any source, extract `(titre, nom, prenom)` with the correct assignment of family name vs given name, regardless of:
- case convention used in the source,
- order (LASTNAME Firstname vs Firstname LASTNAME),
- presence/absence of `Dr` / `Pr` / `Professeur` prefix,
- comma separator, multi-word surnames, hyphenated names.

## Title extraction

Strip `Dr`, `Pr`, or `Professeur` (case-insensitive) from the start; normalize to `Dr` or `Pr`.

## Ordering rules (current)

After title removal, the raw name is split on whitespace.

1. **Comma-separated** (`LASTNAME, Firstname`): part before comma is `nom`, part after is `prenom`.
2. **Mixed case**: words in all-uppercase are `nom`, others are `prenom`. Concatenated in source order.
3. **All uppercase** (e.g. `DUPONT JEAN`): first word is `nom`, rest is `prenom`.
4. **All titlecase** (e.g. `Dupont Jean`): per the source label `NOM – PRENOM`, first word is treated as `nom`, rest as `prenom`.

Rule 4 is fragile: a Word document following French convention may write `Jean Dupont` and be parsed as `nom=JEAN prenom=Dupont`. See the fix below.

## Swap detection *(new)*

When case gives no signal (rule 4 above — "all titlecase"), pick the order using a **given-name lexicon**:

- Maintain a list of common French first names (compact frozenset, e.g. top 2–3k). Use a library such as `names-dataset` or ship a static frozenset in `src/normalize_names.py`; the list does not need to be exhaustive — it only resolves ambiguity in the all-titlecase case.
- For a two-word titlecase name:
  - If **word 0 is in the first-name lexicon** and word 1 is not → treat word 0 as `prenom`, word 1 as `nom` (swap).
  - If **word 1 is in the first-name lexicon** and word 0 is not → treat word 0 as `nom`, word 1 as `prenom` (keep current behavior).
  - If **both** or **neither** are recognized → keep current behavior (first word as `nom`) and emit a warning in the Journal flagging the ambiguity.
- For >2 words: apply the same test to the outermost two (first and last), since French compound surnames typically stay together.

Matching is case-insensitive, accent-stripped, hyphen-normalized (`Jean-Pierre` matches `jean-pierre` and `jean pierre`).

## Title on implied rows

Some sources omit `Dr/Pr`. When a row unambiguously names a doctor (after the NOM–PRENOM label), treat the title as empty rather than guessing.

## Multi-name cells

A single cell may list several doctors (`SERRANO Emilie - CHERIET Farah`, `Dupont & Durand`, `Dr X et Dr Y`). `split_multiple_names` splits on `-`, `/`, `&`, `,`, or ` et ` **when followed by an uppercase token**, to avoid splitting inside a single surname. Each resulting name is parsed independently.

## Reference resolution

A name field of `idem`, `idem pediatrie`, `pas de referent`, etc., does not produce a real doctor; the text is moved to `notes`. For `idem pediatrie`, the parser later resolves the reference by copying the pediatrician with the same specialty into the adult-sector slot.
