# SPDX-License-Identifier: GPL-3.0-only

import os

from . import utils
from . import cas

# Default path for project files
cfgPath = ".fspx/"

def is_output(name: str) -> bool:
    if name[0] == ":":
        return True
    else:
        return False

def to_outpath(name: str) -> str:
    if is_output(name):
        return "outputs/" + name[1:]
    else:
        return name


def importInputPaths(job: dict, name: str, dstore: str) -> dict:
    """ Import inputs for job into dstore and update job manifest
    """

    assert(type(job['inputs']) is dict)

    # read manifest
    m = readManifest(name)
    mvalid = True

    # find unhashed paths and import them
    for file, hash in job['inputs'].items():
        if not is_output(file):
            # import paths if needed
            if hash == None:
                hash = cas.import_paths([file], dstore)
                hash = hash[file]
            elif not cas.hash_exists(hash, dstore):
                hash = cas.import_paths([file], dstore)
                hash = hash[file]
        else:
            # import to check hash
            hash = cas.import_paths([to_outpath(file)], dstore)
            hash = hash[to_outpath(file)]

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

    # clear output in manifest
    if not mvalid:
        m['outputs'] = {}

    updateManifest(name, m)

    return m['inputs']

def importOutputPaths(job, name, dstore):

    assert(type(job['outputs']) is list)

    m = readManifest(name)

    # Import outputs into store
    storeHashes = cas.import_paths(job['outputs'], dstore, prefix="{}/".format(job['workdir']))

    m['outputs'] = storeHashes
    updateManifest(name, m)

    return storeHashes

def readManifest(name: str) -> dict:

    mfile = "{}/{}.manifest".format(cfgPath, name)
    if os.path.exists(mfile):
        m = utils.readJson(mfile)
    else:
        m = {'inputs':{}, 'function':"", 'outputs':{}}

    return m

def updateManifest(name, data):

    mfile = "{}/{}.manifest".format(cfgPath, name)
    if os.path.exists(mfile):
        m = utils.readJson(mfile)
    else:
        m = {}

    m = { **m, **data }

    utils.writeJson(mfile, m)

def findAllJobs(jobsets, jobs = []):

    for name, job in jobsets.items():
        findAllJobs(job['deps'], jobs = jobs)
        jobs.append({ 'name' : name, 'job' : job})

    return jobs

def checkJob(name: str, job: dict, dstore: str) -> bool:
    """Check if the current config matches the manifest
    """

    manifest = readManifest(name)

    if not "outputs" in manifest:
        return False

    # check if outputs exist
    for file in job['outputs']:
        if not file in manifest['outputs']:
            return False

        if not cas.hash_exists(manifest['outputs'][file], dstore):
            return False

    # check if function is still valid
    if job['runScript'] != manifest['function']:
        return False

    # check if input hashes have changed
    for file, hash in job['inputs'].items():

        # check if input exists
        if not file in manifest['inputs']:
            return False

        # check fixed input
        if hash != None:
            if is_output(file):
                # check if expected hash and output match
                outhash = cas.hash_from_store_path(to_outpath(file), dstore)
                if hash != outhash:
                    print("WARNING: output {} has not the expect input hash!".format(file))
                    return False
            if hash != manifest['inputs'][file]:
                return False


        # check hash
        if is_output(file):
            if not os.path.exists(to_outpath(file)):
                return False

            hash = cas.hash_from_store_path(to_outpath(file), dstore)
        else:
            hash = cas.hash_file(file)

        if manifest['inputs'][file] != hash:
            return False

    return True

def checkJobset(jobset: dict, dstore: str, recalc = []) -> tuple[list[str], bool]:
    """Check all jobsets and return invalidated ones
    """

    valid = True
    for name, job in jobset.items():
        if name not in recalc:
            # check children
            recalc, cvalid = checkJobset(job['deps'], dstore, recalc)

            valid = cvalid
            if not checkJob(name, job, dstore):
                valid = False
                recalc.append(name)
        else:
            valid = False

    return recalc, valid

def linkInputsToWorkdir(inputs, workdir, dstore):
    try:
        os.makedirs(workdir + "/inputs")
    except FileExistsError:
        None

    for inp, hash in inputs.items():
        tmpName = "{}/inputs/{}".format(workdir, os.path.basename(to_outpath(inp)))
        cas.link_to_store(tmpName , hash, dstore)


def runJobs(jobset, jobnames, dstore, global_launcher=None):
    """Run a list of jobs
    """
    for name in jobnames:
        job = jobset[name]
        workdir = os.path.expandvars(job['workdir'])

        # Import inputs
        inputs = importInputPaths(job, name, dstore)

        # Link inputs into workdir
        linkInputsToWorkdir(inputs, workdir, dstore)

        # Run job
        if global_launcher == None:
            launcher = job['jobLauncher']
        else:
            launcher = global_launcher

        print("Running job {}, {} ...".format(name, job['runScript']))
        ret = os.system("{} {} \"{}\"".format(job['runScript'], job['workdir'], launcher))
        if os.waitstatus_to_exitcode(ret) != 0:
            print("Running job {} failed!".format(name))
            exit(1)

        # Import outputs
        print("Importing outputs of job {}".format(name))

        try:
            outputs = importOutputPaths(job, name, dstore)
        except FileNotFoundError as not_found:
            print("Output {} missing!".format(not_found.filename))
            return

        # Link outputs into dstore
        try:
            os.makedirs("outputs")
        except FileExistsError:
            None

        for file, hash in outputs.items():
            outName = "outputs/{}".format(file)
            cas.link_to_store(outName, hash, dstore)

        print()


def packageJob(name, job):
    '''Re-write jon definition for export/archival
    '''

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

    # This is irrelevant for an archived job
    job.pop("workdir")

    return job

def copyFilesToExternal(jobsets, targetDir, targetStore, dstore):
    '''Export files for archived jobset
    '''
    for _, job in jobsets.items():

        # copy inputs
        for file, hash in job['inputs'].items():
            if not is_output(file):
                # copy file to to taget
                if not os.path.exists("{}/{}".format(targetStore, hash)):
                    os.system("cp {}/{} {}".format(dstore, hash, targetStore))

                # create symlink to dstore
                inputName = "{}/inputs/{}".format(targetDir, os.path.basename(file))
                if not os.path.exists(inputName):
                    cas.link_to_store(inputName, hash, targetStore)

        # copy outputs
        for file, hash in job['outputs'].items():
            # copy file to to taget
            if not os.path.exists("{}/{}".format(targetStore, hash)):
                os.system("cp {}/{} {}".format(dstore, hash, targetStore))
            cas.link_to_store("{}/outputs/{}".format(targetDir, os.path.basename(file)), hash, targetStore)

def collectJobScripts(jobsets, scripts=[]):
    ''' Collect all jobs scripts
    '''
    for _, job in jobsets.items():
        scripts.append(job['jobScript'])

    return scripts

