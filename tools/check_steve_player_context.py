"""Check official MC Player context in one owned IsolatedServer with explicit --run.

Default invocation performs source/syntax preflight without ports or server startup.
The fixture does not connect a Minecraft client, register a player or call a full tick.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'tools/player_context_fixture'
sys.path.insert(0, str(ROOT / 'tools'))
import check_inventory as inventory

NAMED_JAR_RELATIVE = Path('minecraft/.gradle/loom-cache/minecraftMaven/net/minecraft/minecraft-merged-c2b31d572c/1.21.1-net.fabricmc.yarn.1_21_1.1.21.1+build.3-v2/minecraft-merged-c2b31d572c-1.21.1-net.fabricmc.yarn.1_21_1.1.21.1+build.3-v2.jar')
JAR_SHA256 = '834ee1a9988ed037f0e548b80dc3b59434b40af298257fbc7a72bb2256dffebb'
FIXTURE = HERE / 'OwnedPlayerContextFixture.java'

def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def snapshot(directory):
    return {str(path.relative_to(directory)):digest(path) for path in sorted(directory.rglob('*')) if path.is_file()} if directory.exists() else {}

def preflight():
    jar = ROOT / NAMED_JAR_RELATIVE
    if not jar.is_file() or digest(jar) != JAR_SHA256:
        raise ValueError('Fixed named Minecraft 1.21.1 jar is absent or differs: ' + str(jar))
    if ROOT != inventory.ROOT or inventory.PORT != 8768 or inventory.GAME_PORT != 25580:
        raise ValueError('IsolatedServer root or owned test ports differ')
    ast.parse(Path(__file__).read_text(encoding='utf-8'))
    if not FIXTURE.is_file() or not (HERE/'owned-run.gradle').is_file():
        raise ValueError('Tracked player-context fixture source or init-script is missing')
    return {'namedMergedJarRelativePath':NAMED_JAR_RELATIVE.as_posix(),'namedMergedJarSha256':JAR_SHA256,
            'inventoryRunnerSha256':digest(Path(inventory.__file__)),
            'minecraftBuildScriptSha256':digest(ROOT/'minecraft/build.gradle'),
            'fixtureJavaSha256':digest(FIXTURE),'initScriptSha256':digest(HERE/'owned-run.gradle'),
            'runnerSha256':digest(Path(__file__))}

def fixture_completion_marked(log):
    # Minecraft may prefix redirected System.out with its log/thread labels.
    return any(re.search(r'\bMC_PLAYER_CONTEXT_FIXTURE_RESULT (?:pass|failure)\s*$', line)
               for line in log.splitlines())

class FixtureServer(inventory.IsolatedServer):
    def __init__(self,directory):
        super().__init__(directory)
        self.init_script.write_bytes((HERE/'owned-run.gradle').read_bytes())

def run():
    inputs = preflight()
    src_before = snapshot(ROOT/'minecraft/src')
    build_before = snapshot(ROOT/'minecraft/build')
    runtime = ROOT/'runtime'
    runtime.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='mc-player-context-',dir=runtime)).resolve()
    if directory.parent != runtime.resolve(): raise ValueError('Owned runtime escaped project')
    ticket = str(uuid.uuid4())
    env_values = {'CRIMSONMC_PLAYER_CONTEXT_RUNTIME':str(directory),'CRIMSONMC_PLAYER_CONTEXT_HARNESS':str(HERE),
                  'CRIMSONMC_PLAYER_CONTEXT_TICKET':ticket}
    old = {key:os.environ.get(key) for key in env_values}
    server = None; captured = None; failure = None
    try:
        os.environ.update(env_values)
        server = FixtureServer(directory)
        # Reuse the existing owned-PID/start/port guards; only add Gradle's offline flag.
        real_popen = inventory.subprocess.Popen
        def offline_popen(command,*args,**kwargs):
            command = list(command)
            if 'runServer' not in command or str(server.init_script) not in command:
                raise ValueError('Unexpected process launch outside the owned server')
            command.insert(command.index('runServer'),'--offline')
            return real_popen(command,*args,**kwargs)
        with mock.patch.object(inventory.subprocess,'Popen',side_effect=offline_popen):
            server.start()
        captured = server.process
        output = directory/'player-context-fixture.json'
        deadline = time.monotonic()+90
        # Files.writeString(CREATE_NEW) creates the directory entry before its bytes
        # are complete. The Java marker is emitted only after that write returns.
        while True:
            log = server.log_path.read_text(encoding='utf-8',errors='replace')
            if fixture_completion_marked(log): break
            if server.process.poll() is not None: raise RuntimeError('Owned server exited before fixture report')
            if time.monotonic()>deadline: raise TimeoutError('Fixture report did not appear')
            time.sleep(0.2)
        if not output.is_file(): raise AssertionError('Fixture completion marker has no report')
        report = json.loads(output.read_bytes())
        if report.get('runTicket') != ticket or report.get('result') != 'pass':
            raise AssertionError('Fixture failed or report ticket differs: '+str(output))
        scope = report['scope']
        for key in ('fixtureClientCreated','fixtureNetworkHandlerCreated','registeredWithPlayerManager',
                    'spawnedInWorld','fullEntityOrPlayerTickCalled','twentyHzLifecycleVerified','privateFieldsWritten',
                    'nativeApplied','attackOrDamageCalled','clientModelOrGameRendererVerified'):
            if scope.get(key) is not False: raise AssertionError('Fixture exceeded scope: '+key)
    except BaseException as error:
        failure = error
    finally:
        # Console shutdown targets only the process this object launched, never an HTTP server on an old port.
        try:
            if server is not None:
                if captured is None: captured = server.process
                server.stop(authority=False)
        except BaseException as shutdown_error:
            if failure is None: failure = shutdown_error
        finally:
            for key,value in old.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value
    src_unchanged = snapshot(ROOT/'minecraft/src') == src_before
    build_unchanged = snapshot(ROOT/'minecraft/build') == build_before
    inputs_unchanged = preflight() == inputs
    summary = {'schemaVersion':1,'runTicket':ticket,'runtimeDirectory':str(directory),'fixtureReport':str(directory/'player-context-fixture.json'),
        'inputs':inputs,'fixtureReportProduced':(directory/'player-context-fixture.json').exists(),'ownedLaunchPid':None if captured is None else captured.pid,
        'ownedProcessExitCode':None if captured is None else captured.returncode,
        'normalConsoleShutdown':captured is not None and captured.returncode == 0 and not server.forced_stop,
        'forcedOwnedPidStop':server is not None and server.forced_stop,
        'minecraftSrcUnchanged':src_unchanged,'productionMinecraftBuildUnchanged':build_unchanged,'harnessAndPinnedJarUnchanged':inputs_unchanged,
        'runnerHttpPort':8768,'gamePort':25580,'production8766Or8765Requested':False,'clientConnectedByFixture':False,
        'nativeApplied':False,'failure':None if failure is None else str(failure)}
    with (directory/'runner-result.json').open('x',encoding='utf-8') as stream: json.dump(summary,stream,indent=2);stream.write('\n')
    print(json.dumps(summary,indent=2))
    if failure is not None: raise failure
    if not src_unchanged or not build_unchanged or not inputs_unchanged or server.forced_stop:
        raise AssertionError('Fixture isolation or normal shutdown contract failed')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Run only after reviewing the prepared fixture/init-script')
    args=parser.parse_args()
    if args.run: run()
    else: print(json.dumps({'mode':'prepared-preflight-only','serverStarted':False,'inputs':preflight()},indent=2))

if __name__=='__main__': main()
