import asyncio
import os
import shlex
import sys
import tempfile
from .ufoCompiler import ERROR_MARKER, SUCCESS_MARKER


async def compileUFOToPath(ufoPath, ttPath):
    return await _pool.compileUFO(ufoPath, ttPath)


async def compileUFOToBytes(ufoPath):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        output, error = await compileUFOToPath(ufoPath, tmp.name)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData, output, error


class UFOCompilerPool:

    def __init__(self, maxWorkers=5):
        self.maxWorkers = maxWorkers
        self.workers = []
        self.availableWorkers = asyncio.Queue()

    async def getWorker(self):
        if self.availableWorkers.empty() and len(self.workers) < self.maxWorkers:
            # Add a worker process
            worker = UFOCompilerWorker()
            self.workers.append(worker)
            assert len(self.workers) <= self.maxWorkers
            await worker.start()
            await self.availableWorkers.put(worker)
        return await self.availableWorkers.get()

    async def compileUFO(self, ufoPath, ttPath):
        worker = await self.getWorker()
        output, error = await worker.compileUFO(ufoPath, ttPath)
        await self.availableWorkers.put(worker)
        return output, error


class UFOCompilerWorker:

    async def start(self):
        env = dict(PYTHONPATH=":".join(sys.path))
        args = ["-u", "-m", "fontgoggles.misc.ufoCompiler"]
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, *args,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)

    async def compileUFO(self, ufoPath, ttPath):
        inData = " ".join(shlex.quote(os.fspath(p)) for p in (ufoPath, ttPath))
        self.process.stdin.write((inData + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        output = []
        while True:
            line = await self.process.stdout.readline()
            if not line:
                print("broken subprocess")
                break
            line = line.decode("utf-8")
            line = line.rstrip('\n')
            if line == ERROR_MARKER:
                error = True
                break
            if line == SUCCESS_MARKER:
                error = False
                break
            output.append(line)
        return "\n".join(output), error


def _resetPool():
    global _pool
    _pool = UFOCompilerPool()


_resetPool()
