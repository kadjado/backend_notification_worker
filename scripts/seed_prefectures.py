from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Prefecture, Region


# Codes internes SCDIP ; ce ne sont pas des codes administratifs officiels.
PREFECTURES = [
    ("PREF_GOLFE", "Golfe", "MAR"),
    ("PREF_AGOE_NYIVE", "Agoè-Nyivé", "MAR"),
    ("PREF_ZIO", "Zio", "MAR"),
    ("PREF_YOTO", "Yoto", "MAR"),
    ("PREF_BAS_MONO", "Bas-Mono", "MAR"),
    ("PREF_LACS", "Lacs", "MAR"),
    ("PREF_VO", "Vo", "MAR"),
    ("PREF_AVE", "Avé", "MAR"),

    ("PREF_OGOU", "Ogou", "PLA"),
    ("PREF_MOYEN_MONO", "Moyen-Mono", "PLA"),
    ("PREF_HAHO", "Haho", "PLA"),
    ("PREF_AGOU", "Agou", "PLA"),
    ("PREF_KLOTO", "Kloto", "PLA"),
    ("PREF_KPELE", "Kpélé", "PLA"),
    ("PREF_DANYI", "Danyi", "PLA"),
    ("PREF_WAWA", "Wawa", "PLA"),
    ("PREF_AKEBOU", "Akébou", "PLA"),
    ("PREF_AMOU", "Amou", "PLA"),
    ("PREF_ANIE", "Anié", "PLA"),
    ("PREF_EST_MONO", "Est-Mono", "PLA"),

    ("PREF_TCHAOUDJO", "Tchaoudjo", "CEN"),
    ("PREF_TCHAMBA", "Tchamba", "CEN"),
    ("PREF_BLITTA", "Blitta", "CEN"),
    ("PREF_SOTOUBOUA".upper(), "Sotouboua", "CEN"),
    ("PREF_MO", "Mô", "CEN"),

    ("PREF_KOZAH", "Kozah", "KAR"),
    ("PREF_ASSOLI", "Assoli", "KAR"),
    ("PREF_BASSAR", "Bassar", "KAR"),
    ("PREF_DANKPEN", "Dankpen", "KAR"),
    ("PREF_KERAN", "Kéran", "KAR"),
    ("PREF_DOUFELGOU", "Doufelgou", "KAR"),
    ("PREF_BINAH", "Binah", "KAR"),

    ("PREF_TONE", "Tône", "SAV"),
    ("PREF_CINKASSE", "Cinkassé", "SAV"),
    ("PREF_KPENDJAL_OUEST", "Kpendjal-Ouest", "SAV"),
    ("PREF_KPENDJAL", "Kpendjal", "SAV"),
    ("PREF_OTI_SUD", "Oti-Sud", "SAV"),
    ("PREF_OTI", "Oti", "SAV"),
    ("PREF_TANDJOARE", "Tandjoaré", "SAV"),
]


def main():
    with SessionLocal() as db:
        try:
            regions = {
                region.code: region
                for region in db.scalars(select(Region)).all()
            }

            required_regions = {"MAR", "PLA", "CEN", "KAR", "SAV"}
            missing_regions = required_regions - regions.keys()

            if missing_regions:
                raise ValueError(
                    f"Régions manquantes : {sorted(missing_regions)}. "
                    "Exécute d'abord le script seed_regions."
                )

            if len(PREFECTURES) != 39:
                raise ValueError(
                    f"Le script doit contenir 39 préfectures, "
                    f"mais en contient {len(PREFECTURES)}."
                )

            for code, libelle, region_code in PREFECTURES:
                region = regions[region_code]

                existing_code = db.scalar(
                    select(Prefecture).where(Prefecture.code == code)
                )

                existing_name = db.scalar(
                    select(Prefecture).where(
                        Prefecture.libelle == libelle
                    )
                )

                if existing_code is not None:
                    if (
                        existing_code.libelle != libelle
                        or existing_code.region_id != region.id
                    ):
                        raise ValueError(
                            f"Conflit pour le code {code}: "
                            "le nom ou la région diffère du référentiel attendu."
                        )

                    print(f"Déjà présente : {libelle}")
                    continue

                if existing_name is not None:
                    raise ValueError(
                        f"La préfecture {libelle!r} existe déjà sous "
                        f"le code {existing_name.code!r}. "
                        "Vérifie les données avant de continuer."
                    )

                db.add(
                    Prefecture(
                        code=code,
                        libelle=libelle,
                        region_id=region.id,
                    )
                )
                print(f"À ajouter : {libelle} -> {region.libelle}")

            db.commit()
            print("\nInitialisation des préfectures terminée.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
