#!/bin/sh

set -e  # make sure to abort on error
set -x  # echo commands

cd "${0%/*}"  # cd into the folder containing this script

mkdir -p build

cc -g -fPIC -c -mmacosx-version-min=10.9 -arch x86_64 -arch arm64 -o build/makePathFromOutline.o makePathFromOutline.m

cc -dynamiclib -mmacosx-version-min=10.9 -o ../Lib/fontgoggles/mac/libmakePathFromOutline.dylib -framework AppKit -arch x86_64 -arch arm64 -lsystem.b build/makePathFromOutline.o
