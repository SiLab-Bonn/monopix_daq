#! /usr/bin/bash
#export ROOTSYS=/home/user/Documents/ilcsoft/v01-17-05/root/5.34.18
#export LD_LIBRARY_PATH=/home/user/Documents/eudaq-1.4-newonlinemon/lib:$ROOTSYS/lib:$LD_LIBRARY_PATH
#export LD_LIBRARY_PATH=/home/user/Documents/eudaq-1.4-dev-testbeam/lib:$LD_LIBRARY_PATH
source /home/user/Documents/ilcsoft/v01-17-05/Eutelescope/trunk/build_env.sh

/home/user/anaconda/envs/thinn/bin/jupyter qtconsole --matplotlib=qt
