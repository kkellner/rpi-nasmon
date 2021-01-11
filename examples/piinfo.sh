#!/bin/bash
# pistuff.sh looks at firmware/kernel, and clocks, temps for gpu/cpu
# create this file in the user dir, and make it executable
celsius=$(cat /sys/class/thermal/thermal_zone0/temp | sed 's/.\{3\}$/.&/')
clock0=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq | sed 's/.\{3\}$/.&/')
clock1=$(cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_cur_freq | sed 's/.\{3\}$/.&/')
clock2=$(cat /sys/devices/system/cpu/cpu2/cpufreq/scaling_cur_freq | sed 's/.\{3\}$/.&/')
clock3=$(cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq | sed 's/.\{3\}$/.&/')
echo "Host   => $(date) @ $(hostname)"
echo "Uptime =>$(uptime)"
echo "SW Rev => $(uname -vr)"
# VC4 stuff for RPi variants
echo "FW Rev => $(vcgencmd version)"
echo "==============="
echo "ARM Mem => $(vcgencmd get_mem arm)"
echo "GPU Mem => $(vcgencmd get_mem gpu)"
echo "==============="
echo "Pi Temp  => $(vcgencmd measure_temp)"
echo "Pi Volts => $(vcgencmd measure_volts core)"
echo "Pi Clock => $(vcgencmd measure_clock arm)"
# end VC4 stuff
# rest is from linux, should apply to any
echo "==============="
echo "ARM Temp => ${celsius} °C"
echo "Core0Clock=> ${clock0} MHz"
echo "Core1Clock=> ${clock1} MHz"
echo "Core2Clock=> ${clock2} MHz"
echo "Core3Clock=> ${clock3} MHz"
echo "==============="

