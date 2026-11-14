# Zpráva z Milníku 3 – živé zdroje a výkon

Stav k 14. 11. 2026. Měřeno na Macu M1 (8 jader). Produkční PC s vMixem je ruční test M3-A.

## 1. Výkon (`tools/bench`, 60 s v reálném čase, 25 fps, 8 polí, zápis XML)

| Měřítko | Cíl (SPEC 14.4) | Výsledek |
|---|---|---|
| Latence snímek → zapsaný XML soubor, p95 | ≤ 80 ms | **19,5 ms** (p50 16 ms, max 19 ms) |
| Zpracování | stíhat zdroj | 25,0 / 25 fps, 0 zahozených snímků |
| CPU | ≈ 10 % PC | **6,7 % stroje** (54 % jednoho jádra, z toho ~36 % dekódování 1080p videa ze souboru) |
| Paměť | ≤ 500 MB | 215 MB se souborem; **~500 MB s NDI** (D25) |
| GPU | žádné | žádné (ONNX Runtime jen CPU, OpenCV bez GPU) |

Jak se k tomu došlo:

| Krok | CPU pipeline na snímek |
|---|---:|
| každé pole v každém snímku (M2) | 18,3 ms |
| detekce změny (D22): OCR jen u 4,5 % pole-snímků | ~12 ms |
| šeď přes OpenCV a zmenšení před převodem | 12,2 ms |
| OpenCV na jednom vlákně (D23) | **6,1 ms** |

Přesnost zůstala stejná: 0 špatně publikovaných hodnot na běžném i těžkém zápase, stejné zachycení změn i zpoždění.

## 2. Zátěžový test (SPEC 15.5)

3 hodiny v reálném čase ve smyčce nad těžkým zápasem. **Běží, výsledek doplním.**

## 3. Co je hotové

| Část | Soubor | Testy |
|---|---|---|
| Společný základ živých zdrojů: vlákno, poslední snímek, znovupřipojení s rostoucí prodlevou | `sources/live.py` | 4 |
| NDI (cyndilib): výpis, příjem celých snímků (`allow_video_fields=False`), výpadek | `sources/ndi.py` | 1 (end-to-end proti lokálnímu vysílači, spouští se s `OPTIMA_TIME_NDI_TEST=1`) |
| Capture zařízení přes OpenCV, výpis se jmény, nalezení podle jména | `sources/device.py` | výpis ověřen na Macu |
| Detekce změny (podpis, rozdíl, povinná čtení) | `preprocess.py`, `pipeline.py`, `state.unsettled()` | 3 |
| Supervizor: restart mrtvého vlákna pipeline a výstupů, hlášení zaseknutí | `supervisor.py` | 3 |
| Zabránění uspání PC (Windows) | `power.py` | jen Windows (ruční) |
| API `/api/sources`, metriky procesu (CPU, paměť, vlákna) | `api/app.py`, `runner.py` | v testech API |
| UI: výběr zdroje (soubor / NDI / zařízení), CPU a paměť v semaforu | `frontend/` | 9 (vitest) |
| Měření výkonu a zátěžový test | `tools/bench` | ruční běh |

Ověřeno navíc: aplikace se za běhu přepnula ze souboru na NDI zdroj (lokální testovací vysílač) jen změnou profilu přes API, tak jak to dělá UI.

Celkem 171 testů v Pythonu (+1 volitelný NDI), 9 ve frontendu. Ruff, pyright, oxlint a build jsou čisté.

## 4. Co nejde ověřit bez Matěje

| Co | Ruční test |
|---|---|
| NDI z vMixu (rozlišení, proklad, fps, CPU) | M0-C, M3-A |
| Virtuální kamera vMixu a capture zařízení na Windows | M0-C, M3-A |
| CPU a paměť vedle běžícího vMixu na produkčním PC | M3-A |
| Zabránění uspání (Windows) | M3-A (PC se během 3h testu neuspí) |

## 5. Rizika a otevřené body

- **Paměť s NDI je na hraně cíle 500 MB.** Zhruba 290 MB si bere NDI SDK samo. Jde o pevnou hodnotu, ne o únik. Na Windows se to může lišit.
- **Detekce změny je naladěná na syntetice.** Pojistky (čtení nepotvrzených polí, povinné čtení 1× za sekundu) omezují nejhorší případ na zpoždění do 1 s, nikdy na špatnou hodnotu. Práh se doladí na reálném záznamu.
