# Ruční testy

Testy, které nejde udělat bez reálného vMixu, NDI nebo produkčního PC.

## Doporučené pořadí

| # | Test | Čas | Co je potřeba |
|---|---|---|---|
| 1 | Fotky a kopie XML do `samples/` | 5 min | přístup k produkčnímu PC |
| 2 | M5-A instalace balíčku + self-test | 20 min | Windows PC |
| 3 | M0-B / M2-B vMix čte soubor a HTTP, zámky Windows | 30 min | vMix |
| 4 | M0-C / M3-A obraz z vMixu přes NDI, výkon vedle vMixu | 30 min | vMix + kamera na tabuli |
| 5 | M0-A rychlost PP-OCR na produkčním PC | 5 min | produkční PC |
| 6 | M4-A nová hala do 10 minut podle návodu | 15 min | hala, nebo záznam |
| 7 | Reálný záznam 10–15 min → `tools.labeler` → oprava → `tools.eval` | 1 h | zápas nebo trénink |
| 8 | M2-A 30 minut vMix + titulek | 40 min | vMix |
| 9 | M5-B stínový provoz | zápas | přenos |

Výsledky pošli, podle nich upravím, co je potřeba. Co není v tabulce, je ověřené automaticky (`uv run pytest`, `tools/eval`, `tools/bench`).

Ke každému testu níže: postup, co sledovat, co zapsat a poslat zpátky.

Názvy tlačítek ve vMixu se mezi verzemi mírně liší. Když něco vypadá jinak, zapiš, co vidíš. Postup pak opravím a dám do `OPERATOR.md`.

## Příprava na Windows PC (jednou)

1. Nainstaluj `uv`: v PowerShellu `winget install --id=astral-sh.uv -e`. Pak otevři nový terminál.
2. Zkopíruj repozitář na PC, třeba `C:\optima-time`. Stačí zip celé složky bez `.venv` a `node_modules`.
3. V PowerShellu ve složce repozitáře spusť:
   ```powershell
   uv sync --group spikes --group ndi
   uv run python spikes/ppocr/fetch_models.py
   ```

---

## M0-A: rychlost PP-OCR na produkčním PC (asi 5 minut)

**Proč:** Na Macu M1 trvá model tiny asi 9 ms na výřez. Pro rozhodnutí tiny/small a pro odhad zátěže vedle vMixu potřebuju čísla z PC, kde to poběží.

1. Pusť vMix s běžnou produkcí (preset `4Nations.vmix`), ať jsou čísla z reálné zátěže.
2. Spusť:
   ```powershell
   uv run python spikes/ppocr/ppocr_spike.py --synthetic 300 --min-width 320 160
   ```
3. Pošli zpátky: `spikes/ppocr/out/synthetic*_report.json`, model procesoru (Správce úloh → Výkon → CPU) a zhruba kolik % CPU bral vMix během testu.

Když budou v `samples/` fotky, pustí se pokus i nad nimi (`--samples samples/crops.json`, formát v `spikes/README.md`).

---

## M0-B: vMix čte XML ze souboru a z HTTP adresy (2 × 10 minut)

**Proč:** Ověřit, že vMix soubor, který se 10× za sekundu přepisuje, čte bez chyb a bez probliknutí prázdné hodnoty. Zjistit, jestli nové sloupce nerozbijí stávající mapování a jestli je lepší soubor, nebo HTTP adresa.

**Nepoužívej produkční titulky ani produkční XML soubor.** Udělej si kopii titulku, třeba `TEST tabule`.

### B1: soubor

1. Spusť zapisovač (soubor může být kdekoli, jen ne v síťové složce):
   ```powershell
   uv run python spikes/xml_writer/xml_writer_spike.py --path C:\vmix-data\optima_test.xml --minutes 10
   ```
2. Ve vMixu otevři **Data Sources** (Data Sources Manager) → **+** → **XML**.
   - Vyber soubor `C:\vmix-data\optima_test.xml`.
   - XPath: `/root`.
   - Interval obnovy (Auto refresh / Update every): **100 ms**, nebo nejnižší, co jde nastavit. **Zapiš minimum.**
3. Zkontroluj tabulku v Data Sources: **jaké sloupce vidíš a v jakém pořadí** (`Time`, `penaltya1`, …, `seq`)? Je tam jeden řádek?
4. V kopii titulku napoj pole na sloupce: `Time`, `penaltyh1`, `scoreh` a **`seq`** (to je pořadové číslo zápisu, podle něj se pozná zaseknutí).
5. Sleduj 10 minut:
   - Hlásí vMix chybu (např. „The process cannot access the file…")?
   - Problikne někdy prázdná hodnota u `Time` nebo `scoreh`? Tresty mají být prázdné každých 5 s záměrně.
   - Plynou `seq` a `Time` plynule, nebo se zasekávají nebo skáčou?
6. **Test párování podle názvu:** během běhu zastav zapisovač (Ctrl+C), smaž ze souboru ručně řádek `<penaltya2/>`, ulož a podívej se, jestli se mapování ostatních polí v titulku nerozhodilo. Pak zapisovač pusť znovu.
7. Pošli: výpis z konzole na konci (JSON) a `optima_test_report.json`, odpovědi k bodům 3, 5 a 6. Fotka nebo snímek obrazovky Data Sources pomůže.

### B2: HTTP adresa

1. Zapisovač zase běží (stejný příkaz). HTTP adresa je `http://127.0.0.1:8790/data/values.xml`.
2. Ve vMixu přidej druhý XML Data Source s **URL** místo souboru, XPath `/root`, interval 100 ms.
3. Napoj na něj druhou kopii titulku (nebo přepoj tu první) a sleduj stejné body jako v B1.
4. Napiš, která cesta působila plynuleji (soubor, nebo URL) a jestli si vMix u URL nedrží starou hodnotu (kešování).

### Co bude výsledek

Na základě B1 a B2 zvolím výchozí výstup (soubor, nebo HTTP) a zapíšu to do `DECISIONS.md`.

---

## M0-C: obraz z vMixu přes NDI (asi 15 minut)

**Proč:** Nástroj nemůže otevřít capture kartu, kterou drží vMix. Obraz kamery KOM BOX si proto musí vzít z vMixu. Potřebuju vědět, jak přesně a jestli chodí prokládaný, nebo progresivní obraz.

### C1: NDI z vMixu

1. Ve vMixu: **Settings → Outputs / NDI / SRT**.
   - Najdi možnost poslat **vstup KOM BOX** přes NDI. Buď nastav jeden z výstupů (Output 2/3/4) na vstup KOM BOX a zapni u něj NDI, nebo použij volbu NDI pro jednotlivé vstupy, pokud ji tvoje verze má.
   - **Zapiš, kterou cestou to šlo.**
2. Na stejném PC spusť výpis zdrojů:
   ```powershell
   uv run --group ndi python spikes/ndi/ndi_spike.py --list
   ```
   Zapiš přesný název zdroje (např. `PC (vMix - Output 2)`).
3. Spusť měření dvakrát, s půlsnímky a bez nich (doplň část názvu zdroje):
   ```powershell
   uv run --group ndi python spikes/ndi/ndi_spike.py --source "Output 2" --seconds 60
   uv run --group ndi python spikes/ndi/ndi_spike.py --source "Output 2" --seconds 60 --no-fields
   ```
   Ideálně při běžícím čase na tabuli, aby byl v obraze pohyb.
4. Pošli: oba JSON reporty a PNG snímky ze `spikes/ndi/out/`.

### C2: virtuální kamera vMixu (záložní cesta)

1. Ve vMixu zapni externí výstup (**External**) se zdrojem KOM BOX.
2. Spusť pro indexy 0, 1, 2, … (dokud nenajdeš obraz z vMixu):
   ```powershell
   uv run python spikes/ndi/ndi_spike.py --opencv-index 0 --seconds 20 --width 1920 --height 1080
   ```
3. Pošli report a snímky z indexu, na kterém byl obraz z vMixu.

### Co sledovat

- `resolution` a `frame_formats`: `progressive` je v pořádku, `field_0` a `field_1` znamenají půlsnímky (výška 540).
- `fps_actual` by měla odpovídat 25 nebo 50.
- `combing`: kolem 0,5 je čistý progresivní obraz, nad 1 je obraz roztřepený prokladem.
- `process_cpu_percent_of_one_core`: kolik stojí samotný příjem.

---

## M2-A: záznam → XML → titulek ve vMixu (asi 40 minut)

**Proč:** ověřit celý řetězec na skutečném vMixu: zápis souboru, čtení Data Source, mapování sloupců a 30 minut bez chyby a bez probliknutí (SPEC 15.6).

1. Připrav na Windows syntetický zápas a spusť aplikaci (nebo použij reálný záznam, pokud už je):
   ```powershell
   uv run python scripts/fetch_models.py
   cd frontend; npm ci; npm run build; cd ..
   uv run python -m tools.synth --out samples/synth/default
   uv run optima-time run --profile samples/synth/default/profile.json
   ```
2. V UI v panelu „Výstup pro vMix“ nastav cestu, třeba `C:\vmix-data\optima.xml`. Nepoužívej produkční soubor.
3. Ve vMixu přidej XML Data Source na ten soubor (XPath `/root`, interval 100 ms) a namapuj sloupce `Time`, `scoreh`, `scorea`, `period`, `penaltyh1` na kopii titulku.
4. Zkus tlačítka: „Zapsat testovací data“ (titulek ukáže náhodné hodnoty), „Vyprázdnit (test)“, „Zpět na živé hodnoty“, „Pauza výstupu“ (titulek zamrzne), ruční „Držet“ u skóre.
5. Nech běžet 30 minut. Záznam se přehrává ve smyčce.
   **Hlavně sleduj, jestli vMix někdy hlásí, že k souboru nemá přístup** (D29: Windows na zlomek milisekundy odmítne otevření souboru, který se právě nahrazuje). Když ano, zapiš, jak často, a zkus krok 7 (HTTP).
6. Sleduj:
   - Hlásí vMix chybu?
   - Problikne prázdná hodnota u `Time` nebo skóre?
   - Ukazuje semafor v UI žlutou nebo červenou u „Zápis XML“?
7. Totéž zkus s HTTP adresou `http://127.0.0.1:8787/data/values.xml` místo souboru.
8. Pošli: poznámky, snímky obrazovky a soubory `events-*.jsonl` z `%APPDATA%\OptimaTime\logs`.

## M2-B: simulátor čtenáře proti skutečným zámkům Windows (asi 10 minut)

**Proč:** na Macu se kolize zámků jen emulují. Na Windows je udělá skutečný systém.

```powershell
uv run python -m tools.xml_reader_sim --with-writer --minutes 5 --hold 30
```

Bez `--emulate-lock`: zámky dělá Windows sám. Výsledek musí být `"result": "OK"`. Zajímají mě i hodnoty `max_write_ms` a `slow_writes`. Pošli celý výpis JSON.

---

## M3-A: živý zdroj a výkon na produkčním PC (asi 30 minut)

**Proč:** NDI z vMixu, capture zařízení a hlavně spotřeba CPU a paměti vedle běžícího vMixu jdou změřit jen na tvém PC.

1. Zapni ve vMixu NDI pro vstup s tabulí (viz M0-C).
2. Spusť aplikaci s novým profilem a v UI v panelu „1. Zdroj“ zvol „NDI“ → „Obnovit seznam“ → zdroj z vMixu. Pak nastav rohy, pole a kotvy.
3. Nech běžet aspoň 10 minut při běžící produkci ve vMixu. Do semaforu se dívej na „Zpracování … CPU … MB“.
4. Zapiš si:
   - CPU aplikace ve Správci úloh (Podrobnosti, proces `python` nebo `optima-time`)
   - CPU celého PC a vMixu
   - paměť aplikace
   - jestli vMix nehlásí zahozené snímky
5. Stejné zkus se zdrojem „Capture zařízení“ → `vMix Video External 2` (zapni ve vMixu External output). Pozor: kartu, kterou má otevřenou vMix, aplikace nedostane.
6. Změř výkon i nástrojem, nad syntetickým záznamem (ve vlastním okně, vMix běží):
   ```powershell
   uv run python -m tools.bench samples/synth/default --seconds 120
   ```
   Pošli celý výpis JSON.
7. Volitelně zátěžový test přes noc:
   ```powershell
   uv run python -m tools.bench samples/synth/hard --hours 3 --out bench_3h.jsonl
   ```

---

## M4-A: nová hala do 10 minut podle návodu (SPEC 15.6)

**Proč:** jen člověk ověří, že návod a UI jsou srozumitelné a rychlé.

1. Spusť aplikaci s novým profilem (`optima-time run --profile test-hala`), vMix běží a posílá tabuli přes NDI.
2. Spusť stopky a postupuj **jen podle `docs/OPERATOR.md`, část B** (od kroku 3 „Nový profil“).
3. Zastav stopky, když titulek ve vMixu ukazuje správně čas, skóre i třetinu.
4. Zapiš:
   - celkový čas
   - kde ses zasekl nebo musel hledat
   - co v návodu nebo UI chybí nebo je nejasné
5. Zkus ve hře:
   - **Držet** u skóre
   - **Pauza výstupu**
   - **Nahrát vzorek** (60 s)
   - **Stáhnout diagnostický balíček**
6. Pošli poznámky, změřený čas a vzorek ze `%APPDATA%\OptimaTime\samples\…`.

---

## M5-A: instalace balíčku na Windows (asi 20 minut)

0. **Nejjednodušší cesta:** instalátor `OptimaTime-Setup-0.1.0.exe` si stáhni z GitHubu (Actions → poslední zelený běh → Artifacts → OptimaTime-win64), nebo z Macu příkazem `gh run download -n OptimaTime-win64`. Spusť ho na produkčním PC (administrátor není potřeba) a pokračuj krokem 3. Kroky 1–2 jsou jen pro ruční sestavení.
1. Na PC s Pythonem a Node.js (stačí jednou, sestavovat může jakékoli Windows PC):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
   ```
   Skript spustí testy, sestaví `dist\OptimaTime\`, spustí v ní `--self-test` a zabalí `dist\OptimaTime-<verze>-win64.zip`.
2. Na **produkčním PC** rozbal ZIP třeba do `C:\OptimaTime\`. Na produkčním PC nemusí být Python ani Node.js.
3. V příkazovém řádku spusť `C:\OptimaTime\optima-time.exe --self-test`. Všechno musí být OK. NDI a zařízení můžou hlásit POZOR, pokud je zrovna nic neposílá.
4. Dvojklik na `OptimaTime.exe`:
   - neotevře se konzole
   - otevře se **vlastní okno Optima Time** (ne záložka prohlížeče), přes celou obrazovku
   - v oznamovací oblasti je ikona s menu **Otevřít Optima Time** a **Ukončit**
   - self-test u **Okno programu** ukáže verzi WebView2 (jinak se UI otevře v prohlížeči)
5. Zavření okna křížkem se zeptá „Ukončit Optima Time?“. **Zrušit** nechá okno otevřené, **Ukončit** aplikaci zavře. Stejně **Ukončit** v menu ikony (bez ptaní). Ve Správci úloh nezůstane žádný proces `OptimaTime`. Okno minimalizuj a **Otevřít Optima Time** v menu ikony ho vrátí.
6. Znovu dvojklik: otevře se poslední profil.
7. Během běhu se PC neuspí (nech ho v klidu déle, než je nastavené uspání).
7b. Upozornění: ve vMixu na chvíli vypni NDI výstup (nebo odpoj zdroj). Do ~3 s se ukáže oznámení Windows „Zdroj obrazu vypadl“ a zazní zvuk, po zapnutí „Zdroj obrazu je zpět.“ Zkontroluj, že oznámení nejsou ve Windows vypnutá (Nastavení → Oznámení).
7c. Zámek: Nastavení → 5 → Zamknout nastavení. Z tabletu (`--host` s PINem) zkus posunout pole: musí se objevit „Nastavení je zamčené“.
8. Pošli výpis self-testu a poznámky.

## M5-B: stínový provoz při skutečném přenosu (SPEC 15.6)

**Proč:** poslední krok před ostrým nasazením. Optima Time běží souběžně se stávající aplikací, ale vMix čte jen tu stávající. Po zápase se porovná, co by poslaly do grafiky.

1. Před zápasem: Optima Time s profilem haly, výstup do **vlastního** souboru, např. `C:\vmix-data\optima.xml`. vMix ho nečte, nebo ho čte jen skrytá kopie titulku.
2. Spusť vzorkovač souboru stávající aplikace (zapisuje změny s časem):
   ```powershell
   C:\OptimaTime\optima-time.exe ... (nebo ze zdrojů:)
   uv run python -m tools.shadow sample --path C:\cesta\k\souboru\stavajici-aplikace.xml --out C:\vmix-data\reference.jsonl
   ```
3. Během zápasu nic nedělej. Volitelně nahraj vzorek (Nahrát vzorek, 10–15 minut), poslouží i jako reálný záznam pro ladění.
4. Po zápase porovnej:
   ```powershell
   uv run python -m tools.shadow compare C:\vmix-data\reference.jsonl %APPDATA%\OptimaTime\logs\events-<datum>.jsonl
   ```
   Výsledek ukáže u každého pole počet neshod delších než 1 s a první z nich s časem.
5. Pošli: výstup porovnání, oba JSONL soubory a diagnostický balíček. U každé neshody dohledáme, kdo měl pravdu.
6. **Do ostrého provozu až po čistém stínovém zápase.**
