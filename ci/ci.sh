#!/usr/bin/env bash

readonly CI_IMG="${DEP_CI_REF:-registry.opensource.zalan.do/stups/openjdk}"

docker run \
    --net=host \
    -v /etc/resolv.conf:/etc/resolv.conf \
    -v /usr/local/share/ca-certificates/cdp:/usr/local/share/ca-certificates \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(which docker):/usr/bin/docker \
    --privileged \
    -w /project \
    -v $(pwd):/project \
    "$CI_IMG" "$@"