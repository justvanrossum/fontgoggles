#!/bin/sh

set -e  # make sure to abort on error
set -x  # echo commands

cd "${0%/*}"  # cd into the folder containing this script

mkdir -p build

gcc -g -fPIC -c -mmacosx-version-min=10.9 -o build/makePathFromOutline.o makePathFromOutline.m

ld -dylib -macosx_version_min 10.9 -o libmakePathFromOutline.dylib -framework AppKit -arch x86_64 -lsystem.b build/makePathFromOutline.o
