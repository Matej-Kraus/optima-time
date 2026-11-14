# Zpráva z Milníku 5 – zabalení a příprava ostrého testu

Stav k 14. 11. 2026. Windows balíček jde sestavit jen na Windows (PyInstaller neumí sestavovat pro jiný systém). Stejný spec jsem sestavil a ověřil na macOS. Sestavení na Windows a stínový provoz jsou ruční testy M5-A a M5-B.

## 1. Co je hotové

| Část | Soubor | Ověření |
|---|---|---|
| `--self-test`: modely, ONNX Runtime, OpenCV, skutečné přečtení `12:34` a `7`, zápis XML, složky aplikace, UI, NDI, zařízení | `selftest.py` | ze zdrojů i ze zabalené verze: vše OK |
| Ikona v oznamovací oblasti (Otevřít UI, Ukončit), bez konzole | `tray.py`, `packaging/launcher.py` | jen Windows (M5-A) |
| Spuštění dvojklikem: poslední profil, ikona, prohlížeč | `cli.py` (`settings.json`) | jen Windows (M5-A) |
| PyInstaller: jedna složka, `OptimaTime.exe` (bez konzole) + `optima-time.exe` (konzole) | `packaging/optima-time.spec` | macOS: sestavení za 27 s, 304 MB, self-test OK, běh nad záznamem OK |
| Sestavení na Windows: závislosti, modely, UI, testy, PyInstaller, self-test balíčku, ZIP | `scripts/build_windows.ps1` | M5-A |
| Stínový provoz: vzorkování XML stávající aplikace + porovnání s naším logem událostí | `tools/shadow` | test na umělých datech |
| Návod pro obsluhu | `docs/OPERATOR.md` | M4-A |
| Ruční testy s doporučeným pořadím | `docs/MANUAL_TESTS.md` | — |

Celkem 179 testů v Pythonu (+1 volitelný NDI), 12 ve frontendu. Ruff, pyright, oxlint a build jsou čisté.

## 2. Ověřeno na zabalené verzi (macOS)

- `optima-time --self-test` ze složky `build/dist/OptimaTime`: všech 9 kontrol OK. Modely i UI se načítají z `_internal`.
- `optima-time run` ze zabalené verze nad syntetickým zápasem: 25 fps, UI odpovídá, `/data/values.json` vrací správné hodnoty, kotvy fungují.

## 3. Zátěžový test (3 h)

Běží (začal 11:19, konec ~14:20). Výsledek doplním do `M3_REPORT.md`.

Průběžně: kolem 19. minuty (11:38) byl Mac na několik sekund úplně vytížený mým souběžným sestavováním (PyInstaller, celá sada testů, zabalená aplikace). Aplikace tehdy zahodila 225 snímků, jeden zápis XML trval 948 ms a latence vyskočila na 3,9 s. Před tím i po tom je p95 21–33 ms bez zahozených snímků. Aplikace se zotavila sama, žádné vlákno nespadlo. Plyne z toho jedno doporučení: **na produkčním PC nespouštět během přenosu nic náročného vedle vMixu.**

## 4. Co nejde udělat bez Matěje

| Co | Ruční test |
|---|---|
| Sestavení a instalace na Windows, ikona v liště, neuspání PC | M5-A |
| Stínový provoz při přenosu a porovnání | M5-B |
| Všechny dřívější ruční testy (vMix, NDI, výkon na produkčním PC, reálný záznam, nová hala) | viz pořadí v `MANUAL_TESTS.md` |

## 5. Akceptace MVP (SPEC 15.6): stav

| Kritérium | Stav |
|---|---|
| Čistý syntetický zápas: 0 špatně publikovaných hodnot, 100 % změn | **0 špatných**; 99,38–100 % změn po polích (jediná přeskočená hodnota je při přesunu trestu mezi sloty, viz M2) |
| Reálné záznamy: 0 špatných, ≥ 99 % změn, změna času v souboru do 100 ms (p95) | čeká na záznam; latence na Macu p95 19,5 ms |
| Výkonové cíle 14.4 a zátěžový test | Mac splněno (zátěžový test běží), produkční PC = M3-A |
| Reálný vMix čte soubor 30 minut bez chyby a probliknutí | M2-A |
| Po restartu je soubor do 3 s aktuální; po návratu zdroje čtení do 3 s | logika ověřená testy (start z hodnot v souboru, potvrzení ≤ 400 ms; reconnect s prodlevou 0,5–8 s); na reálném PC M5-A |
| Nová hala do 10 minut podle `OPERATOR.md` | integrační test postupu ✓; člověk = M4-A |
| Stínový provoz | M5-B |
