"""Mock-only launch/session checks; no real game launch, HTTP, services or GUI."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
import steve_game_session as session


IDENTITY = {"pid":42,"creationTime100ns":"134358162934331038",
    "imagePath":r"E:\SteamLibrary\steamapps\common\Crimson Desert\bin64\CrimsonDesert.exe",
    "imageSha256":session.identity.EXE_SHA256,"access":"PROCESS_QUERY_LIMITED_INFORMATION"}
NATIVE = {"apiVersion":1,"gameVersion":"1.0.0.2976","buildOk":True,
    "instanceId":"42:134358162934331038","sessionPreconditions":True,"ready":True}
MC = {"engine":"Minecraft Java 1.21.1","schemaVersion":3,"revision":25}


def endpoints(port,route,timeout=2):
    return copy.deepcopy(NATIVE if port==8765 else MC)


class Clock:
    def __init__(self): self.value=0.0; self.sleeps=[]
    def now(self): return self.value
    def sleep(self,seconds): self.sleeps.append(seconds); self.value+=seconds


class SessionChecks(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.pids = self.stack.enter_context(mock.patch.object(session,"game_process_ids",return_value=[42]))
        self.identity = self.stack.enter_context(mock.patch.object(session.identity,"session_identity",return_value=copy.deepcopy(IDENTITY)))
        self.http = self.stack.enter_context(mock.patch.object(session,"http_json",side_effect=endpoints))
        self.steam = self.stack.enter_context(mock.patch.object(session,"request_steam_launch"))

    def test_01_status_fresh_identity_matching_fixed_build_mc_and_false_automatic_entry(self):
        result = session.status()
        self.assertEqual(result["state"],"scene-ready")
        self.assertTrue(result["sceneReady"])
        self.assertTrue(result["identityStable"])
        self.assertTrue(result["nativeBuildVerified"])
        self.assertTrue(result["mcReady"])
        self.assertIn("Do not press E while scene-ready",result["nextRequired"])
        self.assertIs(result["automaticWorldEntryVerified"],False)
        self.assertEqual(self.identity.call_count,2)
        self.assertEqual([(call.args[0],call.args[1]) for call in self.http.call_args_list],
                         [(8765,"/api/status"),(8766,"/api/state")])
        self.assertFalse(result["guiCapabilities"]["providedToThisCli"])
        self.steam.assert_not_called()

    def test_02_running_launch_reuses_never_fires_steam_even_not_ready(self):
        for ready in (False,True):
            with mock.patch.object(session,"http_json",side_effect=lambda p,r,t:{**NATIVE,"ready":ready} if p==8765 else MC):
                result = session.launch()
            self.assertTrue(result["reusedRunningGame"])
            self.assertFalse(result["launchRequested"])
        self.steam.assert_not_called()

    def test_03_closed_launch_fixed_image_then_absence_recheck_uri_once(self):
        self.pids.return_value=[]
        with mock.patch.object(session,"verify_closed_executable",return_value={"imageSha256":session.identity.EXE_SHA256}) as verify:
            result=session.launch()
        self.assertEqual(result["state"],"launch-requested")
        self.assertTrue(result["launchRequested"])
        self.assertIs(result["automaticWorldEntryVerified"],False)
        verify.assert_called_once_with()
        self.assertEqual(self.pids.call_count,2)
        self.steam.assert_called_once_with()
        self.identity.assert_not_called()
        self.steam.reset_mock()
        with mock.patch.object(session,"http_json",side_effect=lambda p,r,t:NATIVE if p==8765 else {}), \
             mock.patch.object(session,"verify_closed_executable",side_effect=AssertionError("EXE read before backend gate")):
            result=session.launch()
        self.assertEqual(result["state"],"blocked")
        self.assertIn("backend is not ready",result["error"])
        self.assertFalse(result["launchRequested"])
        self.steam.assert_not_called()

    def test_04_multiple_unknown_exe_build_instance_and_false_ready_types_refuse(self):
        self.pids.return_value=[42,43]
        result=session.launch()
        self.assertEqual(result["state"],"blocked")
        self.identity.assert_not_called()
        self.steam.assert_not_called()
        self.pids.return_value=[42]
        self.identity.side_effect=session.identity.IdentityError("unsupported EXE SHA256")
        self.assertEqual(session.launch()["state"],"blocked")
        self.identity.side_effect=None
        for native in ({**NATIVE,"buildOk":False},{**NATIVE,"buildOk":1},
                       {**NATIVE,"gameVersion":"unknown"},{**NATIVE,"instanceId":"other"},
                       {**NATIVE,"ready":1},{**NATIVE,"apiVersion":True}):
            with mock.patch.object(session,"http_json",side_effect=lambda p,r,t:native if p==8765 else MC):
                result=session.launch()
            self.assertEqual(result["state"],"blocked")
            self.assertFalse(result["sceneReady"])
        with mock.patch.object(session,"http_json",side_effect=OSError("connection unavailable")):
            self.assertEqual(session.launch()["state"],"blocked")
        self.steam.assert_not_called()

    def test_05_closed_wrong_executable_and_racing_new_instance_never_launch(self):
        self.pids.return_value=[]
        with mock.patch.object(session,"verify_closed_executable",side_effect=session.identity.IdentityError("wrong fixed EXE")):
            self.assertEqual(session.launch()["state"],"blocked")
        self.pids.side_effect=[[],[42],[42]]
        with mock.patch.object(session,"verify_closed_executable",return_value={"imageSha256":session.identity.EXE_SHA256}):
            result=session.launch()
        self.assertTrue(result["reusedRunningGame"])
        self.steam.assert_not_called()

    def test_06_status_fresh_identity_change_and_mc_false_readiness_do_not_pass(self):
        self.identity.side_effect=[IDENTITY,{**IDENTITY,"creationTime100ns":"134358162934331039"}]
        result=session.status()
        self.assertEqual(result["state"],"blocked")
        self.assertFalse(result["sceneReady"])
        self.identity.side_effect=None
        for mc in ({**MC,"schemaVersion":True},{**MC,"engine":"other"},{**MC,"revision":True}):
            with mock.patch.object(session,"http_json",side_effect=lambda p,r,t:NATIVE if p==8765 else mc):
                result=session.status()
            self.assertEqual(result["state"],"running-not-ready")
            self.assertFalse(result["sceneReady"])

    def waiting(self,reports,timeout=6):
        clock=Clock()
        with mock.patch.object(session,"status",side_effect=reports) as status, \
             mock.patch.object(session.time,"monotonic",side_effect=clock.now), \
             mock.patch.object(session.time,"sleep",side_effect=clock.sleep):
            result=session.wait_ready(timeout,2)
        return result,clock,status

    def running(self,ready=False,identity=IDENTITY):
        result=session.base_report("status")
        result.update(state="scene-ready" if ready else "running-not-ready",gameIdentity=identity,
                      identityStable=True,nativeBuildVerified=True,mcReady=True,sceneReady=ready)
        return result

    def test_07_wait_success_fixed_instance_and_timeout_bounded_no_steam_retries(self):
        result,clock,status=self.waiting([self.running(),self.running(True)])
        self.assertEqual(result["state"],"scene-ready")
        self.assertFalse(result["automaticWorldEntryVerified"])
        self.assertEqual(clock.sleeps,[2])
        result,clock,status=self.waiting([self.running() for _ in range(3)])
        self.assertEqual(result["state"],"timed-out")
        self.assertEqual(result["elapsedSeconds"],6)
        self.assertEqual(clock.sleeps,[2,2,2])
        self.assertEqual(status.call_count,3)
        self.steam.assert_not_called()

    def test_08_wait_disappearance_wrong_instance_build_blocked_abort_without_retry(self):
        closed=session.base_report("status");closed["state"]="closed"
        blocked=session.base_report("status");blocked["error"]="wrong build"
        for end in (closed,blocked,self.running(True,{**IDENTITY,"pid":43})):
            result,clock,status=self.waiting([self.running(),end])
            self.assertEqual(result["state"],"blocked")
            self.assertFalse(result["sceneReady"])
            self.assertEqual(status.call_count,2)
            self.assertEqual(clock.sleeps,[2])
        self.steam.assert_not_called()

    def test_09_wait_parameters_refuse_and_ready_after_deadline_not_accepted(self):
        for timeout,interval in ((121,2),(0,2),(60,1),(float("inf"),2),(60,float("nan")),(True,2)):
            with self.assertRaises(session.SessionError): session.wait_ready(timeout,interval)
        clock=Clock()
        def slow_ready(**kwargs): clock.value=7;return self.running(True)
        with mock.patch.object(session,"status",side_effect=slow_ready), \
             mock.patch.object(session.time,"monotonic",side_effect=clock.now), \
             mock.patch.object(session.time,"sleep",side_effect=clock.sleep):
            result=session.wait_ready(6,2)
        self.assertEqual(result["state"],"timed-out")
        self.assertFalse(result["sceneReady"])

    def test_10_output_bounds_overwrite_links_and_default_status_no_writes(self):
        with tempfile.TemporaryDirectory(prefix="steve-session-output-") as directory:
            root=Path(directory);(root/"runtime").mkdir()
            with mock.patch.object(session,"ROOT",root):
                target=session.output_path("runtime/steve-game-session-test.json")
                report=self.running()
                session.save_report(target,report)
                self.assertEqual(json.loads(target.read_bytes()),report)
                with self.assertRaisesRegex(session.SessionError,"overwrite"):
                    session.save_report(target,report)
                for name in ("runtime/../runtime/steve-game-session-x.json","other/steve-game-session-x.json",
                             "runtime/other.json","runtime/steve-game-session-UPPER.json",str(root.parent/"steve-game-session-x.json")):
                    with self.assertRaises(session.SessionError): session.output_path(name)
                with mock.patch.object(Path,"is_symlink",return_value=True),self.assertRaises(session.SessionError):
                    session.output_path("runtime/steve-game-session-linked.json")
                self.assertEqual(json.loads(target.read_bytes()),report)
        with mock.patch.object(sys,"argv",["steve_game_session.py"]), \
             mock.patch.object(session,"save_report",side_effect=AssertionError("unexpected write")), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(session.main(),0)
        self.steam.assert_not_called()

    def test_11_fixed_steam_uri_only_windows_no_gui_helpers_and_output_rejected_before_launch(self):
        # Exercise the real wrapper with only the OS URI dispatch mocked.
        with mock.patch.object(session.os,"name","nt"),mock.patch.object(session.os,"startfile",create=True) as start:
            REAL_STEAM()
            start.assert_called_once_with("steam://rungameid/3321460")
        with mock.patch.object(session.os,"name","posix"),self.assertRaises(session.SessionError): REAL_STEAM()
        with mock.patch.object(sys,"argv",["steve_game_session.py","launch","--output","../bad.json"]), \
             mock.patch.object(session,"launch",side_effect=AssertionError("launch before output admission")):
            with self.assertRaises(session.SessionError): session.main()

    def test_12_http_exact_get_limits_no_redirect_proxy_and_strict_json(self):
        opener=mock.Mock()
        response=mock.MagicMock()
        response.__enter__.return_value=response
        response.status=200
        response.read.return_value=json.dumps(NATIVE).encode()
        opener.open.return_value=response
        with mock.patch.object(session,"build_opener",return_value=opener):
            self.assertEqual(REAL_HTTP(8765,"/api/status",1),NATIVE)
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,"http://127.0.0.1:8765/api/status")
        self.assertEqual(request.get_method(),"GET")
        self.assertIsNone(request.data)
        response.read.assert_called_once_with(65537)
        for raw in (b'{"ready":true,"ready":false}',b'{"ready":NaN}',b'[]'):
            with self.assertRaises(ValueError): session.strict_json(raw)
        with self.assertRaises(session.SessionError): session.NoRedirect().redirect_request(None,None,None,None,None,None)
        with self.assertRaises(session.SessionError): REAL_HTTP(8765,"/api/player",1)

    def test_13_closed_installation_digest_and_configuration_custody(self):
        with tempfile.TemporaryDirectory(prefix="steve-session-config-") as directory:
            root=Path(directory);(root/"runtime").mkdir()
            config=root/"runtime/installation.json"
            raw=json.dumps({"gameRoot":str(root/"fixed-game")}).encode()
            config.write_bytes(raw)
            with mock.patch.object(session,"ROOT",root), \
                 mock.patch.object(session.identity,"_verify_image",return_value=session.identity.EXE_SHA256) as verify:
                admitted=session.verify_closed_executable()
                self.assertEqual(admitted["imageSha256"],session.identity.EXE_SHA256)
                self.assertEqual(verify.call_args.args[0],root/"fixed-game/bin64/CrimsonDesert.exe")
                self.assertEqual(config.read_bytes(),raw)
            with mock.patch.object(session,"ROOT",root), \
                 mock.patch.object(session.identity,"_verify_image",return_value="0"*64), \
                 self.assertRaises(session.SessionError): session.verify_closed_executable()
            def changed(path):
                config.write_bytes(raw+b" ")
                return session.identity.EXE_SHA256
            with mock.patch.object(session,"ROOT",root), \
                 mock.patch.object(session.identity,"_verify_image",side_effect=changed), \
                 self.assertRaisesRegex(session.SessionError,"changed"):
                session.verify_closed_executable()


REAL_STEAM=session.request_steam_launch
REAL_HTTP=session.http_json


if __name__ == "__main__":
    unittest.main(verbosity=2)
