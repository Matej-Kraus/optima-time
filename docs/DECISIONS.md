# Rozhodnutí

Formát: datum, co, proč, jaké byly alternativy. Novější nahoře. Položky označené **předpoklad** platí, dokud je Matěj nepotvrdí nebo nevyvrátí.

## 2026-11-14 – Doplnění po Milníku 5

### D33. Vlastní okno programu místo záložky v prohlížeči
Zabalená aplikace otevře UI ve vlastním okně (pywebview na Edge WebView2, který je ve Windows 10/11 předinstalovaný). Okno se nedá splést s jinými záložkami. Zavření okna se nejdřív zeptá, protože ukončí i výstup do vMixu. Ikona v liště okno znovu ukáže nebo aplikaci ukončí. Když WebView2 chybí nebo okno selže, otevře se jako dřív prohlížeč a aplikace běží dál. Prohlížeč a přístup z tabletu (`--host` s PINem) fungují dál. Zpracování ani UI se nemění, okno je jen jiný „rám“. Alternativy: Electron nebo Tauri (velké, druhý build systém), jen prohlížeč v režimu `--app` (závisí na nainstalovaném Edge/Chrome a hůř se ovládá zavření).

### D32. Automatický návrh kotev, ruční úprava
Runner drží 12 s historie narovnaného obrazu (60 malých šedých snímků). Kotvy se hledají jako místa, která v aspoň 60 % snímků vypadají jako jejich medián (jas smí kolísat o 15 %), mají výraznou strukturu (gradient) a neleží na polích. Písmena se spojí do slov, vyberou se až 3 nejsilnější, co nejvíc rozmístěné. Kotva se ořízne od pole, které těsně sousedí. Na syntetice: běžný zápas 55/57 oken všechny 3 nápisy, těžký 58/58. Ve 2 oknech, kde animace gólu pokryla většinu okna, vznikla kotva na textu „GÓL!“. Proto je výsledek jen návrh, operátor ho zkontroluje a upraví (posun, změna velikosti, šipky; vzor se sejme znovu). Návrh se spustí sám jen jednou, když profil má pole a žádné kotvy.

### D30. Trest přesunutý ze sousedního slotu se přijme po 2 čteních
Když skončí trest v prvním slotu, tabule do něj posune druhý trest, takže `penaltyh1` skočí nahoru (např. `0:01` → `0:21`). Skok na hodnotu, kterou právě publikuje sourozenecké pole stejné skupiny (`penaltyh1`/`penaltyh2`, skupina = id bez čísla na konci), je očekávaná změna a potvrdí se 2 shodnými čteními místo 400 ms. Jinak by se jedna hodnota přeskočila. Chybné čtení, které by se trefilo přesně do hodnoty souseda a dvakrát po sobě, je nepravděpodobné.

### D31. Instalátor pro jednoho uživatele (Inno Setup)
Instaluje do `%LOCALAPPDATA%\Programs\OptimaTime` bez administrátorských práv. Vytvoří ikonu na ploše, položky v nabídce Start (aplikace, kontrola instalace, složka s profily a logy, odinstalace) a volitelně spouštění s Windows. CI ho sestaví, potichu nainstaluje a spustí self-test nainstalované aplikace. ZIP zůstává jako alternativa.

### D29. Windows: čtenář může v okamžiku náhrady souboru dostat „přístup odepřen“
Zjištěno na Windows v CI (14. 11. 2026). Když čtenář otevírá XML ve chvíli, kdy ho `os.replace()` nahrazuje, Windows otevření odmítne (`PermissionError`, starý soubor čeká na smazání). Soubor přitom nikdy není rozepsaný, je jen na zlomek milisekundy nepřístupný. vMix by v tu chvíli nejspíš jen přeskočil jedno čtení (další je za 100 ms), ale může to hlásit jako chybu. Přesně o takové chybě je vlákno na fóru vMixu ze zadání. Simulátor čtenáře na Windows (CI) hlásí, jak často to nastává (`read_errors`). První měření (CI, 1 min, 10 zápisů/s, čtenář drží soubor 30 ms): 426 čtení, 0 odmítnutých otevření, 0 neúplných XML, zápis při kolizi čekal nejvýš 35 ms. Pokud to vMix v testu M2-A ukazuje jako chybu, výchozí cestou bude HTTP adresa `/data/values.xml`, která soubor nepoužívá. Zápis přímo do cílového souboru (bez náhrady) jako alternativa nepřichází v úvahu: čtenář by pak mohl vidět rozepsané XML.

### D27. Bez inverze barev
Zadání (9.2) zmiňuje úrovně, inverzi a automatickou inverzi po polích, které jsou potřeba pro klasické prahování v referenční aplikaci. PP-OCR čte syrový barevný výřez a zvládá světlé znaky na tmavém i tmavé na světlém. Brána kontrastu (rozpětí percentilů) i podpis pro detekci změny (normalizace) jsou na polaritu necitlivé. Inverze by tedy nic nepřinesla, a proto není. Kdyby přišel glyph engine (Fáze 2), přidá se s ním.

### D28. Časové slévání snímků jako volba, výchozí vypnuto
`preprocess.blend_frames` (1–5) a `blend_mode` (max proti blikání, mean proti šumu) nad narovnaným obrazem. Přidává zpoždění až (N − 1) snímků, proto je výchozí stav vypnuto (SPEC 9.2). Zapnout jen při viditelném blikání na reálné tabuli.

## 2026-11-14 – Milník 3

### D22. Detekce změny: normalizovaný podpis a nejhorší pruh
Podpis výřezu = maximum kanálů, zmenšení na výšku ~24 px, rozmazání, normalizace průměrem a odchylkou (blikání a expozice se neprojeví). Rozdíl = průměrný absolutní rozdíl v nejhorším svislém pruhu širokém zhruba jako jedna číslice. Měřeno na syntetice:

| | stejná hodnota (max) | změna (min) |
|---|---:|---:|
| běžný | 0,144 | 0,221 |
| těžký | 0,223 | 0,206 |

Práh je 0,15. Prostý průměr přes celý výřez rozložení nerozděloval (změna jedné číslice se ztratila v blikání). Pojistky: pole bez potvrzené hodnoty se čtou vždy a každé pole aspoň 1× za sekundu. Výsledek: OCR běží jen u 4,5 % pole-snímků, přesnost a zpoždění zůstaly stejné.

### D23. OpenCV na jednom vlákně
`cv2.setNumThreads(1)`. Malé obrázky z paralelních smyček OpenCV nic nezískají a na 8 jádrech jen spálí režii: spotřeba CPU pipeline klesla z 11,9 na 6,1 ms na snímek (čas na snímek 3,8 → 5,9 ms, hluboko pod 40 ms). Zbytek jader patří vMixu.

### D24. ONNX Runtime bez paměťové arény
`enable_cpu_mem_arena = False` ušetří asi 40 MB a rychlost čtení se nezmění (měřeno pro dávky 1, 4 a 8).

### D25. NDI: ~290 MB si bere samotné NDI SDK
Po připojení k NDI zdroji vyroste paměť o ~290 MB a dál je stálá (45 s měření, žádný růst). Počet bufferů `cyndilib` (`max_buffers`) na tom nic nemění, jde o knihovnu NDI. Celá aplikace s NDI má na Macu ~500 MB, tedy na hraně cíle ze zadání (500 MB). Změřit na produkčním PC (ruční test M3-A). Kdyby to vadilo: nižší šířka pásma NDI (`RecvBandwidth.lowest`) zmenší obraz, ale nejspíš i čitelnost číslic. Nejdřív měřit.

### D26. Výpis capture zařízení: `cv2-enumerate-cameras`
Vrací jména i indexy, které sedí na `cv2.VideoCapture` včetně backendu (DirectShow/MSMF/AVFoundation). Profil ukládá index i jméno a podle jména zařízení najde znovu, když se indexy posunou.

## 2026-11-14 – Milník 2

### D17. Kotvy: práh korelace 0,8
Dobré snímky dávaly skóre ≥ 0,96 (expozice 0,5–1,4×, posun ±8 px), náhodné animace ≤ 0,63. Původní návrh 0,6 propustil animaci se skóre 0,62. Nastavitelné v profilu, ověřit na reálné tabuli (moiré).

### D18. Po startu se navazuje na hodnoty v XML souboru
`BoardState` při startu převezme hodnoty, které v souboru zůstaly, a celý stav zapíše až s nimi. Jinak by se po restartu do grafiky na chvíli dostaly prázdné hodnoty. Logika polí je přesto bere jako „zatím nepotvrzené“, takže první čtení projde pomalejším potvrzením.

### D19. Hodiny po mezeře ve čtení smí „dohnat“ uplynulý čas
Když se pole nějakou dobu nečetlo (kotvy, zakrytí, nečitelné snímky), běžící hodiny se mezitím mohly posunout nejvýš o uplynulý čas, a to ve směru počítání. Takový posun je očekávaná změna, ale potvrzují ho 2 čtení. Bez toho se po každé animaci gólu čekalo 400 ms a ztrácely se změny. Pravidlo platí jen při známém směru počítání.

### D20. Logika hodnot dostává čas zvenku
`BoardState.update(..., now_ns)`: živě je to čas příchodu snímku, v `tools/eval` čas ve videu. Vyhodnocení totiž běží rychleji než reálný čas, takže s hodinami počítače by pravidla „400 ms“ a „2 s“ měřila nesmysl.

### D21. Metrika „špatně publikováno“
Špatně je hodnota, která na tabuli neplatila během poslední 1 s, není skutečnou hodnotou za zakrytím a není to „zatím nic“ při startu. Zpoždění se měří zvlášť (zachycené změny, zpoždění p95).

## 2026-11-14 – Milník 1

### D11. Oprava oddělovače: nejednoznačné čtení bez poslední hodnoty se zahodí
Dvě číslice za oddělovačem znamenají `mm:ss`, jedna `ss.d` (opraví `02.44` i `54:7`). Bez oddělovače se zkusí obě možnosti. Když projdou obě (např. `547` = `5:47` nebo `54.7`), vybere se ta bližší poslední platné hodnotě. Když poslední hodnota chybí, čtení se zahodí. Alternativa: vždy preferovat `mm:ss`. Zamítnuto, protože v poslední minutě by to dávalo špatné hodnoty s vysokou jistotou.

### D12. Typy polí jako diskriminované sjednocení (Pydantic)
`ClockField` / `NumberField` / `PeriodField` podle `type`, každý typ má jen svoje volby a vlastní `parse()` a `render()`. Alternativa: jeden plochý model se všemi volbami. Je jednodušší pro UI, ale profil by pak připouštěl nesmyslné kombinace.

### D13. Náhled v UI Milníku 1: JPEG dotazovaný 2,5× za sekundu, ne MJPEG
Pro minimální stránku na rohy a pole stačí. MJPEG (SPEC 13.1) přijde s plným UI v Milníku 4.

### D14. Brána kontrastu: zmenšení celočíselným poměrem
`contrast()` nejdřív zmenší výřez celočíselným poměrem průměrováním (INTER_AREA). OpenCV má pro takový poměr rychlou cestu: 0,05–0,18 ms místo 1–2,7 ms na pole. Průměrování na rozdíl od podvzorkování nepřehlédne body LED. Percentily se počítají přes `np.partition`.

### D15. Modely: převod `inference.yml` při sestavení
`scripts/fetch_models.py` zapíše `characters.txt` a `config.json`, takže aplikace za běhu nepotřebuje parser YAML. PyYAML je jen ve skupině `dev`.

### D16. Generátor: zakrytí počítané z geometrie
Pole zakrytá procházející osobou se v pravdě počítají z masky postavy promítnuté do souřadnic tabule, včetně okraje výřezu. Ruční seznam zakrytých polí byl chybný: hlava zakryla číslici času, který pravda vedla jako viditelný.

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
