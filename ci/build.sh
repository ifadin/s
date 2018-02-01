#!/usr/bin/env bash

set -e
set -o pipefail

readonly AUTHOR="${AUTHOR:-image author}"
readonly ARTIFACT="${ARTIFACT:-image name}"
readonly REGISTRY="${REGISTRY:-registry.opensource.zalan.do}"

function getLatestTag(){
    # Get latest available image tag in the registry
    # Example: pierone latest --url ${REGISTRY} ${AUTHOR} ${ARTIFACT}
    echo 0
}

readonly LATEST=${LATEST:-$(getLatestTag)}
readonly TAG=$((LATEST+1))
readonly IMAGE="${REGISTRY}/${AUTHOR}/${ARTIFACT}:${TAG}"

# some custom aws encrypted secret
readonly SECRET="${SECRET:-some_secret}"

echo "Decrypting access token..."
## <-- aws authentication goes here
readonly TOK="$(aws --region=eu-central-1 kms decrypt --ciphertext-blob fileb://<(echo "${SECRET}" | base64 --decode) --query Plaintext --output text | base64 --decode | base64 --decode)"

echo "Building ${IMAGE} ..."
docker build -t ${IMAGE} -f Dockerfile.ci --build-arg TOKEN="${TOK}" ../

if [ "$1" == "--push" ]; then
    ## <--- docker registry authentication goes here
    docker push ${IMAGE}
fi