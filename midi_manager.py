import time
import mido

class MidiManager:
    def __init__(self):
        self.port = None
        self.port_name = None
        self.status_message = "No Port Open"  # Tracks dynamic connection status
        self.pending_note_offs = []           # List of dicts: {'note': int, 'channel': int, 'time': float}
        self.available_ports = []
        self.logs = []

        # MIDI clock input (sync slave): listens for clock + transport from a DAW
        self.in_port = None
        self.in_port_name = None
        self.available_in_ports = []
        self.clock_bpm = None                 # Smoothed BPM derived from incoming clock, or None
        self._clock_times = []                # Recent clock-pulse timestamps (one quarter = 24)

        self.log("MIDI Manager initialized.")
        self.refresh_ports()
        self.refresh_input_ports()
        self.open_default_port()

    def log(self, msg):
        """Append a timestamped log entry for system diagnostics."""
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 20:
            self.logs.pop(0)

    def refresh_ports(self):
        """Scan system for available MIDI output ports."""
        try:
            raw_ports = mido.get_output_names()
            seen = set()
            self.available_ports = []
            for p in raw_ports:
                if p not in seen:
                    seen.add(p)
                    self.available_ports.append(p)
            self.log(f"Refreshed ports list. Found {len(self.available_ports)} outputs.")
        except Exception as e:
            self.log(f"Error scanning ports: {e}")
            self.available_ports = []

    def refresh_input_ports(self):
        """Scan system for available MIDI *input* ports (for clock sync)."""
        try:
            raw = mido.get_input_names()
            seen = set()
            self.available_in_ports = []
            for p in raw:
                if p not in seen:
                    seen.add(p)
                    self.available_in_ports.append(p)
            names = ", ".join(self.available_in_ports) if self.available_in_ports else "none"
            self.log(f"Input ports ({len(self.available_in_ports)}): {names}")
        except Exception as e:
            self.log(f"Error scanning input ports: {e}")
            self.available_in_ports = []

    def open_input_port(self, name):
        """Open a MIDI input port by name to receive clock/transport. Closes previous first."""
        if self.in_port:
            try:
                self.in_port.close()
            except Exception:
                pass
        self.in_port = None
        self.in_port_name = None
        self.clock_bpm = None
        self._clock_times = []

        if not name or name == "No MIDI Inputs":
            self.log("Cleared MIDI clock input.")
            return False
        try:
            self.in_port = mido.open_input(name)
            self.in_port_name = name
            self.log(f"Opened clock input port: {name}")
            return True
        except Exception as e:
            self.log(f"Open input failed for '{name}': {e}")
            self.in_port = None
            self.in_port_name = None
            return False

    def poll_sync(self):
        """Drain pending MIDI input messages. Updates self.clock_bpm from clock pulses
        and returns transport events: {'start','continue','stop'} as booleans."""
        events = {'start': False, 'continue': False, 'stop': False}
        if not self.in_port:
            return events
        try:
            pending = list(self.in_port.iter_pending())
        except Exception as e:
            self.log(f"Input poll error: {e}")
            return events

        now = time.time()
        for msg in pending:
            if msg.type == 'clock':
                self._clock_times.append(now)
                if len(self._clock_times) > 24:           # keep ~one quarter note of pulses
                    self._clock_times.pop(0)
                if len(self._clock_times) >= 6:           # enough to estimate tempo
                    span = self._clock_times[-1] - self._clock_times[0]
                    ticks = len(self._clock_times) - 1
                    if span > 0:
                        bpm = 60.0 / ((span / ticks) * 24.0)
                        if 20.0 <= bpm <= 1000.0:
                            # one-pole smoothing to tame jitter
                            self.clock_bpm = bpm if self.clock_bpm is None else (self.clock_bpm * 0.8 + bpm * 0.2)
            elif msg.type == 'start':
                events['start'] = True
                self._clock_times = []
            elif msg.type == 'continue':
                events['continue'] = True
            elif msg.type == 'stop':
                events['stop'] = True
        return events

    def open_default_port(self):
        """Attempt to open the first available port, preferring the Microsoft GS Synth on Windows."""
        if not self.available_ports:
            self.status_message = "No MIDI Ports Found"
            self.log("No MIDI ports found during startup.")
            return False
            
        default_port = None
        for p in self.available_ports:
            if "Microsoft GS Wavetable" in p or "Microsoft GS Wavetable Synth" in p:
                default_port = p
                break
                
        if not default_port:
            default_port = self.available_ports[0]
            
        return self.open_port(default_port)

    def open_port(self, name):
        """Open a MIDI output port by name. Closes previous port first."""
        self.panic()  # Send all notes off before switching ports
        
        self.log(f"Attempting to open port: {name}")
        if self.port:
            try:
                self.port.close()
            except Exception as e:
                self.log(f"Error closing previous port: {e}")
                
        self.port = None
        self.port_name = None
        
        if not name or name == "No MIDI Ports":
            self.status_message = "No Port Open"
            self.log("Disconnected MIDI route.")
            return False
            
        try:
            self.port = mido.open_output(name)
            self.port_name = name
            self.status_message = "Active"
            self.log(f"Success! Opened output port: {name}")
            return True
        except Exception as e:
            err_str = str(e)
            self.log(f"Open failed for '{name}': {e}")
            
            # Formulate user-friendly status message based on common Windows errors
            if "already in use" in err_str.lower() or "exclusive" in err_str.lower() or "device" in err_str.lower():
                self.status_message = "Error: Port Busy / Locked"
            elif "not found" in err_str.lower():
                self.status_message = "Error: Port Disconnected"
            else:
                self.status_message = f"Error: {err_str[:22]}"
                
            self.port = None
            self.port_name = None
            return False

    def send_note_on(self, midi_note, velocity=100, channel=0, gate_length_sec=0.25):
        """Send a Note On message and schedule a corresponding Note Off."""
        if not self.port:
            self.log(f"Send failed: No MIDI port active. Note: {midi_note}")
            return
            
        midi_note = max(0, min(127, int(midi_note)))
        velocity = max(0, min(127, int(velocity)))
        channel = max(0, min(15, int(channel)))
        
        try:
            msg = mido.Message('note_on', note=midi_note, velocity=velocity, channel=channel)
            self.port.send(msg)
            self.log(f"Sent: NoteOn {midi_note} Vel {velocity} Chan {channel+1}")
            
            off_time = time.time() + gate_length_sec
            self.pending_note_offs.append({
                'note': midi_note,
                'channel': channel,
                'time': off_time
            })
        except Exception as e:
            self.log(f"Send NoteOn failed: {e}")

    def update(self):
        """Check and process scheduled Note Off messages. Call this every frame loop."""
        if not self.port or not self.pending_note_offs:
            return
            
        now = time.time()
        still_playing = []
        for note_off in self.pending_note_offs:
            if now >= note_off['time']:
                try:
                    msg = mido.Message('note_off', note=note_off['note'], velocity=0, channel=note_off['channel'])
                    self.port.send(msg)
                    # We can log note offs quietly if we want, or keep it quiet to prevent cluttering
                except Exception as e:
                    self.log(f"Error sending NoteOff: {e}")
            else:
                still_playing.append(note_off)
                
        self.pending_note_offs = still_playing

    def panic(self):
        """Panic button: send note off for all pending notes and send 'All Notes Off' controller messages."""
        if not self.port:
            return
            
        self.log("MIDI Panic triggered (All Notes Off).")
        for note_off in self.pending_note_offs:
            try:
                msg = mido.Message('note_off', note=note_off['note'], velocity=0, channel=note_off['channel'])
                self.port.send(msg)
            except Exception:
                pass
        self.pending_note_offs = []
        
        for chan in range(16):
            try:
                self.port.send(mido.Message('control_change', control=123, value=0, channel=chan))
                self.port.send(mido.Message('control_change', control=120, value=0, channel=chan))
            except Exception:
                pass

    def close(self):
        """Panic and safely close the MIDI ports."""
        self.panic()
        if self.port:
            try:
                self.port.close()
                self.log("MIDI port closed.")
            except Exception as e:
                print(f"Error closing MIDI port: {e}")
            self.port = None
            self.port_name = None
        if self.in_port:
            try:
                self.in_port.close()
            except Exception:
                pass
            self.in_port = None
            self.in_port_name = None
