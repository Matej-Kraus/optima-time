# Ruční testy

Testy, které nejde udělat bez reálného vMixu, NDI nebo produkčního PC. Ke každému: postup, co sledovat, co zapsat a poslat zpátky.

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
