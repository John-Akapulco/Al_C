"""
Generate the H(P) chain for the Al4C3 Fd-3m polymorph (0 to 100 GPa).

Unlike the seven phases in gen_hp_runs.py (which had a pre-relaxed 50 GPa
structure to seed a bidirectional branch), Fd-3m only has the findsym
structure supplied directly (P0/POSCAR, already written by hand). This
script only builds a single ascending chain 0->10->...->100, each point
restarting from the previous (lower) pressure's CONTCAR/WAVECAR/CHGCAR,
and writes Al4C3_Fd-3m/run_chain.sh (one SLURM job/node for the whole
series) plus a per-point INCAR.relax/job.sh fallback -- mirroring the
conventions in gen_hp_runs.py. It does not submit anything to SLURM.
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
PHASE = "Fd-3m"
PRESSURES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

INCAR_TMPL = """SYSTEM = Al4C3 {phase} - H(P) scan @ {p} GPa (ISIF=8)

# electronic
PREC    = Accurate
ENCUT   = 600
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

# k-points (coarse mesh for the H(P) scan)
KSPACING = 0.2
KGAMMA   = .TRUE.

# ionic + volume relaxation under external pressure, cell shape fixed
IBRION  = 2
ISIF    = 8
NSW     = 200
EDIFFG  = -0.01
PSTRESS = {pstress:.1f}        ! kBar = {p} GPa

# electronic restart from the neighbouring pressure point in this branch:
# ISTART=1 reads WAVECAR, ICHARG=1 reads CHGCAR (both copied by job.sh)
ISTART  = {istart}
{icharg_line}
# parallelization (per benchmark: KPAR>1 outperforms NPAR>1 on these
# systems; user-specified KPAR=8, NPAR left at default)
KPAR    = 8

# output -- WAVECAR and CHGCAR are both saved so the *next* pressure
# point in the chain can restart from them (ISTART=1, ICHARG=1)
LWAVE   = .TRUE.
LCHARG  = .TRUE.
"""

JOB_SEED_TMPL = """#!/bin/sh
#SBATCH --job-name=hp_{phase}_P{p}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=06:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

cp INCAR.relax INCAR
{{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
"""

JOB_CHAIN_TMPL = """#!/bin/sh
# Manual fallback: resume ONLY this pressure point by hand (e.g. after a
# crash), reusing CONTCAR/WAVECAR/CHGCAR already sitting in ../P{prev}/.
# The normal path is Al4C3_{phase}/run_chain.sh (one node, whole series).
#SBATCH --job-name=hp_{phase}_P{p}_resume
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=vasp.log
#SBATCH --time=06:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

# restart from the neighbouring pressure point in this branch
cp ../P{prev}/CONTCAR POSCAR
cp ../P{prev}/WAVECAR WAVECAR
cp ../P{prev}/CHGCAR CHGCAR

cp INCAR.relax INCAR
{{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
"""

RUN_CHAIN_TMPL = """#!/bin/sh
#SBATCH --job-name=hp_{phase}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=hp_{phase}.log
#SBATCH --time=72:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {{
    local dir="$1" prev="$2"
    echo "$(date '+%F %T') === starting $dir (prev=${{prev:-none}}) ==="
    cd "$BASE/$dir" || exit 1
    if [ -n "$prev" ]; then
        cp "../$prev/CONTCAR" POSCAR
        cp "../$prev/WAVECAR" WAVECAR
        cp "../$prev/CHGCAR" CHGCAR
    fi
    cp INCAR.relax INCAR
    {{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; }} 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/hp_{phase}.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}}

{step_calls}
echo "$(date '+%F %T') === Al4C3_{phase}: full 0-100 GPa series done ==="
"""


def make_dir(p, prev):
    rdir = os.path.join(BASE, f"Al4C3_{PHASE}", f"P{p}")
    os.makedirs(rdir, exist_ok=True)

    istart = 0 if prev is None else 1
    icharg_line = "" if prev is None else "ICHARG  = 1\n"
    with open(os.path.join(rdir, "INCAR.relax"), "w") as f:
        f.write(INCAR_TMPL.format(phase=PHASE, p=p, pstress=p * 10.0, istart=istart,
                                   icharg_line=icharg_line))

    if prev is None:
        with open(os.path.join(rdir, "job.sh"), "w") as f:
            f.write(JOB_SEED_TMPL.format(phase=PHASE, p=p))
    else:
        with open(os.path.join(rdir, "job.sh"), "w") as f:
            f.write(JOB_CHAIN_TMPL.format(phase=PHASE, p=p, prev=prev))
    os.chmod(os.path.join(rdir, "job.sh"), 0o755)
    return rdir


def main():
    phase_dir = os.path.join(BASE, f"Al4C3_{PHASE}")
    p0_dir = os.path.join(BASE, f"Al4C3_{PHASE}", "P0")
    assert os.path.isfile(os.path.join(p0_dir, "POSCAR")), "P0/POSCAR must exist (findsym structure)"
    assert os.path.isfile(os.path.join(p0_dir, "POTCAR")), "P0/POTCAR must exist"

    sequence = [(0, None)]
    make_dir(0, None)

    prev = 0
    for p in PRESSURES[1:]:
        rdir = make_dir(p, prev)
        shutil.copy(os.path.join(p0_dir, "POTCAR"), os.path.join(rdir, "POTCAR"))
        sequence.append((p, prev))
        prev = p

    step_calls = "\n".join(
        f'run_step "P{p}" "{("P" + str(prev)) if prev is not None else ""}"'
        for p, prev in sequence
    )
    with open(os.path.join(phase_dir, "run_chain.sh"), "w") as f:
        f.write(RUN_CHAIN_TMPL.format(phase=PHASE, step_calls=step_calls))
    os.chmod(os.path.join(phase_dir, "run_chain.sh"), 0o755)

    # append to the shared manifest
    with open(os.path.join(BASE, "run_manifest.txt"), "a") as f:
        for p, prev in sequence:
            f.write(f"{PHASE}\t{p}\t{prev if prev is not None else '-'}\t"
                     f"{'findsym-output (user-supplied)' if prev is None else '-'}\n")

    print(f"Generated {len(sequence)} run directories for Al4C3_{PHASE} "
          f"(single ascending chain 0->100 GPa).")


if __name__ == "__main__":
    main()
