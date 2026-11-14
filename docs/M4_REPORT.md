# Zpráva z Milníku 4 – provozní UI

Stav k 14. 11. 2026. Ruční test s člověkem a reálnou halou (M4-A) čeká na Matěje.

## 1. Co je hotové

| Oblast (SPEC) | Stav |
|---|---|
| Nastavení: zdroj, rohy (lupa, šipky, Shift po 10 px), pole, kotvy, výstup (13.1) | ✓ |
| Živý pohled: velké hodnoty, stavy (✓ = … ! ∅ ⌛ ✋), semafor s větami, živý režim zamyká nastavení (13.2) | ✓ |
| Hold / uvolnit, pauza výstupu, vyprázdnit hodnoty, testovací data (12.1, 13.2) | ✓ |
| Log událostí česky | ✓ |
| Profily: načíst, uložit jako, export, import, průběžné ukládání (13.3) | ✓ |
| Nahrát vzorek: narovnané video + log čtení + profil, rovnou použitelné v `tools/eval` a `tools/labeler` (13.3) | ✓ |
| Diagnostický balíček ZIP: snímky, výřezy, profil, stav, události, logy, verze (13.3) | ✓ |
| Náhled MJPEG ≤ 15 sn./s, zmenšený, nezávislý na zpracování (13.1) | ✓ (+~9 % jádra při dvou náhledech) |
| Přístup ze sítě jen s PINem, výchozí 127.0.0.1 (13.4) | ✓ (CLI bez PINu odmítne `--host`) |
| CLI `--profile NAZEV`, `--host`, `--pin`, `--log-dir`, rotující `app.log` (14.2, 14.3) | ✓ |
| Návod `docs/OPERATOR.md`: známá hala, nová hala, během přenosu, hlášky | ✓ |

## 2. Ověření

- **Celý postup „nová hala“ jako integrační test** (`tests/test_new_hall_flow.py`): z prázdného profilu přes stejné API, které používá UI (zdroj → rohy → 8 polí → 3 kotvy → cesta k XML), se skutečným modelem PP-OCR. Do 2 s je v XML přesně to, co ukazuje tabule.
- UI ověřené v headless Chromu nad syntetickým zápasem, diagnostický ZIP (16 souborů) a stream MJPEG staženy přes HTTP.
- Ustálená spotřeba aplikace na Macu: 42 % jádra bez náhledu (z toho ~30 % dekódování videa ze souboru), 51 % se dvěma náhledy.
- 178 testů v Pythonu (+1 volitelný NDI), 12 ve frontendu. Ruff, pyright, oxlint a build jsou čisté.

## 3. Opravy po cestě

- **Lupa ukazovala špatné místo.** CSS `background-position` v procentech zarovnává obraz jinak, než je potřeba. Teď se počítá v pixelech podle skutečné velikosti náhledu a je to pokryté testem.
- **Překlad popisů událostí** nahrazoval „expected“ i uvnitř „unexpected“. Nahrazuje se od nejdelších frází, pokryté testem.
- **Ukazatel CPU skákal**, protože se průměroval jen přes 300 ms mezi dotazy UI. Teď se průměruje přes 2 s.

## 4. Co zbývá na Matějovi

Ruční test M4-A: nová hala podle návodu, se stopkami. Podle poznámek upravím návod a UI.
