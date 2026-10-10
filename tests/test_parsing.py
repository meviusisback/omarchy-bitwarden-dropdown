#!/usr/bin/env python3
"""Hermetic tests for the bitwarden-dropdown Python helpers.

Extracts CLIENTS_PY and MONITORS_PY verbatim from the real `bitwarden-dropdown`
script (between the PYEOF heredoc marks) and drives them with fixture JSON on
stdin — no compositor, no network, no Bitwarden app. Stdlib only.

The class-spoof guard reads /proc/<pid>/cmdline; tests point PROC_ROOT at a
temp fixture tree so it stays hermetic.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "bitwarden-dropdown")
PY = sys.executable or "/usr/bin/python3"


def extract_helpers():
    """Pull CLIENTS_PY and MONITORS_PY out of the bash script between PYEOF marks."""
    with open(SCRIPT, "r", encoding="utf-8") as h:
        src = h.read()
    blocks = re.findall(r"read -r -d '' (\w+) <<'PYEOF' \|\| true\n(.*?)\nPYEOF\n", src, re.DOTALL)
    found = {name: code for name, code in blocks}
    for req in ("CLIENTS_PY", "MONITORS_PY"):
        if req not in found:
            raise AssertionError(f"{req} heredoc not found between PYEOF markers")
    return found["CLIENTS_PY"], found["MONITORS_PY"]


CLIENTS_PY, MONITORS_PY = extract_helpers()


def run_clients(fixture, app="Bitwarden", proc_root=None):
    """Run the CLIENTS_PY helper against a fixture; returns (stdout, returncode)."""
    env = {"APP": app, "PATH": "/usr/bin"}
    if proc_root:
        env["PROC_ROOT"] = proc_root
    proc = subprocess.run(
        [PY, "-I", "-E", "-s", "-c", CLIENTS_PY],
        input=fixture if isinstance(fixture, str) else json.dumps(fixture),
        capture_output=True, text=True, env=env, timeout=10,
    )
    return proc.stdout.strip(), proc.returncode


def run_monitors(fixture, wsfull="special:bitwarden"):
    """Run the MONITORS_PY helper against a fixture; returns (stdout, returncode)."""
    env = {"WSFULL": wsfull, "PATH": "/usr/bin"}
    proc = subprocess.run(
        [PY, "-I", "-E", "-s", "-c", MONITORS_PY],
        input=fixture if isinstance(fixture, str) else json.dumps(fixture),
        capture_output=True, text=True, env=env, timeout=10,
    )
    return proc.stdout.strip(), proc.returncode


def client(cls="Bitwarden", title="Bitwarden", ws=3, pid=None, **extra):
    c = {"class": cls, "title": title, "workspace": {"id": ws, "name": str(ws)}}
    if pid is not None:
        c["pid"] = pid
    c.update(extra)
    return c


def monitor(active="3", special_id=0, special_name="", **extra):
    m = {
        "name": "HDMI-A-1",
        "activeWorkspace": {"id": 3, "name": active},
        "specialWorkspace": {"id": special_id, "name": special_name},
    }
    m.update(extra)
    return m


def make_proc_fixture(root, pid, cmdline):
    """Create /<root>/<pid>/cmdline with NUL-separated bytes (like the real proc)."""
    d = os.path.join(root, str(pid))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "cmdline"), "wb") as h:
        h.write(cmdline)


class TestExtraction(unittest.TestCase):
    def test_helpers_extracted_nonempty(self):
        self.assertIn("import json", CLIENTS_PY)
        self.assertIn("class", CLIENTS_PY)
        self.assertIn("import json", MONITORS_PY)
        self.assertIn("specialWorkspace", MONITORS_PY)

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
        self.assertIn('WSFULL="special:bitwarden"', src)

    def test_script_never_evals_clients_state(self):
        """The compositor-derived output must be consumed via read, not eval."""
        with open(SCRIPT, "r", encoding="utf-8") as h:
            src = h.read()
        self.assertNotIn('eval "$(clients_state)"', src)
        self.assertIn("read -r PRESENT WSW", src)

    def test_script_uses_clean_env_reexec(self):
        """Keybind path must converge to the widget's env -i (hostile PATH/PYTHONPATH)."""
        with open(SCRIPT, "r", encoding="utf-8") as h:
            src = h.read()
        self.assertIn("BITWARDEN_DROPDOWN_CLEAN", src)
        self.assertIn("/usr/bin/env -i", src)

    def test_script_absolute_shebang(self):
        """#!/usr/bin/env bash resolves bash via PATH (hijackable); must be absolute."""
        with open(SCRIPT, "r", encoding="utf-8") as h:
            first = h.readline().strip()
        self.assertEqual(first, "#!/usr/bin/bash")


class TestClientMatch(unittest.TestCase):
    def test_real_shape_present(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, rc = run_clients([client(pid=4242)], proc_root=root)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "1 3")

    def test_case_insensitive_bitwarden(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([client(cls="bitwarden", pid=4242)], proc_root=root)
        self.assertEqual(out, "1 3")

    def test_case_insensitive_upper(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([client(cls="BITWARDEN", pid=4242)], proc_root=root)
        self.assertEqual(out, "1 3")

    def test_widget_launch_shape(self):
        # Observed live under the widget env -i launch path: class exactly
        # 'Bitwarden', pid -> electron main process cmdline with app.asar.
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 3157640, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients(
                [{"class": "Bitwarden", "title": "Bitwarden", "pid": 3157640,
                  "workspace": {"id": 1, "name": "1"}, "mapped": True, "hidden": False}],
                app="Bitwarden", proc_root=root,
            )
        self.assertEqual(out, "1 1")

    def test_title_spoof_rejected(self):
        """A window whose TITLE contains 'Bitwarden' must never set PRESENT."""
        out, rc = run_clients([client(cls="kitty", title="ssh to Bitwarden server")])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "0 none")

    def test_class_spoof_rejected_by_proc(self):
        """class=Bitwarden but /proc cmdline is a different app -> skipped."""
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 5555, b"/usr/bin/kitty\x00")
            out, _ = run_clients([client(pid=5555)], proc_root=root)
        self.assertEqual(out, "0 none")

    def test_other_class_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([client(cls="foot"), client(pid=4242)], proc_root=root)
        self.assertEqual(out, "1 3")

    def test_no_match(self):
        out, _ = run_clients([client(cls="foot")])
        self.assertEqual(out, "0 none")

    def test_empty_list(self):
        out, _ = run_clients([])
        self.assertEqual(out, "0 none")


class TestHostileFixtures(unittest.TestCase):
    def test_garbage_json(self):
        out, rc = run_clients("not json {{{")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "0 none")

    def test_non_list_json(self):
        """A JSON object (wrong root type) must fail closed, not crash."""
        out, _ = run_clients({"class": "Bitwarden"})
        self.assertEqual(out, "0 none")

    def test_non_dict_entries(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients(["junk", None, 42, client(pid=4242)], proc_root=root)
        self.assertEqual(out, "1 3")

    def test_null_class(self):
        out, _ = run_clients([{"class": None, "title": "x", "workspace": {"name": "2"}}])
        self.assertEqual(out, "0 none")

    def test_missing_workspace_field(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([{"class": "Bitwarden", "pid": 4242, "title": "x"}], proc_root=root)
        self.assertEqual(out, "1 none")

    def test_null_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([{"class": "Bitwarden", "pid": 4242, "workspace": None}], proc_root=root)
        self.assertEqual(out, "1 none")

    def test_workspace_not_dict(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients([{"class": "Bitwarden", "pid": 4242, "workspace": "3"}], proc_root=root)
        self.assertEqual(out, "1 none")

    def test_workspace_name_charset_validated(self):
        """A workspace name with shell metacharacters must be neutralised to 'none'."""
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            for hostile in ["3; touch /tmp/pwn", "$(touch /tmp/pwn)", "a b", "x\ny", "3`id`"]:
                out, _ = run_clients(
                    [{"class": "Bitwarden", "pid": 4242, "workspace": {"name": hostile}}],
                    proc_root=root,
                )
                self.assertEqual(out, "1 none", f"hostile name not neutralised: {hostile!r}")

    def test_workspace_name_valid_special_passes(self):
        with tempfile.TemporaryDirectory() as root:
            make_proc_fixture(root, 4242, b"/usr/lib/electron39/electron /usr/lib/bitwarden/app.asar\x00")
            out, _ = run_clients(
                [{"class": "Bitwarden", "pid": 4242, "workspace": {"name": "special:bitwarden"}}],
                proc_root=root,
            )
        self.assertEqual(out, "1 special:bitwarden")

    def test_oversized_but_valid(self):
        """10k clients, match at the end — bounded work, correct result."""
        fixture = [client(cls="foot", ws=i) for i in range(10000)]
        fixture.append(client(cls="Bitwarden", ws=7))
        out, _ = run_clients(fixture)
        self.assertEqual(out, "1 7")

    def test_unicode_title_does_not_match(self):
        out, _ = run_clients([client(cls="kitty", title="Bitwarden \U0001F510 password")])
        self.assertEqual(out, "0 none")

    def test_app_env_missing_fails_closed(self):
        """APP unset -> want='' -> a classless client does NOT match (fail closed)."""
        out, rc = run_clients([{"class": None, "title": "x"}], app="")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "0 none")


class TestMonitorsVisibility(unittest.TestCase):
    def test_shown_special(self):
        """specialWorkspace.name == special:bitwarden -> VISIBLE=1 (measured ground truth)."""
        out, rc = run_monitors([monitor(special_id=-95, special_name="special:bitwarden")])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "1")

    def test_hidden_special(self):
        """specialWorkspace.name == '' (id 0) -> VISIBLE=0 (measured ground truth)."""
        out, _ = run_monitors([monitor(special_id=0, special_name="")])
        self.assertEqual(out, "0")

    def test_rename_spoof_rejected(self):
        """A normal workspace renamed to 'special:bitwarden' lands in activeWorkspace,
        NOT specialWorkspace — structural parse must ignore it (glob would not)."""
        out, _ = run_monitors([monitor(active="special:bitwarden", special_id=0, special_name="")])
        self.assertEqual(out, "0")

    def test_other_special_ignored(self):
        out, _ = run_monitors([monitor(special_id=-98, special_name="special:ente-auth")])
        self.assertEqual(out, "0")

    def test_multi_monitor_one_shown(self):
        out, _ = run_monitors([
            monitor(special_id=0, special_name=""),
            monitor(name="DP-1", special_id=-95, special_name="special:bitwarden"),
        ])
        self.assertEqual(out, "1")

    def test_garbage_json(self):
        out, rc = run_monitors("not json {{{")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "0")

    def test_non_list(self):
        out, _ = run_monitors({"specialWorkspace": {"name": "special:bitwarden"}})
        self.assertEqual(out, "0")

    def test_non_dict_entries(self):
        out, _ = run_monitors(["junk", None, monitor(special_id=-95, special_name="special:bitwarden")])
        self.assertEqual(out, "1")

    def test_special_not_dict(self):
        m = monitor()
        m["specialWorkspace"] = "special:bitwarden"
        out, _ = run_monitors([m])
        self.assertEqual(out, "0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
