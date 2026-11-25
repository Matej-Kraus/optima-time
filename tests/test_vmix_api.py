import socket
import threading
import time
from urllib.parse import parse_qs

import pytest
from pydantic import ValidationError

from optima_time.config.models import (
    DerivedField,
    OutputsConfig,
    Profile,
    VmixAction,
    VmixApiOutput,
    VmixCommand,
    XmlFileOutput,
)
from optima_time.fields.models import ClockField, IndicatorField, Roi
from optima_time.outputs.vmix_api import Command, VmixApiWorker
from optima_time.runner import make_workers


class FakeVmix:
    """A TCP server that answers like the vMix TCP API: OK for known title fields."""

    def __init__(self, fields: set[str]) -> None:
        self.fields = fields
        self.got: list[dict[str, str]] = []
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn: socket.socket) -> None:
        buf = b""
        with conn:
            conn.sendall(b"VERSION OK 28.0.0.0\r\n")  # vMix greets new clients; must be skipped
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk
                while b"\r\n" in buf:
                    line, buf = buf.split(b"\r\n", 1)
                    _, function, query = line.decode().split(" ", 2)
                    q = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
                    if function != "SetText":
                        q["Function"] = function
                    if q["SelectedName"] in self.fields:
                        self.got.append(q)
                        conn.sendall(b"FUNCTION OK Completed\r\n")
                    else:
                        conn.sendall(b"FUNCTION ER Field not found\r\n")

    def close(self) -> None:
        self.server.close()


def wait(pred, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end and not pred():
        time.sleep(0.01)
    assert pred()


def test_sends_changed_values_and_reports_unknown_fields() -> None:
    vmix = FakeVmix({"Time.Text", "scoreh.Text"})
    w = VmixApiWorker("127.0.0.1", vmix.port, "Skore 1")
    w.start()
    try:
        w.submit({"Time": "12:02", "scoreh": "1", "shots": "5"})
        assert w.flush()
        wait(lambda: len(vmix.got) == 2)
        assert vmix.got[0] == {"Input": "Skore 1", "SelectedName": "Time.Text", "Value": "12:02"}
        assert w.problems == {"shots": "Field not found"}
        assert w.status.ok is True  # a wrong name is a setup problem, not a broken output
        w.submit({"Time": "12:03", "scoreh": "1", "shots": "5"})  # only Time changed
        assert w.flush()
        wait(lambda: len(vmix.got) == 3)
        time.sleep(0.1)
        assert len(vmix.got) == 3 and vmix.got[-1]["Value"] == "12:03"
    finally:
        w.stop()
        vmix.close()


def test_explicit_names_and_reconnect() -> None:
    vmix = FakeVmix({"Cas", "Domaci"})
    w = VmixApiWorker("127.0.0.1", vmix.port, "1", names={"Time": "Cas", "scoreh": "Domaci"})
    assert w.selected_name("scorea") is None  # with explicit names only those are sent
    w.start()
    try:
        w.submit({"Time": "0:42", "scoreh": "", "scorea": "2"})
        assert w.flush()
        wait(lambda: len(vmix.got) == 2)
        assert {g["SelectedName"] for g in vmix.got} == {"Cas", "Domaci"}
        assert w.problems == {}
    finally:
        w.stop()
        vmix.close()


def test_vmix_not_running_fails_softly() -> None:
    port = socket.create_server(("127.0.0.1", 0))
    free = port.getsockname()[1]
    port.close()
    w = VmixApiWorker("127.0.0.1", free, "1")
    w.start()
    try:
        w.submit({"Time": "1:00"})
        wait(lambda: w.status.ok is False)
        assert "vMix" in w.status.message
    finally:
        w.stop()


def test_profile_makes_both_outputs() -> None:
    outputs = OutputsConfig(
        xml_file=XmlFileOutput(path="/tmp/x.xml"),
        vmix_api=VmixApiOutput(enabled=True, input="Skore"),
    )
    names = [w.name for w in make_workers(Profile(outputs=outputs))]
    assert names == ["xml_file", "vmix_api"]
    off = OutputsConfig(vmix_api=VmixApiOutput(enabled=True, input=" "))
    assert make_workers(Profile(outputs=off)) == []


def test_commands_drive_images_visibility_and_colour() -> None:
    vmix = FakeVmix({"Time.Text", "PozadiH.Source", "Logo.Source", "Time.Colour"})
    commands = [
        Command("penaltyh1", "image_visible", "PozadiH.Source"),
        Command("tym", "image", "Logo.Source", "Logo"),
        Command("barva", "text_colour", "Time.Colour"),
        Command("Time", "text_visible", "Nope.Text"),
    ]
    w = VmixApiWorker(
        "127.0.0.1", vmix.port, "Skore", names={"Time": "Time.Text"}, commands=commands
    )
    w.start()
    try:
        values = {"Time": "1:00", "penaltyh1": "", "tym": "C:\\gfx\\a.png", "barva": "#FF0000"}
        w.submit(values)
        assert w.flush()
        wait(lambda: len(vmix.got) == 4)
        got = {g["SelectedName"]: g for g in vmix.got}
        assert got["PozadiH.Source"] == {
            "Function": "SetImageVisibleOff",
            "Input": "Skore",
            "SelectedName": "PozadiH.Source",
        }
        assert got["Logo.Source"]["Input"] == "Logo"  # a command can aim at another title
        assert got["Logo.Source"]["Value"] == "C:\\gfx\\a.png"
        assert got["Time.Colour"]["Function"] == "SetTextColour"
        assert w.problems == {"Time → Nope.Text (text_visible)": "Field not found"}

        vmix.got.clear()
        w.submit(values | {"penaltyh1": "2:00"})  # the penalty starts: only the background
        assert w.flush()
        wait(lambda: len(vmix.got) == 1)
        assert vmix.got[0]["Function"] == "SetImageVisibleOn"
        w.submit(values | {"penaltyh1": "1:59"})  # still on: nothing to send
        assert w.flush()
        time.sleep(0.1)
        assert len(vmix.got) == 1
    finally:
        w.stop()
        vmix.close()


def test_commands_skip_disabled_fields_and_reject_unknown_actions() -> None:
    w = VmixApiWorker(
        "127.0.0.1",
        1,
        "Skore",
        names={"Time": "Cas"},
        commands=[
            Command("lamp", "image_visible", "Lamp.Source"),
        ],
    )
    assert set(w.wanted({"Time": "1:00"})) == {"Time"}
    with pytest.raises(ValueError):
        VmixApiWorker("127.0.0.1", 1, "Skore", commands=[Command("Time", "blink", "X")])


ROI = Roi(x=0, y=0, w=0.2, h=0.2)


def test_profile_checks_command_values() -> None:
    fields = [ClockField(id="Time", roi=ROI), IndicatorField(id="foul1", roi=ROI)]
    derived = [DerivedField(id="fauly", template="{sum:foul1}")]
    ok = VmixApiOutput(
        enabled=True,
        input="Skore",
        commands=[
            VmixCommand(value="fauly", action=VmixAction.TEXT, target="Fauly.Text"),
            VmixCommand(
                value="foul1", action=VmixAction.IMAGE_VISIBLE, target="F1.Source", enabled=False
            ),
        ],
    )
    profile = Profile(fields=fields, derived=derived, outputs=OutputsConfig(vmix_api=ok))
    (worker,) = make_workers(profile)
    assert isinstance(worker, VmixApiWorker)
    assert worker.commands == [Command("fauly", "text", "Fauly.Text", "")]  # disabled one left out
    bad = VmixApiOutput(commands=[VmixCommand(value="shots", target="Strely.Text")])
    with pytest.raises(ValidationError, match="shots"):
        Profile(fields=fields, outputs=OutputsConfig(vmix_api=bad))
