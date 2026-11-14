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
