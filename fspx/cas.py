# SPDX-License-Identifier: GPL-3.0-only

import os
import hashlib


def hashFile(path):
    """Calculate the sha256 of a file
    """
    with open(path, "rb") as f:
        bytes = f.read()
        return hashlib.sha256(bytes).hexdigest();

def hashExists(sha256, dstore):
    storePath = "{}/{}".format(dstore, sha256)

    if not os.path.exists(storePath):
        return False

    return True

def hash_from_store_path(path: str, dstore: str) -> str:

    path = os.path.realpath(path)
    dstore = os.path.realpath(dstore)

    try:
        idx = path.index(dstore)
    except ValueError:
        raise Exception("{} is not data store {}".format(path, dstore))
    else:
        if idx > 0:
            raise Exception("{} is not data store {}".format(path, dstore))

    return os.path.basename(path)

def importPaths(paths, dstore, prefix=""):
    """Copy a list of files into the dstore.

        return: list of sha256 hashes
    """

    # move file into store, helper function
    def moveToStore(p):
        sha256 = hashFile(p)
        name = os.path.basename(p)
        storePath = "{}/{}".format(dstore, sha256)

        if not os.path.exists(storePath):
            print("Importing file {} into {} ({})".format(name, dstore, sha256))
            os.system("cp {} {}".format(p, storePath))

        return sha256

    pathkv = {}

    dstore = os.path.realpath(dstore)

    # create dstore if not yet there
    if not os.path.exists(dstore):
        os.makedirs(dstore)

    # hash all paths
    for p in paths:
        name = p

        # allow environment variables in path
        p = os.path.expandvars("{}{}".format(prefix, p))
        p = os.path.realpath(p)

        # import path
        try:
            idx = p.index(dstore)
        except ValueError:
            hash = moveToStore(p)
        else:
            if idx > 0:
                hash = moveToStore(p)
            else:
                hash = os.path.basename(p)

        pathkv[name] = hash

    return pathkv
