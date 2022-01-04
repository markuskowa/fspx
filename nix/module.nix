# SPDX-License-Identifier: GPL-3.0-only

{ pkgs, lib, config, ... } :

with lib;
let
  cfg = config;

  jobsetType = with types; attrsOf ( submodule ({...} : {
    options = {
      inputs = mkOption {
	type = with types; attrsOf (nullOr str);
	description = "Input file names with optional hash";
	default = {};
      };

      outputs = mkOption {
	type = with types; listOf str;
	description = "Output file names";
      };

      env = mkOption {
	type = with types; nullOr package;
	description = "Compute environment";
	default = pkgs.coreutils;
      };

      jobScript = mkOption {
	type = types.package;
	description = "The job script";
      };

      dependencies = mkOption {
	type = jobsetType;
	default = {};
      };

      workdir = mkOption {
	type = types.str;
	default = cfg.workdir;
      };
    };
  }));

in {
  options = {
    workdir = mkOption {
      type = types.str;
      description = "Basedirectory for working directories";
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
	    dependencies = fixJobsets job.dependencies;
	  }) jobset;

      project = (builtins.removeAttrs (config // { jobsets = fixJobsets config.jobsets; }) [ "outPath" "_module"]);

      allJobs = let
	collectJobs = x: flatten (mapAttrsToList (name: job: [ name ] ++ collectJobs job.dependencies ) x);
	allJobs = collectJobs cfg.jobsets;
      in if length (unique allJobs) != length allJobs then
	throw "Job names must be unique within project"
	else allJobs;

      allOutputs = let
	collectOutputs = x: flatten (mapAttrsToList (name: job: job.outputs ++ collectOutputs job.dependencies ) x);
	allOutputs = collectOutputs cfg.jobsets;
      in if length (unique allOutputs) != length allOutputs then
	throw "Output names must be unique within project"
	else allOutputs;

      nixShell = job: pkgs.writeScript "nixShell" ''
        #!/usr/bin/env nix-shell
        #!nix-shell -i bash -p ${job.env}

        cd ${job.workdir}
        ${job.jobScript}
      '';

      in pkgs.runCommand "project" {} ''
      mkdir -p $out

      echo '${builtins.toJSON project}' > $out/project.json
      echo "${concatStringsSep "\n" allJobs}" > $out/allJobs
      echo "${concatStringsSep "\n" allOutputs}" > $out/allOutputs
    '';

  };
}

