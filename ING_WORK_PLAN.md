# Plan wdrożenia modelu ING

Stan: 2 listopada 2026. Gałąź robocza: `stage`. Nie łączymy z `main` przed porównaniem z indywidualnym harmonogramem banku.

| Etap | Stan | Rezultat / warunek zakończenia |
| --- | --- | --- |
| 1. Zabezpieczenie | Wykonane | Commit `0d9ab43`, gałąź `stage` wypchnięta na GitHub; baza: 70 testów bez przeglądarki. |
| 2. Dane referencyjne | Częściowe | Znamy historyczne kwoty rat i nadpłat. Brakuje salda, stopy, liczby rat przed zmianą, raty po samej nadpłacie i skutecznych dat aneksów/księgowania. Nie wyznaczamy tych wartości z samych rat. |
| 3. Reguły modelu | Wdrożone jako jawne założenia | Nadpłata obniża ratę; osobny aneks ma własną datę; pełne miesiące; limit raty i opcjonalne ręczne widełki. Algorytm bankowy nadal do uzgodnienia. |
| 4. Silnik i regresje | Wdrożone | `src/ing.py`, walidacja w `src/models.py`, integracja z podsumowaniem i scenariuszami. Testy niezależnych kwot i rozliczenia kapitału/odsetek. |
| 5. Wymagana nadpłata | Wdrożone | Minimalna dodatkowa nadpłata w groszach dla wskazanej daty, skrócenia i limitu raty. Test kwoty mniejszej o grosz. |
| 6. Streamlit | Wdrożone | Dwa modele spłaty, daty księgowania, osobne aneksy, tabela zdarzeń, porównanie samych nadpłat i aneksów, formularz celu. |
| 7. Odbiór i merge | Otwarty | Testy lokalne i przeglądarka wykonane; pozostają porównanie z bankiem i test użytkownika. Po wyjaśnieniu różnic przygotujemy PR do `main` i merge. |

## Jak przetestować aplikację

1. Uruchom `app.py` przez Streamlit i pozostaw domyślny model ING. Wpisz saldo na konkretny dzień, roczną stopę, liczbę rat i termin najbliższej raty. Jeśli znasz ratę z banku, zaznacz jej użycie. Saldo oznacza kapitał bez naliczonych odsetek i opłat.
2. Zaznacz jednorazową nadpłatę i podaj datę zaksięgowania; przy kilku operacjach użyj tabeli nieregularnych nadpłat. W modelu ING strategia to wyłącznie obniżenie raty.
3. Sprawdź tabelę zdarzeń: nadpłata powinna pozostawić termin umowny i obniżyć ratę, jeśli stan oraz rata wejściowa są zgodne z przyjętą metodą obliczeń.
4. Dopisz aneks z datą wejścia w życie i limitem raty. Sprawdź nową ratę, liczbę rat oraz końcową datę. Program wybiera najkrótszy skrócony okres mieszczący się w limicie; nie gwarantuje identyczności z wyborem suwaka w banku.
5. W formularzu wyceny podaj przyszłą datę, skrócenie o miesiąc i obecną ratę jako limit. Wynik jest dodatkową nadpłatą oprócz już wpisanych wpłat do dnia wyceny. Zakłada aneks tego samego dnia. Nie zmienia sam harmonogramu.
6. Kontrola prosta: kapitał 12000 zł, stopa 0%, 12 przyszłych rat, wycena na dzień stanu, skrócenie o miesiąc, limit 1000 zł → wymagana nadpłata 1000 zł, 11 rat po 1000 zł.
7. Powtórz na rzeczywistym kredycie. Zapisz różnice kwot, dat oraz tego, czy rata obejmuje ubezpieczenie. Nie zmieniaj oczekiwanych kwot bankowych tylko po to, aby test przechodził.

## Dane do porównania września

- Kapitał po racie 15.09.2026, przed nadpłatą 300 zł.
- Oprocentowanie, konwencja roku i reguły naliczania z umowy.
- Liczba rat przed wrześniowym aneksem i po nim.
- Skuteczna data zmniejszenia kapitału (zlecenie 19.09 przypada w sobotę).
- Data wejścia aneksu w życie, obniżona rata po samej nadpłacie, rata po aneksie i najbliższy harmonogram.
- Czy rata to wyłącznie kapitał i odsetki; osobno koszty/ubezpieczenia.
- Dla sierpnia analogiczny zestaw; 15.08 jest dniem świątecznym, co wymaga odróżnienia daty umownej od pobrania.

Dane indywidualne zapisujemy lokalnie w ignorowanym `local_data/`; nie publikujemy ich automatycznie w repozytorium.

## Granice aktualnego wdrożenia

- Codzienne odsetki proste, bez codziennej kapitalizacji; zaokrąglenie raz na rozliczenie.
- Przedział `[początek, koniec)`; skuteczne daty operacji podaje użytkownik. Przesunięcie wyświetlanej daty pobrania nie zmienia odsetek.
- Kolejność wspólnej daty: rata → zmiana stopy → nadpłata → aneks.
- Rata kalendarzowa liczona jako minimalna stała kwota w groszach, spłacająca saldo do końca okresu i pokrywająca odsetki, bez większej raty końcowej. Jest to model do kalibracji, a nie odtworzony wzór banku.
- Limit aneksu jest pułapem, nie żądaniem dokładnie tej samej raty. Sprawdzamy podane widełki kwotowe, ale nie bankowe uprawnienia, terminy ani opłaty za aneks.
- Wycena celu zakłada nadpłatę i aneks tego samego dnia, przy aktualnej stopie; przyszłe zmiany stopy mogą zmienić wynik. Nie jest jeszcze planerem serii automatycznych aneksów co miesiąc.
- Wcześniejsza całkowita spłata pomija późniejsze nadpłaty; podsumowanie pokazuje niewykorzystane kwoty.
- Kredyt w transzach, karencja, zaległości, wakacje kredytowe i raty malejące pozostają poza modelem.

## Kryterium merge do main

Testy jakości i obu modeli przechodzą; rzeczywiste przypadki ING odtwarzają raty, saldo, odsetki i datę końcową co do grosza lub mają wyjaśnione różnice wynikające z udokumentowanej reguły. Użytkownik sprawdza aplikację. Dopiero wtedy PR i merge do `main`; obecny stan nie spełnia jeszcze warunku bankowego.

## Wynik sprawdzeń wdrożenia

2 listopada 2026: **103 testy silnika/formularzy oraz 3 testy Chromium zakończone powodzeniem**. Ruff, kontrola formatowania, MyPy i `git diff --check` również przeszły. Testy przeglądarkowe wykonano na lokalnym serwerze `http://127.0.0.1:8503`. Przypadki bankowe pozostają niezweryfikowane z powodu brakujących danych opisanych wyżej.

CI uruchamia te kontrole także po push na `stage`; lokalny wynik nie stanowi potwierdzenia zakończenia zdalnego zadania GitHub Actions.

## Aktualizacja: saldo z naliczonymi odsetkami

Dodano jawny wybór rodzaju salda. Łączne saldo kapitału i odsetek jest rozdzielane przed utworzeniem parametrów kredytu; odsetki pozostają osobno do rozliczenia w najbliższej racie. Nie są kapitalizowane. `src/scenarios.py`: `principal_from_balance`; `app.py`: wybór rodzaju salda, odsetki na datę stanu i podgląd podziału. Testy w `tests/test_ing.py` oraz `tests/test_app.py` sprawdzają rzeczywiste rozliczenie, nieprawidłowy podział i równoważność obu sposobów wprowadzania danych.

Potwierdzono część odsetkową i kapitałową najbliższej raty po prawidłowym wydzieleniu kapitału oraz podaniu istniejącej raty z banku. Samodzielne wyznaczenie jej wysokości i rat po aneksie pozostaje do zweryfikowania; kryterium merge nie jest jeszcze spełnione.
