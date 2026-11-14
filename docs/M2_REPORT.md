# Zpráva z Milníku 2 – logika hodnot a XML

Stav k 14. 11. 2026. Reálná data a vMix zatím nejsou k dispozici (Matěj je dodá na konci). Všechno je ověřené na syntetických zápasech a simulátoru. Ruční testy M2-A a M2-B jsou připravené v `MANUAL_TESTS.md`.

## 1. Výsledek

| Zápas (4 min, 8 polí) | Špatně publikováno (M1 naivně → M2) | Zachycené změny | Zpoždění p95 | Snímky zachycené kotvou |
|---|---:|---:|---:|---:|
| běžný | 23 → **0** | 99,38–100 % po polích | 0–80 ms | 446 |
| těžký | 15 → **0** | 99,38–100 % po polích | 0–80 ms | 418 |

- Zpoždění publikace je 0 ms u hodin a trestů (očekávaný tik se přijme hned). U skóre je 40 ms (2 čtení), u periody 80 ms (3 čtení).
- Jediná nezachycená změna na zápas: když skončí první trest a druhý se přesune do slotu 1, `penaltyh1` skočí nahoru (`0:01` → `0:21`). Taková změna je neočekávaná a potvrzuje se 400 ms, takže `0:21` se přeskočí a publikuje se rovnou `0:20`. Do grafiky nic špatného neodejde.
- Simulátor čtenáře XML (5 minut, zápis 10× za sekundu, emulované zámky Windows): 2 168 čtení, 0 neúplných nebo nekompletních XML, 2 883 zápisů, nejdelší zápis 52 ms (čekal na čtenáře), na konci soubor obsahoval poslední hodnoty.

## 2. Co je hotové

| Část | Soubor | Testy |
|---|---|---|
| Druh změny a co je potřeba k přijetí (SPEC 11.4), dohnání hodin po mezeře (D19) | `fields/plausibility.py` | v `test_confirm` |
| Kandidát a potvrzení v čase, prázdná hodnota (11.5), ruční hold (11.6), učení směru počítání | `fields/confirm.py` | 23 |
| Kotvy rozložení (9.4): šablona, normalizovaná korelace, návrat po N shodách | `guard.py` | 6 |
| Stav tabule, stavy polí, události do denního JSONL | `state.py` | 6 |
| XML ve tvaru dnešního souboru, pracovní vlákno výstupu, režimy živě / pauza / test | `outputs/` | 9 |
| Atomický zápis, opakování při zamčeném souboru, nahlášení zápisu delšího než 250 ms | `outputs/xml_file.py` | v `test_outputs` |
| Runner: stav, výstupy, výpadek zdroje, start z hodnot v souboru (D18) | `runner.py` | v `test_api` |
| API: `/data/values.xml\|json`, hold, pauza, testovací data, vyprázdnění, kotvy, události | `api/app.py` | 5 |
| Simulátor čtenáře XML (SPEC 15.4) | `tools/xml_reader_sim` | 1 (+ 5 min ručně) |
| Vyhodnocení přes skutečnou logiku, kotvy v syntetických profilech | `tools/eval`, `tools/synth/anchors.py` | 10 |
| UI: semafor s větami, publikované hodnoty, hold, výstup, kotvy, log, živý režim | `frontend/` | 9 (vitest) |

Celkem 177 testů v Pythonu a 9 ve frontendu. Ruff, pyright, oxlint a build jsou čisté. UI jsem ověřil v headless Chromu nad syntetickým zápasem se zápisem XML.

## 3. Co jsem po cestě opravil

- **Výchozí práh kotev 0,6 propustil animaci** (skóre 0,62), test to zachytil. Nový výchozí práh je 0,8 (D17).
- **`BoardState` při startu nejdřív zapsal prázdné hodnoty** a teprve potom převzal hodnoty ze souboru, takže by titulek probliknul. Opraveno (D18) a pokryto testem.
- **Pravidla „400 ms“ a „2 s“ měřila čas hodinami počítače**, takže ve vyhodnocení neplatila. Čas teď přichází se snímkem (D20).
- **Po animaci gólu se hodiny potvrzovaly 400 ms** a mezitím se ztrácely změny. Nově hodiny smí po mezeře dohnat uplynulý čas (D19).
- **Metrika měla dvě chyby:** počítala jako chybu „ještě nic“ při startu a pozdní hodnotu po dvou rychlých změnách. Opraveno a pokryto testy (D21).

## 4. Co nejde ověřit bez Matěje

| Co | Ruční test |
|---|---|
| vMix čte soubor 30 minut bez chyby a bez probliknutí, mapování sloupců, HTTP varianta | M2-A |
| Skutečné zámky Windows proti zapisovači | M2-B |
| Práh kotev na reálné LED tabuli (moiré, expozice) | M2-A + reálný záznam |
| Přesný tvar XML (deklarace, BOM, konce řádků) | kopie produkčního XML do `samples/` |

## 5. Na co si dát pozor

- **Kotvu zakryje i člověk.** Kotva pak zastaví čtení všech polí, i těch, která vidět jsou. Je to bezpečné, jen se hodnoty na chvíli zdrží. Na syntetice to vyšlo zhruba na 1,7 s.
- **Popisy pravidel v logu jsou zatím anglicky** („expected, 1 reads“). Do Milníku 4 je přeložím.
