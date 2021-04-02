#!/usr/bin/env bash

layer=$1

regions="$2"

get_versions () {
  echo $(aws lambda list-layer-versions --layer-name "$layer" --region "$region" --output text --query LayerVersions[].Version | tr '[:blank:]' '\n')
}

for region in $regions;
do
  versions=$(get_versions "$region")
  for version in $versions;
  do
    echo "deleting arn:aws:lambda:$region:*:layer:$layer:$version"
    aws lambda delete-layer-version --region "$region" --layer-name "$layer" --version-number "$version"
  done
done