# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

import json

def read_json(path):
    with open(path, "rb") as f:
        return json.load(f)

def write_json(path, js):
    with open(path, "w") as jsfile:
        json.dump(js, jsfile)


