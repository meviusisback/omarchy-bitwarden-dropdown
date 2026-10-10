-- BEGIN meviusisback.bitwarden-dropdown (generated; do not edit)
-- Bitwarden as a dropdown overlay on its own special workspace.
-- The rule assigns the workspace + float + centering at first map; the SIZE is
-- deliberately NOT forced -- Bitwarden (Electron) sizes/reflows its own window,
-- and forcing a fixed box (e.g. 70%x50%) clipped the app's content at the
-- bottom. The toggle script only shows/hides the workspace; it never resizes.
-- NOTE: move={"center","36"}'s y is effectively inert here (the window lands
-- vertically centered); kept for parity with the ente-auth template.
o.window("Bitwarden", {
  workspace = "special:bitwarden",
  float = true,
  move = { "center", "36" },
  animation = "slide top",
  border_size = 3,
  rounding = 8,
})
-- END meviusisback.bitwarden-dropdown
