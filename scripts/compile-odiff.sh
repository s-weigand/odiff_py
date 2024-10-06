#!/usr/bin/sh
set -eux

ODIFF_VERSION="$(grep -v '^#' .odiff-version | xargs -d '\n')"
export ODIFF_VERSION
git clone --branch "$ODIFF_VERSION" --depth 1 https://github.com/dmtrKovalenko/odiff
cd odiff || exit
/root/.vcpkg/vcpkg install
export PKG_CONFIG_PATH="$PWD/vcpkg_installed/x64-linux/lib/pkgconfig/"
LIBPNG_CFLAGS="$(pkg-config --cflags libspng_static)"
export LIBPNG_CFLAGS
LIBPNG_LIBS="$(pkg-config --libs libspng_static)"
export LIBPNG_LIBS
LIBTIFF_CFLAGS="$(pkg-config --cflags libtiff-4)"
export LIBTIFF_CFLAGS
LIBTIFF_LIBS="$(pkg-config --libs libtiff-4)"
export LIBTIFF_LIBS
LIBJPEG_CFLAGS="$(pkg-config --cflags libturbojpeg)"
export LIBJPEG_CFLAGS
LIBJPEG_LIBS="$(pkg-config --libs libturbojpeg)"
export LIBJPEG_LIBS
opam init --disable-sandboxing --shell-setup
opam switch --no-install --packages=ocaml-variants.5.2.0+options,ocaml-option-flambda create .
opam exec -- opam install . --deps-only --with-test -y
opam exec -- dune build --verbose
opam exec -- dune exec ODiffBin -- --version
opam exec -- dune runtest
mkdir /project/odiff_py/bin
opam exec -- dune clean
opam exec -- dune build --release
cp "_build/default/bin/ODiffBin.exe" "/project/odiff_py/bin/odiff.exe"
cp "LICENSE" "/project/odiff_py/bin/LICENSE-odiff"
