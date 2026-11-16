#!/bin/sh
# Assemble the project page (site/) with the guide pictures into _site/, ready for GitHub Pages.
#   scripts/build_site.sh            # then open _site/index.html, or serve the folder
#   scripts/build_site.sh OUT        # into another folder (tests/test_docs.py uses this)
set -eu
cd "$(dirname "$0")/.."
out="${1:-_site}"
rm -rf "$out"
mkdir -p "$out/images"
cp site/index.html site/style.css "$out/"
cp frontend/public/favicon.svg "$out/"
cp docs/images/room-revealed.png docs/images/room-player.png docs/images/phone-player.png \
  docs/images/dark-mode.png docs/images/settings-queue-filter.png docs/video/tour-poster.png \
  "$out/images/"
touch "$out/.nojekyll"
echo "built $out/"
