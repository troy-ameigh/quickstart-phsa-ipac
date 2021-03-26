#!/usr/bin/env bash
CURRENT_DIR=$(reldir=$(dirname -- "$0"; echo x); reldir=${reldir%?x}; cd -- "$reldir" && pwd && echo x); CURRENT_DIR=${CURRENT_DIR%?x}
cd "$CURRENT_DIR"
OIFS="$IFS"
IFS=$'\n'


SUFFIX=""
RUNTIME=""
REGION=""

while getopts ":hs:r:t:" opt; do
	case ${opt} in
		h  )
		 	echo "Usage: $0 -s <suffix> -t <runtime> -r <region>"
			exit 0
			;;
		s  )
			SUFFIX=$OPTARG
			;;
		t  )
			RUNTIME=$OPTARG
			;;
		r  )
			REGION=$OPTARG
			;;
		\? )
			echo "Invalid option: -$OPTARG" 1>&2
			exit 1
			;;
	esac
done
shift $((OPTIND -1))

if [ -z ${RUNTIME} ] || [ -z ${REGION} ]; then
	echo "Usage: $0 -s <suffix> -t <runtime> -r <region>"
	exit 1
fi

LAYERS="$(cd $CURRENT_DIR; ls -d */ | awk -F'/' '{print $1}')"

for LAYER in $LAYERS
do
	echo -e "\nPublishing layer $LAYER..."
	cd $CURRENT_DIR
	
	aws lambda publish-layer-version --layer-name ${LAYER}${SUFFIX} --zip-file fileb://${LAYER}/${LAYER}.zip --compatible-runtimes ${RUNTIME} --region ${REGION}
done
