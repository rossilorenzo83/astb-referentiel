# ASTB - Annuaire des Medecins STB

Outil Python pour l'association **ASTB** (Association pour l'Aide a la Recherche en Sclerose Tubereuse de Bourneville) permettant de construire et maintenir un annuaire structure de medecins specialistes prenant en charge les patients atteints de **Sclerose Tubereuse de Bourneville (STB)** en France.

## Contexte

L'association ASTB recoit regulierement des fichiers Word et Excel contenant des coordonnees de medecins specialistes dans differentes villes et disciplines. Ces fichiers sont souvent mal structures (donnees en vrac dans une seule colonne, formats heterogenes). L'association a besoin d'un referentiel unique, structure et filtrable pour repondre aux familles qui cherchent un specialiste dans leur region.

Cet outil :
- **Analyse dynamiquement** la structure de chaque fichier d'entree (Excel ou Word)
- **Extrait** les informations des medecins (nom, specialite, hopital, telephone, email, etc.)
- **Genere** un annuaire Excel structure avec filtres, tri par region/ville/specialite
- **Enrichit** un annuaire existant sans perdre les donnees deja presentes
- **Detecte les transferts** de medecins d'un hopital a un autre

## Fonctionnalites

### Analyse dynamique des fichiers

Le scanner detecte automatiquement le format de chaque fichier :

| Format detecte | Description |
|---|---|
| Tableau multi-colonnes | Excel avec en-tetes de colonnes (Nom, Specialite, Tel...) |
| Colonne unique structuree | Excel avec sections numerotees et labels de champs |
| Paragraphes avec sections | Word avec en-tetes de style (villes, blocs de texte) |
| Texte libre | Document sans structure identifiable (extraction par regex) |

Les synonymes de champs sont reconnus en francais (Medecin, Hopital, Tel., Adresse mail, Specialite, etc.).

### Enrichissement incremental

Le workflow standard :

1. Un annuaire Excel existe deja (genere precedemment par l'outil)
2. L'association recoit un nouveau fichier avec des informations supplementaires
3. L'outil importe le nouveau fichier et **enrichit** l'annuaire :
   - Mise a jour des coordonnees modifiees (telephone, email, adresse)
   - Ajout de nouveaux medecins
   - Detection des transferts (meme medecin, ville differente)
   - Aucune suppression de donnees existantes

### Detection des transferts

Quand un medecin apparait dans une nouvelle ville avec la meme specialite, l'outil :
- Met a jour sa ville, son hopital et ses coordonnees
- Ajoute une note "Transfere de [ancienne ville]"
- Log le transfert dans le journal d'import

### Sortie Excel structuree

L'annuaire genere contient 3 feuilles :

- **Annuaire Complet** : tableau filtrable avec 17 colonnes (Region, Ville, Specialite, Secteur, Nom, Prenom, Hopital, Telephone, Email, etc.), tri automatique, en-tete fige
- **Par Ville** : tableau croise ville x specialite avec le nombre de medecins
- **Journal Import** : avertissements, conflits et transferts detectes

## Installation

### Prerequis

- Python 3.10+
- tkinter (inclus avec Python sur Windows, `sudo apt install python3-tk` sur Linux)

### Installation des dependances

```bash
cd astb-referentiel
pip install -r requirements.txt
```

Les seules dependances sont :
- `openpyxl` (lecture/ecriture Excel)
- `python-docx` (lecture Word)

### Lancement

**Linux / macOS :**
```bash
python3 -m src.main
```

**Windows :**
```
python -m src.main
```
ou double-cliquer sur `run.bat`.

### Empaquetage en .exe (Windows)

Pour distribuer l'outil sans necessiter d'installation Python :

```
build.bat
```

Produit un fichier `dist/ASTB_Annuaire.exe` autonome.

## Utilisation

### Premier usage : generer un annuaire

1. Lancer l'application
2. Cliquer **+ Ajouter** pour selectionner les fichiers sources (Word .docx ou Excel .xlsx)
3. Remplir le champ **Origine** (ex: "Import initial - avril 2026")
4. Choisir le dossier de sortie
5. Cliquer **Generer l'annuaire**

### Usage courant : enrichir un annuaire existant

1. Lancer l'application
2. Dans **Annuaire existant**, selectionner le fichier `Annuaire_Medecins_STB.xlsx` precedemment genere
3. Cliquer **+ Ajouter** pour selectionner le(s) nouveau(x) fichier(s) recu(s)
4. Remplir le champ **Origine** (ex: "CHU Nantes - avril 2026")
5. Cliquer **Enrichir l'annuaire**

Le bouton change automatiquement de texte selon qu'un annuaire existant est charge ou non.

## Architecture

```
astb-referentiel/
    src/
        main.py                 # Interface graphique (tkinter)
        models.py               # Modele Doctor (17 champs), mapping regions
        normalize.py            # Normalisation de texte francais (noms, telephones, accents)
        merge.py                # Deduplication, enrichissement, detection de transferts
        reader_excel.py         # Lecture d'un annuaire existant
        writer_excel.py         # Generation de l'annuaire Excel structure
        scanner/
            __init__.py         # Point d'entree : scan_and_parse(path)
            template.py         # Structures de donnees (FileTemplate, LayoutType, etc.)
            synonyms.py         # Dictionnaire de synonymes de champs medicaux francais
            scan_excel.py       # Scanner de fichiers Excel
            scan_word.py        # Scanner de documents Word
            generic_parser.py   # Parseur generique pilote par le template infere
    tests/
        test_models.py          # Tests du modele et du mapping de regions
        test_normalize.py       # Tests de normalisation (telephones, noms, champs)
        test_parsers.py         # Tests d'integration sur fichiers reels
        test_scanner.py         # Tests du scanner et assertions de base
        test_enrichment.py      # Tests d'enrichissement, transferts, lecture annuaire
    requirements.txt
    run.bat                     # Lanceur Windows
    run.sh                      # Lanceur Linux/macOS
    build.bat                   # Empaquetage PyInstaller
```

### Pipeline de traitement

```
Fichier (.xlsx/.docx)
    |
    v
Scanner (scan_excel / scan_word)
    |- Lecture en memoire (une seule passe)
    |- Classification du layout (TABULAR, SINGLE_COLUMN, PARAGRAPH, FREETEXT)
    |- Detection des champs via dictionnaire de synonymes
    |- Detection des sections (specialites, villes, secteurs)
    v
FileTemplate (description de la structure)
    |
    v
Parseur generique (generic_parser)
    |- Dispatch par LayoutType
    |- Extraction des Doctor via le template
    |- Post-traitement (noms multiples, references "idem", normalisation)
    v
list[Doctor]
    |
    v
Enrichissement / Deduplication (merge.py)
    |- Correspondance par nom + specialite + ville
    |- Detection de transferts (meme medecin, ville differente)
    |- Mise a jour des champs, ajout des nouveaux
    v
Ecriture Excel (writer_excel.py)
    |- Annuaire Complet (filtrable)
    |- Resume Par Ville
    |- Journal Import
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

123 tests couvrant :
- Normalisation de texte (telephones, noms, accents, champs concatenes)
- Modele Doctor (region, deduplication, score de completude)
- Scanner (classification des layouts, detection d'en-tetes)
- Synonymes de champs (correspondance francais/variantes)
- Parsing d'integration sur fichiers reels (9 villes Excel, 14 villes Word)
- Enrichissement (mise a jour, transferts, non-suppression, lecture annuaire)

## Donnees personnelles

Les fichiers sources contenus dans `resources/` ne sont **pas inclus** dans ce depot. Ils contiennent des coordonnees reelles de medecins et ne doivent pas etre publies. Le fichier `.gitignore` exclut le dossier `resources/` et `output/`.

Pour executer les tests d'integration, placez les fichiers sources dans `resources/` :
- `RESEAU STB_association ASTB.xlsx`
- `Prise en charge sclerose de Bourneville.docx`

## Regions couvertes

L'outil reconnait automatiquement les villes et les associe a leur region administrative :

| Region | Villes |
|---|---|
| Ile-de-France | Paris, Bobigny |
| Provence-Alpes-Cote d'Azur | Marseille, Nice |
| Occitanie | Toulouse, Montpellier |
| Nouvelle-Aquitaine | Bordeaux, Limoges |
| Auvergne-Rhone-Alpes | Saint-Etienne, Annecy, Lyon, Grenoble, Clermont-Ferrand |
| Grand Est | Reims, Nancy, Strasbourg |
| Hauts-de-France | Lille |
| Pays de la Loire | Nantes, Angers |
| Centre-Val de Loire | Tours |
| Normandie | Rouen |
| Bretagne | Brest |
| Bourgogne-Franche-Comte | Dijon |
| La Reunion | La Reunion |

De nouvelles villes sont ajoutees automatiquement lorsqu'elles apparaissent dans les fichiers importes. Le mapping ville-region peut etre etendu dans `src/models.py`.

## CI/CD

Le projet inclut un pipeline GitHub Actions (`.github/workflows/ci.yml`) :

- **Tests** : execute les 123 tests unitaires sur Ubuntu et Windows, Python 3.10/3.11/3.12
- **Build** : genere un executable Windows `ASTB_Annuaire.exe` via PyInstaller (disponible en artifact)

Les tests utilisent des donnees synthetiques generees programmatiquement (`tests/conftest.py`). Aucun fichier sensible n'est necessaire pour executer le pipeline.

## Licence

Projet benevole pour l'association ASTB. Usage libre pour les associations de patients.
