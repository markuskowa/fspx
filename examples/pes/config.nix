{ pkgs, ... } :

let
  # we need to specify the launcher to make it run with slurm
  molpro = input: ''
      #SBATCH -J molpro
      #SBATCH -c 1
      #SBATCH -p f2

      # srun gets confused by CPU binding
      export SLURM_CPU_BIND=none

      cp inputs/* .
      molpro --launcher "mpiexec.hydra -np $SLURM_CPUS_PER_TASK molpro.exe" ${input}
    '';

  pes = {
    inputs = {
      "inputs/co2-pes.inp" = null;
      "outputs/geom.act" = null;
    };
    outputs = [ "pes.dat" ];
    env = pkgs.qchem.molpro;
    jobLauncher = "sbatch -W";
    jobScript = pkgs.writeShellScript "pes" ''
      ${molpro "co2-pes.inp"}
    '';
    dependencies = { inherit opt; };
  };

  opt = {
    inputs = {
      "inputs/co2-opt.inp" = null;
    };
    outputs = [ "geom.act" ];
    env = pkgs.qchem.molpro;
    jobLauncher = "sbatch -W";
    jobScript = pkgs.writeShellScript "opt" ''
      ${molpro "co2-opt.inp"}
    '';
  };

  interp = {
    inputs = {
      "outputs/pes.dat" = null;
      "inputs/interp.m" = null;
    };
    outputs = [ "pes_interp.dat" ];
    env = pkgs.octave;
    jobScript = pkgs.writeShellScript "interp" ''
      octave inputs/interp.m
    '';

    dependencies = { inherit pes; };
  };

in {
  workdir = "$GSCRATCH/fspx-demo";
  dstore = "./dstore";
  jobsets = {
    inherit interp;
  };
}
