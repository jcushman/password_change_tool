from fabric.api import *

def build():
    local("pyinstaller -y build/main.spec")

def make_icon():
    local("iconutil --convert icns assets/icon.iconset")