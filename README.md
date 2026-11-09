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

## Nowy model ING — gałąź `stage`

Domyślnie aplikacja wybiera **ING — nadpłata i osobny aneks (model do weryfikacji)**. Dotychczasowe strategie pozostają w modelu **Ogólny**. `main` pozostaje wersją odniesienia; punkt startowy zmian zapisano w commicie `0d9ab43`.

1. Wprowadź stan kredytu: saldo, datę tego salda, pozostałą liczbę rat, bieżącą stopę i opcjonalnie ratę z banku oraz już naliczone odsetki.
2. Wybierz nadpłatę. Przy jednorazowej możesz wskazać dokładną datę zaksięgowania; nieregularne nadpłaty mają własne daty. Każda nadpłata w modelu ING obniża ratę, bez automatycznego skrócenia umowy.
3. Opcjonalnie wpisz aneks: datę wejścia w życie i limit raty. Program wybiera najkrótszy pełny okres, dla którego wyliczona rata nie przekracza limitu. Wynik może być niższy od wybranego limitu: to jawna konwencja modelu, nie potwierdzona reguła odwzorowania suwaka ING. Opcjonalne minimum/maksimum wpisz z banku. Przy braku możliwości skrócenia program zgłasza błąd.
4. Tabela zdarzeń pokazuje ratę przed i po nadpłacie oraz przed i po aneksie. Osobne porównanie pokazuje dodatkowy efekt aneksów względem samych nadpłat.
5. W formularzu **Ile nadpłacić…** podaj datę, liczbę miesięcy skrócenia i limit raty. Wynik to minimalna **dodatkowa** nadpłata, przy aneksie tego samego dnia. Wcześniejsze wpisane operacje, również nadpłaty z dnia wyceny, są uwzględnione; przyszłe nie finansują celu. Wynik 0 oznacza, że cel nie wymaga dodatkowej wpłaty. Wycena nie dodaje automatycznie zdarzeń do harmonogramu. Aneks już wpisany na dzień wyceny trzeba usunąć przed wyceną.

Model ING nalicza odsetki proste po kolejnych datach księgowania. Kolejność tego samego dnia: rata umowna → zmiana stopy → nadpłata → aneks. Aneks może obowiązywać między ratami. Naliczonych odsetek nie dopisujemy do kapitału: rozliczamy je w najbliższej racie. Nadpłata całego kapitału wymaga też zapłaty naliczonych odsetek tego dnia. Przyszłe stopy nie są używane do wyceny dzisiejszej raty; przeliczenie następuje w dniu zmiany stopy.

Rata kalendarzowa jest wyszukiwana w groszach: ma pokrywać odsetki i spłacić saldo najpóźniej w ostatnim terminie, bez większej raty końcowej. Ostatnia rata może być mniejsza. W szczególnych przypadkach bardzo małego salda spłata może nastąpić wcześniej niż umowny termin. Model ogólny zachowuje swój wcześniejszy algorytm i jego ograniczenia opisane poniżej.

**Nie potwierdzono jeszcze zgodności kwot z konkretnym kredytem ING.** Do kalibracji potrzebujemy salda i oprocentowania przed nadpłatą, liczby pozostałych rat, dat księgowania i obowiązywania aneksu oraz raty po samej nadpłacie. Nie wyznaczamy automatycznie widełek ani uprawnień do aneksu. Daty pobrania po świętach mają charakter informacyjny; nie przesuwają okresu odsetkowego. Aktualna rata z banku pozostaje do pierwszego przeliczenia; nie służy do odgadywania salda lub stopy.

Warunek zakończenia: zgodność obliczeń z harmonogramem banku i testy obu modeli. Dane indywidualnego kredytu przechowuj w ignorowanym katalogu `local_data/`, poza GitHubem.

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

Strategie **modelu ogólnego**:

- **Obniżenie raty**: część nadpłaty obniża następną ratę; nie kasuje wcześniej osiągniętego skrócenia.
- **Skrócenie okresu / Keep installment**: rata jest utrzymywana, a faktyczna spłata może nastąpić wcześniej. To symulacja stałego budżetu, nie automatyczna zmiana umowy ING.
- **Skrócenie okresu / Whole months**: pozostały okres jest zaokrąglany w dół do pełnych miesięcy, a rata przeliczana. Rata może wzrosnąć. Dostępność i warunki takiej zmiany trzeba ustalić z bankiem.
- **Mixed**: jawny podział kwoty na powyższe cele. Przy kilku strategiach w jednym okresie obie części są sumowane; nie obowiązuje zasada „ostatnia strategia wygrywa”.

W modelu ogólnym osobna tabela **dyspozycji skrócenia umowy** pozwala wpisać nową liczbę rat po wybranym umownym terminie płatności. Daty obowiązywania dyspozycji są jawne; wydłużenie kredytu nie jest obsługiwane. Standardowy scenariusz porównawczy nie uwzględnia tych instrukcji.

W modelu ogólnym operacje w dniu raty mają ustaloną kolejność: rata, nadpłata, przeliczenie na kolejny okres, dyspozycja nowego okresu. Nadpłaty między ratami zmniejszają odsetki od swojej rzeczywistej daty; zmiana raty dotyczy następnego okresu. Całkowitą spłatę kapitału i odsetek rozliczamy w dniu nadpłaty. Te reguły wymagają uzgodnienia z księgowaniem konkretnego kredytu ING.

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

CI instaluje przypięte zależności, wykonuje Ruff, MyPy i testy, uruchamia serwer, czeka na endpoint zdrowia i wykonuje Playwright. Testy jednostkowe oraz AppTest są uruchamiane pod `coverage` z pomiarem rozgałęzień. CI wymaga osobno co najmniej **99% wykonanych linii i 99% rozgałęzień**; liczy wartości przed zaokrągleniem. Raporty JUnit, JSON, HTML, ślady i zrzuty z niepowodzeń trafiają do `test-results/`. Artefakty przeglądarkowe są zapisywane w `test-results/browser/`, aby kolejne uruchomienie Playwright nie usuwało raportu pokrycia.

Pomiar lokalny (po zainstalowaniu aktualnych zależności):

```bash
.venv/bin/python -m coverage run -m pytest -m 'not e2e'
.venv/bin/python -m coverage report
.venv/bin/python -m coverage json
.venv/bin/python -m coverage html
```

Raport otworzysz w `test-results/coverage/index.html`. Zakres pomiaru obejmuje `app.py`, wszystkie moduły `src/` oraz skrypty `scripts/`; pomija testy, środowiska zewnętrzne, dane prywatne i narzędzia asystenta. Konfiguracja znajduje się w `pyproject.toml`. Testy interfejsu AppTest są częścią raportu; testy przeglądarkowe są osobnym sprawdzeniem i nie są doliczane do coverage serwera.

Testy walidacji, granic harmonogramów i uruchamiania znajdują się w `test_validation_edges.py`, `test_financial_edges.py`, `test_app_edges.py` i `test_desktop_launcher.py`. Skrypt ikony ma testy cyklu życia, jednoczesnych kliknięć, błędów i CLI z izolowanymi granicami systemowymi. Testy uszkodzonego zapisu harmonogramu celowo wprowadzają błąd w wierszu księgi, aby sprawdzić kontrolę zgodności kapitału i płatności. Nie zastępują one niezależnych testów matematycznych ani porównania z bankiem. Wysokie coverage oznacza wykonanie kodu przez testy, nie potwierdzenie wszystkich możliwych kombinacji danych.

## Źródła i granica zgodności

[ING — Mam już kredyt hipoteczny](https://www.ing.pl/indywidualni/kredyty-i-pozyczki/kredyt-hipoteczny/mam-juz-kredyt), sprawdzono 2 listopada 2026: dzienne odsetki pobierane miesięcznie, obniżenie raty po nadpłacie, osobny proces skrócenia, okres 60 miesięcy stałej stopy i zasady pobierania rat w niedziele/święta.

[Ustawa zmieniająca dni wolne od pracy od 2025 r.](https://eli.gov.pl/api/acts/DU/2024/1965/text.html) stanowi podstawę uwzględnienia Wigilii w kalendarzu.

To nie zastępuje indywidualnej umowy. Brakujące potwierdzenie obejmuje konwencję roku, reguły zaokrągleń i granice dni, dokładny algorytm rat ING, kolejność operacji, moment przeliczenia raty, warunki skracania, datę księgowania, składki oraz opłaty.

Transze, karencja, raty malejące, zaległości, wakacje kredytowe i kredyty walutowe nie należą do bieżącego modelu. Jeżeli występują w Twoim kredycie, trzeba rozszerzyć model przed porównaniem. Kryterium akceptacji: uzgodniony przypadek bankowy z wyjaśnionymi różnicami groszowymi, nie samo przejście testów.

Robocze raporty audytu i plany prac są przechowywane lokalnie, poza repozytorium. Zasady działania i ograniczenia kalkulatora opisuje ten README.

## Saldo ING zawierające naliczone odsetki

W polu **Jaką kwotę podajesz?** wybierz **Sam kapitał** albo **Łączne saldo: kapitał + naliczone odsetki**. W drugim wariancie program odejmuje osobno podane odsetki od łącznego salda. Obie kwoty przepisz z banku na tę samą datę. Opłaty i ubezpieczenia nie należą do tego salda. Pole odsetek oznacza kwotę już naliczoną na datę stanu, a nie pełną część odsetkową następnej raty. Program pokazuje wynik podziału przed obliczeniami i odrzuca saldo bez dodatniego kapitału.

Testy syntetyczne sprawdzają rozdzielenie salda i rozliczenie odsetek przy **podanej** racie. Prywatne porównania z bankiem pozostają poza repozytorium. Algorytm samodzielnego wyznaczania raty i rat po aneksie nadal wymaga potwierdzenia.

## Uruchamianie pomocnicze na macOS

Skrypt `scripts/launch_desktop.py` można uruchomić interpreterem środowiska projektu lub wywoływać z lokalnej aplikacji macOS. Gotowa ikona `.app` jest lokalnym skrótem i nie jest częścią repozytorium. Uruchamia serwer wyłącznie na `127.0.0.1`, wybiera wolny port i otwiera domyślną przeglądarkę. Kolejne kliknięcie korzysta z tej samej instancji, jeśli nadal działa. Po ponownym uruchomieniu komputera serwer jest uruchamiany od nowa.

Zamknięcie karty przeglądarki nie zatrzymuje serwera. Stan uruchomienia oraz log znajdują się w ignorowanym `local_data/desktop/`. Ikona wskazuje aktualną lokalizację projektu; po przeniesieniu katalogu trzeba odtworzyć skrót. Uruchamia wersję kodu z bieżącego lokalnego katalogu, bez pobierania zmian z GitHuba.


## Co przechowujemy w repozytorium

- Kod aplikacji i skrypty uruchomieniowe (`app.py`, `src/`, `scripts/`).
- Testy oparte na danych syntetycznych (`tests/`).
- Zależności, konfigurację jakości, automatyczne kontrole GitHub Actions oraz instrukcję uruchomienia.

Poza Git pozostają środowiska Python, cache, logi, raporty i zrzuty testów, sekrety, dane bankowe (`local_data/`), lokalne ustawienia asystenta oraz robocze dokumenty `AUDIT_STATUS.md` i `ING_WORK_PLAN.md`. Dodanie pliku do `.gitignore` nie usuwa jego starszych wersji z historii repozytorium.

## Język interfejsu: PL / EN

Przełącznik w prawym górnym rogu zmienia język etykiet, opisów, błędów, ostrzeżeń, tabel i wykresu. Domyślnie wybrany jest polski. Wybór jest pamiętany w bieżącej sesji; nowa sesja zaczyna się po polsku. Przełączenie zachowuje wpisane dane, wiersze scenariuszy, strategie i gotowy wynik wyceny nadpłaty. Zmiana danych finansowych unieważnia wcześniejszą wycenę, aby nie pokazywać nieaktualnego wyniku.

Kwoty wynikowe są formatowane jako `4 748,90 zł` w PL i `4,748.90 PLN` w EN. Waluta i obliczenia pozostają takie same. Daty w tabelach i na osi wykresu mają format ISO. CSV w obu wersjach ma identyczne dane, angielskie nazwy kolumn i niezmienny format liczbowy. Pomocnicze menu Streamlit i natywne kontrolki przeglądarki mogą korzystać z języka swojego środowiska.

Tłumaczenia znajdują się w `locales/pl.json` i `locales/en.json`. Oba pliki muszą zawierać te same klucze i parametry tekstów. `src/i18n.py` odpowiada za prezentację i formatowanie; `src/messages.py` definiuje błędy z kodami niezależnymi od języka. Wartości enumów, strategie, nazwy zdarzeń, komentarze i identyfikatory w kodzie są angielskie. Silnik zwraca kody błędów i ostrzeżeń, a interfejs dobiera ich tłumaczenie. Komunikaty diagnostyczne wyjątków pozostają angielskie.

Testy `tests/test_i18n.py` sprawdzają kompletność słowników oraz zachowanie formularzy, tabel i wyników. Testy przeglądarkowe dodatkowo weryfikują PL → EN → PL i identyczność pobieranego CSV.
