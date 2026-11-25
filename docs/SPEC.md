# Specifikace Optima Time: OCR světelné tabule pro vMix

Verze zadání **1.3 z 25. 11. 2026**. Projekt čte florbalovou světelnou tabuli:
**čas, skóre, třetinu a tresty**. Hlavní výstup je XML soubor ve stejném tvaru,
jaký vMix čte už dnes; HTTP feed je jeho síťová varianta a TCP API vMixu je
volitelný rychlý výstup.

Milníky 0–5 a část Fáze 2 jsou implementované. Tento dokument je produktová
specifikace a akceptační smlouva, ne návod k založení nového projektu. Aktuální
stav je v `docs/PLAN.md`, rozhodnutí v `docs/DECISIONS.md`, ruční produkční
ověření v `docs/MANUAL_TESTS.md` a operátorský postup v `docs/OPERATOR.md`.

## 0. Rozsah aktualizace 1.3

Dodatečný referenční balík ze ScoreSight a veřejné dokumentace Scoreboard OCR
byl porovnán s hotovou aplikací. Rozhodnutí, co zachovat, selektivně doplnit
nebo odložit, jsou v `docs/REFERENCE_REVIEW.md`.

- Aplikace zůstává zaměřená na **florbal**, ne hokej.
- Existující interní id polí a profily se nepřejmenovávají. Rozdílné názvy ve
  vMixu řeší mapování na výstupu.
- Celý referenční balík ani paralelní balíček `scoreboard_io` se nevendorizují.
- XML zůstává hlavní cestou; Web API vMixu na portu 8088 slouží k načtení
  titulků a polí, TCP 8099 k volitelnému přímému výstupu.
- Staré profily si zachovají chování. Nově vytvořené tresty se po dvou sekundách
  prázdna vymažou a hodnota `0:00` je vymaže ihned.

---

## 1. Cíl, kontext a priority

Stavíš nástroj pro živé sportovní přenosy. Kamera snímá fyzickou světelnou tabuli v hale. Nástroj z obrazu v reálném čase čte **čas, skóre, třetinu a trestové časy** a zapisuje je do XML souboru. vMix si ten soubor čte jako Data Source a hodnoty ukazuje v grafice, takže je nikdo nepřepisuje ručně. Dnes tuhle práci dělá komerční aplikace Scoreboard OCR. Chceme vlastní nástroj, který máme plně pod kontrolou a umíme si ho upravit.

Uživatel a zadavatel je Matěj: full-stack vývojář (Python/FastAPI, React/TypeScript), který nástroj sám obsluhuje při přenosech. Není specialista na počítačové vidění, takže rozhodnutí v téhle oblasti stručně zdůvodňuj.

Priority, v tomhle pořadí:

1. **Na vysílání nesmí odejít špatná hodnota.** Pozdě a správně je lepší než hned a špatně. Když si nástroj není jistý, drží poslední platnou hodnotu.
2. **Nízká latence.** Změna na tabuli má být v souboru zhruba do 100 ms od příchodu snímku. vMix si ji přečte při svém nejbližším čtení (interval 100 ms).
3. **Rychlé nastavení na místě.** Nová hala do 10 minut, známá hala načtením profilu.
4. **Lehký provoz vedle vMixu** na stejném PC: malá zátěž CPU, žádná práce pro GPU (tu potřebuje vMix).
5. **Offline.** Žádný internet, licenční server ani telemetrie.

## 2. Slovník

- **Tabule**: fyzická světelná tabule v hale.
- **Zdroj**: video s tabulí (NDI, capture zařízení, soubor).
- **Pole**: jeden čtený údaj (čas, skóre domácích…) s oblastí v obraze a pravidly.
- **Profil**: uložené nastavení pro konkrétní halu a sport (zdroj, rohy, pole, výstupy).
- **Přečtená hodnota**: co vrátil rozpoznávač z jednoho snímku.
- **Publikovaná hodnota**: co prošlo validací a potvrzením a smí ven.
- **Data Source**: funkce vMixu, která v pravidelném intervalu čte soubor nebo adresu a hodnoty mapuje na pole titulku.
- **Titulek**: vstup typu Title (GT) ve vMixu s pojmenovanými textovými a obrázkovými poli.

## 3. Referenční aplikace: Scoreboard OCR (pozorované chování)

Tohle je popis chování, které chceme funkčně pokrýt. Vychází jen z veřejné dokumentace a z fotek. Binárku nedekompiluj, nepřebírej její grafiku, texty ani formát presetů (viz pravidla v 16.2).

### 3.1 Pracovní postup a UI

Tři kroky v horní liště: **1. Select Capture → 2. Choose Output → 3. Add Digits**, vedle nich Load a Save (preset).

Krok 3 na fotkách:

- **Define Corners**: uživatel označí 4 rohy tabule a aplikace obraz perspektivně narovná.
- Seznam polí s aktuálně přečtenou hodnotou u každého, tlačítka Add, Edit, Delete.
- U vybraného pole: rozbalovací **Format**, zaškrtávátko **Ignore empty values**, tlačítka **+ Automatic**, **+ One Digit**, **+ Symbol**.
- Hlavní plátno ukazuje narovnaný a prahovaný obraz (bílé znaky na černé). Vybrané pole má zelený rámeček a boxy jednotlivých číslic.
- Vlevo dole malý barevný živý náhled zdroje.
- Dolní lišta: `High contrast`, `Invert Colors`, `Field Auto invert`, posuvníky `Black Level`, `White Level`, `Italic correction`, `Pixel Connectivity`, `Erode`, `Dilate`. Stavový řádek ukazuje fps zdroje a zpracování a zahozené snímky. Odkaz Report problem pošle popis se snímkem obrazovky.

### 3.2 Vstupy

Fotka nebo záznam tabule (pro testování doma), Blackmagic DeckLink, AJA, ostatní capture karty, USB převodníky a webkamery, zachytávání obrazovky (řešené přes NDI nástroje), NDI, SRT (caller i listener), RTMP, RTSP, HDMI výstup tabulí Bodet.

Doporučené obcházení, když capture karta nejde otevřít napřímo: poslat kameru z vMixu přes NDI, nebo použít druhý výstup vMixu jako virtuální capture zařízení (`vMix Video External 2`).

### 3.3 Zpracování obrazu a rozpoznávání

Doložená fakta:

- Aplikace rozpoznává jen bílé číslice na černém pozadí. `Invert Colors` převrací celý obraz, `Field Auto invert` dynamicky jen jedno pole (například když barva pozadí značí podávající tým).
- **Automatic**: v označené oblasti najde víc číslic najednou. Je nutný tam, kde číslice nebo oddělovače během zápasu mění pozici (typicky poslední minuta na „počítačových" tabulích). Číslice musí být po prahování plné (souvislé) a v oblasti nesmí být nic jiného (rámečky, loga).
- **One Digit**: uživatel nakreslí zvlášť obdélník pro každou číslici. Doporučeno při vibracích a u číslic s rámečkem.
- **Symbol**: každý obdélník dává 1, když v něm něco svítí, a 0, když je černý. Víc obdélníků se sčítá (2 ze 3 svítí → 2). Slouží pro oddechové časy, fauly, bonus, směr podání.
- Changelog opakovaně uvádí „Added fonts", samostatné `Erode` a `Dilate`, „Italic correction" a „lepší rozpoznání pomalu se měnících číslic".

Odhad (nepotvrzeno): prahování úrovněmi → morfologie, která spojí LED body do plných tvarů → segmentace na souvislé oblasti → porovnání každého znaku s knihovnou fontů → validace formátem → odeslání jen změn.

Doporučení ke kameře z dokumentace: pevný stativ bez vibrací, volný výhled, maximální zoom s celou tabulí v záběru, **ruční expozice (raději tmavší obraz kvůli kontrastu)**, ruční ostření, nastavení 50/60 Hz proti blikání. Levná alternativa je IP kamera s RTSP, ale přidá až 400 ms latence.

### 3.4 Pole a formáty

| Formát | Příklad výstupu | Účel |
|---|---|---|
| Custom | `56` | bez validace (skóre, fauly) |
| Time (mm:ss) | `5:13` | čas zápasu nebo trestu bez desetin |
| Time (mm:ss, ss.d) | `12:45`, `45.9` | čas s desetinami v poslední minutě |
| Time (hh:mm:ss.d) | `12:05:13.4` | atletika, plavání |
| Shot clock (ss) | `19` | |
| Shot clock (ss, s.d) | `4.9` | desetiny pod nastavenou hranicí (např. 24 → 6 → 5 → 4.9) |
| Period (1st…4th, OT) | `2nd` | 5 a víc → `OT` |
| Period Custom (1st…9th) | `5th` | |
| Symbols | číslo | počet svítících symbolů |
| Script | cokoli | vlastní výstup skriptem |

Další chování:

- **Ignore empty values** u pole: prázdné čtení se neposílá, grafika drží poslední platnou hodnotu (něco zakryje tabuli, tabule se po zápase vypne). Nehodí se tam, kde prázdno něco znamená (shot clock).
- **Padded**: doplnění mezerami kvůli zarovnání v grafice, tři varianty.
- Názvy polí smí obsahovat mezery, podtržítka, tečku i nelatinkové znaky. Pro XML výstup nesmí obsahovat mezeru ani začínat číslicí.
- **Scripted output**: skript nad hodnotami polí. Čte `field["název"]`, předchozí hodnotu `old["název"]`, výsledek zapisuje do `output`. Použití: názvy period, skládání polí, doplnění nul, prahy (fauly ≥ 5 → `BONUS`), cesta k obrázku podle hodnoty (obrázek faulů, pozadí běžícího trestu), validace.

### 3.5 Výstupy a napojení na vMix

**XML soubor** (cesta, kterou chceme jako hlavní):

- Aplikace zapisuje soubor, ve kterém je každé pole podřízeným prvkem kořene `<root>`, například `<root><clock>1:30</clock><shot_clock>10</shot_clock></root>`. Soubor se aktualizuje, když se číslice na tabuli změní.
- Ve vMixu se přidá XML Data Source, do XPath se zadá `/root` a sloupce se namapují na pole titulků (jde víc titulků naráz).
- Interval „Update data every" se má snížit z 1 s na 100 ms.

**Přímé API vMixu** (doporučená cesta reference, u nás záložní):

- Seznam titulků a názvů polí si aplikace načte z `http://<host>:8088/api` (XML stav vMixu).
- Hodnoty posílá přes TCP API na portu 8099 příkazy typu `FUNCTION SetText Input=<id vstupu>&SelectedName=Clock&Value=6:31`.
- Názvy polí se musí přesně shodovat s názvy v titulku (rozlišují se velká a malá písmena). U GT titulků mají textová pole příponu `.Text`.
- Obrázky: pole s příponou `.Source` a příkaz `FUNCTION SetImage … Value=C:\cesta\obrazek.png`.

Další cesty do vMixu: CSV (nedoporučeno, vMix formátuje čísla podle národního prostředí), HTTP feed (stejné XML na adrese místo v souboru), HTML stránka ve vstupu Web Browser čtoucí `http://localhost:8080/results.json`.

Obecné výstupy: TXT, víc TXT souborů, CSV, WebSocket, HTTP klient, HTTP služba, TCP/UDP socket. WebSocket a socket posílají jen změněné hodnoty.

Ladění výstupu: **Send Test Data** pošle náhodné hodnoty do všech polí, **Clear Test Data** je smaže. U výstupu je indikátor spojení (červená/zelená se zprávou).

### 3.6 Provozní vlastnosti

- Rozpoznávání běží 25–60× za sekundu, náhled se kvůli CPU překresluje jen 5× za sekundu.
- Udávaná latence: capture kolem 100 ms (DeckLink), OCR do 50 ms, socket pod 5 ms, celkem od 150 ms.
- Zátěž kolem 10 % CPU notebookového i5, asi 200 MB RAM.
- Presety pro sport a kameru, start z příkazové řádky (`--autostart`, `--minimized`, `--preset`, `--log-folder`), dvě instance na jednom PC.
- Licence se při startu ověřuje online. **Tohle nechceme.**

## 4. Druhá reference: ScoreSight (open source)

ScoreSight (`github.com/royshil/scoresight`) je otevřený nástroj se stejným účelem: licence MIT, Python 3.13, PySide6, OpenCV, ONNX Runtime, cyndilib (NDI), FastAPI. Aktivně se vyvíjí (verze 0.4.3 vyšla 2. 11. 2026).

Matěj se rozhodl pro vlastní nástroj. ScoreSight používej jako **referenci a měřítko**, ne jako základ. Jeho zdrojový kód smíš číst a jednotlivé části převzít, když zachováš MIT hlavičku a zapíšeš to do `THIRD_PARTY.md`.

Poučení z jeho vývoje, která přebíráme (ověř si je v jeho repozitáři, hlavně `ocr_eval/`, `scripts/fetch_models.py` a CHANGELOG):

- PP-OCRv6 (rozpoznávací modely PaddleOCR spuštěné přes ONNX Runtime) přečetl na 2 040 reálných výřezech tabulí přesně 95 % hodnot (model small) a 90 % (model tiny). Tesseract ve výchozím nastavení 31 %, nejlépe vyladěný 46 %.
- PP-OCR chce **syrový barevný výřez**. Binarizace mu ubrala 28–44 procentních bodů.
- Rychlost na jednom vlákně CPU: tiny asi 3,5 ms, small asi 16,5 ms na výřez.
- Dekódování omezené na povolené znaky podle typu pole (maska v CTC dekodéru) nestálo žádnou přesnost a odstraňuje chyby.
- Zbývající chyby jsou hlavně hodiny s nepřečtenou dvojtečkou. Oddělovač se dá doplnit z formátu.
- Zhasnuté LED bodové matice se dají přečíst jako číslice. Před čtením je potřeba kontrolovat kontrast výřezu.
- Filtrování podle pravidel hry: změna platí až po potvrzení druhým čtením. Změna, kterou sport nedovoluje (skok o 5, pokles skóre), platí až když vydrží 3 s.
- OCR běží ve vlastním vlákně vždy nad nejnovějším snímkem. Výstupy běží v pracovních vláknech, která drží jen poslední hodnotu každého pole, takže pomalý cíl nic nezablokuje.

## 5. Produkční prostředí a požadavky

Co je vidět na fotkách (stav 13. 11. 2026):

- vMix s presetem `4Nations.vmix`. Běží i Excel se souborem `Data-4Nations…` (nejspíš Data Source pro jiná pole titulků).
- Kamera na tabuli je ve vMixu jako vstup **KOM BOX**.
- Scoreboard OCR 25.12.04 běží podle fotek nejspíš na stejném PC jako vMix (ověř otázkou 4), zpracování ukazuje 50 fps.
- V presetu jsou pole `Time` a čtyři trestové časy `penaltyh1`, `penaltyh2`, `penaltya1`, `penaltya2`. Když tabule ukazuje `00:00`, pole `Time` dává ven `0:00`.
- Nastavení obrazu na fotce: Black Level 170, White Level 122, Dilate 5, ostatní 0.
- **Tabule je plnobarevná LED video stěna, ne klasický sedmisegment.** Znaky jsou vykreslené bezpatkovým fontem: zelený čas `00:00` nahoře uprostřed, pod ním bílý nápis `PERIÓDA` a číslo periody, vlevo `DOMÁCI`, vpravo `HOSTIA`, pod nimi tyrkysové skóre. Na okrajích záběru je vidět rastr LED (moiré).

Co řekl a poslal Matěj:

- Chce číst **čas, skóre (góly), třetinu a tresty**. Nic dalšího.
- vMix u něj zpracovává **XML soubory**, takže chce, aby nástroj průběžně zapisoval aktuální hodnoty do XML souboru, který vMixu předá.
- Kamera na tabuli jde do PC přes **SDI**, občas vedené optikou. Na straně PC je to tedy vstup capture karty.
- Stávající XML, které dnes zapisuje Scoreboard OCR a čte vMix (opsáno z fotky prohlížeče):

```xml
<root>
  <Time>23:54</Time>
  <penaltya1/>
  <penaltyh1/>
</root>
```

Z toho plyne: kořen `<root>`, jedno pole je jeden podřízený prvek, prázdná hodnota je prázdný prvek, názvy rozlišují velikost písmen. Prvky jsou v abecedním pořadí. Skóre a třetina v souboru dnes nejsou.

Důsledky pro návrh:

- Font i rozložení se hala od haly liší. Knihovna sedmisegmentových vzorů nestačí.
- Číslice se při změně počtu znaků posouvají (skóre 9 → 10).
- Video stěna může kdykoli ukázat něco jiného než skóre (animace gólu, reklama, opakovaný záběr). Nástroj v tu chvíli nesmí zapsat nesmysl (viz 9.4).

## 6. Rozsah

**MVP (musí být):**

- Pole: čas zápasu, skóre domácích, skóre hostů, třetina, trestové časy (počet podle tabule, viz otázka 2).
- Zdroje: video soubor a obrázek, NDI, lokální capture zařízení (včetně virtuální kamery vMixu).
- Narovnání ze 4 rohů, pole kreslená myší.
- Rozpoznávání PP-OCRv6, validace, potvrzování, pravidla věrohodnosti, politika prázdné hodnoty, hlídání rozložení.
- Výstup: XML soubor pro vMix Data Source, stejná data na HTTP adrese.
- Webové UI: nastavení a živý pohled, ruční přepsání hodnoty (hold), pauza výstupu.
- Profily, logy, záznam vzorků, CLI.
- Testy: jednotkové, syntetický generátor, simulátor čtenáře XML, vyhodnocení na záznamech.
- Balíček pro Windows.

**Fáze 2 (po MVP, podle potřeby):**

- Přímé API vMixu (TCP) jako druhý výstup, obrázky a viditelnost v titulku.
- Ruční pole (například střely, které tabule neukazuje), symboly, odvozená pole se šablonami.
- Výřez obrazovky a síťové streamy jako zdroje, stabilizace obrazu při posunu kamery, zpoždění výstupu.
- Klasický „glyph" engine s učením fontu (10.4), pokud měření ukáže mezeru.
- Živé HTML overlaye, obecný TCP/UDP/WebSocket výstup, pravidla jednotlivých sportů, víc zdrojů v jedné instanci.

**Nedělat:**

- Čtení názvů týmů a obecného textu, automatické hledání tabule v obraze, cloud, účty, licencování, inference na GPU.
- Produkční podpora macOS a Linuxu. Vývoj a testy na nich ale běžet musí (viz 7.2).

## 7. Architektura a technologie

### 7.1 Rozhodnutí

| Oblast | Rozhodnutí | Proč |
|---|---|---|
| Jádro | Python 3.13 (při chybějícím wheelu 3.12) | Matějův stack; stejná sada závislostí běží na 3.13 ve ScoreSight |
| Obraz | OpenCV (`opencv-python-headless`), NumPy | standard, při výpočtu uvolňuje GIL |
| OCR | ONNX Runtime jen na CPU + modely PP-OCRv6 rec | sekce 4 a 10 |
| API | FastAPI + Uvicorn, REST a WebSocket | Matějův stack; UI jde otevřít i z jiného zařízení |
| UI | React + TypeScript + Vite, sestavené do statických souborů, které servíruje backend | Matějův stack; žádné CDN, všechno offline |
| NDI | `cyndilib` | MIT, hotové wheely, používá ho ScoreSight |
| Konfigurace | modely Pydantic v2, soubory JSON | validace a migrace |
| Nástroje | `uv`, `ruff`, `pyright`, `pytest`; frontend `npm`, `vitest` | rychlé a běžné |
| Balení | PyInstaller (one-folder) + instalátor nebo zip | ověřeno pro tuhle sadu knihoven |

Když s některým rozhodnutím nesouhlasíš, řekni to v Milníku 0 a uveď důvod. Neměň ho mlčky.

### 7.2 Běhový model

Jeden proces, vlákna:

- **Capture** (jedno na zdroj): drží jen poslední snímek s časovou značkou.
- **Pipeline**: narovnání → výřezy → detekce změny → rozpoznání → logika polí → stav.
- **Výstupy**: jedno pracovní vlákno na každý výstup (v MVP zapisovač XML).
- **API**: asyncio smyčka Uvicornu. S ostatními vlákny komunikuje přes thread-safe fronty.

Zásady:

- Mezi stupni platí „poslední vyhrává". Žádná fronta nesmí růst. Když pipeline nestíhá, staré snímky se zahodí a zvýší se čítač.
- Jádro (geometrie, rozpoznávání, logika polí, výstupy) musí jít importovat a testovat bez UI a bez Windows. Platformní zdroje jsou za rozhraním a na jiném systému se ohlásí jako nedostupné.
- Čas měř přes `time.monotonic_ns()`. Do logu událostí zapisuj i čas hodin.

```text
zdroj ─► capture (poslední snímek) ─► narovnání ─► výřezy polí ─► detekce změny
      ─► rozpoznání (PP-OCR) ─► validace + potvrzení ─► stav
      ─► výstupy (XML soubor, HTTP data)
      └► UI (WebSocket) + log událostí
```

### 7.3 Navržená struktura repozitáře

```text
backend/tabule_ocr/
  sources/       base.py, file.py, ndi.py, device.py
  geometry.py    homografie, ROI
  preprocess.py
  guard.py       hlídání rozložení
  recognizers/   base.py, ppocr.py
  fields/        models.py, formats.py, confirm.py, plausibility.py, transforms.py
  state.py       stav tabule a události
  pipeline.py
  outputs/       base.py, xml_file.py, data_http.py
  api/           REST, WebSocket, MJPEG náhled
  config/        modely profilu, migrace, úložiště
  cli.py
frontend/        React + TypeScript
tools/           synth (generátor), eval, xml_reader_sim, labeler
tests/
docs/            SPEC.md, PLAN.md, DECISIONS.md, BACKLOG.md, OPERATOR.md, MANUAL_TESTS.md
```

## 8. Vstup videa

Společné rozhraní `VideoSource`: otevření, `read_latest()` vracející snímek BGR s monotónní časovou značkou a pořadovým číslem, zavření, stav (`connecting`, `ok`, `lost`), informace (rozlišení, fps), čítače přijatých a zahozených snímků. Každý zdroj se po výpadku sám připojuje znovu s rostoucí prodlevou. U prokládaného signálu (1080i) zajisti odstranění prokladu, jinak se číslice při změně roztřepí.

| Zdroj | Poznámky |
|---|---|
| **Soubor / obrázek** | Pro vývoj a testy. Smyčka, rychlost přehrávání (včetně „co nejrychleji" pro vyhodnocení), skok na čas. |
| **NDI** | `cyndilib`: výpis zdrojů v síti, plná kvalita, progresivní snímky. Ošetři změnu rozlišení za běhu a zmizení zdroje. |
| **Capture zařízení** | OpenCV s DirectShow/MSMF. Výpis zařízení se jmény (vyber knihovnu, nebo se inspiruj enumerátorem ve ScoreSight), volba rozlišení, fps a formátu (MJPG). Sem patří i virtuální kamera vMixu (`vMix Video`, `vMix Video External 2`). |
| **Výřez obrazovky (Fáze 2)** | `dxcam` na Windows, `mss` jinde. Záložní cesta, když nejde NDI. |
| **URL (Fáze 2)** | RTSP, SRT, RTMP, HTTP přes FFmpeg backend OpenCV nebo PyAV. Nastav nízké zpoždění a vlákno, které vyprazdňuje buffer. |

Cesta signálu ve stávajícím provozu: kamera na tabuli jde přes SDI (občas po optice) do capture karty a je vstupem vMixu (KOM BOX). Vstup capture karty nemůžou otevřít dvě aplikace zároveň, takže nástroj si obraz bere z vMixu: vMix pošle vstup dál přes NDI (Settings → Outputs / NDI / SRT: NDI pro kamerové vstupy, nebo vstup přiřazený na Output 2–4 se zapnutým NDI) a nástroj čte NDI. Druhá možnost je virtuální kamera vMixu. SDI bývá prokládané (1080i50); ověř, jestli z vMixu chodí progresivní snímky. Přesný postup ve vMixu ověř v aktuální verzi a edici a popiš ho v `OPERATOR.md`.

## 9. Geometrie a předzpracování

### 9.1 Narovnání

- Uživatel označí 4 rohy tabule. Spočítej homografii do pravoúhlého plátna (poměr stran z rohů, šířka omezená, například 1280 px).
- Volitelně otočení po 90° a ořez.
- Souřadnice rohů i polí ukládej relativně (0–1), aby profil přežil změnu rozlišení zdroje.

### 9.2 Úpravy obrazu

- PP-OCR dostává syrový barevný výřez. Úpravy níže jsou pro náhled, hlídání rozložení a případný glyph engine.
- Úrovně (černý a bílý bod), inverze, automatická inverze po polích (kanonický tvar je světlý znak na tmavém pozadí).
- Pro převod do šedi u LED používej maximum z kanálů R, G, B, ne jas. Červené a modré LED mají v jasu málo.
- Volitelné časové slévání posledních N snímků (maximum nebo průměr po pixelech) proti blikání a moiré LED. Výchozí stav vypnuto, protože přidává zpoždění.

### 9.3 Brána kontrastu

Výřez s příliš malým kontrastem (zhasnutá tabule, zhasnuté LED) se nečte a pole dostane stav „prázdné". Práh je nastavitelný po polích.

### 9.4 Hlídání rozložení (layout guard)

Video stěna umí přepnout na animaci nebo reklamu. Uživatel proto označí 1–3 **kotvy**: statické části rozložení (například nápis `PERIÓDA`). Nástroj si uloží jejich vzor a v každém snímku ho porovná (normalizovaná korelace nad zmenšeným výřezem). Když kotvy nesedí, snímek se bere jako „tabule neukazuje skóre": žádné pole se nečte, publikované hodnoty se drží a UI to viditelně hlásí. Návrat nastane až po několika po sobě jdoucích shodách.

Stejné kotvy později poslouží pro odhad posunu kamery (Fáze 2: malý posun se dorovná úpravou homografie, velký vyvolá varování).

## 10. Rozpoznávání

### 10.1 Rozhraní

```python
class Recognizer(Protocol):
    def read(self, crops: list[Crop]) -> list[Reading]: ...   # dávkově

# Reading: text, confidence (0–1), per_char_confidence, engine, elapsed_ms
```

Engine se volí po polích. Přidání dalšího enginu nesmí vyžadovat zásah do pipeline.

### 10.2 Výchozí engine: PP-OCRv6 rec přes ONNX Runtime

- Modely: oficiální ONNX exporty z Hugging Face (`PaddlePaddle/PP-OCRv6_tiny_rec_onnx`, `PaddlePaddle/PP-OCRv6_small_rec_onnx`), licence Apache-2.0. Stahuj je skriptem při sestavení, s připnutou revizí a kontrolou SHA-256, a přibal je do aplikace. Za běhu se nic nestahuje.
- Bez detekčního kroku: výřez pole už je řádek textu.
- Předzpracování podle evaluace ScoreSight: výška 48 px, BGR, škálování do [-1, 1], doplnění zprava na šířku aspoň 320 px, dávkování podle šířky. **Ověř to proti `inference.yml` u modelu a proti implementaci ve ScoreSight**, neber to jako hotový fakt.
- Vlastní hladové CTC dekódování s maskou povolených znaků podle typu pole (číslice, `:`, `.`).
- Kolem výřezu nech okraj. Jednoznakové výřezy (skóre `0`–`9`) bývají pro řádkové modely těžší, proto je testuj zvlášť.
- Jen `CPUExecutionProvider`. Počet vláken ONNX Runtime omez (výchozí 1–2, nastavitelné), ať nástroj nebere výkon vMixu.
- Výchozí model `tiny`, volitelně `small`. Volbu udělej na základě měření na reálném záznamu (10.6).

### 10.3 Detektor symbolů (Fáze 2)

Obdélník svítí, když jeho jas (maximum kanálů) překročí práh. Hystereze (dva prahy) a potvrzení přes několik snímků. Pole typu symbol vrací počet svítících obdélníků.

### 10.4 Glyph engine (Fáze 2, jen když bude potřeba)

Klasický postup podobný referenční aplikaci: prahování → morfologie (spojení LED bodů) → korekce sklonu kurzívních číslic → souvislé oblasti → klasifikace každého znaku proti vzorům. Vzory vzniknou „naučením" na konkrétní tabuli (operátor jednou potvrdí číslice 0–9), plus sada vygenerovaná z fontů. Hodí se pro pevné tabule, kde je důležitý determinismus a rychlost. **Nezačínej ho, dokud vyhodnocení neukáže, že PP-OCR na reálných záznamech nestačí.**

### 10.5 Kdy se čte

- Zpracovává se každý snímek zdroje. Častěji to nejde a nedává to smysl: nová informace přijde nejdřív s dalším snímkem (při 25–50 snímcích za sekundu jednou za 20–40 ms).
- Každý snímek se pro každé pole levně porovná s minulým výřezem (zmenšený a rozmazaný rozdíl). OCR běží jen při změně a jednou za čas povinně (například každou sekundu), aby se chyba nezacyklila.
- Všechna pole, která se v daném snímku mají číst, jdou do modelu jednou dávkou.

### 10.6 Nejdřív měř

Než začneš ladit, postav vyhodnocení (15.3): přesnost enginu na jednotlivých výřezech a přesnost publikovaných hodnot proti pravdě. Každou změnu v rozpoznávání nebo logice polí doprovoď čísly před a po.

## 11. Pole: model, formáty a logika hodnot

### 11.1 Model pole

`id` (ASCII bez mezer, nezačíná číslicí; stabilní interní identifikátor), `label`
(libovolný text pro UI), `type`, oblast v narovnaném obraze, engine a jeho
parametry, formát, politika prázdné hodnoty, pravidla potvrzení a věrohodnosti,
transformace výstupu, příznak zapnuto.

`id` si volí uživatel a velikost písmen se zachovává. Výchozí profil používá
názvy ze stávajícího XML: `Time`, `penaltyh1`, `penaltya1` (případně
`penaltyh2`, `penaltya2`), `scoreh`, `scorea`, `period`. Kvůli existujícím
profilům se tato id nepřejmenovávají. Pokud cílové XML používá jiné názvy,
profil mapuje interní id na název výstupního prvku (12.1).

Typy v MVP: `clock` (čas zápasu i trestový čas), `number` (skóre), `period` (třetina). Ve Fázi 2: `symbol`, `manual`, `computed`.

### 11.2 Zpracování jednoho čtení

1. **Brány**: zdroj v pořádku, kotvy sedí, kontrast stačí. Jinak se nečte.
2. **Čtení**: text a jistota z enginu.
3. **Normalizace**: jen povolené znaky. Chybějící oddělovač se doplní podle formátu a poslední platné hodnoty (`1245` → `12:45`).
4. **Validace formátu**: regulární výraz a význam (sekundy < 60 a podobně).
5. **Potvrzení v čase** (11.4).
6. **Věrohodnost** (11.4).
7. **Publikace**: změna stavu → transformace → výstupy.

Stavy pole pro UI a log: nová hodnota, beze změny, zamítnuto, prázdné, zastaralé (zdroj vypadl), drženo ručně.

### 11.3 Formáty

- **Hodiny**: `mm:ss` (minuty i trojciferné), `m:ss` pro tresty, volitelně přechod na `ss.d` v poslední minutě. Směr počítání `nahoru`, `dolů` nebo `auto` (odvodí se z prvních změn). Styl výstupu: jak je na tabuli, bez úvodní nuly (`0:00`, tak to dnes posílá referenční aplikace), nebo s nulou.
- **Číslo**: počet číslic od–do, volitelně odstranění nebo doplnění úvodních nul.
- **Třetina**: výchozí výstup je číslo, jak je na tabuli (1–3, případně prodloužení). Volitelně převod na text přes tabulku v profilu (například `1` → `1. tretina`).
- **Vlastní**: regulární výraz.
- **Zarovnání**: volitelné doplnění mezerami na pevnou šířku, aby text v grafice neposkakoval.

Ostatní formáty z tabulky v 3.4 (shot clock, `hh:mm:ss.d`) připrav tak, aby šly doplnit bez přepisování, ale v MVP je neimplementuj.

### 11.4 Potvrzení a věrohodnost

Důvod: cena chyb je nesouměrná, viz priorita 1. Výchozí hodnoty níže jsou návrh. Udělej je nastavitelné po polích a dolaď je podle měření.

| Typ | Očekávaná změna → rychlé přijetí | Neočekávaná změna → pomalé přijetí |
|---|---|---|
| Čas zápasu | stejná hodnota nebo krok o 1 s ve směru počítání: přijmi hned při dostatečné jistotě | cokoli jiného (skok, nová perioda, oprava času): 3 shodná čtení po sobě nebo 400 ms beze změny |
| Skóre | zvýšení o 1: 2 shodná čtení | pokles nebo větší skok: hodnota musí vydržet 2 s |
| Trestový čas | objevení z prázdna: 2 čtení; odpočet o 1 s: hned | skok: jako čas zápasu |
| Třetina | zvýšení o 1: 3 shodná čtení | jinak 3 s |

### 11.5 Prázdná hodnota

Po polích: `hold` (držet poslední platnou; výchozí pro čas, skóre, třetinu),
`clear` (zapsat prázdno po nastavitelném zpoždění; výchozí pro tresty), `value`
(zapsat zadaný řetězec, například `0`). Existující profily zachovávají uložené
zpoždění. Nová florbalová šablona používá u trestů 2 s: krátké zakrytí nesmí
trest skrýt, ale skončený trest musí zmizet. Trestové hodiny mají samostatnou
volbu „nula znamená prázdno“; ve výchozí šabloně `0:00` vymaže výstup ihned.

### 11.6 Ruční přepsání (hold)

Operátor zadá hodnotu pole ručně. Ta se publikuje a OCR se pro pole ignoruje, dokud hold nezruší. V UI musí být výrazně vidět. Je to pojistka pro chvíle, kdy čtení selže.

Ruční pole bez oblasti v obraze (například střely) a odvozená pole se šablonami patří do Fáze 2.

## 12. Výstupy

### 12.1 XML soubor (hlavní výstup)

Tvar souboru (cesta je v profilu):

```xml
<?xml version="1.0" encoding="utf-8"?>
<root>
  <Time>12:45</Time>
  <penaltya1/>
  <penaltyh1>1:32</penaltyh1>
  <period>2</period>
  <scorea>1</scorea>
  <scoreh>2</scoreh>
</root>
```

- Tvar kopíruje stávající soubor (sekce 5): kořen `<root>`, výchozí název prvku
  je `id` pole a prázdná hodnota je prázdný prvek (`<penaltya1/>`).
- Profil může mapovat interní id na jiný platný a jedinečný název XML prvku.
  Prázdná mapa znamená identitu a zachovává všechny staré profily. Stejná mapa
  se používá pro soubor, `/data/values.xml` i `/data/values.json`; při startu se
  existující XML mapuje zpět na interní id.
- Fotka stávajícího souboru je z prohlížeče, který neukazuje XML deklaraci, kódování ani konce řádků. Přesný tvar (deklarace, kódování, BOM, konce řádků) proto převezmi ze skutečného souboru v `samples/`. Dokud ho nemáš, piš UTF-8 s deklarací jako v příkladu.
- V souboru jsou **vždy všechna zapnutá pole** ve stálém (abecedním) pořadí, i prázdná, aby vMixu nemizely sloupce. Hodnoty escapuj, kódování UTF-8.
- Stávající prvky `Time`, `penaltyh1`, `penaltya1` musí zůstat beze změny názvu. vMix by měl sloupce párovat podle názvu, takže nové prvky (`scoreh`, `scorea`, `period`) stávající mapování nerozbijí; ověř to v Milníku 0.

**Kdy se zapisuje: jen když se změní publikovaná hodnota.** Matěj původně uvažoval o zápisu na časovač každých 5 ms. To nedělej, ze tří důvodů:

1. Nová informace vzniká nejdřív s dalším snímkem (20–40 ms) a hodnoty se mění typicky jednou za sekundu.
2. vMix soubor čte ve svém intervalu (nastavuje se 100 ms), častější zápis nic nezrychlí.
3. vMix záměrně nečte soubor, který má právě otevřený jiný program. Na fóru vMixu je popsaný případ, kdy aplikace přepisovala soubor velmi často a vMix hlásil, že k němu nemá přístup. Doporučení vývojáře vMixu: soubor při změně celý uložit a nenechávat ho otevřený.

**Jak se zapisuje:**

- Zapiš obsah do dočasného souboru ve stejné složce, zavři ho a přes `os.replace()` jím nahraď cílový soubor. Cílový soubor nikdy nedrž otevřený.
- Když náhrada selže, protože cíl má právě otevřený vMix nebo antivir (`PermissionError`), zkus to po několika milisekundách znovu. Zapisovací vlákno drží jen poslední stav, takže se nic nehromadí.
- Zápis, který se nepovede déle než 250 ms, zaloguj a ukaž v UI.
- Při startu a po obnovení zdroje zapiš celý stav. Při ukončení nech v souboru poslední hodnoty, nebo ho podle nastavení vyprázdni.
- **Pauza výstupu** zastaví přepisování a hodnoty v grafice zůstanou stát.
- **Testovací data**: tlačítka „Zapsat testovací data" (náhodné platné hodnoty do všech polí) a „Vyprázdnit". Ukazatel posledního úspěšného zápisu.

**Nastavení ve vMixu** (popiš krok za krokem v `OPERATOR.md` a ověř v aktuální verzi): Data Sources Manager → přidat XML → vybrat soubor → XPath `/root` → interval čtení 100 ms → v Title Editoru namapovat sloupce na pole titulku. Pole titulku napojené na Data Source se nesmí zároveň řídit jinou cestou.

**Volitelné sloupce** (jen po dohodě s Matějem, otázka 2): příznak běžícího trestu, nebo cesta k obrázku podkladu trestu (průhledný PNG znamená schováno). vMix umí z Data Source plnit i obrázky v titulku; ověř, jak přesně.

### 12.2 Stejná data na HTTP adrese

Backend servíruje totéž XML na `http://127.0.0.1:<port>/data/values.xml` a pro ladění i `/data/values.json`. Odpovědi se nesmí kešovat. XML Data Source ve vMixu umí číst i webovou adresu, takže je to záloha pro případ, že by čtení souboru zlobilo (zamykání, antivir, síťový disk). V Milníku 0 obě cesty porovnej na reálném vMixu a výchozí zvol podle výsledku.

### 12.3 Přímé API vMixu a načtení polí

Přímý TCP výstup je implementovaná volitelná cesta vedle XML. Obejde soubory i
interval čtení. Web API na portu 8088 se používá read-only pro načtení titulků a
jejich textových polí, aby operátor nemusel ručně opisovat názvy:

- Načtení titulků: `GET http://<host>:8088/api/` vrací XML. Každý `<input>` má
  atributy `key` (GUID), `number`, `type`, `title` a podřízené prvky
  `<text index name>`. Požadavek má krátký timeout, omezenou velikost odpovědi a
  srozumitelně odlišuje špatný port, přihlášení, neplatné XML a nedostupný vMix.
- Odesílání přes TCP API (pevný port 8099, zprávy UTF-8 ukončené `\r\n`):

```text
→ FUNCTION SetText Input=877bb3e7-58bd-46a1-85ce-0d673aec6bf5&SelectedName=Clock.Text&Value=12%3A45\r\n
← FUNCTION OK Completed\r\n
← FUNCTION ER <chybová zpráva>\r\n
```

- Další požadavek pošli až po odpovědi na předchozí. Vstup adresuj přes `key`. U GT titulků má text příponu `.Text`, obrázek `.Source`. Hodnoty kóduj procenty, mezera je `%20`, nikdy `+`.
- Další funkce: `SetImage`, `SetTextVisibleOn/Off`, `SetImageVisibleOn/Off`, `SetTextColour`, `PauseRender` a `ResumeRender`.
- Web Controller musí být zapnutý. Zkoušej s výchozím zabezpečením vMixu; jeho
  vypnutí uveď jen jako krok při potížích. Discovery samo hodnoty neposílá.

Později podle potřeby: HTTP SetText jako další transport, proud změn přes
WebSocket nebo SSE, průhledná HTML stránka pro vstup Web Browser a obecný
TCP/UDP výstup.

## 13. Uživatelské rozhraní

Webová aplikace v češtině (texty na jednom místě kvůli případnému překladu), tmavý vzhled, čitelná z odstupu. Backend ji servíruje na `http://127.0.0.1:<port>`.

### 13.1 Nastavení

Stejný myšlenkový model jako reference: **1. Zdroj → 2. Výstup → 3. Pole**.

- **Zdroj**: typ, výběr ze seznamu, živý náhled, rozlišení a fps.
- **Výstup**: cesta k XML souboru, náhled aktuálního obsahu, čas posledního zápisu, testovací data, adresa HTTP varianty.
- **Rohy**: tažení 4 bodů, lupa pro přesnost, posun šipkami (se Shiftem po 10 px), okamžitý náhled narovnaného obrazu.
- **Pole**: přidání → nakreslení obdélníku v narovnaném obraze. Seznam polí s živou hodnotou, stavem a jistotou. Panel nastavení pole. Miniatura výřezu, který jde do OCR.
- **Kotvy** pro hlídání rozložení.

Náhled posílej jako MJPEG (nejvýš 10–15 snímků za sekundu, zmenšený), nezávisle na rychlosti zpracování. Překryvy (rohy, pole, kotvy) kresli v prohlížeči.

### 13.2 Živý provoz

- Velké hodnoty všech polí, u každého stav (✓ nová, = beze změny, ! zamítnuto,
  ∅ prázdné, ruka = hold) a stáří posledního platného čtení. Stav nesmí být
  sdělen jen barvou.
- Semafor: zdroj, zpracování (fps, latence), kotvy, zápis XML. Jakýkoli problém je červený pruh se srozumitelnou větou a návrhem, co udělat.
- Ovládání: hold nebo přepsání pole, **Pauza výstupu**, **Vyprázdnit hodnoty**.
- Log událostí (změny, zamítnutá čtení, chyby zápisu).
- Nastavení je v živém režimu zamčené proti nechtěnému posunu pole.

### 13.3 Profily a diagnostika

- Uložit, načíst, duplikovat, export a import profilu. Průběžné automatické ukládání.
- **Nahrát vzorek**: uloží N sekund narovnaného obrazu a log čtení jako testovací data do `samples/`.
- **Diagnostický balíček**: snímek, výřezy, profil a logy v jednom zipu.

### 13.4 Přístup a zabezpečení

Výchozí vazba jen na `127.0.0.1`. Přístup ze sítě (tablet, druhý PC) se zapíná výslovně a je chráněný tokenem nebo PINem, protože UI ovládá grafiku ve vysílání.

## 14. Konfigurace, CLI, provoz a výkon

### 14.1 Konfigurace

- Adresář `%APPDATA%\TabuleOCR\` (`profiles\*.json`, `settings.json`, `logs\`, `samples\`), přepsatelný proměnnou prostředí.
- Profil má `schema_version` a migrace. Zápis je atomický. Poškozený soubor se zálohuje a nástroj nastartuje s výchozím nastavením.

Ilustrativní tvar profilu (není závazný):

```json
{
  "schema_version": 1,
  "name": "hala-florbal",
  "source": { "type": "ndi", "name": "PC (vMix - KOM BOX)" },
  "geometry": { "corners": [[0.12, 0.08], [0.91, 0.10], [0.90, 0.86], [0.11, 0.83]], "rotate": 0 },
  "anchors": [{ "roi": [0.40, 0.33, 0.20, 0.07] }],
  "fields": [
    { "id": "Time", "label": "Čas", "type": "clock", "roi": [0.36, 0.05, 0.28, 0.22],
      "format": "mm:ss", "direction": "auto", "blank": "hold", "style": "no_leading_zero" },
    { "id": "scoreh", "label": "Góly domácí", "type": "number", "roi": [0.03, 0.72, 0.14, 0.24],
      "digits": [1, 2], "blank": "hold" },
    { "id": "scorea", "label": "Góly hosté", "type": "number", "roi": [0.83, 0.72, 0.14, 0.24],
      "digits": [1, 2], "blank": "hold" },
    { "id": "period", "label": "Třetina", "type": "period", "roi": [0.46, 0.42, 0.08, 0.14],
      "blank": "hold" },
    { "id": "penaltyh1", "label": "Trest domácí 1", "type": "clock", "roi": [0.03, 0.55, 0.14, 0.10],
      "format": "m:ss", "direction": "down", "blank": "clear" },
    { "id": "penaltya1", "label": "Trest hosté 1", "type": "clock", "roi": [0.83, 0.55, 0.14, 0.10],
      "format": "m:ss", "direction": "down", "blank": "clear" }
  ],
  "outputs": [
    { "type": "xml_file", "path": "C:\\vmix-data\\tabule.xml" }
  ]
}
```

### 14.2 CLI

`tabule-ocr --profile NAZEV --port 8787 --autostart --no-browser --log-dir CESTA`, dále `--self-test` (kontrola instalace bez UI: modely, knihovny, zápis do adresářů) a nástroje `tools/eval`, `tools/synth`, `tools/xml_reader_sim`. Víc instancí smí běžet vedle sebe s různým profilem a portem. V zabalené verzi se neotvírá okno konzole; stačí ikona v oznamovací oblasti s volbami Otevřít UI a Ukončit.

### 14.3 Spolehlivost

- Výjimka v pipeline nebo výstupu nesmí shodit proces. Vlákna hlídá supervizor a restartuje je. Pipeline má „tep", který hlídá watchdog.
- Výpadek zdroje: pole přejdou do stavu „zastaralé", publikované hodnoty se drží, UI hlásí problém, zdroj se sám připojuje znovu.
- Čisté ukončení na Ctrl+C a zavření. Zabraň uspání počítače za běhu.
- Logy: rotující aplikační log a denní log událostí v JSONL (změny hodnot, zamítnutá čtení, chyby zápisu) s časem.

### 14.4 Výkonové cíle

Ber je jako cíle. Změř je na produkčním PC a nahlas, když některý nejde splnit.

- Latence od příchodu snímku po dokončený zápis souboru: p95 do 80 ms při zdroji 25 fps a 8 polích.
- Zátěž: do zhruba 10 % CPU produkčního PC, paměť do 500 MB, žádné využití GPU.
- Náhled v UI nesmí zpomalit zpracování.

## 15. Testování a akceptační kritéria

### 15.1 Jednotkové testy

Formáty, normalizace, potvrzování, věrohodnost, politika prázdné hodnoty, transformace, sestavení XML (escapování, stálé pořadí, prázdná pole). Čisté funkce, tabulkové případy včetně okrajových (skóre 9 → 10, hodiny 0:00, konec trestu, nová perioda).

### 15.2 Syntetický generátor (`tools/synth`)

Vykreslí tabuli (bezpatkový font jako na fotkách, sedmisegment, bodová matice), přidá perspektivu, rozmazání, šum, změnu expozice, zakrytí, blikání a „cizí obsah" (animace). Odehraje časovou osu zápasu (běžící čas, góly, tresty, změna periody) a uloží video a pravdu jako JSONL.

### 15.3 Vyhodnocení (`tools/eval`)

Nad syntetickými i reálnými záznamy počítá:

- přesnost enginu na výřezech (přesná shoda),
- **počet špatně publikovaných hodnot**,
- podíl zachycených změn a zpoždění publikace (medián, p95),
- čas na snímek.

Pravda pro reálné záznamy: JSONL událostí (čas, pole, hodnota). Navrhni nejjednodušší způsob, jak ji Matěj vyrobí (nástroj předvyplní změny z OCR, člověk je jen opraví).

### 15.4 Simulátor čtenáře XML (`tools/xml_reader_sim`)

Chová se jako vMix: každých 100 ms soubor otevře, přečte a zavře, a to tak, že po dobu čtení brání jeho nahrazení. Test ověří, že čtenář nikdy neuvidí neúplné nebo neplatné XML, že v něm nikdy nechybí pole a že zapisovač po kolizi zápis dokončí. Pusť ho proti zapisovači s 10 změnami za sekundu aspoň několik minut.

### 15.5 Zátěžový test

Aspoň 3 hodiny ve smyčce nad záznamem: žádný pád, žádné mrtvé vlákno, paměť neroste o víc než desítky MB, latence se nezhoršuje, žádný zápis nevisí.

### 15.6 Akceptace MVP

- Čistý syntetický zápas: 0 špatně publikovaných hodnot, 100 % změn zachyceno.
- Reálné záznamy z haly: 0 špatně publikovaných hodnot, aspoň 99 % změn zachyceno, změna času v souboru do 100 ms od příchodu snímku (p95).
- Výkonové cíle z 14.4 a zátěžový test.
- Reálný vMix čte soubor 30 minut bez chybové hlášky a bez probliknutí prázdné hodnoty (ruční test).
- Po restartu nástroje je soubor do 3 s aktuální. Po návratu zdroje se čtení obnoví do 3 s.
- Matěj nastaví novou halu podle `OPERATOR.md` do 10 minut.
- **Stínový provoz**: nástroj běží při skutečném přenosu souběžně se stávající aplikací a zapisuje do vlastního souboru, který vMix nečte (nebo ho čte skrytý kopírovaný titulek). Logy se po zápase porovnají. Do ostrého provozu jde až po čistém stínovém zápase.

Když některé kritérium nejde splnit, neohýbej test. Ukaž čísla a navrhni, co s tím.

## 16. Milníky a pravidla práce

### 16.1 Milníky

Po každém milníku se zastav, ukaž výsledek (co běží, čísla z měření, co nefunguje) a počkej na schválení.

| Milník | Obsah | Hotovo, když |
|---|---|---|
| **0. Otázky, plán, ověření rizik** | Otázky ze sekce 17. `docs/PLAN.md`, `CLAUDE.md`, kostra repozitáře s nástroji. Tři jednorázové pokusy ve `spikes/`: PP-OCR nad Matějovými snímky tabule (přesnost a čas); skript, který 10 minut přepisuje XML desetkrát za sekundu, a Matěj ho zkusí číst reálným vMixem ze souboru i z HTTP adresy; příjem NDI (pokud je k dispozici Windows). | Krátká zpráva s výsledky pokusů a upravený plán. Žádný produkční kód. |
| **1. Jádro nad záznamem** | Zdroj soubor, geometrie, model polí, PP-OCR engine, formáty a validace, generátor a vyhodnocení, minimální stránka pro rohy a pole. | Nástroj přečte syntetický i reálný záznam a `tools/eval` vypíše metriky. |
| **2. Logika hodnot a XML** | Potvrzování, věrohodnost, prázdné hodnoty, kotvy, stav a události. Zapisovač XML, HTTP varianta, testovací data, simulátor čtenáře. | Záznam → XML → titulek v reálném vMixu se mění správně. 0 špatně publikovaných hodnot na testovacích datech. |
| **3. Živé zdroje a výkon** | NDI, capture zařízení, znovupřipojení, detekce změny, měření. | Cíle z 14.4 na produkčním PC, zátěžový test. |
| **4. Provozní UI** | Úplné nastavení, živý pohled, hold, pauza, profily, stavové hlášky, vzorky, diagnostika. | Nová hala do 10 minut podle návodu. |
| **5. Zabalení a ostrý test** | Balíček pro Windows, `--self-test`, `OPERATOR.md`, `MANUAL_TESTS.md`, stínový provoz. | Čistý stínový zápas. |
| **Fáze 2** | Položky z `BACKLOG.md` podle priorit, které určí Matěj. | |

### 16.2 Pravidla

- **Jazyk**: se mnou česky. Kód, identifikátory, komentáře a commity anglicky. Texty v UI česky.
- **Nejdřív plán.** Před každým milníkem krátký plán a seznam souborů, pak teprve kód.
- **Malé ověřené kroky.** Po každé změně spusť testy a lint. Netvrď, že něco funguje, dokud jsi to nespustil. Když něco ověřit nemůžeš (reálný vMix, NDI, produkční PC), řekni to a připrav postup pro Matěje do `MANUAL_TESTS.md`.
- **Nepřidávej nic navíc.** Nápady mimo aktuální milník zapisuj do `docs/BACKLOG.md`. Rozsah MVP je záměrně malý.
- **Fakta ověřuj.** Chování vMixu, API knihoven a modelů si ověř v aktuální dokumentaci, ne z paměti. Verze závislostí připni. Tvrzení v tomto zadání označená „ověř" opravdu ověř.
- **Rozhodnutí zapisuj** do `docs/DECISIONS.md` (co, proč, jaké byly alternativy). `CLAUDE.md` udržuj aktuální: příkazy pro spuštění, testy, sestavení, konvence.
- **Čistá implementace.** Scoreboard OCR nedekompiluj, neanalyzuj jeho soubory ani síťový provoz a nepřebírej jeho grafiku, texty ani formát presetů. Vycházej z veřejné dokumentace a z popisu chování. Kód ScoreSight (MIT) smíš číst i přebírat s uvedením licence.
- **Licence závislostí.** Veď `THIRD_PARTY.md`. Než by se nástroj šířil mimo firmu, upozorni na podmínky NDI SDK (cyndilib na ně výslovně odkazuje) a na uvedení ochranné známky NDI®.
- **Bezpečnost a soukromí.** Žádná telemetrie a žádná síťová volání kromě nastavených zdrojů a výstupů. Modely se stahují jen při sestavení.
- **Bezpečné selhání.** Při jakékoli pochybnosti se drží poslední platná hodnota. Neplatná hodnota neopustí proces.
- **Vývoj mimo Windows.** Jádro, testy, generátor a simulátor musí běžet i na macOS a Linuxu.

### 16.3 Největší rizika

| Riziko | Jak ho držet pod kontrolou |
|---|---|
| Blikání a moiré LED, přepaly | Doporučení ke kameře v návodu, časové slévání, maximum kanálů, vyhodnocení na reálných záznamech |
| Cizí obsah na video stěně | Kotvy rozložení (9.4) |
| Zakrytí tabule, zhasnutí | Brána kontrastu, politika prázdné hodnoty, potvrzování |
| Posun kamery | Varování z kotev, ve Fázi 2 stabilizace |
| Jednoznakové výřezy a dvojtečka | Okraj výřezu, doplnění oddělovače z formátu, případně glyph engine |
| vMix nepřečte soubor, který se zrovna přepisuje | Zápis jen při změně, dočasný soubor a náhrada, opakování, HTTP varianta, v krajním případě přímé API |
| Zátěž vedle vMixu | Detekce změny, dávky, omezení vláken, měření na produkčním PC |
| Neověřitelné části při vývoji | Simulátor čtenáře, ruční testy, stínový provoz |

## 17. Otevřené otázky pro Matěje

Zeptej se na ně hned na začátku, najednou. Co se nedozvíš, navrhni jako výchozí hodnotu a označ jako předpoklad.

1. **Sport a čas**: jaký sport (třetiny ukazují na florbal nebo hokej), počítá čas nahoru, nebo dolů, ukazuje tabule v poslední minutě desetiny? Ve stávajícím XML je čas `23:54`. Jak tabule počítá, že se na ni dostane víc než 20 minut (rozcvička, přestávka, průběžný čas)?
2. **Tresty**: pošli fotku tabule s běžícími tresty. Kolik trestů na tým tabule ukazuje (starší preset měl 2 + 2, dnešní XML má 1 + 1), je u nich jen čas, nebo i číslo hráče? Má se v grafice schovat podklad, když trest neběží?
3. **Cesta signálu**: jaké rozlišení a snímkovou frekvenci má SDI vstup, je prokládaný a jaká capture karta v PC je? Může vMix poslat vstup KOM BOX ven přes NDI nebo jako virtuální kameru (edice vMixu, volné výstupy)?
4. **Kde nástroj poběží**: na PC s vMixem, nebo na samostatném? Jaký procesor a kolik výkonu zbývá při přenosu? Pokud na samostatném, kam se má XML zapisovat (sdílená složka), nebo bude vMix číst HTTP adresu?
5. **vMix**: verze a edice. Na která pole titulku jsou dnes namapované sloupce `Time`, `penaltyh1`, `penaltya1` a kam se mají mapovat nové `scoreh`, `scorea`, `period`? Kde stávající XML soubor leží?
6. **Záznamy**: nahraješ 10–15 minut tabule (běžící čas, gól, trest, změna periody, ideálně i animace na stěně)? Bez toho nejde rozpoznávání pořádně vyladit.
7. **Vývojové prostředí**: na jakém systému vyvíjíš a máš při vývoji přístup k Windows s vMixem?
8. **Obsluha**: bude nástroj používat i někdo další? Je potřeba otevřít UI z jiného zařízení v síti?
9. **Šíření**: jen interní použití, nebo se má nástroj dostat i mimo firmu (ovlivní licence a balení)?
10. **Termín**: licence stávající aplikace na fotce platí do 8. 2. 2027. Má být vlastní nástroj do té doby připravený na ostrý provoz?

## 18. Zdroje

Scoreboard OCR (veřejná dokumentace):

- Úvod a funkce: https://scoreboard-ocr.com/start
- vMix (včetně XML výstupu): https://scoreboard-ocr.com/vmix
- XML výstup: https://scoreboard-ocr.com/xml
- Vstupy: https://scoreboard-ocr.com/inputs
- Formáty: https://scoreboard-ocr.com/format
- Symboly: https://scoreboard-ocr.com/symbols
- Automatic a One Digit: https://scoreboard-ocr.com/add_automatic_manual
- Inverze: https://scoreboard-ocr.com/invert
- Scripted output: https://scoreboard-ocr.com/scripted_output
- Výstupy a grafické systémy: https://scoreboard-ocr.com/graphics
- Kamera: https://scoreboard-ocr.com/recommended_camera_settings
- FAQ (latence, capture): https://scoreboard-ocr.com/faq
- Služba a příkazová řádka: https://scoreboard-ocr.com/service
- Požadavky: https://scoreboard-ocr.com/hardware_and_software_requirements
- Changelog: https://scoreboard-ocr.com/changelog

vMix:

- Typy Data Sources (XML, JSON, soubor i adresa): https://sd4.vmix.com/help/DataSourcesTypes.html
- Fórum: vMix nečte soubor otevřený jiným programem: https://forums.vmix.com/posts/m71884-Datasources-error--process-cannot-access-file
- HTTP API: https://free.vmix.com/help29/DeveloperAPI.html
- TCP API: https://sdapi01.vmix.com/help/TCPAPI.html
- Funkce (SetText, SetImage…): https://img.vmix.com/help/ShortcutFunctionReference.html
- Web Controller a zabezpečení: https://www.vmix.com/help27/WebController.html

ScoreSight a modely:

- Repozitář: https://github.com/royshil/scoresight
- Vydání a změny: https://github.com/royshil/scoresight/releases
- Vyhodnocení OCR (PR #70): https://github.com/royshil/scoresight/pull/70
- PP-OCRv6 small rec (ONNX): https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx
- PP-OCRv6 tiny rec (ONNX): https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_onnx

Knihovny:

- cyndilib (NDI): https://cyndilib.readthedocs.io/en/latest/overview.html
- dxcam (zachytávání obrazovky, Fáze 2): https://pypi.org/project/dxcam/
