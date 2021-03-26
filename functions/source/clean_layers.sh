#!/usr/bin/env bash
CURRENT_DIR=$(reldir=$(dirname -- "$0"; echo x); reldir=${reldir%?x}; cd -- "$reldir" && pwd && echo x); CURRENT_DIR=${CURRENT_DIR%?x}
cd $CURRENT_DIR

rm -fr */*\.zip
rm -fr */python/*

