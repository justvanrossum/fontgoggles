import asyncio
import os
import shlex
import sys
import tempfile
from .workServer import ERROR_MARKER, SUCCESS_MARKER


async def compileUFOToPath(ufoPath, ttPath):
    pool = getCompilerPool()
    func = "fontgoggles.misc.ufoCompiler.compileMinimumFontToPath"
    args = [
        os.fspath(ufoPath),
        os.fspath(ttPath),
    ]
    return await pool.callFunction(func, args)


async def compileUFOToBytes(ufoPath):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        output, error = await compileUFOToPath(ufoPath, tmp.name)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData, output, error


async def compileDSToPath(dsPath, ttFolder, ttPath):
    pool = getCompilerPool()
    func = "fontgoggles.misc.dsCompiler.compileMinimumFontToPath"
    args = [
        os.fspath(dsPath),
        os.fspath(ttFolder),
        os.fspath(ttPath),
    ]
    return await pool.callFunction(func, args)


async def compileDSToBytes(dsPath, ttFolder):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        output, error = await compileDSToPath(dsPath, ttFolder, tmp.name)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData, output, error


def getCompilerPool():
    loop = asyncio.get_running_loop()
    pool = getattr(loop, "__FG_compiler_pool", None)
    if pool is None:
        pool = CompilerPool()
        loop.__FG_compiler_pool = pool
    return pool


class CompilerPool:

    def __init__(self, maxWorkers=5):
        self.loop = asyncio.get_running_loop()
        self.maxWorkers = maxWorkers
        self.workers = []
        self.availableWorkers = asyncio.Queue()

    async def getWorker(self):
        if self.availableWorkers.empty() and len(self.workers) < self.maxWorkers:
            # Add a worker process
            worker = CompilerWorker()
            self.workers.append(worker)
            assert len(self.workers) <= self.maxWorkers
            await worker.start()
            return worker
        else:
            return await self.availableWorkers.get()

    async def callFunction(self, func, args):
        worker = await self.getWorker()
        output, error = await worker.callFunction(func, args)
        await self.availableWorkers.put(worker)
        return output, error


class CompilerWorker:

    async def start(self):
        env = dict(PYTHONPATH=":".join(sys.path))
        args = ["-u", "-m", "fontgoggles.misc.workServer"]
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, *args,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)

    async def callFunction(self, func, args):
        args = [func] + args
        inData = " ".join(shlex.quote(item) for item in args)
        self.process.stdin.write((inData + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        output = []
        error = True
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
