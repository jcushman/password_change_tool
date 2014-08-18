from fabric.api import *

def build(zip=True):
    local("pyinstaller -y build/main.spec")
    local("cp build/Info.plist dist/FreshPass.app/Contents/")
    if zip:
        local("cd dist && rm -f FreshPass.app.zip && zip -r FreshPass.app.zip FreshPass.app")

def make_icon():
    local("iconutil --convert icns assets/icon.iconset")
