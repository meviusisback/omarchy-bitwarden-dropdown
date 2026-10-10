import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar widget for the Bitwarden dropdown. Single shield button: click toggles
// the real Bitwarden app on special:bitwarden; the icon tracks visibility
// polled every 2s. No secrets ever reach this process: the poll prints
// VISIBLE=[01] and the toggle takes no input. The Bitwarden app owns the
// login and the vault -- this widget never touches credential files.
Panel {
  id: root

  moduleName: "meviusisback.bitwarden"
  ipcTarget: "meviusisback.bitwarden"
  manageIpc: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  property bool appVisible: false
  property bool busy: false

  function scriptPath() {
    // bitwarden-dropdown ships next to this file inside the plugin folder.
    // plugin dir comes from `omarchy plugin add` (fixed path, no spaces), so
    // plain file:// stripping is enough; no percent-decoding layer.
    return Qt.resolvedUrl("bitwarden-dropdown").toString().replace(/^file:\/\//, "")
  }

  // Every automatic process starts with a CLEARED environment plus an explicit
  // allowlist. DISPLAY is load-bearing: Bitwarden is Electron, and under
  // env -i without XDG_SESSION_TYPE it resolves X11 first -- no DISPLAY means
  // "Missing X server" and the app exits before mapping any window (verified
  // on host). LANG/LC_ALL keep the app in the user's locale (env -i drops it).
  // Residual: allowlisted values are visible in /proc cmdline to local users;
  // the socket dir itself (0700) remains the real boundary, and no secrets
  // pass here.
  readonly property var cliEnvPassthrough: [
    "XDG_RUNTIME_DIR", "HYPRLAND_INSTANCE_SIGNATURE", "WAYLAND_DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "LANG", "LC_ALL"
  ]

  function cliArgv(args) {
    const argv = ["/usr/bin/env", "-i", "HOME=" + (Quickshell.env("HOME") || "")]
    for (const name of root.cliEnvPassthrough) {
      const value = Quickshell.env(name) || ""
      if (value !== "") argv.push(name + "=" + value)
    }
    return argv.concat([root.scriptPath()], args)
  }

  // Single-flight poll: skip the tick while the previous poll is alive or a
  // toggle is running. The status verb answers in well under the 2s interval.
  function refresh() {
    if (statusProc.running || busy) return
    statusProc.running = true
  }

  function runToggle() {
    if (busy) return
    busy = true
    pollTimer.running = false
    actionProc.command = root.cliArgv(["toggle"])
    actionProc.running = true
  }

  Process {
    id: statusProc
    command: root.cliArgv(["status"])
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        // Strict shape only: anything else fails closed to inactive, and the
        // raw output is never logged or rendered anywhere.
        const line = (text || "").trim()
        root.appVisible = (line === "VISIBLE=1")
      }
    }
    stderr: StdioCollector {
    }
    // Recovery if the poll itself fails to spawn or exit: never wedge the icon.
    // Success keeps the parsed value; only a real failure clears to inactive.
    onExited: function(exitCode) {
      if (exitCode !== 0) root.appVisible = false
    }
  }

  Process {
    id: actionProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.busy = false
        pollTimer.running = true
        root.refresh()
      }
    }
    stderr: StdioCollector {
    }
    // stdout always closes at process end, but a failed spawn might not: the
    // exit signal is the authoritative busy-clear.
    onExited: {
      root.busy = false
      pollTimer.running = true
      root.refresh()
    }
  }

  // Watchdog: worst legitimate toggle under a degraded compositor is ~70s
  // (Electron launch wait ~60s worst case + bounded snapshot reads + show
  // retries with dispatch timeouts). Past 90s the action is treated as stuck:
  // terminate it and recover instead of leaving the button disabled with
  // polling suspended.
  Timer {
    id: toggleWatchdog
    interval: 90000
    repeat: false
    running: root.busy
    onTriggered: {
      actionProc.running = false
      root.busy = false
      pollTimer.running = true
      root.refresh()
    }
  }

  Timer {
    id: pollTimer
    interval: 2000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  IpcHandler {
    target: "meviusisback.bitwarden"
    function toggle(): void { root.runToggle() }
    function status(): void { root.refresh() }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    enabled: !root.busy
    text: "\uf132"
    tooltipText: root.appVisible
      ? "Bitwarden: shown (SUPER + SHIFT + B to hide)"
      : "Bitwarden: hidden (SUPER + SHIFT + B to show)"
    active: root.appVisible
    useActiveColor: true
    activeColor: root.accent

    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.runToggle()
    }
  }

  Component.onCompleted: root.refresh()
  Component.onDestruction: {
    statusProc.running = false
    actionProc.running = false
  }
}
