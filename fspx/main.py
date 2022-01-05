# SPDX-License-Identifier: GPL-3.0-only

import os
import sys

from . import utils
from . import fspx
from . import cas

# Default path for project files
cfgPath = fspx.cfgPath

# Path nix module files
instDir = "nix/"


def cmdBuild(cfgnix):
    '''Build the project configuration from nix configuration file
    '''

    print("Build it")
    try:
        os.mkdir(cfgPath)
    except FileExistsError:
        None
    ret = os.system("nix-build {}/project.nix --arg config {} --out-link {}/cfg --show-trace".format(instDir, cfgnix, cfgPath))
    return os.waitstatus_to_exitcode(ret)

def cmdList(config):
    '''List all jobs in project
    '''
    for job in fspx.findAllJobs(config['jobsets']):
        print(job['name'])

def cmdCheck(config):
    '''Check if job results are valid
    '''

    jobs, valid = fspx.checkJobset(config['jobsets'], config['dstore'], recalc=[])

    if not valid:
        print("The following jobs need to be re-run:")

        for j in jobs:
            print(j['name'])

    return jobs, valid

def cmdShell(config, jobname):
    '''Start a shell with job environment
    '''
    job = fspx.findJob(config['jobsets'], jobname)
    os.system("nix-shell -p {}".format(job['env']))


def cmdExport(config, toDir, targetStore):
    '''Export the project
    '''

    # Copy config file and update hashes
    jobsets = {}
    for name, job in config['jobsets'].items():
        jobsets[name] = fspx.packageJob(name, job)

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

    fspx.copyFilesToExternal(config['jobsets'], toDir, targetStore, config['dstore'])

    # Fix dstore
    config['dstore'] = os.path.relpath(targetStore, toDir)
    utils.writeJson("{}/config.json".format(toDir), config)

    # Create NAR
    print("Save job scripts to NAR archive...")
    allJobScripts = fspx.collectJobScripts(config['jobsets'])
    os.system("nix-store --export $(nix-store -qR {}) > {}/jobScripts.nar".format(" ".join(allJobScripts), toDir))

def cmdInit():

    # create directories
    dirs = [ 'inputs' 'src' ];

    for d in dirs:
        try:
            os.makedirs(d)
        except FileExistsError:
            None

#
# Main
#

def main():
    if len(sys.argv) < 2:
        print("help")
        exit(0)


    argv = sys.argv[1:]

    if argv[0] == "init":
        cmdInit()

    if argv[0] == "build":
        ret = cmdBuild(argv[1])
        exit(ret)

    config = utils.readJson("{}/cfg/project.json".format(cfgPath))

    if argv[0] == "list":
        cmdList(config)

    elif argv[0] == "run":

        if len(argv) == 1:
            jobs, valid = fspx.checkJobset(config['jobsets'], config['dstore'], recalc=[])
            if not valid:
                fspx.runJobs(config['jobsets'], list(map(lambda x: x['name'], jobs)), config['dstore'])
        else:
            fspx.runJobs(config['jobsets'], argv[1:], config['dstore'])

    elif argv[0] == "check":
        jobs, valid = cmdCheck(config)
        if not valid:
            exit(1)


    elif argv[0] == "shell":

        if len(argv) != 2:
            print("job name is missing")
            exit(1)

        cmdShell(config, argv[1])


    elif argv[0] == "export":
        if not cmdCheck(config):
            print("Project data is not valid. Can not export project.")
            exit(1)

        cmdExport(config, argv[1], argv[2])

    elif argv[0] == "import":
        cas.importPaths(argv[1:], config['dstore'])


    exit(0)

if __name__ == '__main__':
    main()
