# SPDX-License-Identifier: GPL-3.0-only

import json

def readJson(path):
    with open(path, "rb") as f:
        return json.load(f)

def writeJson(path, js):
    with open(path, "w") as jsfile:
        json.dump(js, jsfile)


