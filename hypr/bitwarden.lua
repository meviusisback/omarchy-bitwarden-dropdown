-- BEGIN meviusisback.bitwarden-dropdown (generated; do not edit)
-- Bitwarden as a dropdown overlay on its own special workspace.
-- The rule places the window at first map (70%x50% logical, centered). The
-- toggle script re-asserts this geometry on every show because Electron
-- restores its own saved size/position after the first map.
-- NOTE: move={"center","36"}'s y is effectively inert here (the window lands
-- vertically centered, matching the script's reassert); kept for parity with
-- the ente-auth template.
o.window("Bitwarden", {
  workspace = "special:bitwarden",
  float = true,
  size = { "(monitor_w*70/100)", "(monitor_h*50/100)" },
  move = { "center", "36" },
  animation = "slide top",
  border_size = 3,
  rounding = 8,
})
-- END meviusisback.bitwarden-dropdown
