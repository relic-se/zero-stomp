# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import microcontroller

import zero_stomp

# Scan for programs
programs = zero_stomp.get_programs()

try:
    zero_stomp.load_program(save=False)
except OSError:
    # Reset the device in safe mode unable to load program
    microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
    microcontroller.reset()
