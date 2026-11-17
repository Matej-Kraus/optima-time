# Backlog

Nápady mimo aktuální milník. Priority určuje Matěj.

## Fáze 2 (ze zadání, sekce 6)

- Přímé API vMixu (TCP 8099) jako druhý výstup, obrázky a viditelnost v titulku.
- Ruční pole (střely), symboly, odvozená pole se šablonami.
- Výřez obrazovky a síťové streamy jako zdroje, stabilizace obrazu, zpoždění výstupu.
- Glyph engine (jen pokud měření ukáže mezeru u PP-OCR).
- Živé HTML overlaye, obecný TCP/UDP/WebSocket výstup, pravidla sportů, víc zdrojů v jedné instanci.

## Nápady z Milníku 0

- Automatická volba tiny/small podle naměřeného času (jako „PP-OCR automatic" ve ScoreSight). Rozhodnout po měření na produkčním PC.
- Hybrid: tiny pro běžné čtení, small jen pro potvrzení neočekávané změny (skok skóre, nová perioda). Přesnost small tam, kde na ní záleží, za cenu tiny.

## Nápady z Milníku 1

- Starlette hlásí, že `TestClient` nad `httpx` je zastaralý a doporučuje `httpx2`. Vyměnit, až to bude v ekosystému stabilní (jen dev závislost).
- Generátor: font a rozložení podle skutečných fotek tabule, až budou v `samples/`.
- Labeler: pole, která jsou od začátku záznamu zhasnutá, zapisovat od snímku 0 (teď až po `blank_delay_ms`).
- UI: lupa a posun rohů šipkami (SPEC 13.1) patří do Milníku 4.

## Nápady z Milníků 2–5

- Instalátor (MSI/Inno Setup) se zástupcem na ploše a volitelným spuštěním s Windows. Teď je to ZIP.
- Narovnávat jen oblasti polí a kotev místo celé tabule (`warpPerspective` je teď největší položka CPU pipeline, ~1,4 ms na snímek).
- Hybrid tiny/small: small jen pro potvrzení neočekávané změny.
- Kotvy: při zakrytí kotvy se zastaví čtení všech polí. Šlo by vyžadovat shodu většiny kotev místo všech (rozhodnout podle reálných dat).
- NDI s nižší šířkou pásma kvůli paměti (~290 MB bere NDI SDK), jen pokud to nepoškodí čitelnost.
- Popisy pravidel v logu událostí posílat strukturovaně (kód + čísla) místo anglické věty, překlad v UI.

## Nápady po Milníku 5

- ~~Ruční jas, kontrast a gama obrazu v profilu haly~~ hotovo (D36). Původní poznámka: (dotaz kolegy, 2026-11-14). Posuvníky v Nastavení (krok 1 nebo 5. Pokročilé) s živým náhledem narovnané tabule a výřezů, uložené v profilu, použité před čtením i před sejmutím kotev. Pozor: změna po sejmutí kotev zhorší jejich shodu (vzory sejmout znovu, nebo úpravu kotvám nedávat). Nezachrání přepálené číslice, to musí vyřešit expozice kamery. Teď se obraz upravuje automaticky (nejjasnější barevný kanál, normalizace výřezu v modelu, detekce změn odolná vůči jasu), proto rozhodnout až podle reálného záznamu z haly (issue #5): implementovat jen, když tmavý nebo bledý obraz prokazatelně způsobuje chyby čtení.

## Srovnání se Scoreboard OCR (jen veřejný web, 2026-11-17)

Hotovo z jejich funkcí: úprava obrazu (D36), SRT/RTSP/RTMP vstup (D37), zpoždění (D38), testovací data, „ignorovat prázdné“ (prázdná hodnota), názvy period, presety (profily), automatický start s profilem, tichá instalace, druhá instance (`--port`).

Chybí, podle užitku pro florbal s vMixem:
- **Přímý výstup do vMix API** (TCP 8099 / HTTP SetText), rychlejší než XML Data Source. Ze zadání Fáze 2. Až po ověření s vMixem v hale.
- **Odvozená pole a šablony výstupu** (jejich „scripted output“): spojit pole („0 : 2“), výchozí hodnota pro prázdné, text podle podmínky, jiný obrázek podle hodnoty (vMix SetImage), viditelnost prvku (trest běží → ukázat pozadí). Fáze 2.
- **Indikátory / symboly**: obdélník svítí = 1, nesvítí = 0, víc obdélníků = počet (time-out, fauly). Jednoduché, náš kontrastní práh to skoro umí.
- **Další výstupy**: TCP/UDP, WebSocket, CSV/TXT, CasparCG, OBS. Malé každý zvlášť, až bude potřeba.
- **Snímání obrazovky** jako zdroj.
- **Automatické nalezení tabule** (rohů).
- Nepotřebujeme: časomíra střelby (shot clock), formát hh:mm:ss (atletika), korekce kurzívy, automatická inverze (náš model čte i kurzívu, inverze je ruční), licence a připojení k internetu.

Máme navíc: kotvy proti animacím, potvrzování a věrohodnost hodnot, ruční držení a pauza, zámek nastavení, upozornění, seznam Připraveno k přenosu, kontrola názvů podle XML, diagnostika a vzorky, nástroje na vyhodnocení (eval, replay), přístup z tabletu s PINem, běh bez internetu.
