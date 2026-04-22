"""Data model for the ASTB doctor referential."""

from dataclasses import dataclass, field
from datetime import date


# City -> French administrative region mapping
# Covers all cities found in the ASTB source files
CITY_TO_REGION = {
    "paris": "Ile-de-France",
    "paris robert debre": "Ile-de-France",
    "bobigny": "Ile-de-France",
    "marseille": "Provence-Alpes-Cote d'Azur",
    "nice": "Provence-Alpes-Cote d'Azur",
    "toulouse": "Occitanie",
    "montpellier": "Occitanie",
    "bordeaux": "Nouvelle-Aquitaine",
    "limoges": "Nouvelle-Aquitaine",
    "tours": "Centre-Val de Loire",
    "saint-etienne": "Auvergne-Rhone-Alpes",
    "annecy": "Auvergne-Rhone-Alpes",
    "reims": "Grand Est",
    "nancy": "Grand Est",
    "nantes": "Pays de la Loire",
    "angers": "Pays de la Loire",
    "rouen": "Normandie",
    "brest": "Bretagne",
    "dijon": "Bourgogne-Franche-Comte",
    "la reunion": "La Reunion",
    "lyon": "Auvergne-Rhone-Alpes",
    "strasbourg": "Grand Est",
    "lille": "Hauts-de-France",
    "grenoble": "Auvergne-Rhone-Alpes",
    "clermont-ferrand": "Auvergne-Rhone-Alpes",
}


def get_region(ville: str) -> str:
    """Return the French administrative region for a city name."""
    if not ville:
        return ""
    key = ville.lower().strip()
    if key in CITY_TO_REGION:
        return CITY_TO_REGION[key]
    # Fuzzy: try prefix match for compound names
    for city_key, region in CITY_TO_REGION.items():
        if key.startswith(city_key) or city_key.startswith(key):
            return region
    return ""


SPECIALTY_MAP = {
    "NEPHROLOGUES": "NEPHROLOGIE",
    "NEPHROLOGIE": "NEPHROLOGIE",
    "PNEUMOLOGUES": "PNEUMOLOGIE",
    "PNEUMOLOGIE": "PNEUMOLOGIE",
    "PSYCHIATRES": "PSYCHIATRIE",
    "PSYCHIATRIE": "PSYCHIATRIE",
    "GENETICIENS": "GENETIQUE",
    "GENETIQUE": "GENETIQUE",
    "OPHTALMOLOGUES": "OPHTALMOLOGIE",
    "OPHTALMOLOGIE": "OPHTALMOLOGIE",
    "CARDIOLOGUES": "CARDIOLOGIE",
    "CARDIOLOLOGUES": "CARDIOLOGIE",  # typo in source data
    "CARDIOLOGIE": "CARDIOLOGIE",
    "DERMATOLOGUES": "DERMATOLOGIE",
    "DERMATOLOGIE": "DERMATOLOGIE",
    "NEUROLOGUES": "NEUROLOGIE",
    "NEUROLOGIE": "NEUROLOGIE",
    "UROLOGUES": "UROLOGIE",
    "UROLOGIE": "UROLOGIE",
    "AUTRES SPECIALITES": "AUTRE",
}


@dataclass
class Doctor:
    region: str = ""
    ville: str = ""
    type_centre: str = ""
    responsable_centre: str = ""
    specialite: str = ""
    specialite_detail: str = ""
    secteur: str = ""
    titre: str = ""
    nom: str = ""
    prenom: str = ""
    hopital: str = ""
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    notes: str = ""
    source: str = ""
    date_import: str = field(default_factory=lambda: date.today().isoformat())

    # Runtime-only metadata used by writer_excel to highlight cells.
    # Maps field name -> marker dict: {"kind": "conflict"|"inferred"|"phonetic",
    #                                  "comment": "<text>"}.
    # Excluded from dedup/equality/output — not serialized to the Excel rows.
    markers: dict = field(default_factory=dict, compare=False, repr=False)

    def dedup_key(self) -> tuple:
        """Key used for deduplication: (city, last_name, specialty)."""
        import unicodedata
        nom = unicodedata.normalize("NFD", self.nom.upper())
        nom = "".join(c for c in nom if unicodedata.category(c) != "Mn")
        nom = nom.replace("-", "").replace(" ", "")
        ville = unicodedata.normalize("NFD", self.ville.upper())
        ville = "".join(c for c in ville if unicodedata.category(c) != "Mn")
        return (ville, nom, self.specialite)

    def is_empty(self) -> bool:
        """True if this entry has no doctor name and no useful notes."""
        return not self.nom and not self.notes

    def completeness_score(self) -> int:
        """Count of non-empty fields, used to prefer more complete records during merge."""
        score = 0
        for f in [self.nom, self.prenom, self.hopital, self.adresse,
                   self.telephone, self.email]:
            if f:
                score += 1
        return score


COLUMN_HEADERS = [
    "Region",
    "Ville",
    "Type de centre",
    "Responsable du centre",
    "Specialite",
    "Detail specialite",
    "Secteur",
    "Titre",
    "Nom",
    "Prenom",
    "Hopital",
    "Adresse",
    "Telephone",
    "Email",
    "Notes",
    "Source",
    "Date import",
]


def doctor_to_row(doc: Doctor) -> list:
    """Convert a Doctor to a list of values matching COLUMN_HEADERS order."""
    return [
        doc.region,
        doc.ville,
        doc.type_centre,
        doc.responsable_centre,
        doc.specialite,
        doc.specialite_detail,
        doc.secteur,
        doc.titre,
        doc.nom,
        doc.prenom,
        doc.hopital,
        doc.adresse,
        doc.telephone,
        doc.email,
        doc.notes,
        doc.source,
        doc.date_import,
    ]
