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
	    If an input name starts with a colon it is interpreted as output
	    produced by another job.
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
	  Changing the environment will cause recalculation the job.
	'';
	default = pkgs.coreutils;
	example = pkg.octave;
      };

      jobLauncher = mkOption {
	type = types.str;
	description = ''
	  Optional launcher command used to launch the jobScript.
	  This command is put in front of the jobScript call.
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
	  Changing the jobScript will cause recalculation of the job.
	'';
	example = literalExpression ''
	  pkgs.writeShellScript "interp" "octave inputs/interp.m";
	'';
      };

      checkScript = mkOption {
	type = with types; package;
	description = ''
	  Optional check script, veryfying the validity of the outputs.
	'';
	default = pkgs.writeScript "check" ''
	  cd "$1"
	  shift 1

	  printf "Checking for outputs...\n"
	  while (("$#" )); do
	    if [ ! -f "$1" ]; then
	      exit 1
	    fi
	    shift 1
	  done
	'';
      };

      workdir = mkOption {
	type = with types; nullOr str;
	description = ''
	  The working directory for this job.
          This defaults to the working directory of the project plus the job name.
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
	Default base working directory.
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

      allOutputs = let
	collectOutputs = x: flatten (mapAttrsToList (name: job: job.outputs ) x);
	allOutputs = collectOutputs cfg.jobsets;
      in if length (unique allOutputs) != length allOutputs then
	throw "Output names must be unique within project"
	else allOutputs;

      # Remap outputs to { output = jobname; }
      outputsMap = builtins.listToAttrs (flatten (mapAttrsToList (name: job: (map (x: nameValuePair x name ) job.outputs) ) project.jobsets));

      # Remap inputs to { input = jobname; }
      inputsMap = builtins.listToAttrs (flatten (mapAttrsToList (name: job: (map (x: nameValuePair x name ) (attrNames job.inputs)) ) project.jobsets));

      deps = let
	# Used to strip leading colon
	# stripFirst :: str -> str
	stripFirst = x: substring 1 (stringLength x) x;

	# map input name to job name, remove original inputs, clear leading colon
	# input2jobs :: attrs(input/hash) -> attrs(input/jobs)
	inputs2jobs = inputs: listToAttrs (filter (x: x != null) (mapAttrsToList (input: hash:
		  if hasPrefix ":" input then
		    if hasAttr (stripFirst input) outputsMap then
		      let
			name = getAttr (stripFirst input) outputsMap;
		      in {
			inherit name;
			value = getAttr name project.jobsets;
		      }
		    else throw "${input} is not produced by any job!"
		  else null
	        ) inputs));

	# find jobs where outputs are not used by any other job
        # filterTopLevel :: attrs(jobset) -> attrs(jobset)
	filterTopLevel = jobsets: filterAttrs (name: job:
	      foldr (a: b:
		(! (hasAttr ":${a}" (filterAttrs (n: j: j != name) inputsMap))) && b)
	      true job.outputs
	    ) jobsets;

	# Create dependency tree
	# collectDeps :: attrs(jobset) -> attrs(deps)
	collectDeps = jobsets: (mapAttrs (name: job: {
	      inherit (job) inputs outputs runScript;
 	      deps = collectDeps (inputs2jobs job.inputs);
	      } ) jobsets);

	in filterTopLevel (collectDeps project.jobsets);

      in pkgs.runCommand "project" {} ''
      mkdir -p $out

      echo '${builtins.toJSON (project // { inherit deps; }) }' > $out/project.json
      echo '${builtins.toJSON inputsMap}' > $out/inputs.json
      echo '${builtins.toJSON outputsMap}' > $out/outputs.json
      echo '${builtins.toJSON deps}' > $out/deps.json
      echo "${concatStringsSep "\n" allOutputs}" > $out/allOutputs
    '';

  };
}

