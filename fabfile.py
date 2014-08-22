from fabric.api import *

def build(zip=True):
    local("pyinstaller -y build/main.spec")
    local("cp build/Info.plist dist/FreshPass.app/Contents/")
    if zip:
        local("cd dist && rm -f FreshPass.app.zip && zip -r FreshPass.app.zip FreshPass.app")

def make_icon():
    local("iconutil --convert icns resources/icon.iconset")

def combine_tiff():
    # TODO: generalize
    local("tiffutil -cathidpicheck assets/disk-image-background.jpg 'assets/disk-image-background@2x.jpg' -out resources/disk-image-background.tiff")

def create_disk_image():
    #local("hdiutil create assets/mac_disk_image.dmg -volname 'FreshPass Secure Disk' -fs HFS+ -srcfolder assets/mac_disk_image/ -format UDRW")
    local("hdiutil attach -readwrite assets/mac_disk_image.dmg")
    local("osascript 'assets/configure disk image.scpt'")

def prepare_disk_image():
    local("hdiutil convert assets/mac_disk_image.dmg -format UDZO -imagekey zlib-level=9 -o resources/mac_disk_image_compressed.dmg")
    #local("hdiutil convert assets/mac_disk_image.dmg -format UDRO -o assets/mac_disk_image_compressed.dmg")
    local("asr imagescan --source resources/mac_disk_image_compressed.dmg")