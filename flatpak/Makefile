BUILD_DIR=$(HOME)/build-flatpak
REPO_DIR=$(HOME)/public_html/repo
MANIFEST=net.dengine.Doomsday.json
KEY_ID=15674AE498667047A3EB9431BACCFCFB98DB2EDC
BUNDLE_FILE=doomsday.flatpak
BUILD := $(shell ../build_number.py --print)

all: build repo

${MANIFEST}: ${MANIFEST}.in
	sed 's/$${DENG_BUILD}/${BUILD}/' net.dengine.Doomsday.json.in > ${MANIFEST}

build: ${MANIFEST}
	flatpak-builder \
		--repo=${REPO_DIR} \
		--force-clean \
		--gpg-sign=${KEY_ID} \
		${BUILD_DIR} \
		${MANIFEST}

bundle:
	flatpak build-bundle ${REPO_DIR} ${BUNDLE_FILE} net.dengine.Doomsday \
		--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo

repo:
	flatpak build-update-repo ${REPO_DIR} \
		--gpg-sign=${KEY_ID} \
		--generate-static-deltas \
		--prune-depth=3

sync:
	rsync -a --progress --delete-after --rsh="dengpass ssh" ${REPO_DIR}/ skyjake@dengine.net:files/repo/

.PHONY: all ${MANIFEST} bundle repo sync

