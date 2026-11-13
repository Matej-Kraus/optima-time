# Zpráva z Milníku 0

Stav k 13. 11. 2026. Co běží, čísla z měření, co nefunguje nebo čeká na ruční test.

## 1. Kostra repozitáře – hotovo

- Git (lokálně, větev `main`, zatím bez commitu). `uv` 0.13.8, Python 3.13.2.
- Backend `backend/optima_time/` (jen `__init__` a zástupné CLI), `pyproject.toml` s připnutými verzemi, `uv.lock`.
- Frontend `frontend/`: Vite 8 + React 19 + TypeScript 7, vitest, oxlint. Jen prázdná stránka, texty UI v `src/i18n/cs.ts`.
- Dokumenty: `CLAUDE.md`, `DECISIONS.md`, `BACKLOG.md`, `MANUAL_TESTS.md`, `THIRD_PARTY.md`.
- Ověřeno spuštěním: `pytest` 2/2, `ruff check` a `ruff format` čisté, `pyright` bez chyb, `npm test` 1/1, `npm run lint` čisté, `npm run build` projde.

## 2. Ověřená fakta

Podrobnosti v `DECISIONS.md` (D2–D7).

| Tvrzení ze zadání | Výsledek |
|---|---|
| Wheely pro Python 3.13 (Windows x64, macOS arm64) | ✅ všechny včetně `cyndilib` |
| Modely PP-OCRv6 tiny/small ONNX, Apache-2.0 | ✅ připnuté revize, SHA-256 sedí |
| Předzpracování: výška 48, BGR, [-1, 1], doplnění na 320 | ✅ `inference.yml` + ScoreSight |
| CTC s maskou znaků | ✅ funguje (spike A) |
| `cyndilib`: příjem NDI | ✅ na Macu ověřeno proti lokálnímu testovacímu vysílači (1920×1080). Wheel přibaluje knihovnu NDI. |
| vMix XML Data Source: soubor i URL | ✅ dokumentace. ❓ pojmenování sloupců, minimální interval, zamykání: dokumentace mlčí, ověří ruční test M0-B |
| vMix doporučuje soubor celý uložit a nenechávat otevřený | ✅ fórum, vyjádření vývojáře vMixu |

**Nové zjištění:** `cyndilib.Receiver` má výchozí `allow_video_fields=True`. U prokládaného zdroje tak může dodávat půlsnímky (1920×540). ScoreSight tuhle volbu nenastavuje. U nás to ověří test M0-C.

## 3. Pokus A: PP-OCR (syntetické výřezy, Mac M1)

**Fotky ani záznam zatím nejsou, takže pokus běžel jen nad syntetickými výřezy.** Generátor kreslí znaky na rastr LED v barvách tabule (zelený čas, tyrkysové skóre, bílá perioda, barevné tresty). Přidává perspektivu, rozmazání, změnu expozice, šum a JPEG. Varianta „těžké“ navíc dává malá pole (14–30 px), přepaly a silnější rozmazání. Ukázka výřezů: `spikes/ppocr/out/synthetic630_sheet.png`.

### Přesnost (přesná shoda, s maskou znaků; 600 výřezů + 30 zhasnutých)

| Model, min. šířka | Běžné | Těžké | Zhasnutá pole čtená jako prázdná (běžné / těžké) |
|---|---:|---:|---:|
| tiny, 320 | 100 % | 97,8 % | 100 % / 100 % |
| tiny, 160 | 100 % | 99,3 % | 93 % / 100 % |
| small, 320 | 100 % | 99,3 % | 97 % / 100 % |
| small, 160 | 100 % | 99,5 % | 100 % / 93 % |

Druhy chyb (těžká sada):

- **Chybějící nebo zaměněný oddělovač s vysokou jistotou:** `54.7` → `547` (0,97), `02:44` → `02.44` (0,90), `01:28` → `0128` (0,95). Normalizace podle formátu je opraví (zadání 11.2 bod 3).
- **Záměna číslice** u malých jednoznakových výřezů: `5` → `6` (0,54–0,84), `0` → `4` nebo `6`. Tohle odfiltruje jen potvrzení v čase a věrohodnost (Milník 2).
- **Zhasnutá pole přečtená jako číslice** (`00`, `3`) mají nízkou jistotu, nejvýš 0,41. Brána kontrastu a práh jistoty kolem 0,5 je odfiltrují.

**Syntetika je optimistická.** 100 % na běžné sadě znamená hlavně, že generátor je zatím snazší než realita. Rozhodující bude reálný záznam.

### Rychlost (Mac M1, ms na jeden výřez, medián)

| Model | min. šířka 320, 1 vlákno | 320, 2 vlákna | 160, 1 vlákno | 160, 2 vlákna |
|---|---:|---:|---:|---:|
| tiny | 9,2 | 5,3 | 4,8 | **3,0** |
| small | 46,5 | 25,3 | 24,8 | 14,0 |

- Dávka 8 polí stojí tolik co 8 samostatných čtení (tiny 160/2: 20 ms). Dávkování šetří jen režii volání, ne výpočet.
- Small je na M1 asi 2,7× pomalejší, než naměřil ScoreSight na i9-14900K (17 ms). Rozhodující budou čísla z produkčního PC (test M0-A).
- **Odhad zátěže (tiny, 160, 2 vlákna):** OCR běží jen při změně (zadání 10.5). V poslední minutě se čas mění 10× za sekundu (desetiny), běžně 1× za sekundu. K tomu až 4 tresty 1× za sekundu. To dává zhruba 15–20 čtení za sekundu, tedy asi 60 ms výpočtu za sekundu, řádově 6 % jednoho jádra. Small by to bylo asi 4,5× víc.
- **Min. šířka 160 místo 320:** poloviční čas a na syntetice žádná ztráta přesnosti. ScoreSight ale měřil přesnost s 320, takže na reálných datech to musím ověřit.

## 4. Pokus B: XML zapisovač – připravený, čeká na test s vMixem

- Na Macu ověřeno: 204 atomických zápisů za 20 s, medián 0,5 ms, maximum 3,6 ms. Kontrolní čtenář (čte každých 100 ms) neviděl žádné neúplné ani nekompletní XML. HTTP `/data/values.xml` a `/data/values.json` vrací hlavičky proti kešování.
- Kolize se zamčeným souborem (`PermissionError`) nastávají jen na Windows. **Ruční test M0-B** (soubor i URL, 10 minut každý, plus test párování sloupců podle názvu).

## 5. Pokus C: NDI – připravený, čeká na test s vMixem

- Na Macu ověřeno proti lokálnímu NDI vysílači: výpis zdrojů, připojení, příjem BGRA snímků 1920×1080 a uložení snímků. Nízké fps (9,8) způsobil pomalý testovací vysílač, ne příjem.
- **Ruční test M0-C**: NDI z vMixu (s půlsnímky i bez nich) a jako záloha virtuální kamera přes OpenCV. Měří rozlišení, fps, proklad, CPU.

## 6. Co nefunguje nebo chybí

| Co | Proč | Co s tím |
|---|---|---|
| Pokus A na reálných fotkách | `samples/` je prázdné | pošli fotky a kopii XML (otevřený bod 1 v PLAN.md) |
| Čísla z produkčního PC | Mac M1 není produkční PC | ruční test M0-A |
| Chování reálného vMixu (soubor/URL, sloupce, interval) | potřebuje vMix | ruční test M0-B |
| NDI z vMixu, proklad | potřebuje vMix | ruční test M0-C |
| Varování `objc: Class AVF… is implemented in both` na Macu | OpenCV a nainstalovaný NDI HX driver mají stejnou knihovnu | jen vývoj na Macu; zatím bez dopadu, sleduji |

## 7. Úpravy plánu pro Milník 1

Promítnuto do `PLAN.md`:

1. `recognizers/ppocr.py`: minimální šířka jako parametr (výchozí 160, ověřit na reálných datech), výchozí 2 vlákna, spinning vypnutý.
2. `fields/formats.py`: normalizace oddělovače podle formátu (chybějící `:` nebo `.`, záměna `.` ↔ `:`). Patří už do Milníku 1, protože jde o nejčastější chybu s vysokou jistotou.
3. Brána kontrastu a práh jistoty (výchozí 0,5) už v Milníku 1, aby `tools/eval` měřil i zhasnutá pole. Potvrzování a věrohodnost zůstávají v Milníku 2.
4. Generátor (`tools/synth`): těžší varianty (moiré, blikání, cizí obsah) podle toho, co ukáže reálný záznam. Syntetika z pokusu A je na hodnocení příliš snadná.
5. Volba tiny/small: výchozí **tiny**. Definitivně až podle M0-A a reálného záznamu.
