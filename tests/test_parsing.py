#!/usr/bin/env python3
"""Hermetic tests for the bitwarden-dropdown Python parsing helper.

Extracts the CLIENTS_PY heredoc verbatim from the real `bitwarden-dropdown`
script (between the PY_SRC markers) and drives it with fixture JSON on stdin —
no compositor, no network, no Bitwarden app. Stdlib only.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "bitwarden-dropdown")
PY = sys.executable or "/usr/bin/python3"


def extract_helper():
    """Pull CLIENTS_PY out of the bash script between the PYEOF heredoc marks."""
    with open(SCRIPT, "r", encoding="utf-8") as h:
        src = h.read()
    m = re.search(
        r"<<'PYEOF' \|\| true\n(.*?)\nPYEOF\n", src, re.DOTALL
    )
    if not m:
        raise AssertionError("CLIENTS_PY heredoc not found between PYEOF markers")
    return m.group(1)


HELPER = extract_helper()


def run_helper(fixture, app="Bitwarden"):
    """Run the extracted helper against a fixture; returns (stdout, returncode)."""
    env = {"APP": app, "PATH": "/usr/bin"}
    if sys.platform == "darwin":  # pragma: no cover - CI convenience
        env["PATH"] = "/usr/bin:/bin"
    proc = subprocess.run(
        [PY, "-c", HELPER],
        input=fixture if isinstance(fixture, str) else json.dumps(fixture),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return proc.stdout.strip(), proc.returncode


def client(cls="Bitwarden", title="Bitwarden", ws=3, **extra):
    c = {"class": cls, "title": title, "workspace": {"id": ws, "name": str(ws)}}
    c.update(extra)
    return c


class TestExtraction(unittest.TestCase):
    def test_helper_extracted_nonempty(self):
        self.assertIn("import json", HELPER)
        self.assertIn("class", HELPER)

    def test_script_is_pure_ascii(self):
        """Guards pitfall 12e: a glyph literal must never creep into the script."""
        with open(SCRIPT, "rb") as h:
            data = h.read()
        self.assertTrue(all(b < 128 for b in data), "non-ASCII byte in script")

    def test_script_declares_fixed_constants(self):
        with open(SCRIPT, "r", encoding="utf-8") as h:
            src = h.read()
        self.assertIn('APP_CLASS="Bitwarden"', src)
        self.assertIn('WS="bitwarden"', src)


class TestClientMatch(unittest.TestCase):
    def test_real_shape_present(self):
        out, rc = run_helper([client()])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "PRESENT=1 WSW=3")

    def test_case_insensitive_bitwarden(self):
        out, _ = run_helper([client(cls="bitwarden")])
        self.assertEqual(out, "PRESENT=1 WSW=3")

    def test_case_insensitive_upper(self):
        out, _ = run_helper([client(cls="BITWARDEN")])
        self.assertEqual(out, "PRESENT=1 WSW=3")

    def test_mixed_case_widget_launch(self):
        # The widget launches under env -i (XDG_SESSION_TYPE dropped) — the
        # observed class on the host was exactly 'Bitwarden'; keep the exact
        # shape as a regression fixture.
        out, _ = run_helper(
            [{"class": "Bitwarden", "title": "Bitwarden", "workspace": {"id": 1, "name": "1"},
              "pid": 12345, "mapped": True, "hidden": False, "at": [10, 60], "size": [1792, 954]}],
            app="Bitwarden",
        )
        self.assertEqual(out, "PRESENT=1 WSW=1")

    def test_title_spoof_rejected(self):
        """A window whose TITLE contains 'Bitwarden' must never set PRESENT."""
        out, rc = run_helper([client(cls="kitty", title="ssh to Bitwarden server")])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_other_class_ignored(self):
        out, _ = run_helper([client(cls="foot"), client()])
        self.assertEqual(out, "PRESENT=1 WSW=3")

    def test_no_match(self):
        out, _ = run_helper([client(cls="foot")])
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_empty_list(self):
        out, _ = run_helper([])
        self.assertEqual(out, "PRESENT=0 WSW=none")


class TestHostileFixtures(unittest.TestCase):
    def test_garbage_json(self):
        out, rc = run_helper("not json {{{")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_non_list_json(self):
        """A JSON object (wrong root type) must fail closed, not crash."""
        out, _ = run_helper({"class": "Bitwarden"})
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_non_dict_entries(self):
        out, _ = run_helper(["junk", None, 42, client()])
        self.assertEqual(out, "PRESENT=1 WSW=3")

    def test_null_class(self):
        out, _ = run_helper([{"class": None, "title": "x", "workspace": {"name": "2"}}])
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_missing_workspace_field(self):
        out, _ = run_helper([{"class": "Bitwarden", "title": "x"}])
        self.assertEqual(out, "PRESENT=1 WSW=none")

    def test_null_workspace(self):
        out, _ = run_helper([{"class": "Bitwarden", "workspace": None}])
        self.assertEqual(out, "PRESENT=1 WSW=none")

    def test_workspace_not_dict(self):
        out, _ = run_helper([{"class": "Bitwarden", "workspace": "3"}])
        self.assertEqual(out, "PRESENT=1 WSW=none")

    def test_oversized_but_valid(self):
        """10k clients, match at the end — bounded work, correct result."""
        fixture = [client(cls="foot", ws=i) for i in range(10000)]
        fixture.append(client(cls="Bitwarden", ws=7))
        out, _ = run_helper(fixture)
        self.assertEqual(out, "PRESENT=1 WSW=7")

    def test_unicode_title_does_not_match(self):
        out, _ = run_helper([client(cls="kitty", title="Bitwarden \U0001F510 password")])
        self.assertEqual(out, "PRESENT=0 WSW=none")

    def test_app_env_missing_fails_closed(self):
        """APP unset -> want='' -> nothing matches (no accidental wildcard)."""
        out, rc = run_helper([client()], app="")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "PRESENT=0 WSW=none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
