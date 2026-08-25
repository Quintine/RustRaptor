#!/bin/sh
# Launch Raptor: Call of the Shadows (original engine + original data).
# Requires: SDL2 (user-local build OK at ~/.local), GLB files in original/.
set -e
cd "$(dirname "$0")"

if [ ! -d original ]; then
    echo "Extract the original game archive first:" >&2
    echo "  unzip 'Raptor Call of the Shadows 2002 Registered.zip' -d original" >&2
    exit 1
fi

mkdir -p game
for i in 0 1 2 3 4; do
    ln -sf "$PWD/original/Raptor Call of the Shadows/FILE000$i.GLB" "game/FILE000$i.GLB" 2>/dev/null
done

if [ ! -x game/raptor ]; then
    echo "Building raptor (first run)..." >&2
    cmake -E make_directory raptor/build
    ( cd raptor/build && cmake .. -DCMAKE_BUILD_TYPE=Release ${CMAKE_PREFIX_PATH:+-DCMAKE_PREFIX_PATH=$CMAKE_PREFIX_PATH} && make -j"$(nproc)" )
    cp raptor/build/bin/raptor game/
fi

export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$HOME/.local/lib"
cd game
exec ./raptor
