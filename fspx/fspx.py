# SPDX-License-Identifier: GPL-3.0-only

import os
import hashlib
import json
import sys

# Default path for project files
cfgPath = ".fspx/"

# Path nix module files
instDir = "nix/"

def readJson(path):
    with open(path, "rb") as f:
        return json.load(f)

def writeJson(path, js):
    with open(path, "w") as jsfile:
        json.dump(js, jsfile)


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

def importInputPaths(job, name, dstore):
    """ Import inputs for job into dstore and update job manifest
    """

    assert(type(job['inputs']) is dict)

    # read manifest
    m = readManifest(name)
    mvalid = True

    # find unhashed paths and import them
    inputs=[]
    for file, hash in job['inputs'].items():
        # import paths if needed
        if hash == None:
            hash = importPaths([file], dstore)
            hash = hash[file]
        elif not hashExists(hash, dstore):
            hash = importPaths([file], dstore)
            hash = hash[file]

        # check manifest
        if not file in m['inputs']:
            m['inputs'][file] = hash
            mvalid = False
        elif m['inputs'][file] != hash:
            mvalid = False
            m['inputs'][file] = hash

    # check if function has changed
    if job['runScript'] != m['function']:
        m['function'] = job['runScript']
        valid = False

    # clear output in manifest
    if not mvalid:
        m['outputs'] = {}

    updateManifest(name, m)

    return m['inputs']

def importOutputPaths(job, name, dstore):

    assert(type(job['outputs']) is list)

    m = readManifest(name)

    # Import outputs into store
    storeHashes = importPaths(job['outputs'], dstore, prefix="{}/".format(job['workdir']))

    m['outputs'] = storeHashes
    updateManifest(name, m)

    return storeHashes

def linkPath(prefix, path, storePath):
    """Create a symlink into store
    """

    path = "{}{}".format(prefix, path)
    if os.path.islink(path):
        os.remove(path)

    os.symlink(storePath, path)

def readManifest(name):

    mfile = "{}/{}.manifest".format(cfgPath, name)
    if os.path.exists(mfile):
        m = readJson(mfile)
    else:
        m = {'inputs':{}, 'function':"", 'outputs':{}}

    return m

def updateManifest(name, data):

    mfile = "{}/{}.manifest".format(cfgPath, name)
    if os.path.exists(mfile):
        m = readJson(mfile)
    else:
        m = {}

    m = { **m, **data }

    writeJson(mfile, m)

def findAllJobs(jobsets, jobs = []):

    for name, job in jobsets.items():
        findAllJobs(job['dependencies'], jobs = jobs)
        jobs.append({ 'name' : name, 'job' : job})

    return jobs

def findJob(jobsets, name):

    for key, job in jobsets.items():
        if key == name:
            return job
        else:
            return findJob(job['dependencies'], name)

    return {}

def checkJob(name, job, dstore):
    """Check if the current config matches the manifest
    """

    manifest = readManifest(name)

    if not "outputs" in manifest:
        return False

    # check if outputs exist
    for name in job['outputs']:
        if not name in manifest['outputs']:
            return False

        if not hashExists(manifest['outputs'][name], dstore):
            return False

    # check if function is still valid
    if job['runScript'] != manifest['function']:
        return False

    # check if input hashes have changed
    for name, hash in job['inputs'].items():

        # check if input exists
        if not name in manifest['inputs']:
            return False

        # check fixed input
        if hash != None:
            if hash != manifest['inputs'][name]:
                return False

        # check hash
        sha256 = hashFile(name)
        if manifest['inputs'][name] != sha256:
            return False

    return True

def checkJobset(jobset, dstore, recalc = []):
    """Check all jobsets and return invalidated ones
    """

    valid = True
    for name, job in jobset.items():
        # check children
        recalc, cvalid = checkJobset(job['dependencies'], dstore, recalc)

        if not cvalid:
            valid = False
            recalc.append({'name' : name, 'job': job})
        elif not checkJob(name, job, dstore):
            valid = False
            recalc.append({'name' : name, 'job': job})


    return recalc, valid

def runJobs(jobset, jobnames, dstore):
    """Run a list of jobs
    """
    for name in jobnames:
        job = findJob(jobset, name)
        workdir = os.path.expandvars(job['workdir'])

        # Import inputs
        inputs = importInputPaths(job, name, dstore)

        # Link inputs into workdir
        try:
            os.makedirs(workdir + "/inputs")
        except FileExistsError:
            None

        for inp, hash in inputs.items():
            tmpName = "{}/inputs/{}".format(workdir, os.path.basename(inp))
            storeName = "{}/{}".format(os.path.realpath(dstore), hash)
            if os.path.islink(tmpName):
                os.remove(tmpName)

            os.symlink(storeName, tmpName)


        # Run job
        print("running job {}, {}".format(name, job['runScript']))
        ret = os.system(job['runScript'])
        if os.waitstatus_to_exitcode(ret) != 0:
            print("Running job {} failed!".format(name))
            exit(1)

        # Import outputs
        print("Importing outputs of job {}".format(name))

        try:
            outputs = importOutputPaths(job, name, dstore)
        except FileNotFoundError as not_found:
            print("Output {} missing!".format(not_found.filename))

        # Link outputs into dstore
        try:
            os.makedirs("outputs")
        except FileExistsError:
            None
        for file, hash in outputs.items():
            outName = "outputs/{}".format(file)
            storeName = "{}/{}".format(os.path.realpath(dstore), hash)
            if os.path.islink(outName):
                os.remove(outName)
            os.symlink(storeName, outName)

        print()


def cmd_build(cfgnix):
    '''Build the project configuration from nix configuration file
    '''

    print("Build it")
    try:
        os.mkdir(cfgPath)
    except FileExistsError:
        None
    ret = os.system("nix-build {}/project.nix --arg config {} --out-link {}/cfg --show-trace".format(instDir, cfgnix, cfgPath))
    return os.waitstatus_to_exitcode(ret)

def cmd_list():
    '''List all jobs in project
    '''
    for job in findAllJobs(config['jobsets']):
        print(job['name'])

def cmd_check(config):
    '''Check if job results are valid
    '''

    jobs, valid = checkJobset(config['jobsets'], config['dstore'], recalc=[])

    if not valid:
        print("The following jobs need to be re-run:")

        for j in jobs:
            print(j['name'])

    return jobs, valid

def cmd_shell(config, jobname):
    '''Start a shell with job environment
    '''
    job = findJob(config['jobsets'], jobname)
    os.system("nix-shell -p {}".format(job['env']))


def packageJob(name, job):

    manifest = readManifest(name)

    # fix inputs
    inputs = {}
    for file, hash in job['inputs'].items():
        if hash == None:
            hash = manifest['inputs'][file]
        inputs[file] = hash

    job['inputs'] = inputs

    # fix outputs
    outputs = {}
    for file in job['outputs']:
        outputs[file] = manifest['outputs'][file]

    job['outputs'] = outputs

    dependencies = {}
    for dname, djob in job['dependencies'].items():
        dependencies[dname] = packageJob(dname, djob)

    job['dependencies'] = dependencies

    # This is irrelevant for an archived job
    job.pop("workdir")

    return job

def copyFilesToExternal(jobsets, targetDir, targetStore, dstore):

    linkStore = os.path.relpath(targetStore, targetDir + "/io")
    for name, job in jobsets.items():
        for file, hash in job['inputs'].items():
            if not os.path.exists("{}/{}".format(targetStore, hash)):
                os.system("cp {}/{} {}".format(dstore, hash, targetStore))
            if not os.path.exists("{}/{}".format(targetDir, file)):
                os.symlink("{}/{}".format(linkStore, hash), "{}/inputs/{}".format(targetDir, os.path.basename(file)))

        for file, hash in job['outputs'].items():
            if not os.path.exists("{}/{}".format(targetStore, hash)):
                os.system("cp {}/{} {}".format(dstore, hash, targetStore))
            os.symlink("{}/{}".format(linkStore, hash), "{}/outputs/{}".format(targetDir, os.path.basename(file)))

        copyFilesToExternal(job['dependencies'], targetDir, targetStore, dstore)

def collectJobScripts(jobsets, scripts=[]):

    for name, job in jobsets.items():
        scripts.append(job['jobScript'])
        scripts = collectJobScripts(job['dependencies'], scripts)

    return scripts

def cmd_export(config, toDir, targetStore):
    '''Export the project
    '''

    # Copy config file and update hashes
    jobsets = {}
    for name, job in config['jobsets'].items():
        jobsets[name] = packageJob(name, job)

    config['jobsets'] = jobsets

    # Remove workdir (not needed in archive)
    config.pop("workdir")

    # Copy inputs and outputs to archive
    print("Copying files to archive...")
    os.makedirs(toDir)

    os.mkdir("{}/inputs".format(toDir))
    os.mkdir("{}/outputs".format(toDir))

    try:
        os.makedirs(targetStore)
    except FileExistsError:
        None

    copyFilesToExternal(config['jobsets'], toDir, targetStore, config['dstore'])

    # Fix dstore
    config['dstore'] = os.path.relpath(targetStore, toDir)
    writeJson("{}/config.json".format(toDir), config)

    # Create NAR
    print("Save job scripts to NAR archive...")
    allJobScripts =  collectJobScripts(config['jobsets'])
    os.system("nix-store --export $(nix-store -qR {}) > {}/jobScripts.nar".format(" ".join(allJobScripts), toDir))

#
# Main
#

def main():
    if len(sys.argv) < 2:
        print("help")
        exit(0)


    argv = sys.argv[1:]

    if argv[0] == "build":
        ret = cmd_build(argv[1])
        exit(ret)

    config = readJson("{}/cfg/project.json".format(cfgPath))

    if argv[0] == "list":
        cmd_list()

    elif argv[0] == "run":

        if len(argv) == 1:
            jobs, valid = checkJobset(config['jobsets'], config['dstore'], recalc=[])
            if not valid:
                runJobs(config['jobsets'], list(map(lambda x: x['name'], jobs)), config['dstore'])
        else:
            runJobs(config['jobsets'], argv[1:], config['dstore'])

    elif argv[0] == "check":
        jobs, valid = cmd_check(config)
        if not valid:
            exit(1)


    elif argv[0] == "shell":

        if len(argv) != 2:
            print("job name is missing")
            exit(1)

        cmd_shell(config, argv[1])


    elif argv[0] == "export":
        if not cmd_check():
            print("Project data is not valid. Can not export project.")
            exit(1)

        cmd_export(config, argv[1], argv[2])

    elif argv[0] == "import":
        importPaths(argv[1:], config['dstore'])


    exit(0)

if __name__ == '__main__':
    main()
