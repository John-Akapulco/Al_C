#!/bin/sh
#SBATCH --job-name=scfbench_As4S3_28at_ntasks8_NPAR1_KPAR1
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --threads-per-core=1
#SBATCH --exclude=node01,node02,node03,node04,node05,node06,node07,node08
#SBATCH --output=vasp.log
#SBATCH --time=00:30:00

module purge
module load intel
module load impi/2021.13
export OMP_NUM_THREADS=1
export PATH=/opt/ohpc/pub/software/vasp.6.4.2:$PATH
ulimit -s unlimited

srun --mpi=pmi2 --ntasks=$SLURM_NTASKS --cpus-per-task=1 --threads-per-core=1 vasp_std
