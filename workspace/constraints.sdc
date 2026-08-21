# ============================================================
# SDC Timing Constraints - cpu_core_top
# Generated: 15-Mar-2024
# Target: 800 MHz (1.250ns period)
# ============================================================

# Clock Definition
create_clock -name clk -period 1.250 -waveform {0.000 0.625} [get_ports clk]

# Clock Latency
set_clock_latency -source 0.150 [get_clocks clk]
set_clock_latency 0.050 [get_clocks clk]

# Clock Uncertainty
set_clock_uncertainty -setup 0.050 [get_clocks clk]
set_clock_uncertainty -hold 0.025 [get_clocks clk]

# Input Delay (relative to clk)
set_input_delay -clock clk -max 0.300 [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay -clock clk -min 0.100 [remove_from_collection [all_inputs] [get_ports clk]]

# Output Delay (relative to clk)
set_output_delay -clock clk -max 0.300 [all_outputs]
set_output_delay -clock clk -min 0.050 [all_outputs]

# Clock Gating
set_clock_gating_check -setup 0.100 -hold 0.050 [get_clocks clk]

# False Paths
set_false_path -from [get_ports reset_n]
set_false_path -from [get_ports scan_enable]

# Max Transition
set_max_transition 0.150 [current_design]

# Max Capacitance
set_max_capacitance 0.500 [current_design]

# Max Fanout
set_max_fanout 32 [current_design]

# Min Period (for multi-cycle paths)
set_multicycle_path -setup 2 -from [get_pins u_ex/u_mult/array_mult/*] -to [get_pins u_ex/u_mult/mult_reg[*]/D]
set_multicycle_path -hold 1 -from [get_pins u_ex/u_mult/array_mult/*] -to [get_pins u_ex/u_mult/mult_reg[*]/D]

# Drive Strength
set_drive 0.000 [get_ports clk]
set_drive 0.100 [remove_from_collection [all_inputs] [get_ports clk]]

# Load
set_load 0.050 [all_outputs]

# Operating Conditions
set_operating_conditions -min_library NangateOpenCellLibrary -min FF_generic_slow \
                         -max_library NangateOpenCellLibrary -max FF_generic_fast

# Wire Load Model
set_wire_load_mode enclosed
set_wire_load_model -name G200K -library NangateOpenCellLibrary

# Don't Touch
set_dont_touch [get_cells u_fetch/u_icache/tags_reg[*]]
set_dont_touch [get_cells u_regfile/regs_reg[*]]

# Don't Use
set_dont_use [get_lib_cells NangateOpenCellLibrary/CLKBUF_X16]

# Group Paths
group_path -name critical_path -from [get_pins u_decode/instr_reg[*]/CK] -to [get_pins u_ex/*/D]

# Ideal Network
set_ideal_network [get_ports reset_n]
