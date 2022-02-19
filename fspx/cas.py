# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import hashlib


def hash_file(path: str) -> str:
    """Calculate the sha256 of a file
    """
    with open(path, "rb") as f:
        bytes = f.read()
        return hash_data(bytes)

def hash_data(bytes) -> str:
    return hashlib.sha256(bytes).hexdigest();

def hash_exists(sha256: str, dstore: str) -> bool:
    storePath = "{}/{}".format(dstore, sha256)

    if not os.path.exists(storePath):
        return False

    return True

def link_to_store(path: str, hash: str, dstore: str, relative: bool = True) -> None:
    """Create a tracked linked to data store
    """

    store_path = "{}/{}".format(dstore, hash)

    if os.path.islink(path):
        os.remove(path)

    if relative:
        store_path = os.path.relpath(store_path, os.path.dirname(path))
    else:
        store_path = os.path.realpath(store_path)

    os.symlink(store_path, path)

def hash_from_store_path(path: str, dstore: str) -> str:
    """Extract file name (hash) from store path
    """
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

def move_to_store(path: str, dstore: str) -> str:
    sha256 = hash_file(path)
    name = os.path.basename(path)
    storePath = "{}/{}".format(dstore, sha256)

    if not os.path.exists(storePath):
        print("Importing file {} into {} ({})".format(name, dstore, sha256))
        os.system("cp {} {}".format(path, storePath))
        os.system("chmod -w {}".format(storePath))

    return sha256

def import_data(data, dstore: str) -> str:
    hash = hash_data(data)

    if not hash_exists(hash, dstore):
        storePath = "{}/{}".format(dstore, hash)
        print("Importing {} into {}".format(hash, dstore))

        with open(storePath, "wb") as f:
            f.write(data)

        os.system("chmod -w {}".format(storePath))

    return hash

def import_paths(paths: list[str], dstore: str, prefix: str="") -> dict[str, str]:
    """Copy a list of files into the dstore.

        return: list of sha256 hashes
    """

    # move file into store, helper function

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
            hash = move_to_store(p, dstore)
        else:
            if idx > 0:
                hash = move_to_store(p, dstore)
            else:
                hash = os.path.basename(p)

        pathkv[name] = hash

    return pathkv
