import asyncio
import os
import shlex
import sys
from .ufoCompiler import ERROR_MARKER, SUCCESS_MARKER


async def compileUFO(ufoPath, ttPath):
    return await _pool.compileUFO(ufoPath, ttPath)


class UFOCompilerPool:

    def __init__(self, maxWorkers=5):
        self.maxWorkers = maxWorkers
        self.workers = []
        self.availableWorkers = None

    async def getWorker(self):
        if self.availableWorkers is None:
            self.availableWorkers = asyncio.Queue()
            # Populate queue with dummies
            for i in range(self.maxWorkers):
                await self.availableWorkers.put(None)  # worker-to-be-created
        worker = await self.availableWorkers.get()
        if worker is None:
            worker = UFOCompilerWorker()
            await worker.start()
            self.workers.append(worker)
            assert len(self.workers) <= self.maxWorkers
        return worker

    async def compileUFO(self, ufoPath, ttPath):
        worker = await self.getWorker()
        output, error = await worker.compileUFO(ufoPath, ttPath)
        await self.availableWorkers.put(worker)
        return output, error


_pool = UFOCompilerPool()


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
