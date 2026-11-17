# První reálný záznam: 1. třetina SLO–NOR (2026-11-17)

Záznam: `test_time/Casomira - 1 - Camera6 - [10-30-27] [10-54-39].mp4`, 1920×1080, 50 sn./s, 24,2 min, 2,1 GB (jen lokálně, není v gitu).
Pracovní kopie: `samples/real/casomira-1.mp4`, 1280×720, 25 sn./s, H.264, 39 MB (také mimo git, vyrobí ji ffmpeg z originálu).
Profil: `samples/real/profile.json`.

## Tabule

Velká LED stěna s hladkým písmem: čas (počítá nahoru 00:00 → 20:00), PERIÓDA a číslo třetiny, názvy týmů (SLO, NOR), skóre. Trest se ukáže oranžově vedle skóre týmu („01:17“ a bílé číslo hráče „10“). Mezi sledovanými prvky nejsou žádné animace přes tabuli. Síť je jen po stranách tabule, ne přes čísla.

## Nastavení (jako operátor)

- Rohy ručně, narovnání je rovné.
- Pole: Time, period, scoreh, scorea, penaltyh1, penaltya1 (polohu trestu domácích jsem odhadl zrcadlově, v této třetině domácí trest neměli).
- Kotvy navrhla aplikace sama: PERIÓDA a NOR, shoda 0,99 a 0,96.

## Výsledek (`uv run python -m tools.replay …`)

| | |
|---|---|
| Zpracování snímku | medián 4,4 ms, 95 % do 8,6 ms (720p, Mac M1) |
| Ztráta kotev | 0 snímků |
| Čas | 1 200 změn, všechny po 1 s, poslední 19:59 |
| Skóre | NOR 1 v 9:43,8 a 2 v 21:38,0 záznamu (sedí s náhledy), SLO 0 |
| Trest hostů | 02:00 v 12:14,7, po sekundách dolů, zmizel v 14:57,4 (121 změn) |
| Podezřelé změny (skok času, skóre dolů, skok skóre) | **0** |

Bez opravných zásahů a bez ladění prahů. Výchozí úprava obrazu (neutrální) stačila.

## Co ještě ověřit

- Formát času pro vMix: tabule ukazuje `00:00`, pole má „Jak je na tabuli“. Podle produkčního XML nastavit (třeba „Bez úvodní nuly“).
- Druhý trest současně (pozice druhého slotu) a trest domácích: v této třetině nenastaly.
- Číslo hráče u trestu (`10`) jde přidat jako další pole typu Číslo, pokud ho grafika chce.
- Zpoždění: změna na tabuli → zápis XML. Tady se měřit nedá (záznam nemá referenční čas), měří se v hale (M3-A).
