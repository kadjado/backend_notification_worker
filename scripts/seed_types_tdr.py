from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import TypeTDR


REFERENTIEL = [
    ("TDR_PALUDISME", "TDR paludisme"),
]


def main():
    with SessionLocal() as db:
        try:
            for code, libelle in REFERENTIEL:
                existant = db.scalar(
                    select(TypeTDR).where(TypeTDR.code == code)
                )

                if existant is None:
                    db.add(
                        TypeTDR(
                            code=code,
                            libelle=libelle,
                            actif=True,
                        )
                    )
                    print(f"À ajouter : {code} - {libelle}")
                elif existant.libelle != libelle:
                    raise ValueError(
                        f"Le code {code} existe avec un autre libellé."
                    )
                else:
                    print(f"Déjà présent : {code} - {libelle}")

            db.commit()
            print("Initialisation des types de TDR terminée.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
