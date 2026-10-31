from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Commune, Prefecture


# Code de préfecture interne, libellé de commune dans l'annuaire INSEED,
# nombre de communes à créer. Les codes générés sont internes au SCDIP.
REFERENTIEL = [
    ("PREF_AVE", "Avé", 2),
    ("PREF_BAS_MONO", "Bas-Mono", 2),
    ("PREF_YOTO", "Yoto", 3),
    ("PREF_VO", "Vo", 4),
    ("PREF_LACS", "Lacs", 4),
    ("PREF_ZIO", "Zio", 4),
    ("PREF_AGOE_NYIVE", "Agoè-nyivé", 6),
    ("PREF_GOLFE", "Golfe", 7),

    ("PREF_ANIE", "Anié", 2),
    ("PREF_EST_MONO", "Est-Mono", 3),
    ("PREF_MOYEN_MONO", "Moyen-Mono", 2),
    ("PREF_AGOU", "Agou", 2),
    ("PREF_DANYI", "Danyi", 2),
    ("PREF_AKEBOU", "Akébou", 2),
    ("PREF_KPELE", "Kpélé", 2),
    ("PREF_KLOTO", "Kloto", 3),
    ("PREF_OGOU", "Ogou", 4),
    ("PREF_AMOU", "Amou", 3),
    ("PREF_WAWA", "Wawa", 3),
    ("PREF_HAHO", "Haho", 4),

    ("PREF_TCHAOUDJO", "Tchaoudjo", 4),
    ("PREF_TCHAMBA", "Tchamba", 3),
    ("PREF_BLITTA", "Blitta", 3),
    ("PREF_SOTOUBOUA", "Sotouboua", 3),
    ("PREF_MO", "Mô", 2),

    ("PREF_ASSOLI", "Assoli", 3),
    ("PREF_KOZAH", "Kozah", 4),
    ("PREF_BASSAR", "Bassar", 4),
    ("PREF_DANKPEN", "Dankpen", 3),
    ("PREF_DOUFELGOU", "Doufelgou", 3),
    ("PREF_KERAN", "Kéran", 3),
    ("PREF_BINAH", "Binah", 2),

    ("PREF_CINKASSE", "Cinkassé", 2),
    ("PREF_TONE", "Tône", 4),
    ("PREF_KPENDJAL", "Kpendjal", 2),
    ("PREF_KPENDJAL_OUEST", "Kpendjal Ouest", 2),
    ("PREF_OTI", "Oti", 2),
    ("PREF_OTI_SUD", "Oti Sud", 2),
    ("PREF_TANDJOARE", "Tandjoaré", 2),
]


def main():
    with SessionLocal() as db:
        try:
            prefectures = {
                p.code: p for p in db.scalars(select(Prefecture)).all()
            }

            if len(REFERENTIEL) != 39:
                raise ValueError(
                    f"39 préfectures attendues, {len(REFERENTIEL)} trouvées."
                )

            missing = [
                code for code, _, _ in REFERENTIEL
                if code not in prefectures
            ]
            if missing:
                raise ValueError(
                    f"Préfectures absentes de la base : {missing}"
                )

            total_attendu = sum(n for _, _, n in REFERENTIEL)
            if total_attendu != 117:
                raise ValueError(
                    f"117 communes attendues, {total_attendu} configurées."
                )

            a_ajouter = []

            for pref_code, base, nombre in REFERENTIEL:
                prefecture = prefectures[pref_code]

                for numero in range(1, nombre + 1):
                    libelle = f"{base}{numero}"
                    code = f"COM_{pref_code.removeprefix('PREF_')}_{numero}"

                    existante_code = db.scalar(
                        select(Commune).where(Commune.code == code)
                    )
                    existante_nom = db.scalar(
                        select(Commune).where(Commune.libelle == libelle)
                    )

                    if existante_code is not None:
                        if (
                            existante_code.libelle != libelle
                            or existante_code.prefecture_id != prefecture.id
                        ):
                            raise ValueError(
                                f"Conflit sur le code commune {code}."
                            )
                        print(f"Déjà présente : {libelle}")
                        continue

                    if existante_nom is not None:
                        raise ValueError(
                            f"La commune {libelle!r} existe déjà sous "
                            f"le code {existante_nom.code!r}. "
                            "Vérifie le référentiel avant de continuer."
                        )

                    a_ajouter.append(
                        Commune(
                            code=code,
                            libelle=libelle,
                            prefecture_id=prefecture.id,
                        )
                    )

            db.add_all(a_ajouter)
            db.commit()

            print(f"\nCommunes ajoutées : {len(a_ajouter)}")
            print("Initialisation terminée.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
