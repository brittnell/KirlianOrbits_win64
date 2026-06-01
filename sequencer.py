import math
import uuid
import time

# Help for note names
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def midi_to_name(midi_val):
    """Convert MIDI number (e.g. 60) to Note name (e.g. 'C4')"""
    octave = (midi_val // 12) - 1
    note_idx = midi_val % 12
    return f"{NOTE_NAMES[note_idx]}{octave}"

def name_to_midi(name):
    """Convert Note name (e.g. 'C#4') to MIDI number (e.g. 61)"""
    try:
        if len(name) < 2:
            return 60
        octave = int(name[-1])
        note_str = name[:-1].upper()
        if note_str in NOTE_NAMES:
            note_idx = NOTE_NAMES.index(note_str)
            return 12 * (octave + 1) + note_idx
    except Exception:
        pass
    return 60


def get_notes_in_scale(root, scale_name, min_pitch, max_pitch):
    scale_intervals = {
        "Chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "Major": [0, 2, 4, 5, 7, 9, 11],
        "Minor": [0, 2, 3, 5, 7, 8, 10],
        "Pentatonic Major": [0, 2, 4, 7, 9],
        "Pentatonic Minor": [0, 3, 5, 7, 10],
        "Blues": [0, 3, 5, 6, 7, 10],
        "Dorian": [0, 2, 3, 5, 7, 9, 10],
        "Phrygian": [0, 1, 3, 5, 7, 8, 10],
        "Lydian": [0, 2, 4, 6, 7, 9, 11],
        "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "Locrian": [0, 1, 3, 5, 6, 8, 10],
        "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
        "Melodic Minor": [0, 2, 3, 5, 7, 9, 11],
        "Whole Tone": [0, 2, 4, 6, 8, 10],
        "Hijaz / Phrygian Dom": [0, 1, 4, 5, 7, 8, 10],
        "Hungarian Minor": [0, 2, 3, 6, 7, 8, 11],
        "Japanese In Sen": [0, 1, 5, 7, 8],
        "Raga Bhairav": [0, 1, 4, 5, 7, 8, 11],
        "Spanish Gypsy": [0, 1, 4, 5, 7, 8, 10],
        "Acoustic / Lydian Dom": [0, 2, 4, 6, 7, 9, 10],
        "Major Locrian": [0, 2, 4, 5, 6, 8, 10],
        "Enigmatic": [0, 1, 4, 6, 8, 10, 11]
    }
    intervals = scale_intervals.get(scale_name, scale_intervals["Chromatic"])
    valid_notes = []
    for p in range(int(min_pitch), int(max_pitch) + 1):
        if (p - root) % 12 in intervals:
            valid_notes.append(p)
    return valid_notes if valid_notes else [int(min_pitch)]

class Note:
    def __init__(self, x_rel, y_rel, clock_radius=200, midi_note=60, velocity=100, gate_length=0.5, midi_channel=0):
        self.id = str(uuid.uuid4())
        
        # musical properties
        self.midi_note = midi_note
        self.velocity = velocity
        self.gate_length = gate_length      # In beats
        self.midi_channel = midi_channel    # 0-15 representing Channels 1-16
        
        # Orbital shit properties
        self.orbit_mode = 0                 # 0: BPM Percentage, 1: Sync Divisor
        self.orbit_speed = 100.0            # In % mode: 1-400% (default 100%). In sync mode: divisor choice (1-16, default 1)
        
        # positions
        self.norm_r = 0.5                  # Normalized radius (0.0 to 1.0)
        self.polar_angle = 0.0              # Current orbital position in radians (0 to 2pi)
        self.prev_angle = 0.0               # Position in previous frame to avoid skipped triggers
        
        # Generative / random range shit
        self.use_pitch_range = False
        self.pitch_min = 48
        self.pitch_max = 72
        self.pitch_scale = "Chromatic"
        self.pitch_key = "C"
        
        self.use_vel_range = False
        self.vel_min = 80
        self.vel_max = 120
        
        self.use_gate_range = False
        self.gate_min = 0.25
        self.gate_max = 0.75
        
        # Relative coordinates (auto-synced)
        self.x = x_rel
        self.y = y_rel
        
        # Visualz
        self.radius = 20
        self.flash_intensity = 0.0
        self.is_dragging = False
        
        self.update_polar(x_rel, y_rel, clock_radius)
        self.init_norm_r = self.norm_r
        self.init_polar_angle = self.polar_angle

    def update_polar(self, x_rel, y_rel, clock_radius):
        """Calculate normalized polar coordinates from relative coordinates."""
        self.x = x_rel
        self.y = y_rel
        polar_r = math.sqrt(x_rel**2 + y_rel**2)
        
        self.norm_r = min(1.0, max(0.0, polar_r / clock_radius))
        
        raw_angle = math.atan2(self.y, self.x)
        self.polar_angle = (raw_angle + math.pi/2) % (2 * math.pi)
        self.prev_angle = self.polar_angle

    def sync_cartesian(self, clock_radius):
        """Calculate relative x, y coordinates from normalized radius and current clock radius."""
        self.x = self.norm_r * clock_radius * math.sin(self.polar_angle)
        self.y = -self.norm_r * clock_radius * math.cos(self.polar_angle)

    @property
    def polar_r(self):
        return math.sqrt(self.x**2 + self.y**2)

    @property
    def name(self):
        return midi_to_name(self.midi_note)


class Sequencer:
    def __init__(self):
        self.notes = []
        self.bpm = 120
        self.is_playing = False
        
        # Cubic Bezier Spline Control handles
        # Starts stationary (not spinning). Defined relative to center.
        # P0 is fixed at center (0, 0). P1, P2 are handles, P3 is outer tip.
        self.handles = [
            [0.0, -60.0],   # H1 (Inner Control Handle)
            [0.0, -130.0],  # H2 (Middle Control Handle)
            [0.0, -200.0]   # H3 (Outer Anchor Point)
        ]
        
        self.is_line_spinning = False       # Line starts stationary (does not spin)
        self.line_spin_direction = 1        # 1: Clockwise, -1: Counter-Clockwise
        self.sweep_angle = 0.0              # Line spin/sweep angle (radians)
        self.prev_sweep_angle = 0.0
        self.last_tick_time = 0.0
        self.clock_radius = 200
        
        self.add_default_notes()

    def add_default_notes(self):
        """Spawn initial notes in a circle so the user sees a demo immediately."""
        # Spawn three planets orbiting at different radii and sync speeds!
        # Planet 1 (Inner): C4 (60), radius 75px, Sync Divisor 1 (fastest)
        # Planet 2 (Middle): E4 (64), radius 130px, Sync Divisor 2 (half speed)
        # Planet 3 (Outer): G4 (67), radius 180px, Sync Divisor 4 (quarter speed)
        
        # We will add them relative to clock_radius=200
        n1 = Note(0, -75, self.clock_radius, midi_note=60, velocity=100, gate_length=0.5, midi_channel=0)
        n1.orbit_mode = 1
        n1.orbit_speed = 1.0  # Divisor 1
        
        n2 = Note(130, 0, self.clock_radius, midi_note=64, velocity=100, gate_length=0.5, midi_channel=0)
        n2.orbit_mode = 1
        n2.orbit_speed = 2.0  # Divisor 2
        
        n3 = Note(0, 180, self.clock_radius, midi_note=67, velocity=100, gate_length=0.5, midi_channel=0)
        n3.orbit_mode = 1
        n3.orbit_speed = 4.0  # Divisor 4
        
        self.notes.extend([n1, n2, n3])

    def add_note(self, x_rel, y_rel):
        """Add a note at the given relative coordinates."""
        r = math.sqrt(x_rel**2 + y_rel**2)
        scale = [48, 52, 55, 57, 60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84]
        r_normalized = min(1.0, max(0.0, r / self.clock_radius))
        idx = int(r_normalized * (len(scale) - 1))
        pitch = scale[idx]
        
        # new notes default to BPM percentage mode (100%)
        new_note = Note(x_rel, y_rel, self.clock_radius, midi_note=pitch, velocity=100, gate_length=0.5, midi_channel=0)
        new_note.orbit_mode = 0
        new_note.orbit_speed = 100.0  # 100% of BPM
        self.notes.append(new_note)
        return new_note

    def remove_note(self, note):
        if note in self.notes:
            self.notes.remove(note)

    def clear_all(self):
        self.notes = []

    def set_bpm(self, bpm):
        self.bpm = max(1, min(1000, bpm))

    def start(self):
        if not self.is_playing:
            self.is_playing = True
            self.last_tick_time = time.time()
            self.prev_sweep_angle = self.sweep_angle
            for note in self.notes:
                note.prev_angle = note.polar_angle

    def stop(self):
        self.is_playing = False

    def reset_clock(self):
        self.sweep_angle = 0.0
        self.prev_sweep_angle = 0.0

    def get_bezier_points(self, ang=None):
        """Evaluate Cubic Bezier curve points at 100 segments."""
        # P0 is fixed at center (0, 0)
        p0 = (0.0, 0.0)
        
        # Get control handles (H1, H2, H3)
        h1 = self.handles[0]
        h2 = self.handles[1]
        h3 = self.handles[2]
        
        # If line spinning is active, we rotate all control handles!
        if self.is_line_spinning:
            if ang is None:
                ang = self.sweep_angle
            cos_a = math.cos(ang)
            sin_a = math.sin(ang)
            
            p1 = (h1[0] * cos_a - h1[1] * sin_a, h1[0] * sin_a + h1[1] * cos_a)
            p2 = (h2[0] * cos_a - h2[1] * sin_a, h2[0] * sin_a + h2[1] * cos_a)
            p3 = (h3[0] * cos_a - h3[1] * sin_a, h3[0] * sin_a + h3[1] * cos_a)
        else:
            p1 = (h1[0], h1[1])
            p2 = (h2[0], h2[1])
            p3 = (h3[0], h3[1])
            
        points = []
        steps = 100
        for i in range(steps + 1):
            t = i / steps
            # Cubic Bezier formula: B(t) = (1-t)^3 * P0 + 3(1-t)^2 * t * P1 + 3(1-t) * t^2 * P2 + t^3 * P3
            bx = (3 * (1-t)**2 * t * p1[0] + 
                  3 * (1-t) * t**2 * p2[0] + 
                  t**3 * p3[0])
                  
            by = (3 * (1-t)**2 * t * p1[1] + 
                  3 * (1-t) * t**2 * p2[1] + 
                  t**3 * p3[1])
                  
            points.append((bx, by))
        return points

    def get_spline_angle_at_radius(self, norm_r, bezier_points=None):
        """Find the polar angle of the Bezier spline at the note's normalized radius slice."""
        target_r = norm_r * self.clock_radius
        if bezier_points is None:
            bezier_points = self.get_bezier_points()
            
        best_point = None
        min_diff = float('inf')
        
        for p in bezier_points:
            pr = math.sqrt(p[0]**2 + p[1]**2)
            diff = abs(pr - target_r)
            if diff < min_diff:
                min_diff = diff
                best_point = p
                
        if best_point:
            raw_angle = math.atan2(best_point[1], best_point[0])
            return (raw_angle + math.pi/2) % (2 * math.pi)
            
        return 0.0

    def update(self, midi_manager):
        """Update note orbital angles, line rotation (if active) and check triggers."""
        # Decay note trigger flashes
        for note in self.notes:
            if note.flash_intensity > 0:
                note.flash_intensity = max(0.0, note.flash_intensity - 0.08)

        if not self.is_playing:
            return

        now = time.time()
        dt = now - self.last_tick_time
        self.last_tick_time = now

        # 1. Update Line Sweep angle if spinning is enabled
        omega_base = (math.pi * self.bpm) / 120.0  # Base rotation speed (1 full orbit = 4 beats)
        if self.is_line_spinning:
            self.prev_sweep_angle = self.sweep_angle
            self.sweep_angle = (self.sweep_angle + self.line_spin_direction * omega_base * dt) % (2 * math.pi)
            
        # 2. Evaluate current and previous Bezier spline points once per frame
        bezier_points_curr = self.get_bezier_points(self.sweep_angle)
        bezier_points_prev = self.get_bezier_points(self.prev_sweep_angle)

        # 3. Update notes orbital positions and check spline intersection crossings!
        for note in self.notes:
            # Calculate orbital speed
            if note.orbit_mode == 0:
                # BPM percentage mode: speed = % of overall BPM
                pct = note.orbit_speed / 100.0
                omega_note = omega_base * pct
            else:
                # Sync Divisor mode: speed = BPM / divisor
                div = max(1.0, note.orbit_speed)
                omega_note = omega_base / div
                
            note.prev_angle = note.polar_angle
            note.polar_angle = (note.polar_angle + omega_note * dt) % (2 * math.pi)
            note.sync_cartesian(self.clock_radius)
            
            # Find the exact target angle of the Bezier spline at this note's radius slice!
            theta_spline_curr = self.get_spline_angle_at_radius(note.norm_r, bezier_points_curr)
            theta_spline_prev = self.get_spline_angle_at_radius(note.norm_r, bezier_points_prev)
            
            # Use relative coordinates: calculate relative angle of note to spline at start and end of frame
            relative_prev = (note.prev_angle - theta_spline_prev) % (2 * math.pi)
            relative_curr = (note.polar_angle - theta_spline_curr) % (2 * math.pi)
            
            # A collision happens if the relative angle crosses 0 modulo 2pi (in either direction) in minor arc (removed a lot of this)
            if self._is_relative_crossed(relative_prev, relative_curr):
                # Generative / Random range calculations
                trigger_pitch = note.midi_note
                if note.use_pitch_range:
                    import random
                    # Map key name to midi root (0-11)
                    key_idx = NOTE_NAMES.index(note.pitch_key) if hasattr(note, 'pitch_key') and note.pitch_key in NOTE_NAMES else 0
                    valid_pitches = get_notes_in_scale(key_idx, note.pitch_scale, note.pitch_min, note.pitch_max)
                    trigger_pitch = random.choice(valid_pitches)
                    
                trigger_vel = note.velocity
                if note.use_vel_range:
                    import random
                    trigger_vel = int(random.randint(int(note.vel_min), int(note.vel_max)))
                    
                trigger_gate = note.gate_length
                if note.use_gate_range:
                    import random
                    trigger_gate = random.uniform(note.gate_min, note.gate_max)
                    
                # Trigger sound!
                gate_sec = trigger_gate * (60.0 / self.bpm)
                midi_manager.send_note_on(
                    midi_note=trigger_pitch,
                    velocity=trigger_vel,
                    channel=note.midi_channel,
                    gate_length_sec=gate_sec
                )
                note.flash_intensity = 1.0

    def _is_relative_crossed(self, start, end):
        """Check if relative angle crossed 0 modulo 2pi (in either direction) in minor arc."""
        start = start % (2 * math.pi)
        end = end % (2 * math.pi)
        
        diff = (end - start) % (2 * math.pi)
        if diff == 0:
            return False
            
        # Shift relative to start so that start is 0. 
        # Then we check if the target (0, which becomes (2pi - start) % 2pi) was crossed.
        target_shifted = (2 * math.pi - start) % (2 * math.pi)
        
        if diff < math.pi:
            # Clockwise movement along minor arc
            return target_shifted <= diff
        else:
            # Counter-clockwise movement along minor arc
            return target_shifted >= diff

    def save_to_json(self, filepath):
        import json
        data = {
            "bpm": self.bpm,
            "is_line_spinning": self.is_line_spinning,
            "line_spin_direction": self.line_spin_direction,
            "handles": self.handles,
            "notes": [
                {
                    "midi_note": note.midi_note,
                    "velocity": note.velocity,
                    "gate_length": note.gate_length,
                    "midi_channel": note.midi_channel,
                    "orbit_mode": note.orbit_mode,
                    "orbit_speed": note.orbit_speed,
                    "norm_r": note.norm_r,
                    "polar_angle": note.polar_angle,
                    
                    "use_pitch_range": note.use_pitch_range,
                    "pitch_min": note.pitch_min,
                    "pitch_max": note.pitch_max,
                    "pitch_scale": note.pitch_scale,
                    "pitch_key": getattr(note, 'pitch_key', 'C'),
                    "use_vel_range": note.use_vel_range,
                    "vel_min": note.vel_min,
                    "vel_max": note.vel_max,
                    "use_gate_range": note.use_gate_range,
                    "gate_min": note.gate_min,
                    "gate_max": note.gate_max
                }
                for note in self.notes
            ]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def load_from_json(self, filepath):
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        self.bpm = data.get("bpm", 120)
        self.is_line_spinning = data.get("is_line_spinning", False)
        self.line_spin_direction = data.get("line_spin_direction", 1)
        self.handles = data.get("handles", self.handles)
        
        self.notes = []
        for n_data in data.get("notes", []):
            note = Note(0.0, 0.0, self.clock_radius)
            note.midi_note = n_data.get("midi_note", 60)
            note.velocity = n_data.get("velocity", 100)
            note.gate_length = n_data.get("gate_length", 0.5)
            note.midi_channel = n_data.get("midi_channel", 0)
            note.orbit_mode = n_data.get("orbit_mode", 0)
            note.orbit_speed = n_data.get("orbit_speed", 100.0)
            note.norm_r = n_data.get("norm_r", 0.5)
            note.polar_angle = n_data.get("polar_angle", 0.0)
            
            note.use_pitch_range = n_data.get("use_pitch_range", False)
            note.pitch_min = n_data.get("pitch_min", 48)
            note.pitch_max = n_data.get("pitch_max", 72)
            note.pitch_scale = n_data.get("pitch_scale", "Chromatic")
            note.pitch_key = n_data.get("pitch_key", "C")
            note.use_vel_range = n_data.get("use_vel_range", False)
            note.vel_min = n_data.get("vel_min", 80)
            note.vel_max = n_data.get("vel_max", 120)
            note.use_gate_range = n_data.get("use_gate_range", False)
            note.gate_min = n_data.get("gate_min", 0.25)
            note.gate_max = n_data.get("gate_max", 0.75)
            
            note.sync_cartesian(self.clock_radius)
            note.init_norm_r = note.norm_r
            note.init_polar_angle = note.polar_angle
            self.notes.append(note)

    def straighten_spline(self):
        self.handles = [
            [0.0, -60.0],
            [0.0, -130.0],
            [0.0, -200.0]
        ]
        
    def reset_orbits(self):
        self.sweep_angle = 0.0
        self.prev_sweep_angle = 0.0
        for note in self.notes:
            note.norm_r = note.init_norm_r
            note.polar_angle = note.init_polar_angle
            note.sync_cartesian(self.clock_radius)
