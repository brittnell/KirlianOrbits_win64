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
        
        self.log("MIDI Manager initialized.")
        self.refresh_ports()
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
        """Panic and safely close the MIDI port."""
        self.panic()
        if self.port:
            try:
                self.port.close()
                self.log("MIDI port closed.")
            except Exception as e:
                print(f"Error closing MIDI port: {e}")
            self.port = None
            self.port_name = None
