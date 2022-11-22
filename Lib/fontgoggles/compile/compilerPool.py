import asyncio
import os
import shlex
import signal
import sys
import tempfile
from .workServer import ERROR_MARKER, SUCCESS_MARKER


async def compileUFOToPath(ufoPath, ttPath, outputWriter):
    pool = getCompilerPool()
    func = "fontgoggles.compile.ufoCompiler.compileUFOToPath"
    args = [
        os.fspath(ufoPath),
        os.fspath(ttPath),
    ]
    return await pool.callFunction(func, args, outputWriter)


async def compileUFOToBytes(ufoPath, outputWriter):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        await compileUFOToPath(ufoPath, tmp.name, outputWriter)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData


async def compileDSToPath(dsPath, fontNumber, ttFolder, ttPath, outputWriter):
    pool = getCompilerPool()
    func = "fontgoggles.compile.dsCompiler.compileDSToPath"
    args = [
        os.fspath(dsPath),
        str(fontNumber),
        os.fspath(ttFolder),
        os.fspath(ttPath),
    ]
    return await pool.callFunction(func, args, outputWriter)


async def compileDSToBytes(dsPath, fontNumber, ttFolder, outputWriter):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        await compileDSToPath(dsPath, fontNumber, ttFolder, tmp.name, outputWriter)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData


async def compileTTXToPath(ttxPath, ttPath, outputWriter):
    pool = getCompilerPool()
    func = "fontgoggles.compile.ttxCompiler.compileTTXToPath"
    args = [
        os.fspath(ttxPath),
        os.fspath(ttPath),
    ]
    return await pool.callFunction(func, args, outputWriter)


async def compileTTXToBytes(ttxPath, outputWriter):
    with tempfile.NamedTemporaryFile(prefix="fontgoggles_temp", suffix=".ttf") as tmp:
        await compileTTXToPath(ttxPath, tmp.name, outputWriter)
        with open(tmp.name, "rb") as f:
            fontData = f.read()
            if not fontData:
                fontData = None
    return fontData


def getCompilerPool():
    loop = asyncio.get_running_loop()
    pool = getattr(loop, "__FG_compiler_pool", None)
    if pool is None:
        pool = CompilerPool()
        loop.__FG_compiler_pool = pool
    return pool


class CompilerError(Exception):
    pass


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

    async def callFunction(self, func, args, outputWriter):
        if outputWriter is None:
            outputWriter = sys.stderr.write
        worker = await self.getWorker()
        try:
            error = await worker.callFunction(func, args, outputWriter)
        finally:
            await self.availableWorkers.put(worker)
        if error:
            raise CompilerError(func)


class CompilerWorker:

    async def start(self):
        env = dict(PYTHONPATH=":".join(sys.path), PYTHONHOME=sys.prefix)
        args = ["-u", "-m", "fontgoggles.compile.workServer"]
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, *args,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT)

    async def callFunction(self, func, args, outputWriter):
        args = [func] + args
        inData = " ".join(shlex.quote(item) for item in args)
        self.process.stdin.write((inData + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        error = True
        cancelling = False
        while True:
            try:
                line = await self.process.stdout.readline()
            except asyncio.CancelledError:
                self.process.send_signal(signal.SIGINT)
                # We will re-raise only after we've received all
                # our expected output, which should not be much as
                # we just sent SIGINT to the worker process.
                cancelling = True
                continue
            if not line:
                raise RuntimeError("broken subprocess")
                break
            line = line.decode("utf-8")
            line = line.rstrip('\n')
            if line == ERROR_MARKER:
                error = True
                break
            if line == SUCCESS_MARKER:
                error = False
                break
            outputWriter(line + "\n")
        if cancelling:
            raise asyncio.CancelledError()
        return error
