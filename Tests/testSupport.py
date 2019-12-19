import pathlib


testRoot = pathlib.Path(__file__).resolve().parent
testDataFolder = testRoot / "data"


def getFontPath(fileName):
    for child in testDataFolder.iterdir():
        if child.is_dir():
            path = child / fileName
            if path.exists():
                return path
    raise IOError(f"{fileName} not found")
