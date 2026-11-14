# Optima Time

Čte z kamery světelnou tabuli ve sportovní hale (čas, skóre, třetinu, tresty) a průběžně zapisuje hodnoty do XML souboru, který vMix čte jako Data Source. Náhrada za komerční Scoreboard OCR: plně pod naší kontrolou, offline, bez licenčního serveru.

**Zásada:** když si není jistá, drží poslední platnou hodnotu. Do vysílání nikdy nepošle nesmysl, nanejvýš hodnotu o chvíli později.

## Rychlé vyzkoušení (macOS / Linux / Windows ze zdrojů)

```sh
uv sync
uv run python scripts/fetch_models.py           # modely PP-OCR (jednou)
cd frontend && npm ci && npm run build && cd ..  # webové UI (jednou)
uv run python -m tools.synth --out samples/synth/short --short   # umělý zápas (25 s)
uv run optima-time run --profile samples/synth/short/profile.json
```

Otevře se prohlížeč na http://127.0.0.1:8787. Kontrola instalace bez UI: `uv run optima-time --self-test`.

## Dokumentace

| Soubor | Pro koho | Co |
|---|---|---|
| [docs/OPERATOR.md](docs/OPERATOR.md) | obsluha | nastavení haly krok za krokem, provoz, hlášky |
| [docs/MANUAL_TESTS.md](docs/MANUAL_TESTS.md) | Matěj | ruční testy s vMixem a na produkčním PC, v pořadí |
| [docs/SPEC.md](docs/SPEC.md) | vývoj | zadání |
| [docs/PLAN.md](docs/PLAN.md), `docs/M*_REPORT.md` | vývoj | plán a výsledky milníků |
| [docs/DECISIONS.md](docs/DECISIONS.md) | vývoj | rozhodnutí a jejich důvody |
| [CLAUDE.md](CLAUDE.md) | vývoj | příkazy, struktura, konvence |
| [THIRD_PARTY.md](THIRD_PARTY.md) | vývoj | licence závislostí |

## Balíček pro Windows

`scripts/build_windows.ps1` na Windows: testy, sestavení (`OptimaTime.exe` bez konzole s ikonou v liště, `optima-time.exe` pro příkazovou řádku), self-test balíčku a ZIP.
