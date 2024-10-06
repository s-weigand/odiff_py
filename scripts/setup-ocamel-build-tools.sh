#!/usr/bin/sh
set -ex

yum install zip -y
mkdir /build-tools
cd /build-tools || exit
curl -o install-opam.sh  https://opam.ocaml.org/install.sh -L
sh install-opam.sh --download-only
mv opam* /usr/local/bin/opam
chmod +x /usr/local/bin/opam
curl -O https://aka.ms/vcpkg-init.sh -L
(. /build-tools/vcpkg-init.sh)|| exit 0
