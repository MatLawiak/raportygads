# Generator Raportów Marketingowych — Instrukcja dla agenta

## Co robi ten projekt

Skrypt `main.py` pobiera dane z Google Ads i Google Analytics 4 za poprzedni miesiąc, a następnie generuje miesięczny raport marketingowy dla klienta. Raport jest zapisywany jako plik `.md` w folderze `raporty/`.

## Jak uruchomić skrypt

```bash
cd "c:\Users\matla\Documents\Visual Studio Code\Raporty Gads"
python main.py "Nazwa Klienta"
```

Przykład dla Restauracji Biała Dama:
```bash
python main.py "Restauracja Biała Dama"
```

Skrypt automatycznie pobiera dane za **poprzedni pełny miesiąc** (np. jeśli dziś jest kwiecień, pobiera marzec).

## Wymagania przed uruchomieniem

Sprawdź, czy wszystkie poniższe warunki są spełnione:

1. **Zmienna środowiskowa OPENAI_API_KEY** — skrypt używa OpenAI (gpt-4o-mini) do generowania raportu
   ```bash
   echo $OPENAI_API_KEY   # Linux/Mac
   echo $env:OPENAI_API_KEY  # PowerShell
   ```

2. **Plik `google-ads.yaml`** — musi zawierać `use_proto_plus: True` oraz uzupełnione pola:
   - `developer_token`
   - `client_id`, `client_secret`, `refresh_token`
   - `login_customer_id`

3. **Zmienna GOOGLE_APPLICATION_CREDENTIALS** — ścieżka do pliku JSON service account dla GA4
   ```bash
   $env:GOOGLE_APPLICATION_CREDENTIALS="ścieżka\do\plik.json"
   ```

Jeśli któregoś brakuje — poinformuj użytkownika i nie uruchamiaj skryptu.

## Jak pomóc w tworzeniu miesięcznego raportu

Gdy użytkownik poprosi o raport miesięczny, wykonaj kolejno:

### Krok 1 — Sprawdź zmienne środowiskowe
```bash
echo $env:OPENAI_API_KEY
echo $env:GOOGLE_APPLICATION_CREDENTIALS
```

### Krok 2 — Uruchom skrypt
```bash
cd "c:\Users\matla\Documents\Visual Studio Code\Raporty Gads"
python main.py "Restauracja Biała Dama"
```

### Krok 3 — Sprawdź wynik
Po uruchomieniu skrypt zapisze raport do `raporty/raport_restauracja_biała_dama_YYYY-MM.md`. Otwórz ten plik i sprawdź czy raport jest kompletny.

### Krok 4 — Przepisz raport według właściwej struktury

Raport wygenerowany przez skrypt jest bazą — **przepisz go** według poniższej struktury, dopasowując ton i język do właścicielki restauracji (osoba bez technicznej wiedzy o marketingu).

---

## Struktura raportu miesięcznego

Raport składa się zawsze z 4 sekcji:

### 1. Wyniki Google Ads

Opisz wyniki kampanii reklamowych. Uwzględnij:
- Łączne wydatki, kliknięcia, wyświetlenia, CTR, CPC, konwersje, koszt konwersji
- Wyniki per kampania — najlepsza i najsłabsza
- Porównanie do poprzedniego miesiąca (jeśli dane dostępne)
- Wyjaśnienie kierunku zmian (wzrost/spadek) i możliwej przyczyny

### 2. Wyniki GA4 (ruch na stronie)

Opisz zachowanie użytkowników. Uwzględnij:
- Liczba użytkowników i sesji
- Źródła ruchu (Google Ads, organic, direct, inne)
- Współczynnik zaangażowania / odrzuceń
- Konwersje (formularze, telefony, inne cele)

Jeśli brak danych GA4 — napisz to wprost, nie wymyślaj danych.

### 3. Podsumowanie i wnioski

- Co zadziałało najlepiej
- Co wymaga poprawy
- Czy kampanie idą w dobrym kierunku
- Ważne obserwacje (sezonowość, zachowania użytkowników)

### 4. Przewidywane zmiany i rekomendacje

- Optymalizacje kampanii z uzasadnieniem
- Zmiany budżetów z uzasadnieniem
- Planowane testy
- Nowe działania

---

## Zasady pisania raportu

- **Język polski**, prosty, bez technicznego żargonu
- Odbiorca: właścicielka restauracji, nieznająca marketingu cyfrowego
- Krótkie akapity, pogrubienia dla ważnych informacji
- Brak emoji
- Ton profesjonalny, ale ludzki
- Zawsze interpretuj dane — nie przepisuj ich mechanicznie
- Konwersje formularzy to **kluczowy cel** — zawsze je wyróżniaj
- Jeśli coś spada → wyjaśnij możliwą przyczynę
- Jeśli coś rośnie → podkreśl, co na to wpłynęło
- Jeśli brakuje danych → napisz to wprost, nie zgaduj wartości

---

## Znane problemy i jak je rozwiązać

| Problem | Rozwiązanie |
|---|---|
| `use_proto_plus` brakuje w yaml | Dodaj `use_proto_plus: True` do `google-ads.yaml` |
| Brak GOOGLE_APPLICATION_CREDENTIALS | Ustaw zmienną wskazującą na plik JSON service account |
| Brak OPENAI_API_KEY | Ustaw zmienną z kluczem API OpenAI |
| GA4 zwraca brak danych | Sprawdź czy service account ma dostęp do property w GA4 |
| Konto klienta nie znalezione | Sprawdź dokładną nazwę konta w Google Ads MCC |

## Klient testowy

- Nazwa: `Restauracja Biała Dama` (lub `Restauracja Biała Dama - nowe`)
- MCC ID: 8612470472
