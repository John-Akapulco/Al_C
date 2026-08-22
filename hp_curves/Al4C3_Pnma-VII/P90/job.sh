#!/bin/sh
# Manual fallback: resume ONLY this pressure point by hand (e.g. after a
# crash), reusing CONTCAR/WAVECAR/CHGCAR already sitting in ../P80/.
# The normal path is Al4C3_Pnma-VII/run_chain.sh (one node, whole series).
#SBATCH --job-name=hp_Pnma-VII_P90_resume
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
cp ../P80/CONTCAR POSCAR
cp ../P80/WAVECAR WAVECAR
cp ../P80/CHGCAR CHGCAR

cp INCAR.relax INCAR
{ time -p srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 vasp_std ; } 2>> vasp.log
if ! grep -q "General timing" OUTCAR 2>/dev/null; then
    echo "VASP relax step did not finish cleanly -- aborting" >> vasp.log
    exit 1
fi
