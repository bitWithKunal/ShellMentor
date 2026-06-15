########################################################
# SDC Constraints - smart_soc_top
# Tool: Cadence Innovus 21.14
########################################################

# Clock Definitions
create_clock -name clk_core -period 2.000 -waveform {0 1.000} [get_ports CLK_CORE]
create_clock -name clk_mem  -period 3.000 -waveform {0 1.500} [get_ports CLK_MEM]
create_clock -name clk_per  -period 10.00 -waveform {0 5.000} [get_ports CLK_PER]
create_clock -name clk_ref  -period 20.00 -waveform {0 10.00} [get_ports CLK_REF]

# Generated Clocks
create_generated_clock -name clk_div2 -source [get_ports CLK_CORE] -divide_by 2 \
    [get_pins u_clkgen/clk_div2_out]
create_generated_clock -name clk_usb  -source [get_ports CLK_REF] -multiply_by 24 \
    [get_pins u_pll/clk_usb_out]

# Clock Uncertainty
set_clock_uncertainty -setup 0.050 [all_clocks]
set_clock_uncertainty -hold  0.030 [all_clocks]

# Clock Latency
set_clock_latency -source 0.200 [get_clocks clk_core]
set_clock_latency -source 0.150 [get_clocks clk_mem]
set_clock_latency -source 0.100 [get_clocks clk_per]

# Input/Output Delays
set_input_delay  -max 0.400 -clock clk_core [get_ports DATA_IN[*]]
set_input_delay  -min 0.050 -clock clk_core [get_ports DATA_IN[*]]
set_output_delay -max 0.350 -clock clk_core [get_ports DATA_OUT[*]]
set_output_delay -min 0.030 -clock clk_core [get_ports DATA_OUT[*]]

# False Paths
set_false_path -from [get_clocks clk_core] -to [get_clocks clk_per]
set_false_path -from [get_clocks clk_per]  -to [get_clocks clk_core]
set_false_path -from [get_ports RST_N]

# Multicycle Paths
set_multicycle_path -setup 2 -from [get_cells u_core/u_fpu/*] \
    -to [get_cells u_core/u_fpu/result_reg*]
set_multicycle_path -hold  1 -from [get_cells u_core/u_fpu/*] \
    -to [get_cells u_core/u_fpu/result_reg*]

# Timing Exceptions
set_timing_derate -early 0.95 -cell_delay
set_timing_derate -late  1.05 -cell_delay

# Drive Strength
set_driving_cell -lib_cell BUFX4 -library slow_125c [all_inputs]
set_load -pin_load 0.050 [all_outputs]
