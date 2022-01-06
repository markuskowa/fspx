# SPDX-License-Identifier: GPL-3.0-only

{ pkgs, lib, config, ... } :

with lib;
let
  cfg = config;

  jobsetType = with types; attrsOf ( submodule ({...} : {
    options = {
      inputs = mkOption {
	type = with types; attrsOf (nullOr (strMatching "[0-9A-Fa-f]{64}"));
        description = ''
            Input file names with optional hash.
            If the hash value is set to null, a changed input file will be re-imported
            into the data store. Note: only SHA256 base16 hashes are supported.
        '';
        default = {};
        example = literalExpression ''
          {
            input1.dat = null;
            input2.dat = "181210f8f9c779c26da1d9b2075bde0127302ee0e3fca38c9a83f5b1dd8e5d3b";
          }
        '';
      };

      outputs = mkOption {
	type = with types; listOf str;
	description = ''
	  Output file names. Note that these file names need to be unique within a project.
	  These files are import at the end of a job.
	'';
	example = literalExpression ''
	  [ "output1.dat" "output2.dat" ]
	'';
      };

      env = mkOption {
	type = with types; package;
	description = ''
	  Compute environment. A package or nix store path, providing and environment for a job.
	  Changing the environment will invalidate the job.
	'';
	default = pkgs.coreutils;
	example = pkg.octave;
      };

      jobLauncher = mkOption {
	type = types.str;
	description = ''
	  Optional launcher command used to launch the jobScript.
	  This command is put in front of the jobScript.
	  Note, that for batch jobs the launcher needs to wait
	  for the completion of the job.
	'';
	example = "sbatch -W";
	default = "";
      };

      jobScript = mkOption {
	type = types.package;
	description = ''
	  The job script. This needs to be a nix-store path
	  Changing the jobScript will invalidate the job.
	'';
	example = literalExpression ''
	  pkgs.writeShellScript "interp" "octave inputs/interp.m";
	'';
      };

      deps = mkOption {
	type = jobsetType;
	description = ''
	  All jobs that this jobs depends on.
	'';
	default = {};
      };

      workdir = mkOption {
	type = with types; nullOr str;
	description = ''
	  The working directory for this job.
          This defaults to the working directory of the project.
	'';
	default = null;
      };

      description = mkOption {
	type = types.str;
	description = ''
	  An optional description for the job.
	'';
	default = "";
      };
    };
  }));

in {
  options = {
    workdir = mkOption {
      type = types.str;
      description = ''
	Default working directory base.
      '';
      default = builtins.getEnv "TMPDIR";
    };

    dstore = mkOption {
      type = types.str;
      description = "Data store directory";
    };

    jobsets = mkOption {
      default = {};
      description = "Jobset defintions";
      type = jobsetType;
    };

    description = mkOption {
      type = types.str;
	description = ''
	  An optional description for the project.
	'';
      default = "";
    };

    outPath = mkOption {
      internal = true;
      type = types.package;
    };
  };

  config = {
    # Create a flat list of all jobs
    # Create a JSON file for the project
    # Make sure job IDs/names are unique
    # Make sure all outputs have unique names
    outPath = let
      fixJobsets = jobset: mapAttrs (name: job:
	  job // {
	    runScript = nixShell job;
	    deps = fixJobsets job.deps;
	  } // optionalAttrs (job.workdir == null) {
	    workdir = cfg.workdir + "/" + name;
	  }) jobset;

      nixShell = job: pkgs.writeScript "nixShell" ''
        #!/usr/bin/env nix-shell
        #!nix-shell -i bash -p ${job.env}

        cd "$1"
        if [ -z "$2" ]; then
          launcher=""
        else
          launcher="$2"
        fi
        $launcher ${job.jobScript}
      '';

      project = (builtins.removeAttrs (config // { jobsets = fixJobsets config.jobsets; }) [ "outPath" "_module"]);

      allJobs = let
	collectJobs = x: flatten (mapAttrsToList (name: job: [ name ] ++ collectJobs job.deps ) x);
	allJobs = collectJobs cfg.jobsets;
      in if length (unique allJobs) != length allJobs then
	throw "Job names must be unique within project"
	else allJobs;

      allOutputs = let
	collectOutputs = x: flatten (mapAttrsToList (name: job: job.outputs ++ collectOutputs job.deps ) x);
	allOutputs = collectOutputs cfg.jobsets;
      in if length (unique allOutputs) != length allOutputs then
	throw "Output names must be unique within project"
	else allOutputs;

      in pkgs.runCommand "project" {} ''
      mkdir -p $out

      echo '${builtins.toJSON project}' > $out/project.json
      echo "${concatStringsSep "\n" allJobs}" > $out/allJobs
      echo "${concatStringsSep "\n" allOutputs}" > $out/allOutputs
    '';

  };
}

