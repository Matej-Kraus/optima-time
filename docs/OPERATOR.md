# Optima Time – návod pro obsluhu

Optima Time čte z kamery světelnou tabuli (čas, skóre, třetinu, tresty) a průběžně zapisuje hodnoty do XML souboru, který vMix čte jako Data Source. Grafika se tak mění sama.

**Zásada:** když si aplikace není jistá, drží poslední platnou hodnotu. Do vysílání nikdy nepošle nesmysl, nanejvýš hodnotu o chvíli později.

---

## A. Známá hala (1 minuta)

1. Spusť **Optima Time** (zástupce na ploše, nebo `optima-time run --profile NAZEV-HALY`). Otevře se prohlížeč s aplikací.
2. Nahoře v **Profil haly** vyber v rozbalovacím seznamu „Načíst…“ profil haly.
3. Zkontroluj semafor nahoře. Všechna čtyři světla mají být zelená: **Zdroj, Zpracování, Kotvy, Zápis XML**.
4. Zaškrtni **Živý režim** vpravo nahoře. Nastavení se zamkne proti nechtěnému posunu.

Když něco svítí žlutě nebo červeně, pod semaforem je věta, co se děje a co udělat (viz část D).

---

## B. Nová hala (do 10 minut)

### 1. Kamera (před přenosem)

- Pevný stativ, nic nesmí stínit výhled na tabuli.
- Co největší zoom, ale celá tabule v záběru.
- **Ruční expozice, raději tmavší obraz.** Svítící čísla nesmí být přepálená do bílé.
- Ruční ostření a frekvence 50 Hz (proti blikání LED).

### 2. Obraz z vMixu do aplikace (jednou na PC)

Capture kartu s kamerou drží vMix, proto aplikace bere obraz z vMixu přes **NDI**:

1. Ve vMixu: **Settings → Outputs / NDI / SRT**.
2. Nastav jeden z výstupů (Output 2/3/4) na vstup s tabulí (např. **KOM BOX**) a zapni u něj **NDI**. Případně použij volbu NDI pro jednotlivé vstupy, pokud ji tvoje verze má.
3. Potvrď.

> Záložní cesta: virtuální kamera vMixu (**External** výstup → zařízení „vMix Video External 2“).

### 3. Nový profil

1. Spusť aplikaci. V **Profil haly** klikni **Uložit jako nový…** a zadej název, např. `hala-ostrava-florbal`.
2. Od teď se každá změna ukládá sama.

### 4. Zdroj obrazu

1. V panelu **1. Zdroj a rohy tabule** zvol „Zdroj obrazu“ → **NDI (např. vstup z vMixu)**.
2. Klikni **Obnovit seznam** a vyber zdroj z vMixu (např. `PC (vMix - Output 2)`).
3. Do pár sekund se ukáže obraz a světlo **Zdroj** zezelená.
4. Vidíš-li na číslech „hřebeny“ (vodorovné roztřepení při změně), nastav **Odstranění prokladu** na „Prolnutí řádků“.

### 5. Rohy tabule

1. Přetáhni čtyři modré body na **rohy tabule**: levý horní, pravý horní, pravý dolní, levý dolní.
2. Při tažení se ukáže lupa. Na přesné doladění klikni na roh (zoranžoví) a posouvej **šipkami**, se **Shiftem** po 10 px.
3. Vpravo v **2. Narovnaná tabule** musí být tabule rovná, bez okolí.

### 6. Pole

Pro každou hodnotu na tabuli:

1. Klikni **Přidat pole** a táhnutím nakresli obdélník kolem hodnoty v narovnané tabuli.
   - Obdélník ať pokryje **všechny číslice i při nejdelší hodnotě** (např. `20:00`, skóre `10`).
   - Nech kolem znaků trochu místa, ale ať v něm není nic jiného (nápisy, rámečky).
2. V panelu **3. Pole** vpravo nastav:

| Na tabuli | Název v XML | Typ | Další volby |
|---|---|---|---|
| čas zápasu | `Time` | Čas | Desetiny v poslední minutě ✓, Tvar výstupu „Bez úvodní nuly (0:00)“ |
| skóre domácích | `scoreh` | Číslo (skóre) | |
| skóre hostů | `scorea` | Číslo (skóre) | |
| třetina | `period` | Třetina | |
| trest domácí 1, 2 | `penaltyh1`, `penaltyh2` | Čas | Prázdná hodnota „Vyprázdnit“, Tvar „Jak je na tabuli“ |
| trest hosté 1, 2 | `penaltya1`, `penaltya2` | Čas | Prázdná hodnota „Vyprázdnit“, Tvar „Jak je na tabuli“ |

**Názvy v XML musí sedět s tím, co je namapované ve vMixu.** Rozlišují se velká a malá písmena (`Time` není `time`).

3. Ve sloupci s hodnotou se během pár sekund ukáže přečtená hodnota se stavem **✓ nová** nebo **= beze změny**. U každého pole je i malý výřez, který jde do čtení. Číslice v něm musí být celé.

### 7. Kotvy (důležité)

Kotva je **nápis, který se na tabuli nikdy nemění**, např. `PERIÓDA`, `DOMÁCI`, `HOSTIA`. Podle kotev aplikace pozná, že video stěna ukazuje něco jiného (animace gólu, reklama). Pak nic nečte a drží hodnoty.

1. Klikni **Přidat kotvu** a táhnutím označ nápis. Přidej 2–3 kotvy na různých místech tabule.
2. Pod tabulí se ukáže „Kotva: ok“ a čísla blízko 1,0. Světlo **Kotvy** zezelená.

### 8. Výstup pro vMix

1. V **Výstup pro vMix** zadej **Cestu k XML souboru**, např. `C:\vmix-data\tabule.xml`.
   - Pokud měníš stávající aplikaci, použij **novou cestu**. Starý soubor nech, dokud není ověřený souběžný provoz.
2. Světlo **Zápis XML** zezelená a „Poslední zápis“ ukazuje čas.
3. Ve **vMixu** (jednou pro titulek):
   1. **Data Sources** → **+** → **XML** → vyber soubor (nebo zadej adresu `http://127.0.0.1:8787/data/values.xml`).
   2. **XPath:** `/root`.
   3. Interval obnovy (Auto Refresh / Update every): **100 ms**.
   4. V titulku (Title Editor / vlastnosti titulku) přiřaď polím titulku sloupce `Time`, `scoreh`, `scorea`, `period`, `penaltyh1` …
   5. Pole titulku napojené na Data Source se nesmí zároveň měnit jinak (ručně, jiným zdrojem).
4. **Zkouška:** klikni **Zapsat testovací data**. Titulek ve vMixu ukáže náhodné hodnoty. Pak **Zpět na živé hodnoty**.

### 9. Ostrý provoz

- Zaškrtni **Živý režim**.
- Před přenosem nahraj krátký vzorek (**Nahrát vzorek**, 60 s), hodí se pro pozdější ladění.

---

## C. Během přenosu

| Situace | Co udělat |
|---|---|
| Hodnota je špatně nebo se nečte | V řádku pole napiš správnou hodnotu a klikni **Držet**. Grafika ukazuje tvou hodnotu, dokud neklikneš **Uvolnit**. |
| Potřebuješ, aby se grafika nehýbala | **Pauza výstupu**. Grafika drží poslední hodnoty. Pak **Obnovit výstup**. |
| Je potřeba vyčistit hodnoty (po zápase) | **Vyprázdnit hodnoty** (ruční hodnoty zůstanou). |
| Gól, animace na stěně | Nic, aplikace to pozná podle kotev a hodnoty drží. |
| Někdo projde před kamerou | Nic. Hodnoty se drží a po chvíli se čtou dál. |

Stavy u polí:

| Stav | Význam |
|---|---|
| ✓ nová | hodnota se právě změnila |
| = beze změny | čte se stejná hodnota |
| … čeká na potvrzení | nová hodnota se ověřuje (neočekávaná změna se potvrzuje 0,4–3 s) |
| ! zamítnuto | čtení nebylo jisté; drží se poslední hodnota |
| ∅ prázdné | pole nesvítí (např. trest neběží) |
| ⌛ zastaralé | tabule teď není vidět (animace, výpadek); drží se poslední hodnota |
| ✋ drženo ručně | platí ruční hodnota |

---

## D. Když svítí žlutá nebo červená

| Hláška | Co udělat |
|---|---|
| Zdroj obrazu vypadl | Zkontroluj ve vMixu NDI výstup, kabel ke kameře, síť. Aplikace se připojuje sama znovu. |
| Zpracování nestíhá | Zavři náročné programy. Zkontroluj, že je zapnutá detekce změny (výchozí). |
| Tabule ukazuje něco jiného | Během animace normální. Když trvá dlouho, zkontroluj kotvy (nehýbe se kamera?). |
| Zápis XML selhává nebo je pomalý | Soubor má otevřený jiný program (Excel, antivir). Zkus jinou složku nebo HTTP adresu ve vMixu. |
| Výstup je pozastavený / testovací data | Klikni **Obnovit výstup** / **Zpět na živé hodnoty**. |
| Zpracování se zaseklo | Restartuj aplikaci. Hodnoty v souboru zůstanou a po startu se navážou. |

Při jakémkoli problému klikni na **Stáhnout diagnostický balíček** a pošli ho. Obsahuje snímek, výřezy, profil a logy.

---

## E. Spouštění z příkazové řádky

```text
optima-time run --profile hala-ostrava-florbal                 # profil podle jména
optima-time run --profile hala-ostrava --no-browser --port 8788  # druhá instance vedle první
optima-time run --profile hala --host 0.0.0.0 --pin 4821        # přístup z tabletu v síti, jen s PINem
```

Profily, logy a vzorky jsou v `%APPDATA%\OptimaTime\` (`profiles\`, `logs\`, `samples\`).
