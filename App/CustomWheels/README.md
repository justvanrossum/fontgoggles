This folder contains custom wheels, because the ones on PyPI do not qualify or work when codesigning and notarizing the FontGoggles application.

#lxml

The official wheel blocks notarizing:

    "The binary uses an SDK older than the 10.9 SDK."

#uharfbuzz

Codesigning and notarizing works, validating the code signatures works, yet when uharfbuzz gets imported upon running the application on macOS 10.10 (maybe also others, but not 10.15) it results in an dyld ImportError, claiming that the signature is invalid. If I build uharfbuzz from the source, this does not happen. I have no idea what the difference could be.