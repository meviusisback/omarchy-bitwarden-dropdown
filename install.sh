#!/usr/bin/bash
# install.sh - install/uninstall the Bitwarden dropdown (host-side).
# Idempotent: marker-keyed blocks, never duplicated. Usage: ./install.sh [uninstall]
#
# Write discipline (review findings): refuse symlinked targets (including .bak
# destinations and, on uninstall, the config files themselves), pre-check every
# file before the first write (no partial installs), backups + atomic renames
# preserving mode/owner, exact-line marker removal (no sed regex ranges, strip
# comparison so an indented marker still matches), grep -qFx -- for whole-line
# dash-leading markers, O_NOFOLLOW appends that refuse a symlink at OPEN time
# (no check->write TOCTOU) with a byte-wise trailing-newline guard, and ABSOLUTE
# tool paths so a poisoned PATH at install time cannot hijack the operation.
set -euo pipefail

MARKER="meviusisback.bitwarden-dropdown"
# dirname-style resolution works for both ./install.sh and `bash install.sh`
# (a bare ${BASH_SOURCE[0]%/*} yields the filename itself when there is no slash).
REPO_DIR="$(cd -- "$(/usr/bin/dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
HOME_DIR="${HOME:?HOME unset}"
BIN_DST="$HOME_DIR/.local/bin/bitwarden-dropdown"
RULES_DST="$HOME_DIR/.config/hypr/bitwarden.lua"
HYPR_LUA="$HOME_DIR/.config/hypr/hyprland.lua"
BIND_LUA="$HOME_DIR/.config/hypr/bindings.lua"
msg() { printf '%s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

BIND_BEGIN="-- BEGIN $MARKER"
BIND_END="-- END $MARKER"
# Lua-escape the bind path: a quote/backslash in $HOME must not break the string.
_ESCAPED_BIN="${BIN_DST//\\/\\\\}"
_ESCAPED_BIN="${_ESCAPED_BIN//\"/\\\"}"
BIND_LINE="o.bind(\"SUPER + SHIFT + B\", \"Toggle Bitwarden\", \"${_ESCAPED_BIN} toggle\")"
# A newline in $HOME would break out of the generated Lua line: refuse it.
case "$BIN_DST" in
  *$'\n'*|*$'\r'*) die "HOME contains a newline: refusing to write the keybind" ;;
esac
HOOK_LINE="-- Added by the $MARKER script: installs the Bitwarden dropdown window rules."
HOOK_DO="do local path = (os.getenv(\"XDG_CONFIG_HOME\") or os.getenv(\"HOME\") .. \"/.config\") .. \"/hypr/bitwarden.lua\"; local file = io.open(path, \"r\"); if file then file:close(); dofile(path) end end"

# Absolute tool paths (poisoned-PATH hardening, matches the toggle script).
for _t in /usr/bin/hyprctl /usr/bin/sleep /usr/bin/python3 /usr/bin/bash \
          /usr/bin/dirname /usr/bin/install /usr/bin/cmp /usr/bin/mkdir \
          /usr/bin/grep /usr/bin/cp /usr/bin/rm /usr/bin/head \
          /usr/bin/timeout; do
  [ -x "$_t" ] || die "missing trusted tool: $_t"
done
HYPRCTL=/usr/bin/hyprctl
SLEEP=/usr/bin/sleep
PYTHON3=/usr/bin/python3
TIMEOUT_BIN=/usr/bin/timeout

# Bounded, capped compositor reads for install/uninstall (a wedged or verbose
# compositor must never hang the installer or buffer unbounded output).
hypr_out() { "$TIMEOUT_BIN" -k 1 5 "$HYPRCTL" "$@" 2>/dev/null | /usr/bin/head -c 65536 || true; }

# Refuse symlinked write targets (an append/copy through a planted link lands
# elsewhere). Checks the file and its parent dir; call BEFORE any write.
refuse_link() {
  local p="$1" d
  [ ! -L "$p" ] || die "refusing to write $p: it is a symlink"
  d="$(/usr/bin/dirname -- "$p")"
  [ ! -L "$d" ] || die "refusing to write into $d: it is a symlink"
}

# Append fixed lines to a config. Refuses symlinks at OPEN time (O_NOFOLLOW
# makes a swapped-in symlink an open failure, not a redirected write -- this
# closes the check->write TOCTOU window, M6) and guarantees a trailing newline
# byte-wise (NUL-safe), replacing the old ensure_trailing_newline helper. Isolated
# python (-I -E -s) so no PYTHONPATH/usercustomize code can run at install time.
append_block() {
  local path="$1"; shift
  "$PYTHON3" -I -E -s - "$path" "$@" <<'PYEOF'
import os, sys
path, lines = sys.argv[1], sys.argv[2:]
try:
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CREAT, 0o644)
except OSError as e:
    print(f"Error: refusing to append to {path}: {e}", file=sys.stderr)
    raise SystemExit(1)
with os.fdopen(fd, "r+b", buffering=0) as h:
    h.seek(0, os.SEEK_END)
    end = h.tell()
    if end > 0:
        h.seek(end - 1)
        if h.read(1) != b"\n":
            h.write(b"\n")
    for l in lines:
        h.write(l.encode("utf-8", "surrogateescape") + b"\n")
PYEOF
}

do_install() {
  /usr/bin/bash -n "$REPO_DIR/bitwarden-dropdown" || die "toggle script has syntax errors"
  # Pre-check everything first: a missing config must abort BEFORE partial writes.
  for f in "$HYPR_LUA" "$BIND_LUA"; do
    [ -f "$f" ] || die "missing config (nothing written): $f"
  done
  for f in "$BIN_DST" "$RULES_DST" "$HYPR_LUA" "$BIND_LUA" "$HYPR_LUA.bak" "$BIND_LUA.bak"; do
    refuse_link "$f"
  done
  /usr/bin/mkdir -p "$HOME_DIR/.local/bin" "$HOME_DIR/.config/hypr"
  /usr/bin/install -m755 "$REPO_DIR/bitwarden-dropdown" "$BIN_DST"
  /usr/bin/cmp -s "$REPO_DIR/bitwarden-dropdown" "$BIN_DST" || die "copy to $BIN_DST failed to verify"
  /usr/bin/install -m644 "$REPO_DIR/hypr/bitwarden.lua" "$RULES_DST"
  /usr/bin/cmp -s "$REPO_DIR/hypr/bitwarden.lua" "$RULES_DST" || die "copy to $RULES_DST failed to verify"
  # Backups before the first append (only if no .bak exists yet); the .bak
  # destination symlink was already refused above.
  [ -e "$HYPR_LUA.bak" ] || /usr/bin/cp -p "$HYPR_LUA" "$HYPR_LUA.bak"
  [ -e "$BIND_LUA.bak" ] || /usr/bin/cp -p "$BIND_LUA" "$BIND_LUA.bak"
  # Whole-line marker match (-x): a stray mention inside a comment/string must
  # not suppress re-adding the block forever.
  if ! /usr/bin/grep -qFx -- "$HOOK_LINE" "$HYPR_LUA"; then
    append_block "$HYPR_LUA" "$HOOK_LINE" "$HOOK_DO"
    msg "hook added to hyprland.lua"
  else
    msg "hook already present"
  fi
  if ! /usr/bin/grep -qFx -- "$BIND_BEGIN" "$BIND_LUA"; then
    append_block "$BIND_LUA" "$BIND_BEGIN" "$BIND_LINE" "$BIND_END"
    msg "keybind added to bindings.lua"
  else
    msg "keybind already present"
  fi
  # Reload is best-effort: on hosts without a live Hyprland (SSH/TTY) it fails,
  # and that must NOT abort an otherwise-good install (writes already landed).
  "$TIMEOUT_BIN" -k 1 5 "$HYPRCTL" reload >/dev/null 2>&1 \
    || msg "warning: hyprctl reload failed (Hyprland unreachable?) - configs written, reload manually"
  "$SLEEP" 1
  errs="$(hypr_out configerrors)"
  [ -z "$errs" ] || msg "warning: hyprctl configerrors reports: $errs"
  # Harmless dispatcher probe: wrong form must error NOW (exit code checked),
  # right form is a no-op toggled straight back. Warning only.
  "$TIMEOUT_BIN" -k 1 5 "$HYPRCTL" dispatch 'hl.dsp.workspace.toggle_special("zzz-no-such")' >/dev/null 2>&1 \
    || msg "warning: dispatcher probe failed (Hyprland unreachable or non-Lua build?)"
  "$TIMEOUT_BIN" -k 1 5 "$HYPRCTL" dispatch 'hl.dsp.workspace.toggle_special("zzz-no-such")' >/dev/null 2>&1 \
    || msg "warning: dispatcher probe failed on toggle-back"
  # Single-occurrence assert: exactly one Bitwarden bind must exist after
  # install (a duplicate would toggle twice per keypress). hyprctl binds
  # exposes the bind description (not the exec path) under dispatcher __lua.
  binds="$(hypr_out binds | /usr/bin/grep -c 'Toggle Bitwarden' || true)"
  [ "$binds" = "1" ] || msg "warning: expected exactly 1 bitwarden keybind, found $binds"
  msg "Installed. Press SUPER + SHIFT + B for Bitwarden."
}

do_uninstall() {
  # Refuse symlinked configs BEFORE any rewrite (an os.replace through a
  # planted symlink would replace the link and break a dotfiles setup).
  for f in "$BIN_DST" "$RULES_DST" "$HYPR_LUA" "$BIND_LUA"; do
    refuse_link "$f"
  done
  # Marker validation + config rewrite FIRST (atomic, mode-preserving), so an
  # unterminated/indented marker block aborts BEFORE we delete the binary (no
  # half-uninstalled state pointing at a missing executable).
  "$PYTHON3" -I -E -s - "$BIND_LUA" "$HYPR_LUA" <<'PYEOF'
import os, sys
bind_path, hook_path = sys.argv[1], sys.argv[2]

def _atomic_write(path, lines):
    # Preserve the original mode/owner; write via O_EXCL|O_NOFOLLOW temp + rename.
    try:
        st = os.stat(path)
        mode = st.st_mode & 0o7777
    except OSError:
        mode = 0o644
    tmp = path + ".tmp"
    try:
        os.unlink(tmp)  # stale interrupt leftover; unlink never follows links
    except OSError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as h:
        h.writelines(lines)
    os.chmod(tmp, mode)
    os.replace(tmp, path)

def rewrite(path, keep):
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as h:
            lines = h.readlines()
    except FileNotFoundError:
        return False
    kept = [ln for ln in lines if keep(ln)]
    if len(kept) == len(lines):
        return False
    _atomic_write(path, kept)
    return True

BEGIN = "-- BEGIN meviusisback.bitwarden-dropdown"
END = "-- END meviusisback.bitwarden-dropdown"

def drop_block(path):
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as h:
            lines = h.readlines()
    except FileNotFoundError:
        return False
    out, skip, changed = [], False, False
    for ln in lines:
        s = ln.strip()  # strip (not rstrip) so an indented marker still matches
        if not skip and s == BEGIN:
            skip, changed = True, True
            continue
        if skip and s == END:
            skip = False
            continue
        if not skip:
            out.append(ln)
    if skip:
        raise SystemExit(f"unterminated marker block in {path}; leaving it alone (nothing removed)")
    if not changed:
        return False
    _atomic_write(path, out)
    return True

hook_exact = {
    "-- Added by the meviusisback.bitwarden-dropdown script: installs the Bitwarden dropdown window rules.",
    "do local path = (os.getenv(\"XDG_CONFIG_HOME\") or os.getenv(\"HOME\") .. \"/.config\") .. \"/hypr/bitwarden.lua\"; local file = io.open(path, \"r\"); if file then file:close(); dofile(path) end end",
}
print("keybind block removed:", drop_block(bind_path))
print("hook lines removed:", rewrite(hook_path, lambda ln: ln.strip() not in hook_exact))
PYEOF
  # Only delete the binary + rule AFTER the configs validated/rewrote cleanly.
  /usr/bin/rm -f "$BIN_DST" "$RULES_DST"
  "$TIMEOUT_BIN" -k 1 5 "$HYPRCTL" reload >/dev/null 2>&1 \
    || msg "warning: hyprctl reload failed (Hyprland unreachable?) - reload manually"
  msg "Uninstalled."
}

case "${1:-install}" in
  install) do_install ;;
  uninstall) do_uninstall ;;
  *) die "usage: install.sh [install|uninstall]" ;;
esac
