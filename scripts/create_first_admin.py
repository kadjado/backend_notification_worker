import getpass

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Utilisateur


def demander_texte(message: str) -> str:
    while True:
        valeur = input(message).strip()
        if valeur:
            return valeur
        print("Ce champ est obligatoire.")


def main() -> None:
    db = SessionLocal()

    try:
        nombre = db.scalar(
            select(func.count()).select_from(Utilisateur)
        )

        if nombre != 0:
            print(
                "Création refusée : la table utilisateurs "
                "n'est pas vide."
            )
            return

        print("=== Création du premier administrateur national ===")
        nom = demander_texte("Nom : ")
        prenom = demander_texte("Prénom : ")
        email = demander_texte("Email : ").lower()
        fonction = demander_texte("Fonction : ")

        existing = db.scalar(
            select(Utilisateur.id).where(Utilisateur.email == email)
        )
        if existing is not None:
            print("Cet email est déjà utilisé.")
            return

        while True:
            password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
            if len(password) < 12:
                print("Le mot de passe doit contenir au moins 12 caractères.")
                continue

            confirmation = getpass.getpass("Confirmer le mot de passe : ")
            if password != confirmation:
                print("Les mots de passe ne correspondent pas.")
                continue
            break

        administrateur = Utilisateur(
            nom=nom,
            prenom=prenom,
            email=email,
            password_hash=hash_password(password),
            fonction=fonction,
            role="administrateur_national",
            actif=True,
        )

        db.add(administrateur)
        db.commit()

        print("\nAdministrateur national créé avec succès.")
        print(f"Identifiant : {administrateur.id}")
        print(f"Email : {administrateur.email}")
        print(f"Rôle : {administrateur.role}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
