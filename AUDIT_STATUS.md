# Status audytu kalkulatora

Stan wdrożenia poprawek: 2 listopada 2026. Dokument zachowuje numerację 25 punktów pierwotnego audytu i wskazuje ich implementację oraz weryfikację.

„Wdrożone” oznacza zmianę programu i opisany zakres sprawdzenia. Nie oznacza potwierdzonej zgodności z indywidualnym kredytem ING. Przy każdym punkcie rozdzielono lokalizację implementacji, zmianę zachowania i testy lub inne kontrole. Odwołania prowadzą do plików w bieżącym katalogu projektu oraz do zweryfikowanych linii funkcji, klas lub fragmentów formularza. Po dalszej przebudowie kodu numery linii mogą się zmienić; nazwy funkcji pozwalają ponownie odnaleźć implementację.


## Aktualizacja: model nadpłaty i aneksu ING

Wdrożenie na gałęzi `stage`; bazowa wersja audytu: commit `0d9ab43`. Poniższe 25 punktów opisuje historyczną naprawę modelu ogólnego. Model ING ma osobną implementację; nie należy przypisywać mu ograniczenia „aneks tylko w terminie raty” ani automatycznych strategii SHORTEN/MIXED.

- **Modele i walidacja:** `src/models.py` — `RepaymentModel`, `AnnexInstruction`, `LoanParameters.annexes`. Limit raty i opcjonalne widełki pochodzą od użytkownika. Model ING nie przyjmuje starych `TermChange` ani strategii skracania wewnątrz nadpłaty.
- **Chronologia i odsetki:** `src/ing.py` — `simulate_ing`, `LoanState`, `EventResult`. Osobne daty nadpłat i aneksów; grupowanie nadpłat tego samego dnia; dzienne odsetki proste; rozliczenie po całkowitej spłacie; kontrola kapitału i przepływów. Daty operacji oznaczają skuteczne księgowanie, nie wysłanie przelewu.
- **Pełne miesiące i rata:** `src/ing.py` — `quote_payment`, `select_annex`. Minimalna rata w groszach rozliczająca harmonogram, wybór najkrótszego skróconego okresu mieszczącego się w limicie i podanych widełkach. Limit nie oznacza wymuszenia identycznej raty. Przyszłe stopy nie są antycypowane.
- **Odwrotne obliczenie nadpłaty:** `src/ing.py` — `required_overpayment`, `OverpaymentQuote`. Wyszukiwanie minimalnej dodatkowej kwoty co do grosza, uwzględnienie wcześniejszych operacji, odsetek naliczonych i raty przypadającej w dniu wyceny. Założenie: nadpłata i nowy aneks tego samego dnia.
- **Porównanie:** `src/calculator.py` — wybór silnika w `generate_amortization_schedule`; scenariusz bez nadpłat nie zawiera aneksów. `src/scenarios.py` — `build_annexes` parsuje daty, limity i puste opcjonalne widełki.
- **Interfejs:** `app.py` — domyślny model ING, dokładna data jednorazowej nadpłaty, edytor aneksów, tabela rat przed/po zdarzeniu, efekt aneksów względem samych nadpłat, formularz wymaganej nadpłaty. Stare strategie dostępne wyłącznie w modelu ogólnym.
- **Sprawdzenie:** `tests/test_ing.py` — niezależne przypadki zerowej stopy i ręcznie liczonych odsetek, minimalność co do grosza, kilka zdarzeń, aneksy między ratami i w terminie raty, limit bankowy, pełna spłata, rok przestępny, scenariusze stóp, długi kredyt i uzgodnienie przepływów. `tests/test_app.py` — ścieżki nowego formularza. `tests/test_ui_dashboard.py` — rzeczywista przeglądarka, m.in. wycena 1000 zł przy 12000 zł kapitału, zerowej stopie i skróceniu 12 → 11 rat z limitem 1000 zł.

**Do potwierdzenia przed merge do `main`:** dokładny algorytm ING wyliczania rat i pełnych miesięcy, data skutecznego księgowania, zasady granic dni, zaokrągleń i zmiany harmonogramu, widełki oraz porównanie z indywidualnymi harmonogramami. Nie oznaczamy tego etapu jako zakończonego na podstawie samych testów syntetycznych. Szczegóły: `ING_WORK_PLAN.md`.


## 1. Jedna nadpłata przy wybranej racie

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [src/scenarios.py — build_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:40)
- [app.py — wybór numeru raty](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:88)

**Wprowadzone zmiany:** Dla trybu `single` konstruktor wybiera jedną datę przez `dates[month - 1]`, a następnie tworzy jedną nadpłatę. Nie dodaje już wpłaty w każdej iteracji przechodzącej przez wcześniejsze miesiące. Numer raty jest sprawdzany względem pozostałego okresu.

**Weryfikacja i lokalizacja testów:**

- [tests/test_app.py — test_overpayment_occurs_only_in_selected_month](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:17)
- [tests/test_audit_regressions.py — test_scenario_builders_parse_decimal_percent_and_irregular_rows](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:262)

**Zakres i ograniczenia:** Test formularza sprawdza miesiące 1 i 12, jedną wykorzystaną wpłatę i sumę 1000 zł. Nadpłata zaplanowana przy ostatniej racie może zostać niewykorzystana, jeżeli rata wcześniej zamknie kapitał.


## 2. Odsetki według rzeczywistych dat nadpłat

**Status:** Wdrożone; konwencja granic dni pozostaje założeniem do uzgodnienia z umową.

**Lokalizacja implementacji:**

- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — period_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:99)
- [src/calculator.py — calculate_daily_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:63)

**Wprowadzone zmiany:** Okres do raty jest dzielony przy kolejnych datach nadpłat. Najpierw naliczane są odsetki do zdarzenia, następnie zmniejszany jest kapitał. `period_interest` dzieli te fragmenty dodatkowo przy zmianach oprocentowania. Funkcja pomocnicza zwraca niezaokrąglone odsetki, a `money` zaokrągla dopiero sumę okresu.

**Weryfikacja i lokalizacja testów:**

- [tests/test_calculator.py — test_mid_period_overpayment_reduces_current_period_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:257)
- [tests/test_calculator.py — test_multiple_overpayments_in_one_period_follow_actual_dates](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:327)
- [tests/test_audit_regressions.py — test_rate_change_splits_daily_interest_at_effective_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:144)

**Zakres i ograniczenia:** Przykład 10 000 zł, 12%, nadpłata 1000 zł 20 stycznia daje 95,01 zł odsetek za okres 10 stycznia–10 lutego. Przedział naliczania to `[początek, koniec)`.


## 3. Rata wyrównująca i pełne rozliczenie kapitału

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — calculate_simulation_summary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:449)

**Wprowadzone zmiany:** Przy końcu harmonogramu albo możliwości wcześniejszej spłaty rata obejmuje pozostały kapitał i należne odsetki. Pełna nadpłata między ratami ustawia datę końcowego rozliczenia na dzień tej nadpłaty. Po zbudowaniu harmonogramu silnik wymaga salda zero, zgodności sumy kapitału oraz zgodności płatności z kapitałem i odsetkami; przy naruszeniu zgłasza `ArithmeticError`.

**Weryfikacja i lokalizacja testów:**

- [tests/test_calculator.py — test_last_installment_clears_rounding_remainder](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:202)
- [tests/test_calculator.py — test_last_installment_clears_principal_and_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:226)
- [tests/test_calculator.py — test_mid_period_full_principal_repayment_stops_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:284)

**Zakres i ograniczenia:** Dla 10 000 zł na trzy raty przy 0% ostatnia rata wynosi 3333,34 zł. Przy pełnej nadpłacie założono jednoczesne rozliczenie odsetek; księgowanie ING wymaga potwierdzenia.


## 4. Spójne warianty wyliczania rat i kontrola ujemnego kapitału

**Status:** Wdrożone jako jawne warianty symulacji; algorytm rat ING do uzgodnienia.

**Lokalizacja implementacji:**

- [src/models.py — InstallmentMethod](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:20)
- [src/calculator.py — annuity_payment](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:121)
- [src/calculator.py — _reprice_settlement](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:174)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [app.py — wybór sposobu wyliczania raty](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:160)

**Wprowadzone zmiany:** Wariant miesięczny używa stopy rocznej podzielonej przez 12. Wariant kalendarzowy korzysta z rzeczywistych odstępów i zdyskontowanych płatności oraz minimalnej raty pokrywającej odsetki w najdłuższym okresie. Zmiana stopy przelicza pierwsze rozliczenie obejmujące nową stopę. Rata niepokrywająca odsetek powoduje błąd danych zamiast wygenerowania ujemnej części kapitałowej.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_calendar_annuity_matches_independent_discount_factors](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:174)
- [tests/test_audit_regressions.py — test_long_schedule_reconciles_capital_interest_and_cash](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:197)
- [tests/test_audit_regressions.py — test_upward_rate_change_reprices_payment_without_negative_principal](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:308)

**Zakres i ograniczenia:** Minimum raty kalendarzowej może skrócić symulowaną spłatę przy skrajnych stopach także bez nadpłat. Test porównujący wzór z `Fraction` nie stanowi potwierdzenia algorytmu bankowego.


## 5. Kilka nadpłat i różne strategie w jednym okresie

**Status:** Wdrożone dla opisanych zasad symulacji.

**Lokalizacja implementacji:**

- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — _allocations](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:250)

**Wprowadzone zmiany:** Wpłaty są sortowane według dat, a te z tej samej daty grupowane. `_allocations` wylicza rzeczywiście wykorzystaną kwotę oraz jej części na skrócenie i obniżenie raty. Jeżeli suma wpłat przekracza kapitał, podział jest proporcjonalny. Nie obowiązuje już zasada stosowania ostatniej strategii do całego okresu.

**Weryfikacja i lokalizacja testów:**

- [tests/test_calculator.py — test_different_strategies_preserve_each_overpayment_allocation](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:76)
- [tests/test_calculator.py — test_multiple_overpayments_in_one_period_follow_actual_dates](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:327)
- [tests/test_audit_regressions.py — test_oversized_same_day_mixed_payment_is_capped_and_order_independent](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:93)

**Zakres i ograniczenia:** Testy odwracają listy wejściowe i porównują całe harmonogramy. Zmiana rzeczywistych dat może zmienić odsetki; niezależność od kolejności listy nie oznacza niezależności od terminów wpłat.


## 6. Skrócenie okresu i przeliczenie raty

**Status:** Wdrożone jako dwa warianty i osobna dyspozycja; warunki ING pozostają do potwierdzenia.

**Lokalizacja implementacji:**

- [src/models.py — ShorteningPolicy](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:25)
- [src/calculator.py — _remaining_count](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:273)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [app.py — wybór sposobu skracania okresu](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:172)

**Wprowadzone zmiany:** `KEEP_PAYMENT` utrzymuje ratę i pozwala wcześniej spłacić kapitał. `WHOLE_MONTHS` szacuje pozostały okres, zaokrągla jego część ułamkową w dół i przelicza ratę dla krótszego horyzontu. Silnik przechowuje zmieniony horyzont zamiast zawsze wracać do pierwotnej liczby miesięcy.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_whole_month_shortening_changes_term_and_payment](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:119)
- [tests/test_audit_regressions.py — test_later_reduce_does_not_erase_previous_shortening](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:106)

**Zakres i ograniczenia:** Wariant pełnych miesięcy może podwyższyć ratę. Nie oznacza to, że bank zaakceptuje każdą taką zmianę. Oddzielne dyspozycje nowego okresu opisuje punkt 9.


## 7. Podział Mixed i zachowanie wcześniejszego skracania

**Status:** Wdrożone dla przyjętego sposobu rozliczania strategii.

**Lokalizacja implementacji:**

- [src/models.py — Overpayment](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:78)
- [src/calculator.py — _allocations](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:250)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/scenarios.py — build_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:40)

**Wprowadzone zmiany:** Model wymaga obu nieujemnych części Mixed i ich sumy równej kwocie wpłaty. Silnik rozlicza obie części każdej wykorzystanej nadpłaty. Przy obniżaniu kolejnej raty odejmuje wpływ części na redukcję, zamiast przeliczać całe saldo tak, jak gdyby wcześniejszego skracania nie było. Przy ograniczeniu wpłaty do salda podział jest proporcjonalny.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_negative_mixed_allocation_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:70)
- [tests/test_calculator.py — test_different_strategies_preserve_each_overpayment_allocation](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:76)
- [tests/test_audit_regressions.py — test_later_reduce_does_not_erase_previous_shortening](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:106)

**Zakres i ograniczenia:** Mixed jest strategią symulacyjną użytkownika. Jej wykonanie w banku może wymagać nadpłaty i oddzielnej zmiany okresu.


## 8. Codzienne naliczanie zamiast deklarowanej kapitalizacji

**Status:** Wdrożone w opisach kodu, interfejsu i dokumentacji.

**Lokalizacja implementacji:**

- [src/calculator.py — calculate_daily_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:63)
- [app.py — opis odsetek](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:36)
- [README.md](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/README.md)

**Wprowadzone zmiany:** Usunięto opisy sugerujące codzienną kapitalizację i gwarantowaną bankową dokładność. Dokumentacja modułu i funkcji opisuje odsetki proste. Odsetki nie zwiększają automatycznie kapitału przy każdym dniu naliczania.

**Weryfikacja i lokalizacja testów:**

- [tests/test_calculator.py — test_calculate_daily_interest_leap_year](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:28)
- [tests/test_audit_regressions.py — test_rate_change_splits_daily_interest_at_effective_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:144)

**Zakres i ograniczenia:** Testy sprawdzają arytmetykę odsetek prostych; zgodność samych opisów sprawdzono przez przegląd tekstu. Nie ma osobnego testu automatycznego treści README.


## 9. Oddzielna dyspozycja skrócenia umowy

**Status:** Wdrożone jako model i formularz; aplikacja nie składa dyspozycji bankowych.

**Lokalizacja implementacji:**

- [src/models.py — TermChange](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:62)
- [src/scenarios.py — build_term_changes](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:109)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — calculate_simulation_summary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:449)
- [app.py — tabela dyspozycji](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:225)

**Wprowadzone zmiany:** Dyspozycja zawiera datę i nową liczbę rat pozostałych po wskazanej racie. Data musi należeć do umownego harmonogramu przed jego końcem, a nowy okres może go tylko skracać. Przeliczana jest przyszła rata. Harmonogram porównawczy bez nadpłat powstaje bez tych dyspozycji, aby nie mieszać scenariuszy.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_separate_term_instruction_does_not_change_standard_scenario](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:127)
- [tests/test_audit_regressions.py — test_term_extension_and_non_due_instruction_are_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:135)
- [tests/test_app.py — test_term_editor_updates_accelerated_scenario_only](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:120)

**Zakres i ograniczenia:** Możliwe opłaty, wymagania i data obowiązywania zmiany wynikają z umowy oraz procesu ING; nie są automatycznie pobierane z banku.


## 10. Konwencja roku i zaokrąglenia

**Status:** Wdrożone jako jawne ustawienia; właściwy wybór zależy od umowy.

**Lokalizacja implementacji:**

- [src/models.py — DayCount](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:15)
- [src/calculator.py — calculate_daily_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:63)
- [src/calculator.py — money](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:25)
- [app.py — wybór konwencji odsetek](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:166)

**Wprowadzone zmiany:** Dodano ACT/ACT z mianownikiem 365 lub 366 dla odpowiedniego fragmentu roku oraz ACT/365 ze stałym mianownikiem. Przejście między latami dzieli naliczanie. Kwoty rozliczenia zaokrąglane są do groszy metodą `ROUND_HALF_UP`; granice dni opisano jako `[początek, koniec)`.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_leap_year_conventions_and_cross_year_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:161)
- [tests/test_calculator.py — test_mid_period_overpayment_reduces_current_period_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:257)

**Zakres i ograniczenia:** Sam wybór `Decimal` nie dowodzi zgodności z bankiem. Mianownik, granice dni i moment zaokrąglenia muszą zostać porównane z dokumentami kredytu.


## 11. Zmiany oprocentowania i okresowo stała stopa

**Status:** Wdrożone jako scenariusze użytkownika, nie prognozy.

**Lokalizacja implementacji:**

- [src/models.py — RateChange](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:52)
- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)
- [src/scenarios.py — build_rate_changes](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:102)
- [src/calculator.py — rate_on](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:91)
- [src/calculator.py — period_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:99)
- [src/calculator.py — _reprice_settlement](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:174)
- [src/calculator.py — dates_after_fixed](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:511)
- [app.py — tabela zmian stóp](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:202)
- [app.py — koniec obecnego okresu stałego](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:189)

**Wprowadzone zmiany:** Datowane stopy są parsowane bez dzielenia przez float. Model odrzuca zmiany przed końcem zadeklarowanego okresu stałego i powielone daty zmian. Odsetki uwzględniają rzeczywisty dzień wejścia nowej stopy. Pierwsza rata obejmująca nową stopę jest przeliczana na podstawie naliczonych odsetek. Po ostatniej zmianie utrzymywana jest ostatnia stopa, a wyjście poza okres stały jest sygnalizowane.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_rate_change_splits_daily_interest_at_effective_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:144)
- [tests/test_audit_regressions.py — test_fixed_period_rejects_early_changes_and_warns_about_future](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:244)
- [tests/test_audit_regressions.py — test_upward_rate_change_reprices_payment_without_negative_principal](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:308)
- [tests/test_app.py — test_rate_editor_applies_change_and_invalid_rate_is_reported](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:95)

**Zakres i ograniczenia:** Domyślna propozycja daty to pięć lat od daty stanu. Dla istniejącego kredytu trzeba wpisać rzeczywisty koniec obecnego okresu stałego. Brak przyszłych stóp nie oznacza ich przewidzenia.


## 12. Data umowna i data pobrania raty

**Status:** Wdrożone oddzielnie; wpływ księgowania na odsetki ING do uzgodnienia.

**Lokalizacja implementacji:**

- [src/calculator.py — collection_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:212)
- [src/calculator.py — _easter](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:161)
- [src/models.py — InstallmentDetails](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:178)
- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)
- [app.py — włączenie kalendarza pobrania](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:178)

**Wprowadzone zmiany:** Harmonogram ma osobne pola `payment_date` i `collection_date`. Opcjonalny kalendarz uwzględnia niedziele, polskie święta stałe i ruchome oraz Wigilię od 2025 r. Sama sobota nie przesuwa terminu. Po niedzieli lub święcie szukany jest dzień roboczy. API pozwala dopisać `additional_holidays`.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_collection_calendar_does_not_move_interest_dates](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:232)
- [tests/test_audit_regressions.py — test_payment_dates_handle_same_month_first_payment_and_month_end](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:225)

**Zakres i ograniczenia:** Zmiana daty pobrania celowo nie przesuwa w tym modelu okresu odsetkowego. To jawna konwencja, nie potwierdzone odtworzenie księgowania konkretnej umowy.


## 13. Stan istniejącego kredytu na konkretny dzień

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)
- [src/calculator.py — payment_dates](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:41)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [app.py — data stanu kapitału](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:126)
- [app.py — najbliższa rata](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:133)
- [app.py — wcześniej naliczone odsetki](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:140)
- [app.py — aktualna rata bankowa](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:150)

**Wprowadzone zmiany:** Zamiast narzuconego `date.today()` użytkownik wybiera datę stanu. Może podać dokładną pierwszą ratę, wcześniej naliczone odsetki i aktualną ratę bankową. Bez jawnej pierwszej daty wybierany jest najbliższy przyszły termin, również w tym samym miesiącu. Przy dniach 29–31 krótszy miesiąc jest obsługiwany bez utraty pierwotnego dnia na przyszłość.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_start_date_payment_is_applied_and_prior_interest_is_not_lost](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:83)
- [tests/test_audit_regressions.py — test_payment_dates_handle_same_month_first_payment_and_month_end](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:225)
- [tests/test_app.py — test_invalid_first_payment_is_reported_without_traceback](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:56)

**Zakres i ograniczenia:** Wpisywane wcześniejsze odsetki dotyczą czasu przed datą stanu. Odsetki od tej daty silnik nalicza sam; trzeba uniknąć podwójnego ujęcia tej samej kwoty.


## 14. Nieregularne nadpłaty z indywidualnymi datami

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [src/scenarios.py — build_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:40)
- [src/scenarios.py — date_input](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:31)
- [src/scenarios.py — decimal_input](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:17)
- [app.py — edytowalna lista nadpłat](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:253)

**Wprowadzone zmiany:** Dodano tryb nieregularny z wieloma wierszami. Każdy wiersz zawiera własną datę, kwotę, strategię i ewentualny podział Mixed. Konstruktor scenariusza parsuje daty ISO i kwoty dziesiętne, a silnik nadaje zdarzeniom kolejność według dat.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_scenario_builders_parse_decimal_percent_and_irregular_rows](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:262)
- [tests/test_app.py — test_irregular_editor_adds_two_dated_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:75)

**Zakres i ograniczenia:** Nieregularne wpłaty są osobnym trybem formularza. Test edytora wprowadza dwie różne kwoty i sprawdza ich łączną sumę w harmonogramie.


## 15. Bezpieczne zależności między polami formularza

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [app.py — inicjalizacja i ograniczanie numeru raty](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:79)
- [app.py — komunikat dla zerowych nadpłat](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:121)
- [app.py — obsługa błędów wejścia](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:335)
- [src/scenarios.py — build_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:40)

**Wprowadzone zmiany:** Domyślny numer raty jest ograniczony do długości kredytu i ponownie ograniczany po skróceniu okresu. Suma Mixed 0 + 0 tworzy pustą listę wpłat, zamiast niepoprawnego obiektu nadpłaty. Błędy budowy i obliczeń scenariusza są prezentowane przez `st.error`, po czym `st.stop` zatrzymuje renderowanie wyniku.

**Weryfikacja i lokalizacja testów:**

- [tests/test_app.py — test_short_term_single_overpayment_does_not_crash](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:32)
- [tests/test_app.py — test_zero_mixed_means_no_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:45)
- [tests/test_app.py — test_invalid_first_payment_is_reported_without_traceback](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:56)

**Zakres i ograniczenia:** Model nadal wymaga dodatniej kwoty pojedynczego obiektu `Overpayment`; interpretacja zera jako braku wpłaty jest odpowiedzialnością konstruktora scenariusza.


## 16. Walidacja danych finansowych i dat

**Status:** Wdrożone dla wejść obsługiwanych przez model.

**Lokalizacja implementacji:**

- [src/models.py — validate_money](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:30)
- [src/models.py — validate_rate](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:41)
- [src/models.py — validate_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:46)
- [src/models.py — Overpayment](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:78)
- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — calculate_simulation_summary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:449)
- [src/scenarios.py — decimal_input](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:17)

**Wprowadzone zmiany:** Dodano sprawdzanie skończonych wartości Decimal, groszy, znaków kwot, zakresów stóp, całkowitej liczby rat i dat. Ujemne części Mixed oraz niespójne sumy są odrzucane. Nadpłaty poza pierwotnym zakresem symulacji powodują błąd. Wpłaty ponad saldo lub po wcześniejszej spłacie w tym zakresie są wykazywane jako niewykorzystane.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_invalid_principal_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:53)
- [tests/test_audit_regressions.py — test_invalid_rate_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:59)
- [tests/test_audit_regressions.py — test_invalid_term_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:65)
- [tests/test_audit_regressions.py — test_negative_mixed_allocation_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:70)
- [tests/test_audit_regressions.py — test_out_of_range_overpayment_is_not_silently_dropped](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:78)
- [tests/test_audit_regressions.py — test_oversized_same_day_mixed_payment_is_capped_and_order_independent](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:93)

**Zakres i ograniczenia:** Komunikat o niewykorzystanych planowanych kwotach jest częścią podsumowania. Pełna obsługa wszystkich możliwych typów zewnętrznych danych nie jest deklaracją tego modelu.


## 17. Krok zmiany kwoty kapitału

**Status:** Wdrożone; minimum dostosowano do istniejącego kredytu.

**Lokalizacja implementacji:**

- [app.py — pole pozostałego kapitału](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:41)
- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)

**Wprowadzone zmiany:** Pole kapitału ma `step=1000.0` i wartość domyślną 300 000 zł. Minimum wynosi 0,01 zł, aby można było odtworzyć końcówkę już spłacanego kredytu. Model dopuszcza dodatnią kwotę z dokładnością do groszy.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_invalid_principal_is_rejected](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:53)

**Zakres i ograniczenia:** Zmiana minimum z user stories (1000 zł) jest celowym odstępstwem opisanym w README. Sam krok widgetu sprawdzono w deklaracji pola; nie ma osobnego testu automatycznego kliknięć przycisku zwiększania.


## 18. Rozdzielenie kapitału, kosztów i kwoty do zapłaty

**Status:** Wdrożone jako model przyszłych kosztów podawanych przez użytkownika.

**Lokalizacja implementacji:**

- [src/models.py — LoanParameters](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:104)
- [src/models.py — SimulationSummary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:194)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — calculate_simulation_summary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:449)
- [app.py — koszt jednorazowy](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:273)
- [app.py — koszt przy płatności](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:279)
- [app.py — składka zależna od salda](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:286)
- [app.py — metryki finansowe](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:339)

**Wprowadzone zmiany:** Podsumowanie rozdziela kapitał, odsetki, koszt poza kapitałem i całą przyszłą kwotę do zapłaty. Dodano koszt jednorazowy, stały koszt przy każdej płatności oraz składkę od salda początkowego okresu według stawki rocznej / 12. Usunięto mylące nazywanie sumy kapitału i odsetek całkowitym kosztem kredytu.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_costs_are_separate_from_principal_and_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:252)
- [tests/test_app.py — test_dashboard_labels_describe_future_payments_and_end_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:66)

**Zakres i ograniczenia:** To nie jest automatyczna taryfa ING. Koszty już poniesione nie są doliczane, a oszczędności odsetkowe pozostają oddzielne od oszczędności innych kosztów.


## 19. Rzeczywista liczba płatności i data końca

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [app.py — liczba pozycji z harmonogramu](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:346)
- [app.py — data ostatniego rozliczenia](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:348)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)
- [src/calculator.py — calculate_simulation_summary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:449)

**Wprowadzone zmiany:** Liczba pozostałych płatności pochodzi z długości wygenerowanego harmonogramu. Data końca pochodzi z ostatniej pozycji, a przy pełnej nadpłacie między ratami jest to dzień nadpłaty. `months_saved` oznacza różnicę liczby pozycji obu harmonogramów; nie służy już do sztucznego wyliczania liczby płatności przez odejmowanie od pierwotnej wartości pola.

**Weryfikacja i lokalizacja testów:**

- [tests/test_calculator.py — test_mid_period_full_principal_repayment_stops_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py:284)
- [tests/test_app.py — test_dashboard_labels_describe_future_payments_and_end_date](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:66)

**Zakres i ograniczenia:** Liczba płatności nie oznacza liczby pełnych miesięcy kalendarzowych, szczególnie przy końcowym rozliczeniu pomiędzy ratami.


## 20. Wykres dat i saldo początkowe

**Status:** Wdrożone; agregacja salda pozostaje jawna.

**Lokalizacja implementacji:**

- [app.py — budowa serii dat i salda początkowego](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:371)
- [app.py — wykres kapitału](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:380)
- [app.py — tabele porównawcze i eksport CSV](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:390)

**Wprowadzone zmiany:** Każda seria zaczyna się od daty stanu i kwoty początkowej, a dalsze punkty używają dat harmonogramu zamiast indeksów od zera. Serie są łączone po datach; po spłacie saldo pozostaje zerowe. Przy powtórzonej dacie zachowywany jest ostatni stan. Tabele mają polskie opisy, a eksport CSV zachowuje dziesiętne wartości źródłowe.

**Weryfikacja i lokalizacja testów:**

- [tests/test_ui_dashboard.py — test_dashboard_single_overpayment_and_chart](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_ui_dashboard.py:29)

**Zakres i ograniczenia:** E2E sprawdza obecność sekcji wykresu i eksportu, nie każdy punkt serii. Oś i saldo początkowe zweryfikowano w kodzie. Wykres agreguje saldo przy ratach, a nie przy każdej nadpłacie między nimi.


## 21. Rozdzielone przebiegi testów i wyniki weryfikacji

**Status:** Wdrożone. Ostatnio potwierdzony pełny przebieg obejmował 72 zaliczone przypadki.

**Lokalizacja implementacji:**

- [tests/test_calculator.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py)
- [tests/test_audit_regressions.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py)
- [tests/test_app.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py)
- [tests/test_ui_dashboard.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_ui_dashboard.py)
- [tests/conftest.py — pytest_collection_modifyitems](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/conftest.py:17)
- [pyproject.toml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/pyproject.toml)

**Wprowadzone zmiany:** Zwykły `pytest` uruchamia testy obliczeń, danych i AppTest oraz pomija oznaczone testy E2E. `--run-e2e` włącza Playwright dla działającego serwera. Oddzielny marker pozwala wybrać odpowiedni przebieg w CI. W poprzedniej pełnej weryfikacji zaliczono 70 przypadków bez przeglądarki i 2 przeglądarkowe; przeszły również Ruff, formatowanie i MyPy.

**Weryfikacja i lokalizacja testów:**

- [tests/conftest.py — pytest_addoption](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/conftest.py:6)
- [.github/workflows/ci.yml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/.github/workflows/ci.yml)

**Zakres i ograniczenia:** Ta aktualizacja dokumentacji nie uruchamia testów ponownie. Lokalny pełny raport jest zapisywany przez pytest w `test-results/all.xml`; bieżący wynik po dalszych zmianach wymaga nowego wykonania.


## 22. Niezależne oczekiwania finansowe i uzgodnienie przepływów

**Status:** Wdrożone; testy finansowe nie zastępują przypadku referencyjnego ING.

**Lokalizacja implementacji:**

- [tests/test_audit_regressions.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py)
- [tests/test_calculator.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_calculator.py)
- [src/calculator.py — generate_amortization_schedule](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:296)

**Wprowadzone zmiany:** Dodano oczekiwane kwoty dla nadpłat w środku okresu, lat przestępnych i zmian stóp. Wzór raty kalendarzowej jest porównywany z niezależnym rachunkiem dyskontowym przez `Fraction`. Dla harmonogramów 420 rat, trzech poziomów stóp i strategii sprawdzane są nieujemne kwoty, sumy kapitału, przepływy oraz saldo zero. Te same podstawowe uzgodnienia są wykonywane także przez silnik.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_calendar_annuity_matches_independent_discount_factors](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:174)
- [tests/test_audit_regressions.py — test_long_schedule_reconciles_capital_interest_and_cash](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:197)
- [tests/test_audit_regressions.py — test_upward_rate_change_reprices_payment_without_negative_principal](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:308)

**Zakres i ograniczenia:** Nie wszystkie możliwe kombinacje dat i parametrów są objęte testami. Dodatkowa wcześniejsza próba 144 kombinacji była sprawdzeniem roboczym, nie nowym plikiem testów w repozytorium.


## 23. Testy wartości w formularzu i przeglądarce

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [tests/test_app.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py)
- [tests/test_ui_dashboard.py — DashboardPage](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_ui_dashboard.py:9)
- [tests/test_ui_dashboard.py — test_dashboard_single_overpayment_and_chart](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_ui_dashboard.py:29)
- [tests/test_ui_dashboard.py — test_dashboard_short_term_does_not_crash](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_ui_dashboard.py:54)
- [tests/conftest.py — app_url](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/conftest.py:27)

**Wprowadzone zmiany:** Testy AppTest korzystają z kluczy widgetów zamiast zależeć od kolejności pól. Sprawdzają kwoty i terminy, zerowy Mixed, walidację pierwszej daty i edytowalne tabele. Playwright sprawdza m.in. wyświetloną sumę nadpłat 1000 zł, krótki okres oraz dostępność eksportu. Adres aplikacji pochodzi z `--app-url` lub `APP_URL`.

**Weryfikacja i lokalizacja testów:**

- [tests/test_app.py — test_overpayment_occurs_only_in_selected_month](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:17)
- [tests/test_app.py — test_irregular_editor_adds_two_dated_overpayments](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:75)
- [tests/test_app.py — test_rate_editor_applies_change_and_invalid_rate_is_reported](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:95)
- [tests/test_app.py — test_term_editor_updates_accelerated_scenario_only](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_app.py:120)

**Zakres i ograniczenia:** Test przeglądarkowy czeka na wynik liczbowy jako potwierdzenie wykonania skryptu. Raporty, ślady niepowodzeń i zrzuty są zapisywane przez polecenia CI; nie są dowodem zgodności z bankowym harmonogramem.


## 24. Podział odpowiedzialności i precyzja wejścia

**Status:** Wdrożone.

**Lokalizacja implementacji:**

- [src/scenarios.py](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py)
- [src/scenarios.py — percent_input](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/scenarios.py:27)
- [src/calculator.py — annuity_payment](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:121)
- [src/calculator.py — period_interest](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/calculator.py:99)
- [src/models.py — SimulationSummary](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/src/models.py:194)
- [app.py — ograniczony cache funkcji run_simulation](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/app.py:293)

**Wprowadzone zmiany:** Budowę nadpłat, zmian stóp i dyspozycji przeniesiono do czystego modułu scenariuszy. Wspólne funkcje obsługują raty, odsetki i zaokrąglenia. Harmonogramy w modelu mają typ `list[InstallmentDetails]`, zamiast `List[Any]`. Procent jest przeliczany przez `Decimal` / `Decimal("100")`. Cache formularza otrzymuje parametry i gotową listę nadpłat oraz ma ograniczenie liczby wpisów i czasu.

**Weryfikacja i lokalizacja testów:**

- [tests/test_audit_regressions.py — test_scenario_builders_parse_decimal_percent_and_irregular_rows](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/tests/test_audit_regressions.py:262)
- [pyproject.toml — konfiguracja MyPy](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/pyproject.toml)

**Zakres i ograniczenia:** Konwersja do float pozostaje w warstwie prezentacji tabel i wykresu; źródłem obliczeń finansowych i CSV są wartości Decimal. Wiersze edytorów są walidowane po przekształceniu do danych domenowych.


## 25. Dokumentacja, zależności i kontrole CI

**Status:** Wdrożone w plikach projektu; wykonanie zdalnego GitHub Actions wymaga uruchomienia workflow.

**Lokalizacja implementacji:**

- [README.md](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/README.md)
- [requirements.txt](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/requirements.txt)
- [requirements.lock.txt](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/requirements.lock.txt)
- [pyproject.toml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/pyproject.toml)
- [.github/workflows/ci.yml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/.github/workflows/ci.yml)
- [.gitignore](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/.gitignore)
- [.gitattributes](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/.gitattributes)

**Wprowadzone zmiany:** README opisuje aktualne możliwości i ograniczenia zamiast gwarancji bankowej dokładności. Przypięto zależności bezpośrednie i zapisano wersje testowanego środowiska w locku. Dodano konfiguracje Ruff, MyPy i pytest. CI kontroluje kod aplikacji i testy, uruchamia AppTest, czeka na endpoint zdrowia Streamlit, wykonuje E2E i zapisuje rzeczywiste raporty JUnit. Dodano pomijanie środowisk i raportów oraz reguły końców linii.

**Weryfikacja i lokalizacja testów:**

- [.github/workflows/ci.yml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/.github/workflows/ci.yml)
- [pyproject.toml](/Users/kasjankarpinski/Desktop/Python/loan-overpayment-calculator/pyproject.toml)

**Zakres i ograniczenia:** Workflow nie deklaruje generowania raportu coverage. Lock odtwarza testowane wersje, ale instalacja na innym systemie lub Pythonie wymaga dostępnych zgodnych pakietów. Lokalne przejście kontroli nie jest informacją o wykonaniu zdalnego CI.


## Warunek zamknięcia zgodności z ING

Pozostaje uzgodnienie na danych użytkownika: zanonimizowana umowa określająca konwencję roku, granice dni, zaokrąglenia, kolejność księgowania i opłaty; stan kredytu na konkretną datę; harmonogram przed nadpłatą i po niej oraz po zmianie okresu. Należy porównać kapitał, odsetki, ratę, datę końca i wyjaśnić wszystkie różnice groszowe. Publiczne informacje banku i przejście testów programu nie wystarczają do potwierdzenia zgodności z konkretną umową.

Dokumentowane założenia obejmują m.in. kolejność rata–nadpłata w dniu raty, rozliczenie pełnej spłaty z odsetkami w dniu nadpłaty, przeliczenie pierwszej raty obejmującej nową stopę i oddzielenie pobrania od umownego naliczania odsetek. Do czasu porównania z bankiem są to konwencje symulacji.

## Weryfikacja po dodaniu modelu ING

2 listopada 2026: 103 testy backendu i AppTest oraz 3 testy przeglądarkowe Chromium przeszły. Ruff, formatowanie, MyPy i kontrola białych znaków również przeszły. Automatyczne kontrole GitHub Actions rozszerzono o gałąź `stage`. Odbiór na indywidualnym harmonogramie ING i merge do `main` pozostają otwarte.

## Aktualizacja: kapitał a saldo łączne ING

`src/scenarios.py` — `principal_from_balance`: walidacja salda i odsetek, wydzielenie dodatniego kapitału z kwoty łącznej. `app.py` — wybór „Sam kapitał” / „Łączne saldo”, wyjaśnienie daty i zakresu odsetek oraz podgląd kapitału przyjmowanego do obliczeń. `tests/test_ing.py` — zgodność rozliczenia potwierdzonego przypadku ING i odrzucenie nieprawidłowego podziału. `tests/test_app.py` — identyczny harmonogram dla równoważnego wpisania kapitału i salda łącznego, błąd dla odsetek równych saldu. Potwierdzenie dotyczy rozliczenia istniejącej raty podanej z banku, a nie jej samodzielnego wyznaczenia.
