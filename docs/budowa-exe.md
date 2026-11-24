# Budowa paczki Neto Incident Monitor na Windows

Do budowy użyj czystego checkoutu wybranego commitu, CPythona 3.12.6 x64, Git i PowerShell. Plik `requirements-build.txt` przypina pakiety wraz z sumami kontrolnymi kół Windows, a `scripts/build-inputs.json` opisuje oczekiwaną wersję Pythona, parametry analityki oraz Chromium i FFmpeg. [Wymagania](../requirements-build.txt) · [Manifest wejść](../scripts/build-inputs.json)

## Przygotowanie parametrów analityki

Uzyskaj plik JSON zgodny z rewizją i SHA-256 w manifeście. Przechowuj go w katalogu wejść z dostępem odpowiednim dla zatwierdzonych definicji instancji. Z tego samego zatwierdzonego arkusza osoba uprawniona może odtworzyć plik na osobnej ścieżce. Polecenie sprawdza 27 definicji, eksportuje osiem pól technicznych i wypisuje sumę kontrolną pliku. Katalog wyniku musi istnieć. [Importer](../tools/import_dashboard_api.py)

```powershell
py -3.12 -m tools.import_dashboard_api 'C:\wejscia\zatwierdzony-arkusz.xlsx' `
  --package-parameters --output 'C:\wejscia\dashboard-api.json'
```

Pliki wejściowe paczki pozostają osobne od lokalnego pliku użytkownika `dashboard-api.json`. Świeży profil pobiera listy agentów i lokalizacji po logowaniu. Pakiet zachowuje pierwszeństwo lokalnych ustawień. [Kontrakt dashboardu](kontrakty/kontrakt-odczytu-dashboardu.md#pobieranie-agentów-i-lokalizacji)

## Budowa i sprawdzenie wyniku

```powershell
.\scripts\build_exe.ps1 -DashboardParameters 'C:\wejscia\dashboard-api.json' `
  -OutputDirectory '.\build\kandydat-1'
```

Skrypt tworzy własne środowisko Pythona, katalog binariów przeglądarki, pliki robocze i wynik. Domyślnie pozyskuje koła z PyPI i binaria poleceniem Playwright. W razie braku dostępu do tych usług możesz podać przechowywane kopie wejść. `-Wheelhouse` przyjmuje katalog kół, a `-BrowserCache` katalog zawierający pełne foldery odpowiednich rewizji Chromium i FFmpeg. Budowa sprawdza sumy kontrolne kół i drzew obu komponentów. `-Python` przyjmuje ścieżkę do interpretera, jeśli użycie `py -3.12` nie wybiera właściwego Pythona. [Skrypt](../scripts/build_exe.ps1) · [Weryfikacja wejść](../tools/package_inputs.py)

Otwórz `build-report.json` i sprawdź wynik, commit, pole `clean_checkout`, wersje, rewizje oraz SHA-256 ZIP-a. `package-files.json` zawiera wykaz plików paczki i ich SHA-256. Do odbioru utwórz drugi checkout tego samego commitu i użyj nowej ścieżki wyniku, a następnie porównaj oba raporty i wykazy. [Budowa i raport](../tools/build_package.py)

Rozpakuj każdy ZIP do osobnego katalogu i porównaj pliki z wykazem. Ustaw `LOCALAPPDATA` wyłącznie dla procesu testowego na pusty katalog próbny i uruchom rozpakowane EXE z argumentami `--smoke-test <ścieżka-do-raportu.json>`. Sprawdź kod zakończenia oraz pola `ok`, `frozen`, `dashboard_config`, `browser_from_bundle` i `browser_version`. Przy świeżym profilu pole `dashboard_scope_present` ma wartość `false`. Do drugiej próby w innym profilu przygotuj syntetyczne, poprawne listy i nieużywaną w rzeczywistym ruchu wartość zastępującą jeden parametr. Wynik ma potwierdzić listy oraz wymienić nadpisany klucz w `dashboard_local_overrides`. [Próba offline](../tools/package_smoke.py)

```powershell
$candidate = (Resolve-Path -LiteralPath '.\build\kandydat-1').Path
$unpacked = Join-Path $candidate 'unpacked'
$zip = Get-ChildItem -LiteralPath $candidate -Filter '*.zip' -File
Expand-Archive -LiteralPath $zip.FullName -DestinationPath $unpacked
$exe = Join-Path $unpacked 'Neto Incident Monitor\Neto Incident Monitor.exe'
$report = Join-Path $candidate 'smoke-fresh.json'
$profile = Join-Path $candidate 'profile-fresh'
New-Item -ItemType Directory -Path $profile | Out-Null
$previousLocalData = $env:LOCALAPPDATA
try {
    $env:LOCALAPPDATA = $profile
    $result = Start-Process -FilePath $exe -ArgumentList '--smoke-test', ('"{0}"' -f $report) `
        -WindowStyle Hidden -Wait -PassThru
    if ($result.ExitCode -ne 0) { throw 'Próba offline nie powiodła się.' }
} finally {
    $env:LOCALAPPDATA = $previousLocalData
}
Get-Content -Raw -LiteralPath $report
```

## Ponowienie i aktualizacja wejść

- Każdy przebieg otrzymuje nowy katalog wyniku. Gdy operacja zostanie przerwana lub narzędzie zgłosi błąd, odczytaj etap i kod przyczyny z raportu, uzupełnij wejście i użyj nowego katalogu. `dashboard_digest` oznacza inną wersję parametrów, a `browser_digest` inną zawartość folderu przeglądarki. Przy `tool_failed` sprawdź odpowiednie narzędzie dla wskazanego etapu, używając wyłącznie izolowanych wejść.
- Zmianę parametrów zacznij od zatwierdzonych definicji i porównania warunków z obecnym kontraktem. Wygeneruj nowy plik, zwiększ numer rewizji parametrów i wpisz jego SHA-256 do manifestu. Raport zmiany powinien opisać zakres pól i odbiór, czego dotyczy wersja oraz skąd osoba uprawniona uzyska wejście.
- Zmianę zestawu narzędzi zacznij w świeżym środowisku Windows x64. Pobierz dokładne wersje kół bez dystrybucji źródłowych, zapisz ich sumy i sprawdź `pip check`. Z metadanych przypiętego Playwright odczytaj rewizje Chromium i FFmpeg, zainstaluj je w izolowanym katalogu i wyznacz skróty przez `tools.package_inputs.browser_digest`. Po aktualizacji powtórz obie budowy i próby offline. Dla zmienionego Chromium zweryfikuj także scenariusze sesji wskazane w planie.
- Przy dodawaniu zasobu potrzebnego w EXE uwzględnij go na liście w specyfikacji PyInstallera. [Specyfikacja](<../scripts/Neto Incident Monitor.spec>)
