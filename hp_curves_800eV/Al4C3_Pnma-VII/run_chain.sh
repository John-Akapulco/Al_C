#!/bin/sh
# 800eV/0.05 combined PBE+r2SCAN H(P) chain for Al4C3_Pnma-VII: 0-70 GPa
# every 10 GPa, alternating PBE/r2SCAN at each pressure, each step
# restarting from the immediately preceding one (WAVECAR+CHGCAR+CONTCAR),
# except P0_PBE which is seeded from the earlier 600eV/0.2 r2SCAN@0GPa
# CONTCAR. See gen_hp_runs_800eV.py for the full scheme.
#SBATCH --job-name=hires_Pnma-VII
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --cpus-per-task=1
#SBATCH --output=hires_Pnma-VII.log
#SBATCH --time=240:00:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

BASE="$SLURM_SUBMIT_DIR"

run_step() {
    local dir="$1" prev="$2"
    echo "$(date '+%F %T') === starting $dir (prev=${prev:-none}) ==="
    cd "$BASE/$dir" || exit 1
    if [ -n "$prev" ]; then
        cp "../$prev/CONTCAR" POSCAR
        cp "../$prev/WAVECAR" WAVECAR
        cp "../$prev/CHGCAR" CHGCAR
    fi
    cp INCAR.relax INCAR
    { time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; } 2>> vasp.log
    if ! grep -q "General timing" OUTCAR 2>/dev/null; then
        echo "$(date '+%F %T') VASP did not finish cleanly in $dir -- aborting chain" >> "$BASE/hires_Pnma-VII.log"
        exit 1
    fi
    echo "$(date '+%F %T') === finished $dir ==="
}

run_step "P0_PBE" ""
run_step "P0_r2SCAN" "P0_PBE"
run_step "P10_PBE" "P0_r2SCAN"
run_step "P10_r2SCAN" "P10_PBE"
run_step "P20_PBE" "P10_r2SCAN"
run_step "P20_r2SCAN" "P20_PBE"
run_step "P30_PBE" "P20_r2SCAN"
run_step "P30_r2SCAN" "P30_PBE"
run_step "P40_PBE" "P30_r2SCAN"
run_step "P40_r2SCAN" "P40_PBE"
run_step "P50_PBE" "P40_r2SCAN"
run_step "P50_r2SCAN" "P50_PBE"
run_step "P60_PBE" "P50_r2SCAN"
run_step "P60_r2SCAN" "P60_PBE"
run_step "P70_PBE" "P60_r2SCAN"
run_step "P70_r2SCAN" "P70_PBE"
echo "$(date '+%F %T') === Al4C3_Pnma-VII: 800eV/0.05 PBE+r2SCAN 0-70 GPa chain done ==="
