"""
Generate the directory tree for the Al4C3 H(P) enthalpy-vs-pressure scan.

For each of the 7 relaxed 50 GPa polymorphs, builds a chain of ISIF=8
relaxations from 0 to 100 GPa (step 10 GPa), seeded at 50 GPa from the
existing 0.03 KSPACING relaxation, then re-optimized at KSPACING=0.2 with
LWAVE=.TRUE./LCHARG=.TRUE. so each subsequent pressure point restarts from
the previous point's WAVECAR (wavefunctions), CHGCAR (charge density) and
CONTCAR (ionic positions) in the same branch:
  50->40->30->20->10->0     (going down to the low-pressure bound)
  50->60->70->80->90->100   (going up to the high-pressure bound)

One SLURM node is reserved *per phase* for the whole chain: each phase's
11 pressure points run sequentially inside a single job
(Al4C3_<phase>/run_chain.sh), on the same node, from the 50 GPa seed to
both boundaries (0 and 100 GPa) -- the node is only released once the
entire 11-point series for that phase is done.

Only the seed (P=50) directories get a POSCAR copied here (from the
existing relaxed structure at KSPACING=0.03). The other pressure points'
POSCAR/WAVECAR/CHGCAR are fetched from the previous point's output by
run_chain.sh, at the point in the sequence where that previous step has
just finished (same job, same node allocation).

Each P<pressure>/ directory also gets a standalone job.sh, kept only as a
manual fallback to resume a single step by hand (e.g. after a crash)
without re-running the whole per-phase chain -- it is NOT what
submit_chain.sh uses.

This script only creates local files (INCAR.relax, POTCAR, job.sh,
run_chain.sh, and POSCAR for the seeds) -- it does not submit anything to
SLURM.
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)

# phase label -> source directory (existing 50 GPa relaxation, KSPACING=0.03)
# holding CONTCAR.relaxed + POTCAR to seed the P=50 point of the scan
PHASES = {
    "I-43d":        "Al4C3_I-43d_50GPa",
    "Pnma-III":     "Al4C3_Pnma-III_50GPa",
    "Pnma":         "Al4C3_Pnma_50GPa",
    "Pnma-VII":     "Al4C3_Pnma-VII_50GPa",
    "R-3m":         "Al4C3_R-3m_50GPa",
    "Pbam":         "Al4C3_Pbam",
    "anti-CaFe2O4": "Al4C3_anti-CaFe2O4",
}

SEED_P = 50
DOWN = [40, 30, 20, 10, 0]   # each restarts from the previous (higher) pressure
UP = [60, 70, 80, 90, 100]   # each restarts from the previous (lower) pressure

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

# Single SLURM job per phase: reserves ONE node for the whole 11-point
# series (both branches), released only once the last point finishes.
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

BASE="$(cd "$(dirname "$0")" && pwd)"

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


def make_dir(phase, p, prev=None):
    rdir = os.path.join(BASE, f"Al4C3_{phase}", f"P{p}")
    os.makedirs(rdir, exist_ok=True)

    istart = 0 if prev is None else 1
    icharg_line = "" if prev is None else "ICHARG  = 1\n"
    with open(os.path.join(rdir, "INCAR.relax"), "w") as f:
        f.write(INCAR_TMPL.format(phase=phase, p=p, pstress=p * 10.0, istart=istart,
                                   icharg_line=icharg_line))

    if prev is None:
        with open(os.path.join(rdir, "job.sh"), "w") as f:
            f.write(JOB_SEED_TMPL.format(phase=phase, p=p))
    else:
        with open(os.path.join(rdir, "job.sh"), "w") as f:
            f.write(JOB_CHAIN_TMPL.format(phase=phase, p=p, prev=prev))
    os.chmod(os.path.join(rdir, "job.sh"), 0o755)
    return rdir


def main():
    manifest = []
    for phase, srcdir in PHASES.items():
        src = os.path.join(REPO, "structures", srcdir)
        phase_dir = os.path.join(BASE, f"Al4C3_{phase}")

        seed_dir = make_dir(phase, SEED_P, prev=None)
        shutil.copy(os.path.join(src, "CONTCAR.relaxed"), os.path.join(seed_dir, "POSCAR"))
        shutil.copy(os.path.join(src, "POTCAR"), os.path.join(seed_dir, "POTCAR"))
        manifest.append((phase, SEED_P, None, srcdir))

        # execution order for this phase's single chained job: seed first,
        # then the whole descending branch, then the whole ascending branch
        sequence = [(SEED_P, None)]

        prev = SEED_P
        for p in DOWN:
            rdir = make_dir(phase, p, prev=prev)
            shutil.copy(os.path.join(src, "POTCAR"), os.path.join(rdir, "POTCAR"))
            manifest.append((phase, p, prev, None))
            sequence.append((p, prev))
            prev = p

        prev = SEED_P
        for p in UP:
            rdir = make_dir(phase, p, prev=prev)
            shutil.copy(os.path.join(src, "POTCAR"), os.path.join(rdir, "POTCAR"))
            manifest.append((phase, p, prev, None))
            sequence.append((p, prev))
            prev = p

        step_calls = "\n".join(
            f'run_step "P{p}" "{("P" + str(prev)) if prev is not None else ""}"'
            for p, prev in sequence
        )
        with open(os.path.join(phase_dir, "run_chain.sh"), "w") as f:
            f.write(RUN_CHAIN_TMPL.format(phase=phase, step_calls=step_calls))
        os.chmod(os.path.join(phase_dir, "run_chain.sh"), 0o755)

    with open(os.path.join(BASE, "run_manifest.txt"), "w") as f:
        f.write("phase\tpressure_GPa\tdepends_on_GPa\tseed_source\n")
        for phase, p, prev, src in manifest:
            f.write(f"{phase}\t{p}\t{prev if prev is not None else '-'}\t{src if src else '-'}\n")

    print(f"Generated {len(manifest)} run directories and {len(PHASES)} run_chain.sh "
          f"(1 SLURM job/node per phase) for {len(PHASES)} phases.")


if __name__ == "__main__":
    main()
