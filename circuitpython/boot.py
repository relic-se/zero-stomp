# SPDX-FileCopyrightText: Copyright (c) 2024 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import os
import storage
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

# Configure storage

storage.remount("/", readonly=False)
m = storage.getmount("/")
m.label = "ZERO_STOMP"

storage.remount("/", readonly=False)
storage.enable_usb_drive()

# Ensure that apps folder exists

try:
    os.stat("/apps")
except OSError:
    os.mkdir("/apps")
