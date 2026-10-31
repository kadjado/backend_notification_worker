from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Region


REGIONS = [
    ("MAR", "Maritime"),
    ("PLA", "Plateaux"),
    ("CEN", "Centrale"),
    ("KAR", "Kara"),
    ("SAV", "Savanes"),
]


def main():
    with SessionLocal() as db:
        try:
            for code, libelle in REGIONS:
                region = db.scalar(
                    select(Region).where(Region.code == code)
                )

                if region is None:
                    # Évite de créer une deuxième ligne portant le même nom.
                    region_par_nom = db.scalar(
                        select(Region).where(Region.libelle == libelle)
                    )

                    if region_par_nom is not None:
                        raise ValueError(
                            f"La région {libelle!r} existe déjà avec "
                            f"le code {region_par_nom.code!r}. "
                            "Vérifie le référentiel avant de continuer."
                        )

                    db.add(Region(code=code, libelle=libelle))
                    print(f"À ajouter : {code} - {libelle}")
                elif region.libelle != libelle:
                    raise ValueError(
                        f"Le code {code!r} existe déjà avec le nom "
                        f"{region.libelle!r}, au lieu de {libelle!r}."
                    )
                else:
                    print(f"Déjà présente : {code} - {libelle}")

            db.commit()
            print("\nInitialisation terminée.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
