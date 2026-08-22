import os, shutil, stat

BASE = "/home/gilles/Al_C/benchmarks/scf_speed_test"
TEMPL = os.path.join(BASE, "_templates")
NODE = "node16"

systems = {
    "Ta4C3_7at": 7,
    "Ccubic_16at": 16,
    "As4S3_28at": 28,
}

INCAR_TMPL = """SYSTEM = SCF speed benchmark {name} {natoms}at ntasks{ntasks} NPAR{npar} KPAR{kpar}

PREC    = Accurate
ENCUT   = 600
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

KSPACING = 0.03
KGAMMA   = .TRUE.

IBRION  = -1
NSW     = 0

NPAR    = {npar}
KPAR    = {kpar}

LWAVE   = .FALSE.
LCHARG  = .FALSE.
"""

JOB_TMPL = """#!/bin/sh
#SBATCH --job-name=scfbench_{tag}
#SBATCH --nodes=1
#SBATCH --nodelist={node}
#SBATCH --ntasks={ntasks}
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=00:30:00

module purge
module load intel
module load impi/2021.13
module load vasp/6.5.0
export OMP_NUM_THREADS=1
ulimit -s unlimited

srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std
"""

runs = []

# Partie A: sweep NPAR/KPAR at ntasks=40, for all 3 systems
combos = [(1,1),(4,2),(2,4),(1,4),(8,1),(1,8)]
for name, natoms in systems.items():
    for npar, kpar in combos:
        runs.append((name, natoms, 40, npar, kpar))

# Partie B: core scaling on 28-atom system, NPAR=1/KPAR=1
for ntasks in (4, 8, 16, 24):
    runs.append(("As4S3_28at", 28, ntasks, 1, 1))

print(f"Total runs: {len(runs)}")

for name, natoms, ntasks, npar, kpar in runs:
    tag = f"{name}_ntasks{ntasks}_NPAR{npar}_KPAR{kpar}"
    rdir = os.path.join(BASE, tag)
    os.makedirs(rdir, exist_ok=True)
    shutil.copy(os.path.join(TEMPL, name, "POSCAR"), os.path.join(rdir, "POSCAR"))
    shutil.copy(os.path.join(TEMPL, name, "POTCAR"), os.path.join(rdir, "POTCAR"))
    with open(os.path.join(rdir, "INCAR"), "w") as f:
        f.write(INCAR_TMPL.format(name=name, natoms=natoms, ntasks=ntasks, npar=npar, kpar=kpar))
    jobpath = os.path.join(rdir, "job.sh")
    with open(jobpath, "w") as f:
        f.write(JOB_TMPL.format(tag=tag, node=NODE, ntasks=ntasks))
    st = os.stat(jobpath)
    os.chmod(jobpath, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

with open(os.path.join(BASE, "run_list.txt"), "w") as f:
    for name, natoms, ntasks, npar, kpar in runs:
        tag = f"{name}_ntasks{ntasks}_NPAR{npar}_KPAR{kpar}"
        f.write(f"{tag}\t{name}\t{natoms}\t{ntasks}\t{npar}\t{kpar}\n")

print("done")
