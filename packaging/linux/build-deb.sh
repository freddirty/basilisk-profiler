#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build dist/basilisk-profiler_<version>_amd64.deb from a PyInstaller one-folder build.
#   packaging/linux/build-deb.sh [version]     (default: __version__ of the package)
# Needs: pyinstaller in the active Python, dpkg-deb.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
VERSION=${1:-$("$PYTHON" -c "import re;print(re.search(r'__version__ = .(.+?).$', open('src/basilisk_profiler/__init__.py').read(), re.M).group(1))")}

"$PYTHON" -m PyInstaller packaging/linux/basilisk_profiler.spec --noconfirm

PKGROOT=$(mktemp -d)
trap 'rm -rf "$PKGROOT"' EXIT
install -d "$PKGROOT/opt" "$PKGROOT/usr/bin" "$PKGROOT/DEBIAN" \
    "$PKGROOT/usr/share/applications" "$PKGROOT/usr/share/icons/hicolor/256x256/apps" \
    "$PKGROOT/usr/lib/udev/rules.d" "$PKGROOT/usr/share/doc/basilisk-profiler"
cp -a dist/basilisk-profiler "$PKGROOT/opt/basilisk-profiler"
ln -s /opt/basilisk-profiler/basilisk-profiler "$PKGROOT/usr/bin/basilisk-profiler"
install -m644 packaging/linux/basilisk-profiler.desktop "$PKGROOT/usr/share/applications/"
install -m644 packaging/linux/app.png \
    "$PKGROOT/usr/share/icons/hicolor/256x256/apps/basilisk-profiler.png"
install -m644 packaging/linux/70-basilisk-profiler.rules "$PKGROOT/usr/lib/udev/rules.d/"
install -m644 LICENSE "$PKGROOT/usr/share/doc/basilisk-profiler/copyright"
install -m755 packaging/linux/postinst packaging/linux/postrm "$PKGROOT/DEBIAN/"

SIZE=$(du -sk --exclude=DEBIAN "$PKGROOT" | cut -f1)
cat > "$PKGROOT/DEBIAN/control" <<CONTROL
Package: basilisk-profiler
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Attila K <noreply@github.com>
Installed-Size: $SIZE
Depends: libc6 (>= 2.39), libegl1, libgl1, libfontconfig1, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libdbus-1-3, udev
Homepage: https://github.com/freddirty/basilisk-profiler
Description: Profile manager for the Razer Basilisk V3 Pro
 Maps keyboard functions to the mouse buttons, stores profiles in the
 mouse's onboard slots and switches profiles by the active window (X11).
 Talks to the mouse over hidraw; includes the udev rule that gives the
 logged-in user access. Not affiliated with Razer Inc.
CONTROL

OUT="dist/basilisk-profiler_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group -Zxz --build "$PKGROOT" "$OUT"
echo "$OUT"
