"""Run the prepared full-playerTick fixture only in an owned isolated world."""
from __future__ import annotations
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'tools/player_tick_fixture'
sys.path.insert(0, str(ROOT / 'tools'))
import check_inventory as inventory
import check_steve_player_context as context
digest, snapshot = context.digest, context.snapshot
FIXTURE = HERE / 'OwnedPlayerTickFixture.java'

def preflight():
    jar = ROOT / context.NAMED_JAR_RELATIVE
    if not jar.is_file() or digest(jar) != context.JAR_SHA256:
        raise ValueError('Fixed named Minecraft jar is absent or differs')
    if ROOT != inventory.ROOT or inventory.PORT != 8768 or inventory.GAME_PORT != 25580:
        raise ValueError('Owned root/ports differ')
    ast.parse(Path(__file__).read_text(encoding='utf-8'))
    sources = [FIXTURE, HERE / 'owned-run.gradle', Path(__file__), Path(inventory.__file__),
               Path(context.__file__), ROOT / 'minecraft/build.gradle']
    return {'namedMergedJarRelativePath': context.NAMED_JAR_RELATIVE.as_posix(),
        'namedMergedJarSha256': context.JAR_SHA256,
        'sourceSha256': {p.relative_to(ROOT).as_posix(): digest(p) for p in sources}}

class FixtureServer(inventory.IsolatedServer):
    def __init__(self, directory):
        super().__init__(directory)
        self.init_script.write_bytes((HERE / 'owned-run.gradle').read_bytes())

def run():
    inputs = preflight()
    before = {name: snapshot(ROOT / name) for name in ('minecraft/src', 'minecraft/build')}
    directory = Path(tempfile.mkdtemp(prefix='mc-player-tick-', dir=ROOT / 'runtime')).resolve()
    if directory.parent != (ROOT / 'runtime').resolve():
        raise ValueError('Owned directory escaped runtime')
    ticket = str(uuid.uuid4())
    environment = {'CRIMSONMC_PLAYER_TICK_RUNTIME': str(directory),
        'CRIMSONMC_PLAYER_TICK_HARNESS': str(HERE), 'CRIMSONMC_PLAYER_TICK_TICKET': ticket}
    old = {key: os.environ.get(key) for key in environment}
    server = None
    captured = None
    failure = None
    report = None
    try:
        os.environ.update(environment)
        server = FixtureServer(directory)
        popen = inventory.subprocess.Popen
        def offline(command, *args, **kwargs):
            command = list(command)
            if 'runServer' not in command or str(server.init_script) not in command:
                raise ValueError('Unexpected launch outside owned server')
            command.insert(command.index('runServer'), '--offline')
            return popen(command, *args, **kwargs)
        with mock.patch.object(inventory.subprocess, 'Popen', side_effect=offline):
            server.start()
        captured = server.process
        deadline = time.monotonic() + 90
        while True:
            log = server.log_path.read_text(encoding='utf-8', errors='replace')
            if any(re.search(r'\bMC_PLAYER_TICK_FIXTURE_RESULT (?:pass|failure)\s*$', row) for row in log.splitlines()):
                break
            if server.process.poll() is not None:
                raise RuntimeError('Owned server exited before fixture completion')
            if time.monotonic() > deadline:
                raise TimeoutError('Fixture did not complete')
            time.sleep(0.2)
        report = json.loads((directory / 'player-tick-fixture.json').read_bytes())
        if report.get('runTicket') != ticket or report.get('result') != 'pass':
            raise AssertionError('Fixture failed or ticket differs: ' + str(directory))
    except BaseException as error:
        failure = error
    finally:
        try:
            if server is not None:
                if captured is None:
                    captured = server.process
                server.stop(authority=False)
        except BaseException as stop_error:
            if failure is None:
                failure = stop_error
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    unchanged = {name: snapshot(ROOT / name) == saved for name, saved in before.items()}
    inputs_unchanged = inputs == preflight()
    result = {'schemaVersion': 1, 'runTicket': ticket, 'runtimeDirectory': str(directory),
        'inputs': inputs, 'ownedLaunchPid': None if captured is None else captured.pid,
        'ownedProcessExitCode': None if captured is None else captured.returncode,
        'normalConsoleShutdown': captured is not None and captured.returncode == 0 and not server.forced_stop,
        'forcedOwnedPidStop': server is not None and server.forced_stop,
        'productionDirectoriesUnchanged': unchanged, 'sourcesAndPinnedJarUnchanged': inputs_unchanged,
        'production8766Or8765Requested': False, 'runnerHttpPort': 8768, 'gamePort': 25580,
        'nativeApplied': False, 'failure': None if failure is None else str(failure)}
    with (directory / 'runner-result.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    if failure is not None:
        raise failure
    if not all(unchanged.values()) or not inputs_unchanged or not result['normalConsoleShutdown']:
        raise AssertionError('Isolation or normal shutdown check failed')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.run:
        run()
    else:
        print(json.dumps({'serverStarted': False, 'inputs': preflight()}, indent=2))
