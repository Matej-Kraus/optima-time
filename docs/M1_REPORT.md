# Zpráva z Milníku 1 – jádro nad záznamem

Stav k 14. 11. 2026. **Kritérium „Nástroj přečte syntetický i reálný záznam a `tools/eval` vypíše metriky“ je splněné jen pro syntetické záznamy.** Reálný záznam zatím není. Nástroje jsou na něj připravené (`tools/labeler`, `tools/eval`).

## 1. Co je hotové

| Část | Soubor | Testy |
|---|---|---|
| Formáty a oprava oddělovače (`mm:ss`, `m:ss`, `ss.d`, číslo, perioda, zarovnání) | `fields/formats.py` | 49 |
| Model pole a profilu (Pydantic, typy `clock` / `number` / `period`), atomické ukládání, migrace, záloha poškozeného souboru | `fields/models.py`, `config/` | 9 |
| Narovnání ze 4 rohů, otočení po 90°, výřezy s okrajem, převod bodů tam a zpět | `geometry.py` | 11 |
| PP-OCRv6 přes ONNX Runtime: dávky podle šířky, CTC s maskou znaků, jistota po znacích | `recognizers/` | 9 |
| Šeď jako maximum kanálů, brána kontrastu, odstranění prokladu | `preprocess.py` | 5 |
| Zdroj soubor/obrázek: smyčka, rychlost, „co nejrychleji“, skok na čas | `sources/` | 6 |
| Pipeline: brány → čtení → normalizace → validace formátu | `pipeline.py` | 6 |
| Běh na pozadí, API, CLI `optima-time run` | `runner.py`, `api/`, `cli.py` | 1 |
| Minimální stránka: rohy, kreslení polí, nastavení pole, živé hodnoty, výřezy | `frontend/` | 5 (vitest) |
| Generátor zápasů (LED stěna podle fotek, florbal, desetiny, tresty 2 + 2, animace gólu, zakrytí, volitelně proklad) | `tools/synth` | 5 |
| Vyhodnocení (přesnost výřezů, naivní publikace, zachycené změny, zpoždění, čas) | `tools/eval` | 7 |
| Předvyplnění pravdy pro reálný záznam a stránka na její opravu | `tools/labeler` | ruční běh |
| Stažení modelů s kontrolou SHA-256 a převodem na `characters.txt` / `config.json` | `scripts/fetch_models.py` | ruční běh |

Celkem 109 testů v Pythonu a 5 ve frontendu. Ruff, pyright, oxlint a build jsou čisté. UI jsem ověřil v headless Chromu: obraz, rohy, narovnaná tabule, rámečky polí a živé hodnoty.

## 2. Čísla (Mac M1, 2 vlákna ONNX Runtime)

Syntetické zápasy: 4 minuty, 25 fps, ~5 980 snímků, 8 polí, 1 248–1 250 změn hodnot. Každé pole se čte v každém snímku (detekce změny přijde v Milníku 3).

| Záznam | Model, šířka | Přesnost výřezů | Jisté špatné čtení | Zhasnuté → číslo | Zachycené změny | Zpoždění p95 | Čas na snímek (medián) |
|---|---|---:|---:|---:|---:|---:|---:|
| běžný | tiny, 160 | 100 % | 0 | 0 | 100 % | 0 ms | 15 ms |
| běžný | tiny, 320 | 100 % | 0 | 0 | 100 % | 0 ms | 26 ms |
| běžný | small, 160 | 100 % | 0 | 0 | 100 % | 0 ms | 66 ms |
| těžký | tiny, 160 | 99,85 % | 0 | 0 | 100 % | 0 ms | 15 ms |
| těžký | tiny, 320 | 100 % | 0 | 0 | 100 % | 0 ms | 25 ms |
| těžký | small, 160 | 100 % | 0 | 0 | 100 % | 0 ms | 67 ms |

- „Jisté špatné čtení“ znamená špatnou hodnotu, která prošla formátem i prahem jistoty. Zatím nenastala ani jednou.
- Jediné nedokonalé místo: tiny na těžkém záznamu četl malou tmavou `0` skóre hostů správně, ale s jistotou 0,42–0,49, tedy pod prahem 0,5 (53 snímků). Pole drželo hodnotu, nic špatného se nepublikovalo.
- **Špatně publikované hodnoty při naivní publikaci (bez potvrzování): 13–23 na zápas, všechny ve chvílích, kdy pole nebylo vidět** (animace gólu, člověk před tabulí). Na viditelné tabuli ani jedna. Přesně to řeší kotvy, potvrzování a věrohodnost v Milníku 2.
- Při zakrytí se napůl zakrytá číslice přečetla jako `31:41` místo `01:41` s jistotou 0,80. Práh jistoty tedy nestačí a kontrola věrohodnosti je nutná.
- Živý běh v aplikaci: 24,8 snímků za sekundu (zdroj 25), 9,6 ms na snímek, když jsou 4 pole zhasnutá a brána je přeskočí.

**Pozor:** syntetika je snazší než skutečnost (font je Arial, světlo je rovnoměrné, kamera nevibruje). Čísla ukazují, že řetězec funguje a že metriky měří správně, ne kolik to dá v hale.

## 3. Doporučení

- **Výchozí tiny se šířkou 160** (D5, D9): stejná přesnost jako small a 4× rychlejší. Small zůstává volbou. Definitivně rozhodne reálný záznam a měření na produkčním PC (M0-A).
- Práh jistoty 0,5 nechat a doladit na reálných datech. Jednoznaková pole (skóre, perioda) mohou potřebovat vlastní práh. Rozhodnu podle čísel, ne odhadem.

## 4. Opravy a zjištění po cestě

- Brána kontrastu stála 14 ms na snímek. Po změně zmenšování (D14) stojí asi 1 ms.
- Generátor měl chybnou pravdu u zakrytí: ruční seznam polí nezahrnoval čas, který zakrývala hlava osoby. Teď se zakrytí počítá z geometrie (D16) a vše jsem znovu vygeneroval a vyhodnotil.
- Metrika původně počítala jako chybu i správné přečtení skutečné hodnoty za zakrytím. Opraveno a pokryto testem.

## 5. Co chybí a co potřebuju

| Co | Stav |
|---|---|
| Vyhodnocení na reálném záznamu | čeká na záznam (do 2 týdnů). Postup: `tools.labeler` → oprava v `review.html` → `tools.eval` |
| Ruční testy M0-A/B/C na Windows s vMixem | čekají |
| Fotky a kopie XML do `samples/` | čekají |

## 6. Návrh na Milník 2

Podle plánu: potvrzování a věrohodnost (11.4), politika prázdné hodnoty (11.5), kotvy rozložení (9.4), stav a události, zapisovač XML s HTTP variantou, testovací data, simulátor čtenáře XML. Cíl: **0 špatně publikovaných hodnot** na obou syntetických zápasech (teď 13–23) a reálný záznam → XML → titulek ve vMixu.
