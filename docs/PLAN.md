# PLAN – Milník 0 a 1

Projekt **optima-time**. Python balíček `optima_time`, příkaz `optima-time`, konfigurace v `%APPDATA%\OptimaTime\`. Zadání je v `docs/SPEC.md` (v1.2).

Stav: Milníky 0 (13. 11.) a 1–5 (14. 11. 2026) jsou hotové, viz `docs/M0_REPORT.md` až `M5_REPORT.md`. Zbývají ruční testy podle pořadí v `MANUAL_TESTS.md` a úpravy podle reálných dat. Reálná data a ruční testy dodá Matěj na konci; milníky 3–5 pokračují bez nich.

## 1. Shrnutí odpovědí

| Oblast | Odpověď | Dopad na návrh |
|---|---|---|
| Sport | florbal, 3 třetiny | výchozí pravidla věrohodnosti pro florbal |
| Směr času | nevím / liší se | směr `auto` (odvodí se z prvních změn), nastavitelný |
| Desetiny v poslední minutě | **ano** | formát `mm:ss` + přechod na `ss.d` je v MVP (zadání ho mělo jako volitelný) |
| Čas nad 20 min (23:54) | rozcvička / přestávka | hodiny nesmí mít horní mez 20:00; minuty i trojciferné |
| Tresty | 2 + 2, jen čas | pole `penaltyh1`, `penaltyh2`, `penaltya1`, `penaltya2` |
| Formát trestu v XML | přesně jak je na tabuli | styl výstupu `as_is` |
| Neběžící trest | prázdný prvek stačí | žádné sloupce navíc, politika `clear` |
| Prodloužení | číslem (4) | `period` = číslo 1–4, bez převodu na text |
| Skóre v XML | bez úvodní nuly | normalizace `03` → `3` |
| Excel `Data-4Nations…` | nevím | **otevřený bod** (kolize mapování) |
| Kde poběží | na PC s vMixem | přísné limity CPU a vláken, žádné GPU |
| Signál | 1080i50 | odstranění prokladu je nutnost; ověřit, co posílá vMix |
| Cesta z vMixu | nevím | Milník 0 vyzkouší NDI i virtuální kameru |
| Vytížení PC | nevím | **otevřený bod**, změřit při přenosu |
| vMix | edice 4K / Pro / Max | NDI výstup by měl být k dispozici |
| Vývoj | Mac (M1) + Windows s vMixem kdykoli | pokusy s vMixem a NDI lze dělat hned |
| Záznam tabule | do 2 týdnů | Milník 1 začne na syntetických datech, reálná data doplní |
| Termín | není pevný | žádné zkracování rozsahu kvůli termínu |
| Obsluha | i další lidé, lokálně | UI jen `127.0.0.1`; důraz na `OPERATOR.md` a srozumitelné hlášky |
| Šíření | jen interně | balení podle zadání; licence NDI jen evidovat |
| Repozitář | lokální git | `git init`, žádný remote |

## 2. Otevřené body (napiš nebo pošli, až budeš moct)

Ze seznamu zatím nic neblokuje start Milníku 0. Body 1 a 2 jsou ale potřeba pro pokusy A a B.

1. **Do `samples/`**: fotky tabule (i s běžícími tresty a s desetinami v poslední minutě) a **kopie skutečného XML souboru**, který dnes čte vMix.
2. **Cesta ke stávajícímu XML** a na která pole titulku jsou namapované sloupce `Time`, `penaltyh1`, `penaltya1`. Kam se mají namapovat `scoreh`, `scorea`, `period`?
3. **Číslo verze vMixu** (Help → About), model procesoru a capture karty.
4. **Excel**: plní dnes ve vMixu skóre nebo třetinu?
5. **Další haly**: bude se nástroj používat i jinde než u téhle tabule?
6. **Nejbližší zápas**, kde půjde nahrát záznam a změřit vytížení CPU při přenosu.

Co zůstane bez odpovědi, řeším výchozí hodnotou a zapíšu jako předpoklad do `docs/DECISIONS.md`.

## 3. Milník 0 – otázky, plán, ověření rizik

Cíl: kostra repozitáře, ověření faktů a tři jednorázové pokusy. **Žádný produkční kód.**

### 0.1 Kostra repozitáře

- `git init`, `.gitignore`. Spec je už přesunutý do `docs/SPEC.md`.
- Instalace `uv` (Homebrew). Python 3.13 je na Macu k dispozici.
- `pyproject.toml` (uv, připnuté verze), `ruff`, `pyright`, `pytest`. Prázdný balíček `backend/optima_time/` a jeden smoke test.
- `frontend/`: Vite + React + TypeScript, `vitest`. Jen šablona, žádné funkce.
- Dokumenty: `CLAUDE.md` (příkazy, konvence), `docs/DECISIONS.md`, `docs/BACKLOG.md`, `docs/MANUAL_TESTS.md`, `THIRD_PARTY.md`.
- Ověření: `uv run pytest`, `ruff`, `pyright`, `npm test` a `npm run build` projdou.

### 0.2 Ověření faktů (označených v zadání „ověř")

| Co | Kde |
|---|---|
| ONNX modely PP-OCRv6 tiny/small: existence, revize, SHA-256, `inference.yml` (výška, normalizace, slovník znaků) | Hugging Face |
| Předzpracování a CTC dekódování s maskou; `ocr_eval/`, `scripts/fetch_models.py`, CHANGELOG | ScoreSight (MIT) |
| Wheely `cyndilib` pro Python 3.13 na Windows x64 a macOS arm64 | PyPI |
| Wheely `onnxruntime` a `opencv-python-headless` pro 3.13 | PyPI |
| XML Data Source: soubor i URL, XPath, interval, párování sloupců podle názvu | dokumentace vMixu |
| NDI výstup vstupu a virtuální kamera v edici 4K/Pro; posílá vMix progresivní snímky? | dokumentace vMixu + pokus C |

Výsledky zapíšu do `DECISIONS.md`. Když něco nesedí se zadáním, ozvu se.

### 0.3 Pokusy (`spikes/`, jednorázový kód, do produkce se nepřebírá)

**A. PP-OCR nad fotkami tabule** (`spikes/ppocr/`)
- Stáhne tiny i small model (připnutá revize, kontrola SHA-256).
- Výřezy z fotek ručně (souřadnice v JSON): čas, skóre, perioda, tresty. Navíc výřezy se zhasnutou tabulí.
- Měří přesnost (přesná shoda) a čas na výřez (1 vlákno) pro tiny a small, s maskou znaků i bez ní. Zvlášť jednoznakové výřezy a čas s desetinami.
- Běží na Macu M1 i na Windows PC. Na Windows jsou čísla relevantnější.
- Potřebuje: fotky v `samples/` (otevřený bod 1). Bez nich jen na syntetických výřezech a s jasným upozorněním.

**B. XML zapisovač pro reálný vMix** (`spikes/xml_writer/`)
- Skript 10 minut přepisuje XML 10× za sekundu. Atomicky přes dočasný soubor a `os.replace()`, s opakováním při `PermissionError`.
- Zároveň servíruje stejné XML na `http://127.0.0.1:<port>/data/values.xml` bez kešování.
- Obsahuje `Time` (počítá), `penaltyh1–2`, `penaltya1–2` (střídavě prázdné a plné), `scoreh`, `scorea`, `period`. Tvar převezme ze skutečného souboru, pokud ho budu mít.
- Loguje počty kolizí a nejdelší dobu zápisu.
- Ty ho na Windows napojíš na vMix nejdřív ze souboru, pak z URL. Postup bude krok za krokem v `MANUAL_TESTS.md`.
- Sledujeme: chybové hlášky vMixu, probliknutí prázdné hodnoty a to, jestli nové sloupce nerozbijí stávající mapování.

**C. Příjem NDI** (`spikes/ndi/`)
- Výpis NDI zdrojů, příjem vstupu KOM BOX z vMixu, měření rozlišení, fps, prokladu a zátěže CPU.
- Pokud NDI nepůjde, stejný test s virtuální kamerou vMixu přes OpenCV.
- Na Macu ověřím jen instalaci a výpis zdrojů. Měření proběhne na tvém Windows PC podle `MANUAL_TESTS.md`.

### 0.4 Výstup Milníku 0

`docs/M0_REPORT.md`: čísla z pokusů, doporučení tiny/small, doporučení soubor/HTTP, cesta signálu z vMixu. K tomu upravený `PLAN.md` pro Milník 1. Pak se zastavím a počkám na schválení.

## 4. Milník 1 – jádro nad záznamem

Cíl: nástroj přečte syntetický i reálný záznam a `tools/eval` vypíše metriky. Potvrzování, věrohodnost, kotvy a zapisovač XML patří do Milníku 2.

### 4.1 Soubory

```text
backend/optima_time/
  sources/base.py        VideoSource (rozhraní, stavy, čítače)
  sources/file.py        video a obrázek: smyčka, rychlost včetně „co nejrychleji", skok na čas, deinterlace
  geometry.py            homografie ze 4 rohů, relativní souřadnice 0–1, rotace po 90°, výřezy polí s okrajem
  preprocess.py          šeď jako max(R,G,B), úrovně, inverze, brána kontrastu
  recognizers/base.py    Recognizer, Crop, Reading
  recognizers/ppocr.py   ONNX Runtime (CPU, omezená vlákna), dávkování podle šířky, CTC s maskou znaků
  fields/models.py       Pydantic model pole (clock, number, period)
  fields/formats.py      normalizace a validace: mm:ss, m:ss, ss.d, číslo, perioda; doplnění oddělovače
  config/models.py       profil (schema_version 1), načtení a uložení JSON
  pipeline.py            jednoduchá synchronní smyčka: snímek → narovnání → výřezy → OCR → formát
  api/                   FastAPI: náhled snímku (narovnaný i surový), CRUD profilu
  cli.py                 `optima-time run --profile … --source soubor`
frontend/                jedna stránka: tažení 4 rohů, kreslení obdélníků polí, uložení profilu
tools/synth/             generátor tabule a časové osy zápasu → video + pravda.jsonl
tools/eval/              metriky nad záznamem a pravdou
tools/labeler/           předvyplnění pravdy z OCR (CLI, výstup JSONL k ruční opravě)
scripts/fetch_models.py  stažení modelů s připnutou revizí a SHA-256
tests/                   jednotkové testy formátů, geometrie, CTC dekódování, synth
```

### 4.2 Pořadí práce

1. `fields/formats.py` a testy, včetně okrajových případů: 9 → 10, 0:00, 59.9 → 1:00 a naopak, 23:54 při rozcvičce, perioda 4. **Normalizace oddělovače** (`547` → `54.7`, `02.44` → `02:44`), nejčastější chyba s vysokou jistotou v pokusu A.
2. `geometry.py` a testy (známá homografie, zpáteční převod souřadnic).
3. `recognizers/ppocr.py`, ověřený proti výsledkům pokusu A. Minimální šířka jako parametr (výchozí 160, D9), 2 vlákna bez spinningu (D4). Brána kontrastu a práh jistoty (D10) v `preprocess.py`.
4. `tools/synth`: bezpatkový font podobný tabuli z fotek, zelený čas, tyrkysové skóre, LED rastr a moiré, perspektiva, šum, blikání, animace přes celou stěnu. Florbalová časová osa: rozcvička, 3 třetiny, desetiny v poslední minutě, góly, tresty 2 + 2, změny periody.
5. `sources/file.py` a `pipeline.py`.
6. `tools/eval`: přesnost enginu na výřezech a čas na snímek. Ve velmi jednoduché podobě i „publikovaná hodnota" (bez potvrzování), aby existovala základní čísla pro Milník 2.
7. Minimální API a frontend pro rohy a pole a uložení profilu.
8. `tools/labeler` a vyhodnocení reálného záznamu, jakmile ho pošleš.

### 4.3 Hotovo, když

- `tools/eval` nad syntetickým zápasem a nad reálným záznamem vypíše přesnost na výřezech po polích, podíl zachycených změn a čas na snímek (medián a p95).
- Testy, ruff a pyright projdou na macOS. Jádro nemá žádnou závislost na Windows.
- `M1_REPORT.md` s čísly a návrhem prahů pro Milník 2.

Pokud reálný záznam do konce Milníku 1 nedorazí, odevzdám milník jen se syntetickými čísly a jasně to označím.

## 5. Výchozí předpoklady (do DECISIONS.md)

- Python 3.13. Pokud chybí wheel (cyndilib), přejdu na 3.12 a zapíšu důvod.
- Výchozí model tiny; definitivní volba až podle měření.
- ONNX Runtime 1 vlákno, nastavitelné.
- `Time`: styl `no_leading_zero` (`0:00`), jako dnes. Tresty: `as_is`.
- XML v UTF-8 s deklarací, dokud nebudu mít skutečný soubor.
- Port UI 8787.

S rozhodnutími v sekci 7.1 zadání zatím souhlasím. Případné výhrady vyplynou z ověření v 0.2.

## 6. Milník 2 – logika hodnot a XML (plán 14. 11. 2026)

Matěj dodá reálná data a ruční testy až na konci, proto milníky 2–5 pokračují bez nich. Všechno, co nejde ověřit, jde do `MANUAL_TESTS.md`.

### 6.1 Soubory

```text
backend/optima_time/
  fields/plausibility.py  druh změny (stejná / očekávaná / neočekávaná / objevení) a co je pro přijetí potřeba (SPEC 11.4)
  fields/confirm.py       FieldLogic: kandidát, potvrzení v čase, politika prázdné hodnoty (11.5), ruční hold (11.6)
  guard.py                kotvy rozložení: šablona, normalizovaná korelace, návrat po N shodách (9.4)
  state.py                stav tabule: publikované hodnoty, stavy polí, události do JSONL (denní log)
  outputs/xml.py          sestavení XML (stálé pořadí, prázdné prvky, escapování)
  outputs/base.py         pracovní vlákno výstupu: jen poslední stav, stav zápisu, pauza / test / vyprázdnit
  outputs/xml_file.py     atomický zápis, opakování při PermissionError, hlášení zápisu delšího než 250 ms
  api/                    /data/values.xml|json (bez kešování), hold, pauza, testovací data, kotvy, události
  config/models.py        profil: kotvy, výstupy, pravidla potvrzení po polích
tools/xml_reader_sim/     čtenář jako vMix (každých 100 ms otevřít, přečíst, zavřít) + kontrola úplnosti
tools/synth               profil s kotvami (nápisy PERIÓDA, DOMÁCI, HOSTIA) a šablonami z videa
tools/eval                publikace přes skutečnou logiku (naivní zůstane jako volba)
frontend/                 hold/uvolnit, pauza výstupu, vyprázdnit, testovací data, kotvy, stav zápisu, log událostí
```

### 6.2 Hotovo, když

- 0 špatně publikovaných hodnot na syntetickém běžném i těžkém zápase, aspoň 99 % zachycených změn.
- Simulátor čtenáře: žádné neúplné ani nekompletní XML. Na Windows se ověří ruční test (kolize zámků).
- Ruční test „záznam → XML → titulek ve vMixu“ je připravený v `MANUAL_TESTS.md`.

## 7. Milník 3 – živé zdroje a výkon (plán 14. 11. 2026)

### 7.1 Soubory

```text
backend/optima_time/
  sources/live.py      společný základ živých zdrojů: vlákno, poslední snímek, znovupřipojení s rostoucí prodlevou
  sources/ndi.py       NDI přes cyndilib (výpis zdrojů, příjem, změna rozlišení, zmizení zdroje)
  sources/device.py    capture zařízení přes OpenCV (DirectShow/MSMF na Windows), výpis se jmény (cv2-enumerate-cameras)
  pipeline.py          detekce změny: OCR jen při změně výřezu, při nepotvrzeném poli a povinně 1× za sekundu (SPEC 10.5)
  supervisor.py        hlídání vláken (tep pipeline, pracovní vlákna výstupů) a jejich restart (SPEC 14.3)
  power.py             zabránění uspání PC za běhu (Windows), jinde nic
  api/                 /api/sources (NDI, zařízení), metriky procesu (CPU, paměť)
frontend/            výběr zdroje
tools/bench/         běh v reálném čase se zápisem XML: latence snímek → soubor (p50/p95), CPU, paměť, zahozené snímky;
                     režim zátěžového testu (hodiny ve smyčce, paměť a latence v čase)
```

Nové závislosti: `cv2-enumerate-cameras` 1.4.0 (MIT, výpis kamer), `psutil` 7.2.2 (BSD, CPU a paměť).

### 7.2 Hotovo, když

- Detekce změny ušetří většinu čtení OCR bez ztráty přesnosti (0 špatně publikovaných hodnot na syntetických zápasech).
- Latence snímek → zapsaný soubor p95 ≤ 80 ms při 25 fps a 8 polích (Mac M1; produkční PC = ruční test).
- Zátěžový test 3 h ve smyčce na Macu: žádný pád, žádné mrtvé vlákno, paměť neroste o víc než desítky MB.
- NDI: ověřené proti lokálnímu testovacímu vysílači. NDI z vMixu a capture karta na Windows = ruční test M0-C / M3-A.

## 8. Milník 4 – provozní UI (plán 14. 11. 2026)

### 8.1 Obsah

| Oblast | Co | Kde |
|---|---|---|
| Profily (13.3) | seznam, načíst, uložit jako (duplikát), export, import; průběžné ukládání už běží | `config/profiles.py`, API, UI |
| CLI (14.2) | `--profile NAZEV` hledá i v `%APPDATA%\OptimaTime\profiles`, `--host`, `--pin` | `cli.py` |
| Vzorky (13.3) | „Nahrát vzorek“: N sekund narovnaného obrazu (MP4) + log čtení (JSONL) + profil do `samples\` | `recorder.py` |
| Diagnostika (13.3) | ZIP: snímek, narovnaný snímek, výřezy, profil, stav, události, aplikační log, verze | `diagnostics.py` |
| Logy (14.3) | rotující aplikační log `logs\app.log` | `cli.py` |
| Náhled (13.1) | MJPEG stream (≤ 10 sn./s, zmenšený), nezávislý na zpracování | API, UI |
| Rohy (13.1) | lupa při tažení, posun šipkami (Shift po 10 px) | UI |
| Nastavení pole | práh jistoty, kontrastu, okraj, zpoždění prázdné hodnoty, počet číslic, rozsah periody | UI |
| Přístup ze sítě (13.4) | výchozí jen 127.0.0.1; `--host 0.0.0.0` vyžaduje PIN (cookie po zadání) | API, UI |
| Texty | popisy událostí česky | UI |
| Návod | `docs/OPERATOR.md`: nová hala krok za krokem (do 10 minut) | docs |

### 8.2 Hotovo, když

Nová hala jde nastavit podle `OPERATOR.md`. Ověřím projitím návodu nad syntetickým záznamem od prázdného profilu, čas změřím. Skutečná hala je ruční test.
