#!/usr/bin/env python3
"""
pps-set — CLI tool to control the Atten PPS3205T-3S power supply.

Controls all three channels in a single command via the 24-byte serial
protocol. Stores state between invocations so that reading or changing
one channel doesn't reset the others.

Copyright (C) 2026 Roman Hefele <moi@romanhefele.de>
SPDX-License-Identifier: MIT
"""

import sys, struct, serial, time, re, json, os

PORT = "/dev/ttyUSB0"
BAUD = 9600
STATE_FILE = "/tmp/pps-state.json"

DEFAULT_STATE = {
    'CH1': {'V': 0.0, 'A': 0.0},
    'CH2': {'V': 0.0, 'A': 0.0},
    'CH3': {'V': 0.0, 'A': 0.0},
    'enable': 0, 'ocp': 0, 'mode': 0,
}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_STATE.copy()

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def make_packet(state):
    pkt = bytearray(24)
    pkt[0] = 0xaa
    pkt[1] = 0x20
    struct.pack_into('>H', pkt, 2,  int(state['CH1']['V'] * 100))
    struct.pack_into('>H', pkt, 4,  int(state['CH1']['A'] * 1000))
    struct.pack_into('>H', pkt, 6,  int(state['CH2']['V'] * 100))
    struct.pack_into('>H', pkt, 8,  int(state['CH2']['A'] * 1000))
    struct.pack_into('>H', pkt, 10, int(state['CH3']['V'] * 100))
    struct.pack_into('>H', pkt, 12, int(state['CH3']['A'] * 1000))
    pkt[14] = 0x01
    pkt[15] = state['enable'] & 0x07
    pkt[16] = 0x01
    pkt[17] = 0x00
    pkt[18] = state['ocp'] & 0x01
    pkt[19] = state['mode'] & 0x03
    pkt[23] = sum(pkt[:23]) & 0xff
    return pkt

def parse_response(pkt):
    if len(pkt) < 24:
        return None
    ch1v = struct.unpack_from('>H', pkt, 2)[0] / 100.0
    ch1i = struct.unpack_from('>H', pkt, 4)[0] / 1000.0
    ch2v = struct.unpack_from('>H', pkt, 6)[0] / 100.0
    ch2i = struct.unpack_from('>H', pkt, 8)[0] / 1000.0
    ch3v = struct.unpack_from('>H', pkt, 10)[0] / 100.0
    ch3i = struct.unpack_from('>H', pkt, 12)[0] / 1000.0
    en = pkt[15]
    modes = {0: "Independent", 1: "Series", 2: "Parallel"}
    return {
        'CH1': {'V': ch1v, 'A': ch1i, 'on': bool(en & 0x01)},
        'CH2': {'V': ch2v, 'A': ch2i, 'on': bool(en & 0x02)},
        'CH3': {'V': ch3v, 'A': ch3i, 'on': bool(en & 0x04)},
        'OCP': bool(pkt[18]),
        'Mode': modes.get(pkt[19], "Unknown"),
    }

def print_state(resp):
    for ch in ['CH1', 'CH2', 'CH3']:
        c = resp[ch]
        s = "ON" if c['on'] else "OFF"
        print(f"  {ch}: {c['V']:6.2f} V  {c['A']:5.3f} A  [{s}]")
    print(f"  Mode: {resp['Mode']}  OCP: {'ON' if resp['OCP'] else 'OFF'}")

def send_recv(ser, pkt):
    ser.reset_input_buffer()
    ser.write(pkt)
    time.sleep(0.2)
    return ser.read(24)

def main():
    args = sys.argv[1:]
    if not args:
        print("pps-set — Control the Atten PPS3205T-3S power supply")
        print("")
        print("Usage:")
        print("  pps-set CH1=5.0V/1.0A CH2=3.3V/1.0A CH3=1.8V/0.5A --on")
        print("  pps-set CH1=12.0V/2.0A                  # set one channel, keep others")
        print("  pps-set --on                             # turn on with last values")
        print("  pps-set --off                            # turn off, keep values")
        print("  pps-set --read                           # read without changing")
        sys.exit(1)

    state = load_state()

    # Parse channel settings
    for arg in args:
        m = re.match(r'(CH[123])=([0-9.]+)[Vv]/([0-9.]+)[Aa]', arg)
        if m:
            ch, v, a = m.group(1), float(m.group(2)), float(m.group(3))
            state[ch]['V'] = v
            state[ch]['A'] = a

    if '--on' in args:
        state['enable'] = 0x07
    if '--off' in args:
        state['enable'] = 0x00

    # Send current state, read twice for accurate response
    ser = serial.Serial(PORT, BAUD, bytesize=8, parity='N', stopbits=2, timeout=2)
    time.sleep(0.1)

    pkt = make_packet(state)
    resp_before = send_recv(ser, pkt)
    time.sleep(1.0)
    resp = send_recv(ser, pkt)
    ser.close()

    if len(resp) < 24:
        print("No response from device. Is it on?")
        sys.exit(1)

    # Save state for next invocation
    save_state(state)

    # Show before/after for set commands, just current for --read
    before = parse_response(resp_before)
    result = parse_response(resp)

    if '--read' in args:
        if result:
            print_state(result)
    else:
        if before:
            print("Before:")
            print_state(before)
            print("")
        if result:
            print("After:")
            print_state(result)

if __name__ == '__main__':
    main()
