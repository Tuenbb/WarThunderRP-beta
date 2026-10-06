# WarThunderRPC

To repozytorium zawiera wersję beta z systemem raportowania dla testerów oraz powtarzalną instrukcją budowania pliku EXE na Windows. Zobacz [BETA_TESTING.md](BETA_TESTING.md), aby zapoznać się z wymaganiami, instrukcją budowania i uruchamiania, scenariuszami testowymi oraz zakresem danych zawartych w raporcie diagnostycznym.

Nazwy pojazdów i nacje są pobierane z publicznej strony War Thunder Wiki:
`https://wiki.warthunder.com/unit/<model-id>`.
Aplikacja odczytuje tytuł strony oraz pole **Research country** z karty pojazdu. Nie próbuje określać nacji na podstawie ID pojazdu ani jego typu. Tylko rozpoznane identyfikatory państw otrzymują flagę. Jeśli strona lub pole z państwem jest niedostępne, aplikacja zachowuje nazwę zapasową i nie dodaje nowo ustalonej flagi.

Zapytania są wykonywane wyłącznie przez HTTPS do `wiki.warthunder.com`, z limitem czasu wynoszącym pięć sekund i limitem rozmiaru strony 2 MiB. Lokalny cache znajduje się w:
`%APPDATA%/WarThunderRS/vehicle_names.json`
i jest ograniczony do 1000 wpisów oraz 1 MiB. Istniejące wpisy cache zawierające tylko nazwę nadal mogą być odczytywane i zostaną uzupełnione o dane dotyczące nacji po pomyślnym zapytaniu do Wiki. Aplikacja nie pobiera zdalnych obrazów ani skryptów stron. Skrypty ze stron Wiki nigdy nie są wykonywane.

Klasy pojazdów są rozpoznawane na podstawie znanych lokalnych wartości API `army` oraz dokładnych segmentów kategorii pojazdów: `ground`, `aircraft`, `helicopters`, `ships` i `boats`. Nieznane wartości nie są zgadywane. ID modeli bez kategorii nadal otrzymują czytelną nazwę oraz ograniczony adres URL obrazu Wiki wynikający z ID. Jeśli API nie udostępnia ID modelu, aplikacja podaje znaną klasę, ale nie wymyśla obrazu pojazdu.

Dla nacji posiadających lokalny obraz flagi klucz małego obrazka Discorda jest tworzony na podstawie standardowej nazwy pliku, np. `country_israel` dla `country_israel.png`. Publiczna wersja źródłowa celowo nie zawiera żadnych plików graficznych. Discord wymaga, aby takie klucze były zarejestrowane w panelu zasobów Rich Presence aplikacji. Rozpoznane nacje nadal zachowują tekstową nazwę flagi, nawet jeśli lokalna grafika nie jest dostępna.

Stan bitwy nadal może zostać rozpoznany, gdy `/indicators` zwraca nieprawidłowe lub niedostępne dane pojazdu, pod warunkiem że `/map_info.json` jest prawidłowy, a `/mission.json` zawiera aktywny główny cel. W takim przypadku aplikacja pokazuje bitwę i mapę, ale oznacza dane pojazdu jako niedostępne. Obecne odpowiedzi lokalnego API nie udostępniają w takiej sytuacji nazwy ani klasy okrętu.

Aby sprawdzić, czy obecne lokalne API oferuje dodatkowe informacje o mapie lub pojeździe gracza, uruchom podczas bitwy:

```powershell
python probe_battle_metadata.py
```

Program odczytuje wyłącznie `/map_info.json`, `/mission.json` i `/map_obj.json`. Wynik jest ograniczony, a dynamiczne identyfikatory i niepowiązane wartości tekstowe są ukrywane. Wyświetlane są jedynie ograniczone wartości `status` oraz `text` celów z `/mission.json`, zabezpieczone przed niebezpiecznymi znakami terminala, a także bezpieczne informacje o błędach endpointów.

`/map_obj.json` jest odczytywany jako tablica JSON, a nie wymagany obiekt. Program podsumowuje typy obiektów oraz jawne pola logiczne dotyczące gracza we wszystkich rekordach, jednocześnie ograniczając ilość wyświetlanych danych.

Aby sprawdzić skróconą strukturę oraz możliwe informacje o mapie z lokalnego API, uruchom:

```powershell
python -B probe_map.py
```

Program odpyta tylko `/state`, `/map_info.json`, `/map_obj.json` i `/indicators`, w tej kolejności, oraz będzie kontynuował działanie nawet po błędzie któregoś endpointu. Dla odpowiedzi będących obiektami wyświetlane są ograniczone podsumowania pól i typów na najwyższym poziomie.

Dla tablicy `/map_obj.json` wyświetlane są maksymalnie trzy rekordy wraz z ograniczonymi nazwami pól i przykładowym JSON-em. Każdy endpoint sprawdza występowanie dokładnych kluczy skalarnych:
`map_id`, `name`, `map_name`, `location`, `level` oraz `zone_id`.

Zapytania korzystają z zabezpieczonego klienta localhost z limitem czasu dwóch sekund, wyłączonymi proxy, zablokowanymi przekierowaniami oraz limitem odpowiedzi wynoszącym 1 MB.

Aby sprawdzić aktualny stan oraz planowane dane obrazów Rich Presence bez łączenia się z Discordem ani wykonywania zapytań do Wiki, uruchom:

```powershell
python -B probe_presence.py
```

Program odczytuje wyłącznie dozwolone lokalne endpointy gry oraz lokalny cache nazw pojazdów. Host URL pojazdu ani nazwa lokalnego pliku graficznego nie gwarantują, że Discord go zaakceptuje. Klucze obrazów muszą również być zarejestrowane w zasobach Rich Presence aplikacji Discord.

Program informuje, czy `details` i `state` są faktycznie obecne w wybranym profilu, bez wyświetlania ich skonfigurowanej treści. Sprawdza również dostępność wartości szablonów pojazdu/prędkości, planowane źródła dużego i małego obrazka oraz kolejność stosowania obrazów zastępczych. Nie nawiązuje połączenia Discord RPC ani nie wykonuje zapytań do Wiki.

Discord odrzuca puste pole `state`. Gdy druga linia jest wyłączona lub jej wynik jest pusty, a jednocześnie wysyłany jest co najmniej jeden obraz, aplikacja używa pojedynczego znaku Braille typu „blank” (`U+2800`) jako wartości protokołu. Dzięki temu linia powinna pozostać wizualnie pusta, a Discord zaakceptuje niepusty `state`. Gdy nie ma żadnych obrazów, pole `state` jest pomijane.

Sprawdź działanie w Discordzie przy ustawieniu:

**Hangar → druga linia: Wyłączona**

Jeśli Discord odrzuci niektóre proponowane obrazy, ale zaakceptuje obraz zastępczy, status RPC w GUI pokaże, czy zachowano obraz pojazdu, flagę, oba obrazy czy żaden z nich.

Nazwy map pochodzące z jawnych pól `map_info` lub tytułów mapy w misji mają najwyższy priorytet. Obecny `/map_info.json` zawiera wyłącznie parametry siatki mapy i nie posiada jej nazwy. Tekst celu misji nie jest traktowany jako nazwa mapy.

Potwierdzony fingerprint `0000002c7ebdffff` jest zawarty jako rozwiązanie zastępcze dla:
`[Dominacja #1] Kvarken Południowy`

Nie zastępuje on automatycznego odczytu metadanych ani kompletnego katalogu map. `/map_obj.json` był niedostępny podczas ostatniego testu działającego wyłącznie na obiektach. Test obsługujący tablice znalazł znaczniki mapy/spawnu, ale nie znalazł jednoznacznego pola łączącego gracza z konkretnym pojazdem.

## Rejestrowanie nazw map

Aplikacja ustala nazwę mapy w następującej kolejności:

1. wiarygodna nazwa z lokalnych metadanych API,
2. rejestr fingerprintów użytkownika,
3. znajdujący się w repozytorium zapasowy `map_catalog.json`.

Aby zarejestrować potwierdzoną nazwę mapy, gdy jest ona aktualnie aktywna, użyj:

```powershell
python register_map.py "[Dominacja #1] Kvarken Południowy"
```

Polecenie odczytuje wyłącznie aktualny fingerprint z lokalnego API `/map.img` i zapisuje potwierdzoną nazwę do:

`%APPDATA%\WarThunderRS\map_names.json`

Nie modyfikuje plików gry ani znajdującego się w repozytorium katalogu. Rejestr jest aktualizowany atomowo i ograniczony do 1000 wpisów oraz 256 KiB.

Jeżeli nazwa mapy nie zaktualizuje się od razu, uruchom ponownie aplikację lub odśwież jej stan.

Opcjonalny katalog `.bin` może zostać podany w celu sprawdzenia potencjalnych identyfikatorów poziomów:

```powershell
python register_map.py "Potwierdzona nazwa mapy" --levels-dir "Z:\path\to\War Thunder\levels"
```

Ścieżka do katalogu nigdy nie jest zgadywana ani wpisywana na sztywno. Program wyświetla wyłącznie nazwy plików `.bin`, a ich nazwy bazowe są wyraźnie oznaczone jako niepotwierdzone kandydatury.

Aby zapisać adnotację dotyczącą ID poziomu, użyj:

```powershell
--level-id "candidate_stem"
```

po samodzielnym sprawdzeniu tego ID. Adnotacja nie wpływa na rozpoznawanie nazwy mapy i nie jest przedstawiana jako identyfikator potwierdzony przez API.

Uruchom aplikację za pomocą:

```powershell
python main.py
```

## Dostosowywanie Rich Presence

W uruchomionej aplikacji wybierz **Ustawienia Rich Presence…**, aby skonfigurować pierwszą i drugą linię dla każdego stanu.

Własna druga linia obsługuje:

`{vehicle}`, `{speed}`, `{ias}`, `{tas}` oraz `{kills}`.

Wartości prędkości, IAS i TAS pochodzą z `/state`, udostępnianego przez lokalne API gry. `{speed}` preferuje IAS, a jeśli IAS nie jest dostępne, korzysta z TAS.

Całe opcjonalne wyrażenie można umieścić w nawiasach kwadratowych, np.:

```text
[{vehicle} — IAS {ias}]
```

Wtedy całe wyrażenie zniknie, jeśli jedna z jego wartości będzie niedostępna.

Obecne dane API sprawdzane przez aplikację nie udostępniają potwierdzonego pola z liczbą zabójstw w meczu, dlatego `{kills}` pozostaje na razie puste.

Aby sprawdzić bezpieczne pola lokalnego API podczas lotu lub bitwy, uruchom:

```powershell
python -B probe_vehicle_state.py
```

Program odczytuje wyłącznie `/indicators` i `/state`, wyświetla znane pola prędkości oraz ograniczony zestaw ścieżek skalarnych, których nazwy zawierają `kill`, `frag` lub `score`. Nie wyświetla pełnej odpowiedzi API.

Zaobserwowane potencjalne pole musi zostać dodatkowo potwierdzone, zanim będzie można traktować je jako licznik zabójstw.

Użyj **Zakończ aplikację** w głównym oknie, aby zatrzymać poller i ikonę w zasobniku systemowym, wyczyścić Discord Rich Presence oraz zamknąć aplikację.

Samo zamknięcie okna powoduje natomiast dalsze działanie aplikacji w zasobniku systemowym.
