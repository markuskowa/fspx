# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import hashlib
import base64


def hash_file(path: str) -> str:
    """Calculate the sha256 of a file
    """
    with open(path, "rb") as f:
        bytes = f.read()
        return hash_data(bytes)

def hash_data(bytes) -> str:
    return hashlib.sha256(bytes).hexdigest()

def hash_exists(sha256: str, dstore: str) -> bool:
    storePath = os.path.join(dstore, sha256)

    if not os.path.exists(storePath):
        return False

    return True

def is_valid_name(hashed_name: str) -> bool:
    """Check is filename is valid store file name
    """
    if len(os.path.basename(hashed_name)) == 64:
        return True

    return False

def link_to_store(path: str, hash: str, dstore: str, relative: bool = True, gcroot: bool = False) -> None:
    """Create a tracked link to data store
    """

    store_path = os.path.join(dstore, hash)

    if os.path.islink(path):
        os.remove(path)

    if relative:
        store_path = os.path.relpath(store_path, os.path.dirname(path))
    else:
        store_path = os.path.realpath(store_path)

    os.symlink(store_path, path)

    # hash/link path hash -> link path
    if gcroot:
        gc_path = os.path.join(dstore, "gcroots", hash)
        try:
            os.makedirs(gc_path)
        except FileExistsError:
            None

        link_hash = hashlib.sha1(path.encode()).digest()
        link_hash = base64.b64encode(link_hash, altchars=b"+-").decode("ascii")

        link_name = os.path.join(gc_path, link_hash)
        if relative:
            link_path = os.path.relpath(path, gc_path)
        else:
            link_path = os.path.realpath(path)

        try:
            os.symlink(link_path, link_name)
        except FileExistsError:
            os.remove(link_name)
            os.symlink(link_path, link_name)


def clean_garbage(dstore: str) -> int:
    """Run garbage collection, and delete unlinked and dead files
    """

    files_removed = 0
    # clear gc roots first, weed out dead links
    for file in os.scandir(os.path.join(dstore, "gcroots")):
        if file.is_dir():
            refcount = 0
            for link in os.scandir(file.path):
                if link.is_symlink():
                    # it is a symlink
                    if os.path.exists(link.path):
                        # link is alive
                        if os.path.basename(os.path.realpath(link.path)) == file.name:
                            # link points back to this hash/file
                            refcount = refcount + 1
                        else:
                            # gc-root link is dead, does not point back to itself
                            os.remove(link)

                    elif os.path.lexists(link.path):
                        # dead link, link does not exists anymore
                        os.remove(link)

            print(file.name + " " + str(refcount))
            if refcount == 0:
                # remove root and data file itself
                os.rmdir(file.path)
                os.system("chmod u+w {}".format(os.path.join(dstore, file.name)))
                os.remove(os.path.join(dstore, file.name))
                files_removed = files_removed + 1

    # clear out files that do not have gc root
    for file in os.scandir(dstore):
        if file.is_file():
            if not os.path.exists(os.path.join(dstore, "gcroots", file.name)):
                os.system("chmod u+w {}".format(file.path))
                os.remove(file.path)
                files_removed = files_removed + 1

    return files_removed

def verify_store(dstore: str) -> bool:
    """Verify all files in store
    """
    valid = True

    for file in os.scandir(dstore):
        if file.is_file():
            if is_valid_name(file.name):
                hash = hash_file(os.path.join(dstore, file.name))
                if hash != file.name:
                    print("Invalid file found: {} has hash {}".format(file.name, hash))
                    valid = False
            else:
                print("Invalid filename {}".format(file.name))
                valid = False

    return valid

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

def copy_to_store(path: str, dstore: str) -> str:
    """Copy file into store
    """
    sha256 = hash_file(path)
    name = os.path.basename(path)
    storePath = os.path.join(dstore, sha256)

    if not os.path.exists(storePath):
        print("Importing file {} into {} ({})".format(name, dstore, sha256))
        os.system("cp {} {}".format(path, storePath))
        os.system("chmod -w {}".format(storePath))

    return sha256

def import_data(data, dstore: str) -> str:
    """Write data directly into store
    """
    hash = hash_data(data)

    if not hash_exists(hash, dstore):
        storePath = os.path.join(dstore, hash)
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
            hash = copy_to_store(p, dstore)
        else:
            if idx > 0:
                hash = copy_to_store(p, dstore)
            else:
                hash = os.path.basename(p)

        pathkv[name] = hash

    return pathkv
