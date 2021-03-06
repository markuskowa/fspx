# SPDX-FileCopyrightText: 2022 Markus Kowalewski
#
# SPDX-License-Identifier: GPL-3.0-only

{ pkgs ? import <nixpkgs> {} } :


with pkgs;

python3.pkgs.buildPythonApplication {
  pname = "fspx";
  version = "0.1";
  src = ./.;

  postPatch = ''
    substituteInPlace fspx/main.py --replace \
	'instDir = "nix/"' "instDir = \"$out/share/fspx/nix\""
  '';

  postInstall = ''
    mkdir -p $out/share/fspx/nix
    cp nix/* $out/share/fspx/nix
  '';
}

