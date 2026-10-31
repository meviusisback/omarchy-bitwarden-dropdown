<div align="center">

# Bitwarden dropdown

**La vera app desktop di Bitwarden come dropdown in sovraimpressione: icona scudo sulla barra e toggle con `SUPER + SHIFT + B` ovunque tu sia.**

[![Release](https://img.shields.io/github/v/release/meviusisback/omarchy-bitwarden-dropdown)](https://github.com/meviusisback/omarchy-bitwarden-dropdown/releases)
[![License: MIT](https://img.shields.io/github/license/meviusisback/omarchy-bitwarden-dropdown)](LICENSE)
![Linux](https://img.shields.io/badge/linux-supported-1793d1)

![Bitwarden dropdown](preview.png)

</div>

## Perché esiste

Il password manager serve ovunque, ma aprire la sua finestra spezza il flusso:
workspace occupato, focus perso, finestra da richiudere. Questo plugin tratta
l'app ufficiale di Bitwarden come un dropdown: una pressione di tasti e compare
sopra quello che stai facendo, un'altra e sparisce. Login, sync e ricerca
restano nell'app ufficiale — niente CLI, niente token di sessione nel plugin.

## Cosa fa

- **Widget barra** (`BarWidget.qml`, plugin `meviusisback.bitwarden`): bottone
  scudo, click = toggle, stato rilevato ogni 2 s. Non tocca segreti: legge solo
  `VISIBLE=0/1` e non logga mai l'output raw.
- **Dropdown su special workspace**: la finestra di Bitwarden vive nascosta e
  appare in sovraimpressione quando la chiami, da qualunque workspace.
- **Keybind globale `SUPER + SHIFT + B`** → `~/.local/bin/bitwarden-dropdown toggle`.
- **Chiusura semplice**: premi di nuovo `SUPER + SHIFT + B`. Se hai
  `special_fallthrough` attivo (lo imposta già il plugin dropdown-terminal),
  basta anche cliccare fuori.
- **Nessun segreto toccato**: login e vault restano nell'app di Bitwarden. Lo
  script chiede solo al compositor se la finestra esiste e la sua posizione.

## Installazione

```bash
omarchy plugin add https://github.com/meviusisback/omarchy-bitwarden-dropdown.git
omarchy plugin enable meviusisback.bitwarden
cd ~/.config/omarchy/plugins/meviusisback.bitwarden
./install.sh
```

`install.sh` è idempotente (blocchi marcati, mai duplicati) e installa solo
regola finestra + keybind:

1. copia `bitwarden-dropdown` in `~/.local/bin/` (modo 755, verificato con `cmp`)
2. copia `hypr/bitwarden.lua` in `~/.config/hypr/`
3. aggiunge l'hook di caricamento in `~/.config/hypr/hyprland.lua`
4. aggiunge il keybind `SUPER + SHIFT + B` in `~/.config/hypr/bindings.lua`
5. `hyprctl reload` + controllo `hyprctl configerrors` + assert 1 solo bind

Poi posiziona il widget: `omarchy bar put meviusisback.bitwarden --section right`.

## Utilizzo

- `SUPER + SHIFT + B` ovunque: se l'app gira nascosta la mostra, se visibile
  la nasconde, se non gira la lancia.
- Click sullo scudo nella barra: stessa cosa.
- Per chiudere: di nuovo `SUPER + SHIFT + B`, oppure click fuori se hai
  `special_fallthrough` attivo.

## Requisiti

- Omarchy con Hyprland 0.56+ (sintassi dispatcher Lua)
- App desktop Bitwarden installata (`bitwarden` da pacman, comando
  `/usr/bin/bitwarden-desktop`). **Flatpak/AUR**: se usi un'altra
  installazione, cambia `LAUNCH` in cima a `bitwarden-dropdown` e la classe in
  `hypr/bitwarden.lua` se diversa (verificala con `hyprctl clients -j`).
- **"Close to tray" va disabilitato** in Impostazioni → App di Bitwarden,
  altrimenti chiudere la finestra la manda in tray senza mapparla e il toggle
  non la ripristina (esce con un warning non-fatale).
- Nerd Font per l'icona scudo nella barra

## Configurazione

- Keybind `SUPER + SHIFT + B` (default da manifest): vive in
  `~/.config/hypr/bindings.lua`, installato da `install.sh`.
- Comando di lancio: variabile `LAUNCH` in cima a `bitwarden-dropdown`
  (default `/usr/bin/bitwarden-desktop`).
- Classe finestra: `hypr/bitwarden.lua` (default `Bitwarden`, match
  case-insensitive).

## Come funziona

- `hypr/bitwarden.lua` — regola finestra: la classe `Bitwarden` va su
  `special:bitwarden`, flottante, centrata sotto la barra. La dimensione NON è
  forzata: è l'app Bitwarden a decidere la size e adattare il layout (forzare
  una box fissa 70%x50% tagliava il contenuto in basso).
- `bitwarden-dropdown` — script di toggle: se l'app gira nascosta la mostra,
  se visibile la nasconde, se non gira la lancia (`/usr/bin/bitwarden-desktop`,
  pacman). Usa la sintassi dispatcher Lua di Hyprland 0.56
  (`hl.dsp.workspace.toggle_special`); quella legacy `togglespecialworkspace`
  su questa build fallisce in silenzio.
- Sicurezza: il plugin **non legge** il vault, le password o la config di
  Bitwarden — solo lo stato finestra via compositor (`hyprctl`), con output
  cappato (4 MB) e deadline (`timeout -k`). Il toggle gira sotto `env -i` con
  allowlist esplicita (converge per ogni path di invocazione, incluso il
  keybind), binari assoluti, `python3 -I -E -s`. Il match della finestra è su
  `class` (case-insensitive) **e** verifica che `/proc/<pid>/cmdline` menzioni
  `bitwarden` (difende da class-spoof); `VISIBLE` è deciso strutturalmente da
  `specialWorkspace.name` (difende da rename-spoof). `flock` single-flight sul
  toggle (il keybind gira fuori dal processo QML).
- Differenza dal resto del marketplace: l'Omarchy marketplace ha già
  `io.github.elevate08.qs-bitwarden-cli` e `com.aktivesolutions.bw-vault`
  (bw CLI, verificato). Questo plugin è l'unico che tratta **l'app GUI di
  Bitwarden come dropdown** (stesso pattern del plugin Ente Auth).

Test (suite ermetica: stdlib, niente compositor/rete — estrae gli helper Python
dallo script reale e li guida con fixture JSON):

```bash
python3 -m unittest discover -s tests -v
```

Copre match di classe, charset-validation del workspace name, class-spoof via
/proc, parse strutturale di visibilità, rename-spoof e fixture ostili
(garbage, oversized, unicode).

## Rimozione

```bash
cd ~/.config/omarchy/plugins/meviusisback.bitwarden
./install.sh uninstall
omarchy plugin disable meviusisback.bitwarden
omarchy plugin remove meviusisback.bitwarden
```

Rimuove script, regola, hook e keybind, poi `hyprctl reload`. Resta solo un
backup `*.bak` se creato (cancellalo a mano se non serve).

## Licenza

MIT — vedi [LICENSE](LICENSE).
