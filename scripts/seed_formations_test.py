import random

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Commune, FormationSanitaire


TYPES_FS = ["USP", "CMS", "Hôpital"]
GENERATEUR = random.Random(20261022)


def main():
    with SessionLocal() as db:
        try:
            communes = db.scalars(
                select(Commune).order_by(Commune.code)
            ).all()

            if not communes:
                raise ValueError(
                    "Aucune commune trouvée. "
                    "Initialise d'abord le référentiel géographique."
                )

            # Génération reproductible : une nouvelle exécution produit
            # les mêmes établissements et ne crée pas de doublons.
            donnees = []
            numero = 1

            for commune in communes:
                nombre = GENERATEUR.randint(1, 3)

                for _ in range(nombre):
                    donnees.append({
                        "code": f"TEST_FS_{numero:04d}",
                        "libelle": f"Formation sanitaire {numero}",
                        "type_fs": GENERATEUR.choice(TYPES_FS),
                        "commune_id": commune.id,
                    })
                    numero += 1

            ajoutees = 0

            for item in donnees:
                existante = db.scalar(
                    select(FormationSanitaire).where(
                        FormationSanitaire.code == item["code"]
                    )
                )

                if existante is not None:
                    if (
                        existante.libelle != item["libelle"]
                        or existante.type_fs != item["type_fs"]
                        or existante.commune_id != item["commune_id"]
                    ):
                        raise ValueError(
                            f"Conflit pour {item['code']}. "
                            "Aucune modification automatique effectuée."
                        )

                    continue

                db.add(FormationSanitaire(**item))
                ajoutees += 1

            db.commit()

            total = len(db.scalars(
                select(FormationSanitaire).where(
                    FormationSanitaire.code.like("TEST_FS_%")
                )
            ).all())

            print(f"Communes parcourues : {len(communes)}")
            print(f"Nouvelles formations ajoutées : {ajoutees}")
            print(f"Formations de test enregistrées : {total}")
            print("Initialisation terminée.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
