set -e  # make sure to abort on error
set -x  # echo commands

mkdir -p build

gcc -g -fPIC -c -o build/makePathFromOutline.o makePathFromOutline.m

ld -dylib -macosx_version_min 10.9 -o build/makePathFromOutline.dylib -framework AppKit -arch x86_64 -lsystem.b build/makePathFromOutline.o
