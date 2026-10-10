-- BEGIN meviusisback.bitwarden-dropdown (generated; do not edit)
-- Bitwarden as a dropdown overlay on its own special workspace.
-- The rule only applies at the window's first map; the toggle script below
-- just shows/hides special:bitwarden, so geometry stays as placed here.
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
