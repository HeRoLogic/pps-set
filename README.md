# pps-set

CLI tool to control the **Atten PPS3205T-3S** programmable power supply via its 24-byte serial protocol.

## Why

The Atten PPS3000 series uses a protocol where every packet sent to the device
is a set-command — there is no pure read operation. This means any tool that
polls the device (including sigrok-cli in continuous mode) will reset all
channel values to zero.

`pps-set` solves this by storing the current state in a local file
(`/tmp/pps-state.json`). When you change one channel, the others are sent
along with their previous values. When you read, the last known state is
re-sent so nothing changes on the device.

## Features

- Set voltage and current limit per channel
- Individual channel on/off control
- Series mode (CH1+CH2 in series, up to 64V)
- Parallel mode (CH1||CH2, up to 10A)
- Overcurrent protection (OCP) on/off
- Input validation with clamping to hardware limits
- Requested/Before/After display showing what you asked for vs. what the device reports
- Series/Parallel total voltage and current in output
- Verification warnings if device doesn't match requested state

## Usage

### Basic

```bash
# Set all three channels and turn on
pps-set CH1=5.0V/1.0A CH2=3.3V/1.0A CH3=1.8V/0.5A --on

# Change only CH1, keep CH2 and CH3 as they are
pps-set CH1=12.0V/2.0A

# Read current state without changing anything
pps-set --read

# Turn all outputs off (voltage settings are preserved)
pps-set --off

# Turn back on with previous values
pps-set --on
```

### Individual channel control

```bash
# Only CH1 on, others off
pps-set CH1=5.0V/1.0A --ch1-on --ch2-off --ch3-off

# Turn on CH3 without touching CH1 and CH2
pps-set --ch3-on
```

### Channel modes

```bash
# Series: CH1+CH2 in series (e.g. 15V + 15V = 30V, or ±15V)
pps-set CH1=15.0V/1.0A CH2=15.0V/1.0A --series --on

# Parallel: CH1||CH2 (e.g. 5V with up to 10A)
pps-set CH1=5.0V/2.5A CH2=5.0V/2.5A --parallel --on

# Back to independent
pps-set --independent
```

### Overcurrent protection

```bash
# Enable OCP — channels shut off if current limit is exceeded
pps-set --ocp-on

# Disable OCP — channels stay on, current is limited (CC mode)
pps-set --ocp-off
```

### Output format

Set commands show Requested, Before, and After:

```
Requested:
  CH1:  15.00 V  limit 1.000 A  [ON]
  CH2:  15.00 V  limit 1.000 A  [ON]
  => Series total: 30.00 V / limit 1.000 A
  CH3:   1.80 V  limit 0.500 A  [ON]
  Mode: Series  OCP: ON

Before (measured):
  CH1:   5.00 V  0.000 A  [ON]
  CH2:   3.30 V  0.000 A  [ON]
  => Series total: 8.30 V / 0.000 A
  CH3:   1.72 V  0.000 A  [ON]
  Mode: Independent  OCP: OFF

After (measured):
  CH1:  15.00 V  0.000 A  [ON]
  CH2:  15.00 V  0.000 A  [ON]
  => Series total: 30.00 V / 0.000 A
  CH3:   1.72 V  0.000 A  [ON]
  Mode: Series  OCP: ON
```

- **Requested** shows what you asked for, with `limit` for current (= the max the device will deliver)
- **Before/After** show measured values from the device (actual voltage and current flowing)
- Series/Parallel totals are shown automatically when in those modes
- Values exceeding hardware limits are clamped with a WARNING
- If After doesn't match Requested, a VERIFY warning is shown

## Installation

```bash
# Requires Python 3 and pyserial
sudo apt-get install python3-serial    # Debian/Raspberry Pi OS
# or
pip install pyserial

# Install pps-set
sudo cp pps-set.py /usr/local/bin/pps-set
sudo chmod +x /usr/local/bin/pps-set
```

The default serial port is `/dev/ttyUSB0` (the built-in CH340 USB-serial
adapter in the Atten PPS3205). Edit the `PORT` variable at the top of the
script if your setup differs.

## Supported Devices

Tested on the **Atten PPS3205T-3S**. Should also work with other models
in the PPS3000 series that share the same 24-byte protocol:

| Model | Channels | Current |
|-------|----------|---------|
| PPS3203T-3S | 3 | 3 x 3A |
| PPS3205T-3S | 3 | 3 x 5A |
| PPS3203T-2S | 3 | 2 x 3A + fixed |
| PPS3205T-2S | 3 | 2 x 5A + fixed |
| PPS3003S | 1 | 3A |
| PPS3005S | 1 | 5A |

Rebranded versions (Tenma 72-8795, Velleman PS3005D) likely work too.

## Protocol

9600 baud, 8N2, 24-byte packets in both directions. See the
[sigrok wiki](https://sigrok.org/wiki/Atten_PPS3000_Series) for the full
protocol specification.

## Related Projects

- [pps-tools](https://github.com/mturquette/pps-tools) by Mike Turquette —
  an earlier Python toolkit for the same device family with sampling and
  logging features. `pps-set` differs in its state-file approach for
  non-destructive reads and its focus on quick one-liner control.

- [libsigrok atten-pps3xxx driver](https://github.com/sigrokproject/libsigrok) —
  the official sigrok driver. See also
  [PR #286](https://github.com/sigrokproject/libsigrok/pull/286) which adds
  PPS3205T-3S support.

## License

MIT — see [LICENSE](LICENSE).
