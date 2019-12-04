import asyncio
from corefoundationasyncio import CoreFoundationEventLoop

# Make sure these classes are loaded
from fontgoggles.mac.projectDocument import FGProjectDocument
from fontgoggles.mac.appDelegate import FGAppDelegate


if __name__ == "__main__":
    loop = CoreFoundationEventLoop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        loop.close()
