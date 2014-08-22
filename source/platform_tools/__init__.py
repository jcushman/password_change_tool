import importlib
import sys

platform_module = importlib.import_module('platform_tools.'+sys.platform)
globals().update(platform_module.__dict__)

