# Rozhodnutí

Formát: datum, co, proč, jaké byly alternativy. Novější nahoře. Položky označené **předpoklad** platí, dokud je Matěj nepotvrdí nebo nevyvrátí.

## 2026-11-13 – Milník 0

### D1. Název projektu `optima-time`
Balíček `optima_time`, příkaz `optima-time`, konfigurace `%APPDATA%\OptimaTime\`. Rozhodl Matěj (alternativa: `tabule-ocr` ze zadání).

### D2. Python 3.13, závislosti připnuté
Ověřeno 13. 11. 2026 na PyPI: všechny runtime závislosti mají wheely `cp313` pro Windows x64 i macOS arm64. Fallback na 3.12 není potřeba.

| Balíček | Verze |
|---|---|
| numpy | 2.5.4 |
| opencv-python-headless | 5.0.0.93 |
| onnxruntime | 1.32.0 |
| pydantic | 2.14.3 |
| fastapi | 0.162.7 |
| uvicorn | 0.54.0 |
| cyndilib | 0.1.3 (skupina `ndi`) |

OpenCV 5 je nová hlavní verze. Kdyby se objevila nekompatibilita s dokumentací nebo kódem ScoreSight (ten je na 4.x), zvážíme přechod na 4.x.

### D3. Modely PP-OCRv6 rec: připnuté revize ověřené
Hugging Face, stav 13. 11. 2026 (shodné s revizemi, které měřil ScoreSight):

- `PaddlePaddle/PP-OCRv6_tiny_rec_onnx` @ `2612ab37152ae0a677521bae4e1e3d4fb4cf7c30`, Apache-2.0, slovník 6 904 znaků
- `PaddlePaddle/PP-OCRv6_small_rec_onnx` @ `b8f84f0b80c529de40b4fbb3544b84fa7233a513`, Apache-2.0, slovník 18 708 znaků

`inference.yml` obou modelů potvrzuje: vstup BGR, `image_shape [3, 48, 320]`, dynamická šířka až 3200, `CTCLabelDecode`. Normalizace do [-1, 1] a doplnění nulami zprava odpovídá `resize_norm_img` z PaddleOCR (ověřeno v `ScoreSight src/ppocr_engine.py`). Bod ze zadání (10.2) je tím ověřený.

### D4. ONNX Runtime: 2 vlákna, spinning vypnutý (výchozí)
ScoreSight naměřil, že 2 vlákna zrychlí čtení asi 1,8× za zhruba 5 % CPU navíc a že vypnutý spinning neubírá rychlost a nepálí CPU mezi snímky. Nastavitelné. Alternativa: 1 vlákno (podle zadání 1–2). Definitivně rozhodne měření na produkčním PC.

### D5. tiny vs. small: výchozí tiny, definitivně po měření
Podle evaluace ScoreSight (2 320 reálných výřezů) je small o 5 bodů přesnější celkově a o 15 bodů na hodinách (94 % proti 79,5 % na Commons). Tiny je asi 5× rychlejší. Pokus A na Macu M1: small 24,8 ms na výřez (šířka 160, 1 vlákno), tiny 4,8 ms. Small by vedle vMixu bral asi 4,5× víc CPU. Výchozí je proto **tiny**. Rozhodnutí padne podle M0-A (produkční PC) a reálného záznamu.

### D9. Minimální šířka vstupu 160 místo 320 (k ověření)
Úzké výřezy (skóre, perioda) se doplňují nulami na minimální šířku. Při 160 je čtení 1,9× rychlejší a na syntetice bez ztráty přesnosti. 160 je dolní mez dynamických tvarů v `inference.yml`. ScoreSight měřil přesnost s 320, proto to ověřím na reálném záznamu. Parametr bude v profilu nastavitelný.

### D10. Brána kontrastu a práh jistoty už v Milníku 1
Zhasnutá pole model občas přečte jako číslici (`00`, `3`), vždy ale s jistotou nejvýš 0,41. Chyby s vysokou jistotou jsou hlavně chybějící nebo zaměněný oddělovač, a ty opraví normalizace podle formátu. Proto Milník 1 dostane bránu kontrastu, práh jistoty (výchozí 0,5) a normalizaci oddělovače, aby `tools/eval` měřil realistické chování.

### D6. NDI přes `cyndilib`
Wheel přibaluje knihovnu NDI runtime (`libndi.dylib` na macOS) a licenční texty NDI. Na macOS se `Finder` spustí bez chyby. Šíření mimo firmu se neplánuje (rozhodl Matěj), přesto licenci evidujeme v `THIRD_PARTY.md`.

### D7. XML Data Source ve vMixu: dokumentace nestačí
Oficiální stránka (help29, Data Sources Types) jen říká, že XML zdroj bere soubor i URL a potřebuje XPath. O pojmenování sloupců, minimálním intervalu, zamykání ani kódování nic neříká. Fórum vMixu potvrzuje doporučení vývojáře: soubor při změně uložit celý a nenechávat otevřený. Zbytek ověří pokus B na reálném vMixu.

### D8. Předpoklady z odpovědí Matěje (13. 11. 2026)
- Florbal, 3 třetiny. Směr času **auto**. **Desetiny v poslední minutě ano.** Čas nad 20:00 je rozcvička nebo přestávka.
- Tresty 2 + 2, jen čas, výstup přesně jak je na tabuli, prázdný prvek při neběžícím trestu.
- Prodloužení je perioda `4`. Třetina jde do XML jako číslo. Skóre bez úvodní nuly.
- Nástroj poběží na stejném PC jako vMix (4K/Pro/Max). Signál 1080i50.
- **Předpoklad:** `Time` má styl bez úvodní nuly (`0:00`), jako dnes posílá referenční aplikace.
- **Předpoklad:** XML v UTF-8 s deklarací, dokud nebude v `samples/` skutečný soubor.
