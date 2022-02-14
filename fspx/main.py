# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import argparse

from . import utils
from . import fspx
from . import cas

# Default path for project files
cfgPath = fspx.cfgPath

# Path nix module files
instDir = "nix/"


def cmd_build(cfgnix: str) -> int:
    '''Build the project configuration from nix configuration file
    '''

    print("Build it")
    try:
        os.mkdir(cfgPath)
    except FileExistsError:
        None
    ret = os.system("nix-build {}/project.nix --arg config {} --out-link {}/cfg --show-trace".format(instDir, cfgnix, cfgPath))
    return os.waitstatus_to_exitcode(ret)

def cmd_list(config) -> None:
    '''List all jobs in project
    '''
    for name, _ in config['jobsets'].items():
        print(name)

def cmd_check(config) -> tuple[list[str], bool]:
    '''Check if job results are valid
    '''

    jobs, valid = fspx.check_jobset(config['deps'], config['dstore'], recalc=[])

    if not valid:
        print("The following jobs need to be re-run:")

        for j in jobs:
            print(j)

    return jobs, valid

def cmd_shell(config, jobname: str, dstore: str) -> None:
    '''Start a shell in a job environment
    '''
    job = config['jobsets'][jobname]

    #workdir = os.path.expandvars(job['workdir'])
    workdir = job['workdir']

    # Import inputs
    print("Import and link inputs...")
    inputs = fspx.import_input_paths(job, jobname, dstore)
    fspx.link_inputs_to_workdir(inputs, workdir, dstore)

    print("Run nix-shell...")
    os.system("cd {0}; nix-shell -p {1}".format(workdir, job['env']))


def cmd_export(config, toDir: str, targetStore: str) -> None:
    '''Export the project
    '''

    # Copy config file and update hashes
    jobsets = {}
    for name, job in config['jobsets'].items():
        jobsets[name] = fspx.package_job(name, job)

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

    fspx.copy_files_to_external(config['jobsets'], toDir, targetStore, config['dstore'])

    # Fix dstore
    config['dstore'] = os.path.relpath(targetStore, toDir)
    utils.write_json("{}/config.json".format(toDir), config)

    # Create NAR
    print("Save job scripts to NAR archive...")
    allJobScripts = fspx.collect_job_scripts(config['jobsets'])
    os.system("nix-store --export $(nix-store -qR {}) > {}/jobScripts.nar".format(" ".join(allJobScripts), toDir))

def cmd_init() -> None:

    # create directories
    dirs = [ 'inputs', 'src' ];

    for d in dirs:
        try:
            os.makedirs(d)
        except FileExistsError:
            None

def cmd_run(config, job: str = None, launcher: str = None) -> None:
    if job == None:
        jobs, valid = fspx.check_jobset(config['deps'], config['dstore'])
        if not valid:
            fspx.run_jobs(config['jobsets'], jobs, config['dstore'], global_launcher = launcher)
    else:
        fspx.run_jobs(config['jobsets'], [ job ], config['dstore'], global_launcher = launcher)

def cmd_validate(config, job: str = None, launcher: str = None) -> None:

    # make sure we have a valid job set by attempting to run all jobs
    cmd_run(config, launcher = launcher)

    if job == None:
        all_jobs = fspx.find_all_jobs(config['deps'])
        fspx.validate_jobs(config['jobsets'], map(lambda j: j["name"], all_jobs), config['dstore'], global_launcher = launcher)
    else:
        fspx.validate_jobs(config['jobsets'], [ job ], config['dstore'], global_launcher = launcher)

#
# Main
#

def main():
    argsMain = argparse.ArgumentParser(
            prog = "fspx",
            description = "Functional Scientific Project Execution.")

    cmdArgs = argsMain.add_subparsers(dest="command", help='sub-command help')

    cmdArgs.add_parser("init", help="Setup directories and templates.")

    argsBuild = cmdArgs.add_parser("build", help="Build the project description from Nix config file.")
    argsBuild.add_argument("config_file", type=str, help="Project configuration.")

    cmdArgs.add_parser("list", help="List job names.")

    cmdArgs.add_parser("check", help="Check project and list invalidated jobs.")

    argsRun = cmdArgs.add_parser("run", help="Run jobs")
    argsRun.add_argument("job", nargs='?', help="Job to run. If ommited all invalidated jobs be run.")
    argsRun.add_argument("-l", "--launcher", help="Override job launcher.")

    argsValidate = cmdArgs.add_parser("validate", help="Validate jobs by re-running them")
    argsValidate.add_argument("job", nargs='?', help="Jobs to run. If ommited all jobs will be run.")
    argsValidate.add_argument("-l", "--launcher", help="Override job launcher.")

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
        cmd_init()
        exit(0)

    elif args.command == "build":
        ret = cmd_build(args.config_file)
        exit(ret)

    # Read the config. Every command from here on will need it
    config = utils.read_json("{}/cfg/project.json".format(cfgPath))

    if args.command == "list":
        cmd_list(config)

    elif args.command == "check":
        _, valid = cmd_check(config)
        if not valid:
            exit(1)

    elif args.command == "run":
        cmd_run(config, args.job, args.launcher)

    elif args.command == "validate":
        cmd_validate(config, args.job, args.launcher)

    elif args.command == "shell":
        cmd_shell(config, args.job, config['dstore'])

    elif args.command == "export":
        if not cmd_check(config):
            print("Project data is not valid. Can not export project.")
            exit(1)

        cmd_export(config, args.target_dir, args.target_store)

    elif args.command == "import":
        cas.import_paths(args.file_names, config['dstore'])


    exit(0)

if __name__ == '__main__':
    main()
