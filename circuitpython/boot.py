# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import os
import supervisor
import usb_cdc
import usb_hid
import usb_midi

# Configure USB

supervisor.set_usb_identification(
    manufacturer="relic-se",
    product="zero-stomp",
)

usb_midi.set_names(
    streaming_interface_name="zero-stomp",
    in_jack_name="midi in",
    out_jack_name="midi out"
)

usb_hid.disable()
usb_cdc.enable(console=True, data=False)

# Ensure that apps folder exists

try:
    os.stat("/apps")
except OSError:
    os.mkdir("/apps")
