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

## Usage
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

Set commands show before/after state:
```
Before:
  CH1:   5.00 V  0.000 A  [ON]
  CH2:   3.30 V  0.000 A  [ON]
  CH3:   1.72 V  0.000 A  [ON]
  Mode: Independent  OCP: OFF

After:
  CH1:  12.00 V  0.000 A  [ON]
  CH2:   3.30 V  0.000 A  [ON]
  CH3:   1.72 V  0.000 A  [ON]
  Mode: Independent  OCP: OFF
```

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
