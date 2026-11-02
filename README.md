# Kalkulator nadpłaty kredytu hipotecznego

Osobisty kalkulator przyszłej spłaty kredytu w PLN, oparty na dziennych odsetkach prostych i zdarzeniach z konkretnymi datami. Wspiera porównanie harmonogramu bez nadpłat z harmonogramem przyspieszonym. Nie potwierdzono jeszcze zgodności z indywidualną umową ING: wymaga to porównania ze zanonimizowanym harmonogramem banku.

## Uruchomienie

Wymagany Python 3.12 lub nowszy. Lokalnie testowano również Python 3.14.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m streamlit run app.py --server.port 8502
```

Otwórz http://127.0.0.1:8502. Istniejące lokalne środowisko `.venv-1` można wykorzystać zamiast `.venv`. Nie trzeba aktywować środowiska, jeśli używasz pełnej ścieżki do jego interpretera.

`requirements.txt` przypina wersje zależności bezpośrednich, a `requirements.lock.txt` zapisuje wersje całego testowanego środowiska. Ponowna instalacja na innym systemie lub Pythonie wymaga zgodnych binarnych pakietów.

## Dane istniejącego kredytu

Wprowadź kapitał na wybraną datę, pozostałą liczbę rat, oprocentowanie i dzień raty. Opcjonalnie podaj dokładny termin pierwszej raty, jej bieżącą wysokość z banku oraz odsetki naliczone PRZED datą stanu. Odsetki od daty stanu program dolicza samodzielnie; nie wpisuj ich dwukrotnie.

Bez dokładnego terminu najbliższa rata przypada w bieżącym miesiącu, jeśli wybrany dzień jest jeszcze przed nami, albo w kolejnym miesiącu. Dzień 29–31 jest ograniczany do ostatniego dnia krótszego miesiąca, ale wraca do pierwotnego dnia w kolejnym miesiącu.

Kwota początkowa to pozostały kapitał, nie historyczna kwota wypłaconego kredytu. Koszty już poniesione nie należą do przyszłych płatności. Dodatkowe koszty obejmują wpisaną kwotę jednorazową, koszt przy każdej przyszłej płatności i opcjonalną roczną stawkę ubezpieczenia od salda, dzieloną przez 12. To model kosztów użytkownika, nie automatycznie odtworzona taryfa ING.

## Odsetki i raty

- Kwoty finansowe są liczone przez `Decimal`, a odsetki za okres zaokrąglane raz do groszy, `ROUND_HALF_UP`.
- Odsetki są proste: codzienne naliczanie nie oznacza codziennej kapitalizacji.
- Przedział odsetkowy to `[początek, koniec)`. Nadpłata obniża saldo od swojej daty.
- Można wybrać ACT/ACT (365/366) albo ACT/365. Konwencję trzeba potwierdzić w umowie.
- Rata miesięczna korzysta z klasycznego wzoru ze stopą roczną / 12. Przy dziennych odsetkach ostatnia rata może różnić się od pozostałych.
- Rata kalendarzowa korzysta z sumy zdyskontowanych płatności przy rzeczywistych długościach okresów. Aby nie dopuścić ujemnego kapitału w długim okresie odsetkowym, ma dolną granicę pokrywającą odsetki najdłuższego okresu od salda początkowego. Przy skrajnych stopach może to skrócić spłatę nawet bez nadpłat; interfejs pokazuje rzeczywistą liczbę płatności.
- Aktualna rata z banku zastępuje ratę wyliczoną na początku. Jeżeli rata nie pokrywa odsetek, program zgłasza błąd zamiast tworzyć rosnące zadłużenie.
- Ostatnia płatność rozlicza faktyczny kapitał i odsetki; silnik sprawdza pełną zgodność sum kapitału.

## Nadpłaty i skracanie okresu

Obsługiwane są nadpłaty regularne przy terminach rat, pojedyncza nadpłata przy wybranej racie i tabela nieregularnych wpłat z dokładnymi datami. Zero w kwocie regularnej/jednorazowej oznacza brak nadpłat; model pojedynczej nadpłaty wymaga dodatniej kwoty.

Przy wielu wpłatach silnik rozlicza je chronologicznie. Nadpłaty tej samej daty są grupowane, a niewystarczający kapitał dzielony proporcjonalnie między dyspozycje. Po spłacie kapitału przyszłe wpłaty nie są pobierane. Podsumowanie pokazuje planowane, wykorzystane i niewykorzystane kwoty. Nadpłaty poza pierwotnym zakresem dat są błędem wejścia, a nie cicho pomijanym zdarzeniem.

Strategie:

- **Obniżenie raty**: część nadpłaty obniża następną ratę; nie kasuje wcześniej osiągniętego skrócenia.
- **Skrócenie okresu / Keep installment**: rata jest utrzymywana, a faktyczna spłata może nastąpić wcześniej. To symulacja stałego budżetu, nie automatyczna zmiana umowy ING.
- **Skrócenie okresu / Whole months**: pozostały okres jest zaokrąglany w dół do pełnych miesięcy, a rata przeliczana. Rata może wzrosnąć. Dostępność i warunki takiej zmiany trzeba ustalić z bankiem.
- **Mixed**: jawny podział kwoty na powyższe cele. Przy kilku strategiach w jednym okresie obie części są sumowane; nie obowiązuje zasada „ostatnia strategia wygrywa”.

Osobna tabela **dyspozycji skrócenia umowy** pozwala wpisać nową liczbę rat po wybranym umownym terminie płatności. Daty obowiązywania dyspozycji są jawne; wydłużenie kredytu nie jest obsługiwane. Standardowy scenariusz porównawczy nie uwzględnia tych instrukcji.

Operacje w dniu raty mają ustaloną kolejność: rata, nadpłata, przeliczenie na kolejny okres, dyspozycja nowego okresu. Nadpłaty między ratami zmniejszają odsetki od swojej rzeczywistej daty; zmiana raty dotyczy następnego okresu. Całkowitą spłatę kapitału i odsetek rozliczamy w dniu nadpłaty. Te reguły wymagają uzgodnienia z księgowaniem konkretnego kredytu ING.

## Oprocentowanie okresowo stałe i scenariusze

Podaj pierwszy dzień po obecnym okresie stałym (przy nowym kredycie może to być po 5 latach, a przy istniejącym kredycie okres pozostały będzie krótszy). Tabela zmian stóp przyjmuje datę `YYYY-MM-DD` i stopę w procentach, np. `7.51`. Program nie pozwala na zmiany przed końcem zadeklarowanego okresu stałego.

Po ostatniej zmianie stopa pozostaje stała aż do kolejnej wpisanej daty. Brak scenariusza po okresie stałym oznacza utrzymanie ostatniej stopy i jest wskazany w założeniach. Przyszłe stopy nie są prognozą. Zmiana w środku okresu dzieli naliczanie odsetek; rata jest aktualizowana przy pierwszym rozliczeniu obejmującym nową stopę, z wykorzystaniem rzeczywiście naliczonych odsetek i bez zakładania znajomości przyszłych stóp. To jawna konwencja symulacji, którą trzeba uzgodnić z bankiem.

## Kalendarz i wyniki

Opcjonalna data pobrania uwzględnia niedziele oraz polskie święta, w tym Wigilię od 2025 r. Sama sobota nie przesuwa daty umownej. Po niedzieli/święcie szukamy dnia roboczego. Daty pobrania są oddzielne od dat używanych do naliczania odsetek. Użytkownik API może rozszerzyć listę świąt przez `additional_holidays`.

Interfejs pokazuje pozostały kapitał, odsetki, koszty poza kapitałem, sumę przyszłych płatności, wykorzystane nadpłaty, liczbę płatności oraz datę końcowego rozliczenia. Wykres używa dat i zawiera stan początkowy. Salda są agregowane przy ratach, nie po każdej nieregularnej wpłacie. CSV zachowuje dokładne wartości dziesiętne.

## Testy i kontrole

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
```

Zwykły pytest uruchamia testy silnika, danych i formularza AppTest. Testy przeglądarkowe są jawnie włączane; wymagają uruchomionego Streamlit:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -m e2e --run-e2e --app-url http://127.0.0.1:8502 --tracing retain-on-failure --screenshot only-on-failure
```

CI instaluje przypięte zależności, wykonuje Ruff, MyPy i testy, uruchamia serwer, czeka na endpoint zdrowia i wykonuje Playwright. Raporty JUnit, ślady i zrzuty z niepowodzeń trafiają do `test-results/`. Projekt nie deklaruje generowania raportu coverage.

## Źródła i granica zgodności

[ING — Mam już kredyt hipoteczny](https://www.ing.pl/indywidualni/kredyty-i-pozyczki/kredyt-hipoteczny/mam-juz-kredyt), sprawdzono 2 listopada 2026: dzienne odsetki pobierane miesięcznie, obniżenie raty po nadpłacie, osobny proces skrócenia, okres 60 miesięcy stałej stopy i zasady pobierania rat w niedziele/święta.

[Ustawa zmieniająca dni wolne od pracy od 2025 r.](https://eli.gov.pl/api/acts/DU/2024/1965/text.html) stanowi podstawę uwzględnienia Wigilii w kalendarzu.

To nie zastępuje indywidualnej umowy. Brakujące potwierdzenie obejmuje konwencję roku, reguły zaokrągleń i granice dni, dokładny algorytm rat ING, kolejność operacji, moment przeliczenia raty, warunki skracania, datę księgowania, składki oraz opłaty.

Transze, karencja, raty malejące, zaległości, wakacje kredytowe i kredyty walutowe nie należą do bieżącego modelu. Jeżeli występują w Twoim kredycie, trzeba rozszerzyć model przed porównaniem. Kryterium akceptacji: uzgodniony przypadek bankowy z wyjaśnionymi różnicami groszowymi, nie samo przejście testów.

Status wszystkich punktów pierwotnego audytu znajduje się w [AUDIT_STATUS.md](AUDIT_STATUS.md).
