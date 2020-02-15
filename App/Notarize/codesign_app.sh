#!/bin/bash

set -e # abort on errors

DEV_ID=$1
APP_PATH=$2
ENTITLEMENTS=$3

find "$APP_PATH" -iname '*.so' -or -iname '*.dylib' |
    while read libfile; do
          codesign --sign "$DEV_ID" \
                   --entitlements "$ENTITLEMENTS" \
                   --deep "${libfile}" \
                   --force \
                   --options runtime;
    done;

codesign --sign "$DEV_ID" \
         --entitlements "$ENTITLEMENTS" \
         --deep "$APP_PATH" \
         --force \
         --options runtime;
