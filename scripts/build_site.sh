#!/bin/sh
# Assemble the project page (site/) with the guide pictures into _site/, ready for GitHub Pages.
#   scripts/build_site.sh            # then open _site/index.html, or serve the folder
set -eu
cd "$(dirname "$0")/.."
rm -rf _site
mkdir -p _site/images
cp site/index.html site/style.css _site/
cp frontend/public/favicon.svg _site/
cp docs/images/room-revealed.png docs/images/room-player.png docs/images/phone-player.png \
  docs/images/dark-mode.png docs/images/settings-queue-filter.png docs/video/tour-poster.png \
  _site/images/
touch _site/.nojekyll
echo "built _site/"
