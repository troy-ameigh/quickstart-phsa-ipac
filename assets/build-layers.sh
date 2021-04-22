#!/usr/bin/env bash
CURRENT_DIR=$(reldir=$(dirname -- "$0"; echo x); reldir=${reldir%?x}; cd -- "$reldir" && pwd && echo x); CURRENT_DIR=${CURRENT_DIR%?x}
cd "$CURRENT_DIR"
OIFS="$IFS"
IFS=$'\n'

LAYERS="$(cd $CURRENT_DIR; ls -d */ | awk -F'/' '{print $1}')"

for LAYER in $LAYERS
do
	echo -e "\nBuilding layer $LAYER..."
	cd $CURRENT_DIR
	mkdir -p $LAYER/python
	pip3 install -r $LAYER/requirements.txt -t $LAYER/python/ --upgrade
	cd $LAYER
	zip -q -r $LAYER.zip python/
done
