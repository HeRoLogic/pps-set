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

# PPS3205T-3S limits (highest in the PPS3000 series)
LIMITS = {
    'CH1': {'V_max': 32.0, 'A_max': 5.0},
    'CH2': {'V_max': 32.0, 'A_max': 5.0},
    'CH3': {'V_max':  6.0, 'A_max': 5.0},
}

MODE_NAMES = {0: "Independent", 1: "Series", 2: "Parallel"}

DEFAULT_STATE = {
    'CH1': {'V': 0.0, 'A': 0.0},
    'CH2': {'V': 0.0, 'A': 0.0},
    'CH3': {'V': 0.0, 'A': 0.0},
    'enable': 0, 'ocp': 0, 'mode': 0,
}

CH_BITS = {'CH1': 0x01, 'CH2': 0x02, 'CH3': 0x04}

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

def validate(state):
    """Check values against hardware limits. Returns list of warnings."""
    warnings = []
    for ch in ['CH1', 'CH2', 'CH3']:
        v = state[ch]['V']
        a = state[ch]['A']
        v_max = LIMITS[ch]['V_max']
        a_max = LIMITS[ch]['A_max']
        if v < 0:
            warnings.append(f"{ch}: voltage {v}V is negative, clamped to 0")
            state[ch]['V'] = 0.0
        if v > v_max:
            warnings.append(f"{ch}: voltage {v}V exceeds max {v_max}V, clamped to {v_max}")
            state[ch]['V'] = v_max
        if a < 0:
            warnings.append(f"{ch}: current {a}A is negative, clamped to 0")
            state[ch]['A'] = 0.0
        if a > a_max:
            warnings.append(f"{ch}: current {a}A exceeds max {a_max}A, clamped to {a_max}")
            state[ch]['A'] = a_max
    return warnings

def verify(state, result):
    """Compare requested vs actual values. Returns list of warnings."""
    warnings = []
    for ch in ['CH1', 'CH2', 'CH3']:
        ch_on = bool(state['enable'] & CH_BITS[ch])
        v_req = state[ch]['V']
        v_got = result[ch]['V']
        if ch_on and abs(v_req - v_got) > 0.5:
            warnings.append(f"{ch}: requested {v_req:.2f}V but device reports {v_got:.2f}V")
    for ch in ['CH1', 'CH2', 'CH3']:
        req_on = bool(state['enable'] & CH_BITS[ch])
        got_on = result[ch]['on']
        if req_on != got_on:
            warnings.append(f"{ch}: requested {'ON' if req_on else 'OFF'} but device reports {'ON' if got_on else 'OFF'}")
    return warnings

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
    return {
        'CH1': {'V': ch1v, 'A': ch1i, 'on': bool(en & 0x01)},
        'CH2': {'V': ch2v, 'A': ch2i, 'on': bool(en & 0x02)},
        'CH3': {'V': ch3v, 'A': ch3i, 'on': bool(en & 0x04)},
        'OCP': bool(pkt[18]),
        'mode': pkt[19] if pkt[19] < 3 else 0,
    }

def print_requested(state):
    """Print requested state with 'limit' label for current."""
    mode = state['mode']
    enable = state['enable']
    for ch in ['CH1', 'CH2', 'CH3']:
        v = state[ch]['V']
        a = state[ch]['A']
        on = bool(enable & CH_BITS[ch])
        s = "ON" if on else "OFF"
        print(f"  {ch}: {v:6.2f} V  limit {a:.3f} A  [{s}]")
        if ch == 'CH2':
            if mode == 1:
                total_v = state['CH1']['V'] + state['CH2']['V']
                limit_a = min(state['CH1']['A'], state['CH2']['A'])
                print(f"  => Series total: {total_v:.2f} V / limit {limit_a:.3f} A")
            elif mode == 2:
                total_a = state['CH1']['A'] + state['CH2']['A']
                print(f"  => Parallel total: {state['CH1']['V']:.2f} V / limit {total_a:.3f} A")
    print(f"  Mode: {MODE_NAMES.get(mode, 'Unknown')}  OCP: {'ON' if state['ocp'] else 'OFF'}")

def print_measured(resp):
    """Print measured state from device response."""
    mode = resp['mode']
    for ch in ['CH1', 'CH2', 'CH3']:
        c = resp[ch]
        s = "ON" if c['on'] else "OFF"
        print(f"  {ch}: {c['V']:6.2f} V  {c['A']:5.3f} A  [{s}]")
        if ch == 'CH2':
            if mode == 1:
                total_v = resp['CH1']['V'] + resp['CH2']['V']
                total_a = resp['CH1']['A']
                print(f"  => Series total: {total_v:.2f} V / {total_a:.3f} A")
            elif mode == 2:
                total_a = resp['CH1']['A'] + resp['CH2']['A']
                print(f"  => Parallel total: {resp['CH1']['V']:.2f} V / {total_a:.3f} A")
    print(f"  Mode: {MODE_NAMES.get(mode, 'Unknown')}  OCP: {'ON' if resp['OCP'] else 'OFF'}")

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
        print("  pps-set --on                             # all channels on")
        print("  pps-set --off                            # all channels off")
        print("  pps-set --ch1-on --ch2-off               # individual channel control")
        print("  pps-set --series --on                    # series mode (CH1+CH2)")
        print("  pps-set --parallel --on                  # parallel mode (CH1||CH2)")
        print("  pps-set --independent                    # back to independent")
        print("  pps-set --ocp-on                         # overcurrent protection on")
        print("  pps-set --ocp-off                        # overcurrent protection off")
        print("  pps-set --read                           # read without changing")
        print("")
        print("Limits: CH1/CH2: 0-32V / 0-5A, CH3: 0-6V / 0-5A")
        sys.exit(1)

    state = load_state()

    # Parse channel voltage/current settings
    for arg in args:
        m = re.match(r'(CH[123])=([0-9.]+)[Vv]/([0-9.]+)[Aa]', arg)
        if m:
            ch, v, a = m.group(1), float(m.group(2)), float(m.group(3))
            state[ch]['V'] = v
            state[ch]['A'] = a

    # All channels on/off
    if '--on' in args:
        state['enable'] = 0x07
    if '--off' in args:
        state['enable'] = 0x00

    # Individual channel on/off
    if '--ch1-on' in args:
        state['enable'] |= 0x01
    if '--ch1-off' in args:
        state['enable'] &= ~0x01
    if '--ch2-on' in args:
        state['enable'] |= 0x02
    if '--ch2-off' in args:
        state['enable'] &= ~0x02
    if '--ch3-on' in args:
        state['enable'] |= 0x04
    if '--ch3-off' in args:
        state['enable'] &= ~0x04

    # Channel modes
    if '--independent' in args:
        state['mode'] = 0
    if '--series' in args:
        state['mode'] = 1
    if '--parallel' in args:
        state['mode'] = 2

    # Overcurrent protection
    if '--ocp-on' in args:
        state['ocp'] = 1
    if '--ocp-off' in args:
        state['ocp'] = 0

    # Validate limits before sending
    if '--read' not in args:
        warnings = validate(state)
        for w in warnings:
            print(f"  WARNING: {w}")

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

    before = parse_response(resp_before)
    result = parse_response(resp)

    if '--read' in args:
        if result:
            print_measured(result)
    else:
        print("Requested:")
        print_requested(state)
        print("")

        if before:
            print("Before (measured):")
            print_measured(before)
            print("")

        if result:
            print("After (measured):")
            print_measured(result)

        if result:
            vwarnings = verify(state, result)
            if vwarnings:
                print("")
                for w in vwarnings:
                    print(f"  VERIFY: {w}")

if __name__ == '__main__':
    main()
