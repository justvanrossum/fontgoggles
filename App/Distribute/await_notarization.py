import os
import plistlib
import subprocess
import sys
import time


def getNotarizeInfo(requestUUID, user, passw):
    infoCommand = [
        "xcrun",
        "altool",
        "--notarization-info", requestUUID,
        "-u", user,
        "-p", passw,
        "--output-format", "xml",
    ]
    try:
        result = subprocess.run(infoCommand, check=True, capture_output=True)
    except subprocess.CalledProcessError as error:
        print("STDOUT", error.stdout)
        print("STDERR", error.stderr)
        raise
    return plistlib.loads(result.stdout)


notarizeResult = plistlib.loads(sys.stdin.read().encode("ascii"))

notarisationRequestUUID = None

if "notarization-upload" in notarizeResult:
    notarisationRequestUUID = notarizeResult["notarization-upload"].get("RequestUUID")

if notarisationRequestUUID is None:
    print(notarizeResult)
    sys.exit(1)


waitTime = 16
numTries = 8

for i in range(numTries):
    time.sleep(waitTime)
    response = getNotarizeInfo(notarisationRequestUUID, sys.argv[1], sys.argv[2])
    info = response["notarization-info"]
    status = info["Status"]
    if status in ("success", "invalid"):
        break
    assert status == "in progress"
    # we need to be more patient
    waitTime *= 2
    print(f"trying again in {waitTime} seconds")
else:
    # Giving up
    print("notarization timed out")
    print("RequestUUID:", notarisationRequestUUID)
    sys.exit(1)

logURL = info["LogFileURL"]
os.system(f"curl -s {logURL} > notarize_log.txt")

if status == "invalid":
    print("notarization failed")
    print("RequestUUID:", notarisationRequestUUID)
    sys.exit(1)
