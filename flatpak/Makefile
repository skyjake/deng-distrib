BUILD_DIR=$(HOME)/build-flatpak
MANIFEST=net.dengine.Doomsday.json
KEY_ID=15674AE498667047A3EB9431BACCFCFB98DB2EDC
BUNDLE_FILE=doomsday.flatpak

all: build bundle

build: ${MANIFEST}
	flatpak-builder \
		--repo=repo \
		--force-clean \
		--gpg-sign=${KEY_ID} \
		${BUILD_DIR} \
		${MANIFEST}

bundle:
	flatpak build-bundle repo ${BUNDLE_FILE} net.dengine.Doomsday \
		--runtime-repo=https://flathub.org/repo/flathub.flatpakrepo
