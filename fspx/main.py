# SPDX-License-Identifier: GPL-3.0-only

import os
import sys
import argparse

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
    argsMain = argparse.ArgumentParser(
            prog = "fspx",
            description = "Functional Scientific Project Execution.")

    cmdArgs = argsMain.add_subparsers(dest="command", help='sub-command help')

    argsInit = cmdArgs.add_parser("init", help="Setup directories and templates.")

    argsBuild = cmdArgs.add_parser("build", help="Build the project description from Nix config file.")
    argsBuild.add_argument("config_file", type=str, help="Project configuration.")

    argsList = cmdArgs.add_parser("list", help="List job names.")

    argsCheck = cmdArgs.add_parser("check", help="Check project and list invalidated jobs.")

    argsRun = cmdArgs.add_parser("run", help="Run jobs")
    argsRun.add_argument("job", nargs='?', help="Job to run. If ommited all invalidated jobs be run.")

    argsShell = cmdArgs.add_parser("shell", help="Enter an interactive job shell environment.")
    argsShell.add_argument("job", help="Job to pick shell from.")

    argsExport = cmdArgs.add_parser("export", help="Export a finished project.")
    argsExport.add_argument("target_dir", help="Traget directory. Must be empty.")
    argsExport.add_argument("target_store", help="Traget data store directory.")

    argsImport = cmdArgs.add_parser("import", help="Import files into data store manually.")
    argsImport.add_argument("files", nargs='+', help="Files to import.")

    args = argsMain.parse_args()

    if args.command == None:
        argsMain.print_help()
        exit(1)

    elif args.command == "init":
        cmdInit()
        exit(0)

    elif args.command == "build":
        ret = cmdBuild(args.config_file)
        exit(ret)

    # Read the config. Every command from here on will need it
    config = utils.readJson("{}/cfg/project.json".format(cfgPath))

    if args.command == "list":
        cmdList(config)

    elif args.command == "check":
        jobs, valid = cmdCheck(config)
        if not valid:
            exit(1)

    elif args.command == "run":

        if args.job == None:
            jobs, valid = fspx.checkJobset(config['jobsets'], config['dstore'], recalc=[])
            if not valid:
                fspx.runJobs(config['jobsets'], list(map(lambda x: x['name'], jobs)), config['dstore'])
        else:
            fspx.runJobs(config['jobsets'], args.job, config['dstore'])

    elif args.command == "shell":
        cmdShell(config, args.job)

    elif args.command == "export":
        if not cmdCheck(config):
            print("Project data is not valid. Can not export project.")
            exit(1)

        cmdExport(config, args.target_dir, args.target_store)

    elif args.command == "import":
        cas.importPaths(args.file_names, config['dstore'])


    exit(0)

if __name__ == '__main__':
    main()
