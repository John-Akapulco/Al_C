"""
Generate the r2SCAN H(P) chain for the Al4C3 Fd-3m polymorph (0 to 100 GPa).

Unlike the seven phases in gen_hp_runs_r2scan.py (which have a converged
PBE WAVECAR/CHGCAR at every one of the 11 pressures, since their PBE scan
is complete), Fd-3m's PBE scan is still running -- only P0 (and P10) are
converged so far. So this script only seeds P0 from the converged PBE
Fd-3m/P0 WAVECAR/CHGCAR/CONTCAR, then builds a single ascending r2SCAN
chain 0->10->...->100 where each subsequent point restarts from the
*previous r2SCAN point's* CONTCAR/WAVECAR/CHGCAR (run_chain.sh copies
these forward at run time, same mechanism as gen_hp_run_fd3m.py's PBE
chain) -- there is no PBE data to seed P10..P100 directly.

INCAR settings mirror gen_hp_runs_r2scan.py (METAGGA=R2scan, LASPH,
ADDGRID, LMIXTAU, same ENCUT/EDIFF/KSPACING/ISIF/PSTRESS grid as the PBE
scan). ISTART=1/ICHARG=1 throughout, since every point in this chain
(including P0) starts from an existing WAVECAR/CHGCAR.

This script only writes local files -- it does not submit anything to
SLURM.
"""
import os
import shutil

HP_BASE = os.path.dirname(os.path.abspath(__file__))          # hp_curves/
REPO = os.path.dirname(HP_BASE)
R2SCAN_BASE = os.path.join(REPO, "hp_curves_r2SCAN")

PHASE = "Fd-3m"
PRESSURES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

INCAR_TMPL = """SYSTEM = Al4C3 {phase} - r2SCAN H(P) scan @ {p} GPa (ISIF=8)

# electronic
PREC    = Accurate
ENCUT   = 600
EDIFF   = 1E-5
ISMEAR  = 0
SIGMA   = 0.05

# meta-GGA: r2SCAN, restarting from the previous pressure point in this
# chain (P0 seeded from the converged PBE Fd-3m/P0 WAVECAR/CHGCAR --
# Fd-3m's PBE scan is not complete at other pressures yet)
METAGGA  = R2scan
LASPH    = .TRUE.
ADDGRID  = .TRUE.
LMIXTAU  = .TRUE.
ISTART   = 1
ICHARG   = 1

# k-points (same coarse mesh as the PBE scan, for a like-for-like comparison)
KSPACING = 0.2
KGAMMA   = .TRUE.

# ionic + volume relaxation under external pressure, cell shape fixed
IBRION  = 2
ISIF    = 8
NSW     = 200
EDIFFG  = -0.01
PSTRESS = {pstress:.1f}        ! kBar = {p} GPa

# parallelization
KPAR    = 8

# output -- WAVECAR/CHGCAR saved so the next pressure point can restart
LWAVE   = .TRUE.
LCHARG  = .TRUE.
"""

RUN_CHAIN_TMPL = """#!/bin/sh
#SBATCH --job-name=r2scan_{phase}
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=r2scan_{phase}.log
#SBATCH --time=96:00:00

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
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/r2scan_{phase}.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}}

{step_calls}
echo "$(date '+%F %T') === Al4C3_{phase}: r2SCAN 0-100 GPa series done ==="
"""


def make_dir(p, prev):
    rdir = os.path.join(R2SCAN_BASE, f"Al4C3_{PHASE}", f"P{p}")
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "INCAR.relax"), "w") as f:
        f.write(INCAR_TMPL.format(phase=PHASE, p=p, pstress=p * 10.0))
    return rdir


def main():
    pbe_p0 = os.path.join(HP_BASE, f"Al4C3_{PHASE}", "P0")
    for fname in ("CONTCAR", "WAVECAR", "CHGCAR", "OUTCAR"):
        assert os.path.isfile(os.path.join(pbe_p0, fname)), \
            f"missing {fname} in {pbe_p0} -- PBE Fd-3m P0 must be converged first"

    seed_dir = make_dir(0, None)
    shutil.copy(os.path.join(pbe_p0, "CONTCAR"), os.path.join(seed_dir, "POSCAR"))
    shutil.copy(os.path.join(pbe_p0, "WAVECAR"), os.path.join(seed_dir, "WAVECAR"))
    shutil.copy(os.path.join(pbe_p0, "CHGCAR"), os.path.join(seed_dir, "CHGCAR"))
    shutil.copy(os.path.join(pbe_p0, "POTCAR"), os.path.join(seed_dir, "POTCAR"))

    sequence = [(0, None)]
    prev = 0
    for p in PRESSURES[1:]:
        rdir = make_dir(p, prev)
        shutil.copy(os.path.join(seed_dir, "POTCAR"), os.path.join(rdir, "POTCAR"))
        sequence.append((p, prev))
        prev = p

    step_calls = "\n".join(
        f'run_step "P{p}" "{("P" + str(prev)) if prev is not None else ""}"'
        for p, prev in sequence
    )
    phase_dir = os.path.join(R2SCAN_BASE, f"Al4C3_{PHASE}")
    with open(os.path.join(phase_dir, "run_chain.sh"), "w") as f:
        f.write(RUN_CHAIN_TMPL.format(phase=PHASE, step_calls=step_calls))
    os.chmod(os.path.join(phase_dir, "run_chain.sh"), 0o755)

    with open(os.path.join(R2SCAN_BASE, "run_manifest.txt"), "a") as f:
        for p, prev in sequence:
            f.write(f"{PHASE}\t{p}\t"
                     f"{f'hp_curves_r2SCAN/Al4C3_{PHASE}/P{prev}' if prev is not None else f'hp_curves/Al4C3_{PHASE}/P0 (PBE)'}\n")

    print(f"Generated {len(sequence)} run directories for Al4C3_{PHASE} "
          f"(r2SCAN, single ascending chain 0->100 GPa, P0 seeded from PBE).")


if __name__ == "__main__":
    main()
