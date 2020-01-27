import importlib
import shlex
import sys
import traceback


ERROR_MARKER = "---- ERROR ----"
SUCCESS_MARKER = "---- SUCCESS ----"


def workServer():
    while True:
        input = sys.stdin.readline()
        input = input.strip()
        if not input:
            break
        try:
            command, *args = shlex.split(input)
            moduleName, funcName = command.rsplit(".", 1)
            module = importlib.import_module(moduleName)
            func = getattr(module, funcName)
            func(*args)
        except:
            traceback.print_exc()
            print(ERROR_MARKER)
        else:
            print(SUCCESS_MARKER)


if __name__ == "__main__":
    workServer()
