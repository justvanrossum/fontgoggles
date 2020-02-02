import importlib
import shlex
import signal
import sys
import traceback


def ignoreSignal(sig, frame):
    pass


def raiseKeyboardInterrupt(sig, frame):
    raise KeyboardInterrupt()


ERROR_MARKER = "---- ERROR ----"
SUCCESS_MARKER = "---- SUCCESS ----"


def workServer():
    signal.signal(signal.SIGINT, ignoreSignal)
    while True:
        input = sys.stdin.readline()
        input = input.strip()
        if not input:
            break
        try:
            try:
                signal.signal(signal.SIGINT, raiseKeyboardInterrupt)
                command, *args = shlex.split(input)
                moduleName, funcName = command.rsplit(".", 1)
                module = importlib.import_module(moduleName)
                func = getattr(module, funcName)
                func(*args)
            finally:
                signal.signal(signal.SIGINT, ignoreSignal)
        except KeyboardInterrupt:
            print(ERROR_MARKER)
        except:
            traceback.print_exc()
            print(ERROR_MARKER)
        else:
            print(SUCCESS_MARKER)


if __name__ == "__main__":
    workServer()
