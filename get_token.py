"""
Jednorazowy skrypt do pobrania refresh_token dla Google Ads.

Uruchom raz:
    pip install google-auth-oauthlib
    python get_token.py

Skrypt otworzy przeglądarkę — zaloguj się na konto Google Ads,
zatwierdź dostęp, a refresh_token zostanie wypisany na ekranie.
"""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRET_FILE = (
    "client_secret_5019340360-et258f8k3rpn3um5jnrahn0gf4ahlgod"
    ".apps.googleusercontent.com.json"
)

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def main():
    secret_path = Path(CLIENT_SECRET_FILE)
    if not secret_path.exists():
        print(f"❌ Nie znaleziono pliku: {CLIENT_SECRET_FILE}")
        print("Skopiuj plik JSON z Google Cloud Console do tego folderu.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    # Odczytaj client_id i client_secret z pliku JSON
    with open(secret_path) as f:
        secret_data = json.load(f)
    installed = secret_data.get("installed", secret_data.get("web", {}))
    client_id = installed.get("client_id", "")
    client_secret = installed.get("client_secret", "")

    print("\n" + "=" * 60)
    print("✅ Autoryzacja zakończona pomyślnie!")
    print("=" * 60)
    print("\nUzupełnij plik google-ads.yaml poniższymi danymi:\n")
    print(f"client_id: {client_id}")
    print(f"client_secret: {client_secret}")
    print(f"refresh_token: {creds.refresh_token}")
    print("\n" + "=" * 60)
    print("⚠️  Zachowaj refresh_token w bezpiecznym miejscu.")
    print("    NIE commituj google-ads.yaml do repozytorium Git!")


if __name__ == "__main__":
    main()
