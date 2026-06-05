import pygame
import math
from sequencer import NOTE_NAMES, midi_to_name

# Colors (Electric Blue Kirlian palette — dark base, blue as signal)
COLOR_BG = (8, 10, 14)          # Deep obsidian space (cool near-black)
COLOR_PANEL = (18, 22, 30)      # Slate drawer / panel fill
COLOR_BORDER = (38, 50, 70)     # Blue-gray panel border
COLOR_TEXT = (236, 244, 250)    # Cool spark white
COLOR_MUTED = (128, 142, 160)   # Faint corona gray (dim labels)
COLOR_PRIMARY = (56, 189, 248)  # Sky-cyan accent (#38BDF8) — interactive elements
COLOR_PINK = (255, 121, 198)    # Complementary highlight (selection / active)
COLOR_EMERALD = (80, 250, 123)  # Status green (active / note sent)
COLOR_RED = (255, 85, 85)       # High-voltage ruby (stop / errors)
COLOR_ORANGE = (255, 184, 108)  # Spark amber
COLOR_WHITE = (255, 255, 255)
COLOR_RING = (0, 170, 255)      # Outer clock ring + sweep arm (electric blue #00aaff)

class FontManager:
    def __init__(self):
        pygame.font.init()
        font_choices = ["Segoe UI", "Calibri", "Arial", "sans-serif"]
        self.font_name = pygame.font.match_font(font_choices)
        
        self.fonts = {
            'tiny': pygame.font.Font(self.font_name, 11),
            'small': pygame.font.Font(self.font_name, 14),
            'medium': pygame.font.Font(self.font_name, 16),
            'large': pygame.font.Font(self.font_name, 20),
            'huge': pygame.font.Font(self.font_name, 28)
        }

    def render(self, text, size, color=COLOR_TEXT):
        font = self.fonts.get(size, self.fonts['medium'])
        return font.render(text, True, color)


class Button:
    def __init__(self, x, y, w, h, text, color, hover_color, action, text_color=COLOR_TEXT):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.action = action
        self.is_hovered = False

    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered and self.action:
                self.action()
                return True
        return False

    def draw(self, surface, fm):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=6)
        
        text_surf = fm.render(self.text, 'small', self.text_color)
        tx = self.rect.x + (self.rect.width - text_surf.get_width()) // 2
        ty = self.rect.y + (self.rect.height - text_surf.get_height()) // 2
        surface.blit(text_surf, (tx, ty))


class Slider:
    # Only one slider may be in manual text-entry mode at a time (across the
    # whole app — sidebar sliders and the top-bar BPM slider share this).
    active_editor = None

    def __init__(self, x, y, w, h, min_val, max_val, current_val, label, unit="", integer_only=False, callback=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = current_val
        self.label = label
        self.unit = unit
        self.integer_only = integer_only
        self.callback = callback

        self.is_dragging = False
        self.handle_r = 8

        # Manual value-entry (double-click the readout to type a value)
        self.is_editing = False
        self.edit_text = ""
        self.select_all = False                      # whole value highlighted -> typing replaces it
        self.value_rect = pygame.Rect(0, 0, 0, 0)    # readout hit-area, set in draw()
        self.last_value_click = 0                    # ms timestamp for double-click detection

        self.update_handle_x()

    def begin_edit(self):
        """Enter manual text-entry mode, pre-filled with the current value."""
        if Slider.active_editor is not None and Slider.active_editor is not self:
            Slider.active_editor.commit_edit()
        self.is_editing = True
        if self.integer_only:
            self.edit_text = str(int(round(self.current_val)))
        else:
            self.edit_text = f"{self.current_val:.2f}".rstrip('0').rstrip('.')
        self.select_all = True          # opens with the value "selected" so typing replaces it
        Slider.active_editor = self

    def commit_edit(self):
        """Parse the typed text and apply it (clamped); keep old value if invalid."""
        if not self.is_editing:
            return
        self.is_editing = False
        if Slider.active_editor is self:
            Slider.active_editor = None
        try:
            self.set_value(float(self.edit_text.strip()))
        except ValueError:
            pass

    def cancel_edit(self):
        """Leave text-entry mode without applying the typed value."""
        self.is_editing = False
        if Slider.active_editor is self:
            Slider.active_editor = None

    def update_handle_x(self):
        val_range = self.max_val - self.min_val
        if val_range == 0:
            pct = 0
        else:
            pct = (self.current_val - self.min_val) / val_range
        self.handle_x = self.rect.x + int(pct * self.rect.width)

    def set_value(self, val):
        self.current_val = max(self.min_val, min(self.max_val, val))
        if self.integer_only:
            self.current_val = int(round(self.current_val))
        self.update_handle_x()
        if self.callback:
            self.callback(self.current_val)

    def handle_event(self, event):
        # --- Manual text-entry mode takes priority -------------------------
        if self.is_editing:
            if event.type == pygame.KEYDOWN:
                if (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_a:
                    self.select_all = True          # Ctrl+A re-selects all
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.commit_edit()
                elif event.key == pygame.K_ESCAPE:
                    self.cancel_edit()
                elif event.key == pygame.K_BACKSPACE:
                    if self.select_all:
                        self.edit_text = ""         # selection deleted in one stroke
                        self.select_all = False
                    else:
                        self.edit_text = self.edit_text[:-1]
                elif event.unicode and event.unicode in "0123456789.-":
                    if self.select_all:
                        self.edit_text = ""         # typing over the selection replaces it
                        self.select_all = False
                    self.edit_text += event.unicode
                return True  # swallow ALL keystrokes so global hotkeys don't fire
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.value_rect.collidepoint(event.pos):
                    self.select_all = True          # clicking in the field re-selects all
                    return True
                self.commit_edit()       # clicking elsewhere commits...
                return False             # ...and lets that click act normally
            return False

        # --- Normal mode ---------------------------------------------------
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            # Double-click the value readout to type a value manually
            if self.value_rect.collidepoint(mouse_pos):
                now = pygame.time.get_ticks()
                if now - self.last_value_click <= 400:
                    self.last_value_click = 0
                    self.begin_edit()
                else:
                    self.last_value_click = now
                return True

            expanded_rect = self.rect.inflate(0, 10)
            if expanded_rect.collidepoint(mouse_pos):
                self.is_dragging = True
                self.update_val_from_mouse(mouse_pos[0])
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                self.update_val_from_mouse(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.is_dragging = False
                return True

        return False

    def update_val_from_mouse(self, mouse_x):
        pct = (mouse_x - self.rect.x) / self.rect.width
        pct = max(0.0, min(1.0, pct))
        val = self.min_val + pct * (self.max_val - self.min_val)
        if self.integer_only:
            val = int(round(val))
        self.set_value(val)

    def draw(self, surface, fm):
        lbl_surf = fm.render(self.label, 'small', COLOR_MUTED)
        surface.blit(lbl_surf, (self.rect.x, self.rect.y - 20))
        
        val_str = f"{self.current_val}" if self.integer_only else f"{self.current_val:.2f}"
        if self.label in ("Note Pitch", "Pitch Min", "Pitch Max"):
            val_str = f"{midi_to_name(self.current_val)} ({self.current_val})"
        elif self.label == "Orbit Sync Divisor":
            val_str = f"/{int(self.current_val)}"

        val_surf = fm.render(f"{val_str} {self.unit}".strip(), 'small', COLOR_TEXT)

        if self.is_editing:
            # Manual entry field — keep the number at the SAME right edge and vertical
            # centre as the normal readout; just frame it in a box with a caret.
            txt_surf = fm.render(self.edit_text, 'small', COLOR_WHITE)
            val_h = val_surf.get_height()
            val_cy = (self.rect.y - 20) + val_h // 2          # readout's vertical centre
            right = self.rect.x + self.rect.width             # readout's right edge
            txt_x = right - txt_surf.get_width()              # right-aligned, unchanged position

            box_h = val_h + 6
            box_right = right + 10
            box_left = min(txt_x - 8, box_right - 58)         # enforce a sensible min width
            box = pygame.Rect(box_left, val_cy - box_h // 2, box_right - box_left, box_h)
            pygame.draw.rect(surface, (38, 40, 56), box, border_radius=3)
            pygame.draw.rect(surface, COLOR_PRIMARY, box, width=1, border_radius=3)

            if self.select_all and self.edit_text:
                # Whole value highlighted — typing or Backspace replaces it
                sel = pygame.Rect(txt_x - 2, val_cy - val_h // 2 - 1, txt_surf.get_width() + 4, val_h + 2)
                pygame.draw.rect(surface, COLOR_PRIMARY, sel, border_radius=2)
                hi = fm.render(self.edit_text, 'small', (12, 16, 22))
                surface.blit(hi, (txt_x, val_cy - hi.get_height() // 2))
            else:
                surface.blit(txt_surf, (txt_x, val_cy - txt_surf.get_height() // 2))
                if (pygame.time.get_ticks() // 500) % 2 == 0:     # blinking caret, fixed position
                    cx = right + 2
                    pygame.draw.line(surface, COLOR_WHITE, (cx, val_cy - val_h // 2 + 1), (cx, val_cy + val_h // 2 - 1), 1)
            self.value_rect = box
        else:
            vx = self.rect.x + self.rect.width - val_surf.get_width()
            vy = self.rect.y - 20
            surface.blit(val_surf, (vx, vy))
            self.value_rect = pygame.Rect(vx - 4, vy - 2, val_surf.get_width() + 8, val_surf.get_height() + 4)

        track_y = self.rect.y + self.rect.height // 2
        pygame.draw.line(surface, COLOR_BORDER, (self.rect.x, track_y), (self.rect.x + self.rect.width, track_y), width=4)
        
        if self.handle_x > self.rect.x:
            pygame.draw.line(surface, COLOR_PRIMARY, (self.rect.x, track_y), (self.handle_x, track_y), width=4)
            
        handle_color = COLOR_WHITE if self.is_dragging else COLOR_PRIMARY
        pygame.draw.circle(surface, handle_color, (self.handle_x, track_y), self.handle_r)


class Checkbox:
    def __init__(self, x, y, size, label, is_checked=False, callback=None):
        self.rect = pygame.Rect(x, y, size, size)
        self.label = label
        self.is_checked = is_checked
        self.callback = callback
        self.is_hovered = False
        
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                self.is_checked = not self.is_checked
                if self.callback:
                    self.callback(self.is_checked)
                return True
        return False
        
    def draw(self, surface, fm):
        # Draw small checkbox square with neon glow
        color = COLOR_PRIMARY if self.is_checked else (COLOR_BORDER if not self.is_hovered else COLOR_MUTED)
        pygame.draw.rect(surface, color, self.rect, width=2, border_radius=4)
        
        if self.is_checked:
            # Draw glowing dot inside
            pygame.draw.circle(surface, COLOR_PINK, self.rect.center, self.rect.width // 2 - 3)
            
        lbl = fm.render(self.label, 'small', COLOR_TEXT)
        surface.blit(lbl, (self.rect.x + self.rect.width + 8, self.rect.y + (self.rect.height - lbl.get_height()) // 2))

class Dropdown:
    def __init__(self, x, y, w, h, options, current_option, label, callback=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.options = options
        self.current_option = current_option
        self.label = label
        self.callback = callback
        
        self.is_open = False
        self.hovered_idx = -1
        self.option_height = 28
        self.max_display_items = 10
        self.scroll_offset = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if event.button == 1:
                if self.rect.collidepoint(pos):
                    self.is_open = not self.is_open
                    if self.is_open:
                        self.scroll_offset = 0
                    return True
                elif self.is_open:
                    opts_rect = self.get_options_rect()
                    if opts_rect.collidepoint(pos):
                        relative_y = pos[1] - opts_rect.y
                        idx = (relative_y // self.option_height) + self.scroll_offset
                        if 0 <= idx < len(self.options):
                            self.select_option(self.options[idx])
                        self.is_open = False
                        return True
                    else:
                        self.is_open = False
                        return True
            elif event.button in (4, 5) and self.is_open:
                opts_rect = self.get_options_rect()
                if self.rect.collidepoint(pos) or opts_rect.collidepoint(pos):
                    if event.button == 4:  # Scroll Up
                        self.scroll_offset = max(0, self.scroll_offset - 1)
                    elif event.button == 5:  # Scroll Down
                        self.scroll_offset = min(len(self.options) - self.max_display_items, self.scroll_offset + 1)
                        self.scroll_offset = max(0, self.scroll_offset)
                    return True
                    
        elif event.type == pygame.MOUSEWHEEL and self.is_open:
            if event.y > 0:  # Scroll Up (event.y is positive)
                self.scroll_offset = max(0, self.scroll_offset - 1)
            elif event.y < 0:  # Scroll Down (event.y is negative)
                self.scroll_offset = min(len(self.options) - self.max_display_items, self.scroll_offset + 1)
                self.scroll_offset = max(0, self.scroll_offset)
            return True
                    
        elif event.type == pygame.MOUSEMOTION and self.is_open:
            pos = event.pos
            opts_rect = self.get_options_rect()
            if opts_rect.collidepoint(pos):
                relative_y = pos[1] - opts_rect.y
                self.hovered_idx = (relative_y // self.option_height) + self.scroll_offset
            else:
                self.hovered_idx = -1
                
        return False

    def select_option(self, option):
        self.current_option = option
        if self.callback:
            self.callback(option)

    def get_options_rect(self):
        h = min(len(self.options), self.max_display_items) * self.option_height
        return pygame.Rect(self.rect.x, self.rect.y + self.rect.height, self.rect.width, h)

    def draw(self, surface, fm):
        if self.label:
            lbl_surf = fm.render(self.label, 'small', COLOR_MUTED)
            surface.blit(lbl_surf, (self.rect.x, self.rect.y - 18))
            
        pygame.draw.rect(surface, COLOR_PANEL, self.rect, border_radius=4)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, width=1, border_radius=4)
        
        display_text = str(self.current_option)
        if len(display_text) > 24:
            display_text = display_text[:21] + "..."
            
        text_surf = fm.render(display_text, 'small', COLOR_TEXT)
        surface.blit(text_surf, (self.rect.x + 8, self.rect.y + (self.rect.height - text_surf.get_height()) // 2))
        
        arrow_color = COLOR_PRIMARY if self.is_open else COLOR_MUTED
        arrow_y = self.rect.y + self.rect.height // 2
        arrow_x = self.rect.x + self.rect.width - 12
        if self.is_open:
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x - 4, arrow_y + 2),
                (arrow_x + 4, arrow_y + 2),
                (arrow_x, arrow_y - 2)
            ])
        else:
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x - 4, arrow_y - 2),
                (arrow_x + 4, arrow_y - 2),
                (arrow_x, arrow_y + 2)
            ])

    def draw_options(self, surface, fm):
        if not self.is_open or not self.options:
            return
            
        opts_rect = self.get_options_rect()
        
        shadow_rect = opts_rect.inflate(4, 4)
        pygame.draw.rect(surface, (10, 10, 15), shadow_rect, border_radius=4)
        
        pygame.draw.rect(surface, COLOR_BG, opts_rect, border_radius=4)
        pygame.draw.rect(surface, COLOR_BORDER, opts_rect, width=1, border_radius=4)
        
        visible_options = self.options[self.scroll_offset : self.scroll_offset + self.max_display_items]
        for i, option in enumerate(visible_options):
            opt_rect = pygame.Rect(
                opts_rect.x,
                opts_rect.y + i * self.option_height,
                opts_rect.width,
                self.option_height
            )
            
            actual_idx = i + self.scroll_offset
            if actual_idx == self.hovered_idx:
                pygame.draw.rect(surface, COLOR_PANEL, opt_rect)
                
            text_color = COLOR_PRIMARY if option == self.current_option else COLOR_TEXT
            
            opt_text = str(option)
            if len(opt_text) > 24:
                opt_text = opt_text[:21] + "..."
                
            opt_surf = fm.render(opt_text, 'small', text_color)
            surface.blit(opt_surf, (opt_rect.x + 8, opt_rect.y + (self.option_height - opt_surf.get_height()) // 2))
            
            if i < len(visible_options) - 1:
                pygame.draw.line(surface, COLOR_BORDER, 
                                 (opt_rect.x, opt_rect.y + self.option_height - 1),
                                 (opt_rect.x + opt_rect.width, opt_rect.y + self.option_height - 1))


class PianoKeySelector:
    """One-octave clickable piano keyboard + octave stepper for choosing a MIDI note.

    Replaces the single 'Note Pitch' slider. The 12 keys pick the pitch class; the
    stepper moves the octave. Octave range is configurable (default C0-B8 = MIDI 12-119).
    """

    WHITE = [0, 2, 4, 5, 7, 9, 11]                      # C D E F G A B (semitone offsets)
    BLACK = [(1, 0), (3, 1), (6, 3), (8, 4), (10, 5)]   # (semitone, white-slot it follows)

    def __init__(self, x, y, w, label, callback=None, min_octave=0, max_octave=8):
        self.rect = pygame.Rect(x, y, w, 88)
        self.label = label
        self.callback = callback
        self.min_octave = min_octave
        self.max_octave = max_octave
        self.current_val = 60
        self.is_hovered = False
        self.hover_semitone = None
        self.hover_step = None      # 'minus' / 'plus' / None

        # Vertical metrics (relative to rect.y)
        self.step_h = 22
        self.key_top = 26
        self.white_h = 58
        self.black_h = 38

    # --- value helpers -------------------------------------------------
    @property
    def octave(self):
        return (self.current_val // 12) - 1

    @property
    def semitone(self):
        return self.current_val % 12

    def _min_midi(self):
        return 12 * (self.min_octave + 1)

    def _max_midi(self):
        return 12 * (self.max_octave + 1) + 11

    def set_value(self, midi):
        midi = max(self._min_midi(), min(self._max_midi(), int(round(midi))))
        self.current_val = midi
        if self.callback:
            self.callback(self.current_val)

    def _set_octave(self, octv):
        octv = max(self.min_octave, min(self.max_octave, octv))
        self.set_value(12 * (octv + 1) + self.semitone)

    def _set_semitone(self, semi):
        self.set_value(12 * (self.octave + 1) + semi)

    # --- geometry ------------------------------------------------------
    def _white_w(self):
        return self.rect.width / 7.0

    def _step_rects(self):
        x, y = self.rect.x, self.rect.y
        minus = pygame.Rect(x, y, 24, self.step_h)
        plus = pygame.Rect(x + 28, y, 24, self.step_h)
        return minus, plus

    def _white_rects(self):
        x, y = self.rect.x, self.rect.y + self.key_top
        ww = self._white_w()
        rects = []
        for slot, semi in enumerate(self.WHITE):
            left = x + round(slot * ww)
            right = x + round((slot + 1) * ww)
            rects.append((semi, pygame.Rect(left, y, right - left - 1, self.white_h)))
        return rects

    def _black_rects(self):
        x, y = self.rect.x, self.rect.y + self.key_top
        ww = self._white_w()
        bw = ww * 0.62
        rects = []
        for semi, slot in self.BLACK:
            cx = x + (slot + 1) * ww
            rects.append((semi, pygame.Rect(round(cx - bw / 2), y, round(bw), self.black_h)))
        return rects

    # --- interaction ---------------------------------------------------
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        self.hover_step = None
        self.hover_semitone = None

        minus, plus = self._step_rects()
        if minus.collidepoint(pos):
            self.hover_step = 'minus'
            return
        if plus.collidepoint(pos):
            self.hover_step = 'plus'
            return
        # Black keys sit on top of the white keys, so test them first
        for semi, r in self._black_rects():
            if r.collidepoint(pos):
                self.hover_semitone = semi
                return
        for semi, r in self._white_rects():
            if r.collidepoint(pos):
                self.hover_semitone = semi
                return

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            minus, plus = self._step_rects()
            if minus.collidepoint(pos):
                self._set_octave(self.octave - 1)
                return True
            if plus.collidepoint(pos):
                self._set_octave(self.octave + 1)
                return True
            for semi, r in self._black_rects():     # black keys on top
                if r.collidepoint(pos):
                    self._set_semitone(semi)
                    return True
            for semi, r in self._white_rects():
                if r.collidepoint(pos):
                    self._set_semitone(semi)
                    return True
        return False

    # --- drawing -------------------------------------------------------
    def draw(self, surface, fm):
        # Section label + current note readout (mirrors the old slider header)
        lbl = fm.render(self.label, 'small', COLOR_MUTED)
        surface.blit(lbl, (self.rect.x, self.rect.y - 18))
        name = fm.render(f"{midi_to_name(self.current_val)} ({self.current_val})", 'small', COLOR_TEXT)
        surface.blit(name, (self.rect.x + self.rect.width - name.get_width(), self.rect.y - 18))

        # Octave stepper buttons (triangles, matching the dropdown arrow style)
        minus, plus = self._step_rects()
        for r, kind in ((minus, 'minus'), (plus, 'plus')):
            hot = self.hover_step == kind
            pygame.draw.rect(surface, COLOR_BORDER if hot else COLOR_PANEL, r, border_radius=4)
            pygame.draw.rect(surface, COLOR_BORDER, r, width=1, border_radius=4)
            cy = r.centery
            if kind == 'minus':
                pts = [(r.right - 8, cy - 5), (r.right - 8, cy + 5), (r.x + 7, cy)]
            else:
                pts = [(r.x + 8, cy - 5), (r.x + 8, cy + 5), (r.right - 7, cy)]
            pygame.draw.polygon(surface, COLOR_PRIMARY, pts)

        oct_txt = fm.render(f"Octave {self.octave}", 'small', COLOR_TEXT)
        surface.blit(oct_txt, (plus.right + 10, minus.y + (self.step_h - oct_txt.get_height()) // 2))

        # White keys first
        for semi, r in self._white_rects():
            if semi == self.semitone:
                fill = COLOR_PINK
            elif semi == self.hover_semitone:
                fill = (226, 228, 236)
            else:
                fill = (198, 200, 210)
            pygame.draw.rect(surface, fill, r, border_radius=3)
            pygame.draw.rect(surface, COLOR_BORDER, r, width=1, border_radius=3)
            klbl = fm.render(NOTE_NAMES[semi], 'tiny', (35, 36, 46))
            surface.blit(klbl, (r.centerx - klbl.get_width() // 2, r.bottom - klbl.get_height() - 5))

        # Black keys on top
        for semi, r in self._black_rects():
            if semi == self.semitone:
                fill, txt_col = COLOR_PINK, (20, 20, 28)
            elif semi == self.hover_semitone:
                fill, txt_col = (70, 74, 94), COLOR_TEXT
            else:
                fill, txt_col = (22, 24, 34), COLOR_MUTED
            pygame.draw.rect(surface, fill, r, border_radius=2)
            pygame.draw.rect(surface, (8, 9, 13), r, width=1, border_radius=2)
            klbl = fm.render(NOTE_NAMES[semi], 'tiny', txt_col)
            surface.blit(klbl, (r.centerx - klbl.get_width() // 2, r.bottom - klbl.get_height() - 3))


class NoteSidebar:
    def __init__(self, screen_w, screen_h, on_delete_callback):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.width = 280
        
        self.x = screen_w
        self.target_x = screen_w
        self.slide_speed = 30
        
        self.selected_note = None
        self.on_delete = on_delete_callback
        
        # 1. Pitch Section
        self.pitch_slider = Slider(20, 0, 240, 20, 24, 108, 60, "Note Pitch", integer_only=True, callback=self.update_note_pitch)
        self.pitch_keyboard = PianoKeySelector(20, 0, 240, "Note Pitch", callback=self.update_note_pitch, min_octave=0, max_octave=8)
        self.pitch_ranges_checkbox = Checkbox(160, 0, 16, "Ranges", callback=self.toggle_pitch_range)
        self.pitch_min_slider = Slider(20, 0, 240, 20, 12, 119, 48, "Pitch Min", integer_only=True, callback=self.update_pitch_min)
        self.pitch_max_slider = Slider(20, 0, 240, 20, 12, 119, 72, "Pitch Max", integer_only=True, callback=self.update_pitch_max)
        self.key_dropdown = Dropdown(20, 0, 240, 28, NOTE_NAMES, "C", "Key Selection", callback=self.update_pitch_key)
        self.scale_dropdown = Dropdown(20, 0, 240, 28, [
            "Chromatic", "Major", "Minor", "Pentatonic Major", "Pentatonic Minor", "Blues", 
            "Dorian", "Phrygian", "Lydian", "Mixolydian", "Locrian", "Harmonic Minor", "Melodic Minor", "Whole Tone",
            "Hijaz / Phrygian Dom", "Hungarian Minor", "Japanese In Sen", "Raga Bhairav", "Spanish Gypsy", 
            "Acoustic / Lydian Dom", "Major Locrian", "Enigmatic"
        ], "Chromatic", "Scale Selection", callback=self.update_pitch_scale)
        
        # 2. Velocity Section
        self.velocity_slider = Slider(20, 0, 240, 20, 0, 127, 100, "Velocity", integer_only=True, callback=self.update_note_velocity)
        self.vel_ranges_checkbox = Checkbox(160, 0, 16, "Ranges", callback=self.toggle_vel_range)
        self.vel_min_slider = Slider(20, 0, 240, 20, 0, 127, 80, "Velocity Min", integer_only=True, callback=self.update_vel_min)
        self.vel_max_slider = Slider(20, 0, 240, 20, 0, 127, 120, "Velocity Max", integer_only=True, callback=self.update_vel_max)
        
        # 3. Gate Section
        self.gate_slider = Slider(20, 0, 240, 20, 0.05, 2.0, 0.5, "Gate Length", "beats", callback=self.update_note_gate)
        self.gate_ranges_checkbox = Checkbox(160, 0, 16, "Ranges", callback=self.toggle_gate_range)
        self.gate_min_slider = Slider(20, 0, 240, 20, 0.05, 2.0, 0.25, "Gate Min", "beats", callback=self.update_gate_min)
        self.gate_max_slider = Slider(20, 0, 240, 20, 0.05, 2.0, 0.75, "Gate Max", "beats", callback=self.update_gate_max)
        
        # 4. Channel & Orbit Section
        self.channel_slider = Slider(20, 0, 240, 20, 1, 16, 1, "MIDI Channel", integer_only=True, callback=self.update_note_channel)
        self.mode_btn = Button(20, 0, 240, 28, "Orbit Mode: BPM %", (39, 132, 174), (84, 147, 178), self.toggle_orbit_mode)
        self.speed_slider = Slider(20, 0, 240, 20, 10, 400, 100, "Orbit Speed", "%", integer_only=True, callback=self.update_note_speed)
        
        # 5. Delete Button
        self.delete_btn = Button(20, 0, 240, 34, "DELETE NOTE", (178, 60, 60), (178, 77, 77), self.trigger_delete)
        
    def toggle_pitch_range(self, checked):
        if self.selected_note:
            self.selected_note.use_pitch_range = checked
            
    def toggle_vel_range(self, checked):
        if self.selected_note:
            self.selected_note.use_vel_range = checked
            
    def toggle_gate_range(self, checked):
        if self.selected_note:
            self.selected_note.use_gate_range = checked
            
    def update_pitch_min(self, val):
        if self.selected_note:
            self.selected_note.pitch_min = int(val)
            if self.selected_note.pitch_min > self.selected_note.pitch_max:
                self.selected_note.pitch_max = self.selected_note.pitch_min
                self.pitch_max_slider.set_value(self.selected_note.pitch_min)
            
    def update_pitch_max(self, val):
        if self.selected_note:
            self.selected_note.pitch_max = int(val)
            if self.selected_note.pitch_max < self.selected_note.pitch_min:
                self.selected_note.pitch_min = self.selected_note.pitch_max
                self.pitch_min_slider.set_value(self.selected_note.pitch_max)
                
    def update_pitch_scale(self, scale_name):
        if self.selected_note:
            self.selected_note.pitch_scale = scale_name
            
    def update_pitch_key(self, key_name):
        if self.selected_note:
            self.selected_note.pitch_key = key_name
            
    def update_vel_min(self, val):
        if self.selected_note:
            self.selected_note.vel_min = int(val)
            if self.selected_note.vel_min > self.selected_note.vel_max:
                self.selected_note.vel_max = self.selected_note.vel_min
                self.vel_max_slider.set_value(self.selected_note.vel_min)
            
    def update_vel_max(self, val):
        if self.selected_note:
            self.selected_note.vel_max = int(val)
            if self.selected_note.vel_max < self.selected_note.vel_min:
                self.selected_note.vel_min = self.selected_note.vel_max
                self.vel_min_slider.set_value(self.selected_note.vel_max)
                
    def update_gate_min(self, val):
        if self.selected_note:
            self.selected_note.gate_min = float(val)
            if self.selected_note.gate_min > self.selected_note.gate_max:
                self.selected_note.gate_max = self.selected_note.gate_min
                self.gate_max_slider.set_value(self.selected_note.gate_min)
            
    def update_gate_max(self, val):
        if self.selected_note:
            self.selected_note.gate_max = float(val)
            if self.selected_note.gate_max < self.selected_note.gate_min:
                self.selected_note.gate_min = self.selected_note.gate_max
                self.gate_min_slider.set_value(self.selected_note.gate_max)
 
    def set_note(self, note):
        self.selected_note = note
        if note:
            # Sync normal values
            self.pitch_slider.set_value(note.midi_note)
            self.pitch_keyboard.set_value(note.midi_note)
            self.velocity_slider.set_value(note.velocity)
            self.gate_slider.set_value(note.gate_length)
            self.channel_slider.set_value(note.midi_channel + 1)
            
            # Sync range values and checkboxes
            self.pitch_ranges_checkbox.is_checked = note.use_pitch_range
            self.pitch_min_slider.set_value(note.pitch_min)
            self.pitch_max_slider.set_value(note.pitch_max)
            self.key_dropdown.current_option = getattr(note, 'pitch_key', 'C')
            self.scale_dropdown.current_option = note.pitch_scale
            
            self.vel_ranges_checkbox.is_checked = note.use_vel_range
            self.vel_min_slider.set_value(note.vel_min)
            self.vel_max_slider.set_value(note.vel_max)
            
            self.gate_ranges_checkbox.is_checked = note.use_gate_range
            self.gate_min_slider.set_value(note.gate_min)
            self.gate_max_slider.set_value(note.gate_max)
            
            self.sync_orbit_widgets()
            self.target_x = self.screen_w - self.width
        else:
            self.target_x = self.screen_w
 
    def get_active_widgets(self):
        """Build the list of currently active widgets based on selection states."""
        note = self.selected_note
        if not note:
            return []
            
        widgets = []
        
        # 1. Pitch
        widgets.append(self.pitch_ranges_checkbox)
        if note.use_pitch_range:
            widgets.extend([self.pitch_min_slider, self.pitch_max_slider, self.key_dropdown, self.scale_dropdown])
        else:
            widgets.append(self.pitch_keyboard)
            
        # 2. Velocity
        widgets.append(self.vel_ranges_checkbox)
        if note.use_vel_range:
            widgets.extend([self.vel_min_slider, self.vel_max_slider])
        else:
            widgets.append(self.velocity_slider)
            
        # 3. Gate
        widgets.append(self.gate_ranges_checkbox)
        if note.use_gate_range:
            widgets.extend([self.gate_min_slider, self.gate_max_slider])
        else:
            widgets.append(self.gate_slider)
            
        # 4. Global configurations
        widgets.extend([self.channel_slider, self.mode_btn, self.speed_slider, self.delete_btn])
        return widgets
 
    def sync_orbit_widgets(self):
        note = self.selected_note
        if not note:
            return
            
        if note.orbit_mode == 0:
            self.mode_btn.text = "Orbit Mode: BPM %"
            self.speed_slider.label = "Orbit Speed"
            self.speed_slider.unit = "%"
            self.speed_slider.min_val = 10
            self.speed_slider.max_val = 400
            self.speed_slider.integer_only = True
            
            if note.orbit_speed <= 16:
                note.orbit_speed = int(100.0 / note.orbit_speed)
            self.speed_slider.set_value(note.orbit_speed)
        else:
            self.mode_btn.text = "Orbit Mode: Sync Divisor"
            self.speed_slider.label = "Orbit Sync Divisor"
            self.speed_slider.unit = ""
            self.speed_slider.min_val = 1
            self.speed_slider.max_val = 16
            self.speed_slider.integer_only = True
            
            if note.orbit_speed > 16:
                note.orbit_speed = max(1, min(16, int(round(100.0 / note.orbit_speed))))
            self.speed_slider.set_value(note.orbit_speed)
 
    def toggle_orbit_mode(self):
        if self.selected_note:
            self.selected_note.orbit_mode = 1 - self.selected_note.orbit_mode
            self.sync_orbit_widgets()
 
    def is_visible(self):
        return self.x < self.screen_w
 
    def trigger_delete(self):
        if self.selected_note and self.on_delete:
            self.on_delete(self.selected_note)
            self.set_note(None)
 
    def update_note_pitch(self, val):
        if self.selected_note:
            self.selected_note.midi_note = int(val)
 
    def update_note_velocity(self, val):
        if self.selected_note:
            self.selected_note.velocity = int(val)
 
    def update_note_gate(self, val):
        if self.selected_note:
            self.selected_note.gate_length = float(val)
 
    def update_note_channel(self, val):
        if self.selected_note:
            self.selected_note.midi_channel = int(val) - 1
 
    def update_note_speed(self, val):
        if self.selected_note:
            self.selected_note.orbit_speed = float(val)
 
    def handle_event(self, event):
        if not self.is_visible():
            return False
            
        if hasattr(event, 'pos'):
            pos = event.pos
            if event.type == pygame.MOUSEBUTTONDOWN:
                if pos[0] < self.x:
                    # Click outside the sidebar commits any open value editor
                    if Slider.active_editor is not None:
                        Slider.active_editor.commit_edit()
                    return False

            event_shifted = pygame.event.Event(event.type, {**event.dict, 'pos': (pos[0] - self.x, pos[1])})
        else:
            event_shifted = event
            
        widget_handled = False
        active_widgets = self.get_active_widgets()
        
        # 1. Check if any active dropdown is currently open and process it first (capturing overlaps)
        open_dropdown = None
        for widget in active_widgets:
            if isinstance(widget, Dropdown) and widget.is_open:
                open_dropdown = widget
                break
                
        if open_dropdown:
            if open_dropdown.handle_event(event_shifted):
                # Close all other active dropdowns to be clean
                for widget in active_widgets:
                    if isinstance(widget, Dropdown) and widget != open_dropdown:
                        widget.is_open = False
                return True

        # 1b. A slider in manual text-entry mode gets first crack at the event
        # (so typed keys / commit-clicks reach it before anything else).
        editor = None
        for widget in active_widgets:
            if isinstance(widget, Slider) and widget.is_editing:
                editor = widget
                break
        if editor is not None and editor.handle_event(event_shifted):
            return True

        # 2. Dispatch event to all other active widgets (including closed dropdowns!)
        for widget in active_widgets:
            if widget != open_dropdown and widget is not editor:
                if hasattr(widget, 'check_hover'):
                    m_pos = pygame.mouse.get_pos()
                    widget.check_hover((m_pos[0] - self.x, m_pos[1]))
                    
                if widget.handle_event(event_shifted):
                    # If clicking a dropdown opened it, close all other dropdowns to avoid overlap
                    if isinstance(widget, Dropdown) and widget.is_open:
                        for other in active_widgets:
                            if isinstance(other, Dropdown) and other != widget:
                                other.is_open = False
                    widget_handled = True
                    break
                    
        return widget_handled
 
    def update(self):
        if self.x < self.target_x:
            self.x = min(self.target_x, self.x + self.slide_speed)
        elif self.x > self.target_x:
            self.x = max(self.target_x, self.x - self.slide_speed)
 
    def draw(self, surface, fm):
        if self.x >= self.screen_w:
            return
            
        note = self.selected_note
        if not note:
            return
            
        # Dynamic layout coordinates calculation
        y = 90  # Start below the header
        
        # A. Pitch Section
        self.pitch_ranges_checkbox.rect.y = y
        y += 24
        if note.use_pitch_range:
            self.pitch_min_slider.rect.y = y + 15
            self.pitch_max_slider.rect.y = y + 50
            self.key_dropdown.rect.y = y + 85
            self.scale_dropdown.rect.y = y + 130
            y += 165
        else:
            self.pitch_keyboard.rect.y = y + 28
            y += 120

        # B. Velocity Section
        y += 10
        self.vel_ranges_checkbox.rect.y = y
        y += 24
        if note.use_vel_range:
            self.vel_min_slider.rect.y = y + 15
            self.vel_max_slider.rect.y = y + 50
            y += 75
        else:
            self.velocity_slider.rect.y = y + 15
            y += 45
            
        # C. Gate Section
        y += 10
        self.gate_ranges_checkbox.rect.y = y
        y += 24
        if note.use_gate_range:
            self.gate_min_slider.rect.y = y + 15
            self.gate_max_slider.rect.y = y + 50
            y += 75
        else:
            self.gate_slider.rect.y = y + 15
            y += 45
            
        # D. Channel & Orbit Section
        y += 10
        self.channel_slider.rect.y = y + 15
        y += 45
        
        self.mode_btn.rect.y = y + 10
        self.speed_slider.rect.y = y + 65
        y += 95
        
        # E. Delete Button
        y += 10
        self.delete_btn.rect.y = y
        
        # Update handle_x coordinates for all active sliders
        active_widgets = self.get_active_widgets()
        for widget in active_widgets:
            if hasattr(widget, 'update_handle_x'):
                widget.update_handle_x()
                
        # Draw sidebar panel
        sidebar_surf = pygame.Surface((self.width, self.screen_h), pygame.SRCALPHA)
        pygame.draw.rect(sidebar_surf, (*COLOR_PANEL, 235), (0, 0, self.width, self.screen_h))
        pygame.draw.line(sidebar_surf, COLOR_BORDER, (0, 0), (0, self.screen_h), width=2)
        
        hdr_surf = fm.render("NOTE EDITOR", 'large', COLOR_PRIMARY)
        sidebar_surf.blit(hdr_surf, (20, 30))
        
        sub_surf = fm.render(f"Note Name: {note.name}", 'small', COLOR_TEXT)
        sidebar_surf.blit(sub_surf, (20, 58))
        
        # Draw active widgets EXCEPT dropdowns
        for widget in active_widgets:
            if not isinstance(widget, Dropdown):
                widget.draw(sidebar_surf, fm)
                
        # Draw dropdowns on top of everything inside the sidebar with proper Z-ordering:
        # closed dropdowns first, and the open dropdown last!
        dropdowns = [self.key_dropdown, self.scale_dropdown]
        for dd in dropdowns:
            if dd in active_widgets and not dd.is_open:
                dd.draw(sidebar_surf, fm)
                
        for dd in dropdowns:
            if dd in active_widgets and dd.is_open:
                dd.draw(sidebar_surf, fm)
                dd.draw_options(sidebar_surf, fm)
            
        surface.blit(sidebar_surf, (self.x, 0))


# Non-deformable clean curved/straight line math
def get_curved_line_points(center, r, base_angle, bend_amount):
    """Calculates coordinates for drawing a curved line from center to outer radius."""
    x_c, y_c = center
    points = []
    steps = 40
    
    for i in range(steps + 1):
        curr_r = i * (r / steps)
        curr_ratio = curr_r / r
        ang = base_angle + bend_amount * (curr_ratio ** 2)
        
        p_dx = curr_r * math.sin(ang)
        p_dy = -curr_r * math.cos(ang)
        points.append((x_c + p_dx, y_c + p_dy))
        
    return points


# Spectrum colour stops spanning the selectable pitch range (C0..B8 = MIDI 12..119):
# deep purple (lowest) -> blue -> green (middle) -> yellow -> orange -> fuchsia (highest)
PITCH_SPECTRUM = [
    (0.00, (96, 40, 170)),    # deep purple
    (0.20, (45, 95, 230)),    # blue
    (0.45, (60, 220, 130)),   # green
    (0.65, (240, 225, 70)),   # yellow
    (0.82, (255, 150, 45)),   # orange
    (1.00, (255, 60, 200)),   # fuchsia
]

def pitch_to_color(midi_note, lo=12, hi=119):
    """Map a MIDI pitch to a colour along the PITCH_SPECTRUM gradient."""
    t = (midi_note - lo) / float(hi - lo) if hi != lo else 0.0
    t = max(0.0, min(1.0, t))
    for i in range(len(PITCH_SPECTRUM) - 1):
        t0, c0 = PITCH_SPECTRUM[i]
        t1, c1 = PITCH_SPECTRUM[i + 1]
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
    return PITCH_SPECTRUM[-1][1]


def _note_spectrum_color(note):
    """The spectrum colour for a note (range mode uses the pitch-window midpoint)."""
    base_pitch = note.midi_note
    if getattr(note, 'use_pitch_range', False):
        base_pitch = (note.pitch_min + note.pitch_max) // 2
    return pitch_to_color(base_pitch)


def draw_clock_board(surface, center, r, angle, handles_list, notes, selected_note, fm):
    """Draws the concentric orbit paths, Bezier control polygon, smooth Cubic Bezier curve, and orbiting notes."""
    x_c, y_c = center
    
    # 1. Thin concentric ORBITAL PATHS — tinted to each note's pitch colour,
    #    low opacity (~22%) so they read but don't compete with the notes themselves.
    for note in notes:
        visual_r = note.norm_r * r
        nc = _note_spectrum_color(note)
        ring_color = tuple(int(COLOR_BG[c] + (nc[c] - COLOR_BG[c]) * 0.22) for c in range(3))
        pygame.draw.circle(surface, ring_color, center, int(visual_r), width=1)

    # 2. Glowing outer clock ring
    glow_surf = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
    for w in range(12, 0, -1):
        alpha = int(35 / w)
        pygame.draw.circle(glow_surf, (*COLOR_RING, alpha), (r + 10, r + 10), r + (w // 2), width=2)
    pygame.draw.circle(glow_surf, COLOR_RING, (r + 10, r + 10), r, width=3)
    surface.blit(glow_surf, (x_c - r - 10, y_c - r - 10))
    
    # 3. Calculate rotated Bezier control handles (H0, P1, P2, P3) based on spinning sweep angle
    p0 = (0.0, 0.0)
    h1, h2, h3 = handles_list
    
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    p1 = (h1[0] * cos_a - h1[1] * sin_a, h1[0] * sin_a + h1[1] * cos_a)
    p2 = (h2[0] * cos_a - h2[1] * sin_a, h2[0] * sin_a + h2[1] * cos_a)
    p3 = (h3[0] * cos_a - h3[1] * sin_a, h3[0] * sin_a + h3[1] * cos_a)
        
    # Map coordinates to absolute screen positions
    ap0 = center
    ap1 = (x_c + p1[0], y_c + p1[1])
    ap2 = (x_c + p2[0], y_c + p2[1])
    ap3 = (x_c + p3[0], y_c + p3[1])
    
    # 4. Faint control polygon lines
    pygame.draw.line(surface, (26, 28, 38), ap0, ap1, width=1)
    pygame.draw.line(surface, (26, 28, 38), ap1, ap2, width=1)
    pygame.draw.line(surface, (26, 28, 38), ap2, ap3, width=1)
    
    # 5. Draw smooth Bezier spline line sweep arm
    bezier_points = []
    steps = 100
    for i in range(steps + 1):
        t = i / steps
        bx = (3 * (1-t)**2 * t * p1[0] + 3 * (1-t) * t**2 * p2[0] + t**3 * p3[0])
        by = (3 * (1-t)**2 * t * p1[1] + 3 * (1-t) * t**2 * p2[1] + t**3 * p3[1])
        bezier_points.append((x_c + bx, y_c + by))
        
    if len(bezier_points) >= 2:
        # Sweep arm: single electric-blue line at 50% opacity, half the old thickness.
        # Drawn on an alpha layer so the 50% opacity blends over whatever is beneath.
        line_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.lines(line_surf, (*COLOR_RING, 128), False, bezier_points, width=3)
        surface.blit(line_surf, (0, 0))
        
    # 6. Interactive handles (glowing anchor dots) for control points
    for p_i in [ap1, ap2, ap3]:
        # Glowing blue halo with a white core
        pygame.draw.circle(surface, COLOR_RING, p_i, 8, width=2)
        pygame.draw.circle(surface, COLOR_WHITE, p_i, 4)

    # 7. Orbiting Planet Notes Rendering with multi-layered high-voltage Kirlian auric coronas!
    for note in notes:
        visual_r = note.norm_r * r
        nx = x_c + visual_r * math.sin(note.polar_angle)
        ny = y_c - visual_r * math.cos(note.polar_angle)
        
        note_color = _note_spectrum_color(note)

        # Trigger scaling animation: rest at half size, pop to full size on a hit,
        # then ease back down as the flash decays (smoothstep for a soft settle).
        full_r = note.radius
        base_r = full_r * 0.5
        f = note.flash_intensity
        eased = f * f * (3.0 - 2.0 * f)            # smoothstep over the flash decay
        radius = max(1, int(round(base_r + (full_r - base_r) * eased)))

        # KIRLIAN AESTHETIC: Multi-layered electric coronal discharge rings!
        # Concentric layers with varying opacity of the note's spectrum colour.
        glow_base = note_color
        for layer in range(5, 0, -1):
            # Scale out the glowing radius, making it expand even more during a trigger flash!
            layer_r = radius + (layer * 3) + int(note.flash_intensity * 8)
            alpha = int((20 + note.flash_intensity * 60) / layer)
            
            # Surface with alpha transparency
            layer_surf = pygame.Surface((layer_r * 2 + 10, layer_r * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(layer_surf, (*glow_base, alpha), (layer_r + 5, layer_r + 5), layer_r, width=1)
            surface.blit(layer_surf, (nx - layer_r - 5, ny - layer_r - 5))
            
        # Blended fill transitions (notes brighten toward their colour when hit)
        fill_color = tuple(
            int(COLOR_BG[c] + (note_color[c] - COLOR_BG[c]) * note.flash_intensity * 0.38)
            for c in range(3)
        )

        border_color = note_color
        # Lighten the label slightly so low (purple/blue) notes stay legible
        text_color = tuple(min(255, int(note_color[c] + (255 - note_color[c]) * 0.25)) for c in range(3))

        if note.flash_intensity > 0:
            border_color = tuple(min(255, int(border_color[c] + (255 - border_color[c]) * note.flash_intensity * 0.5)) for c in range(3))
            text_color = COLOR_WHITE
            
        if note == selected_note:
            pygame.draw.circle(surface, COLOR_PINK, (nx, ny), radius + 4, width=2)
            
        pygame.draw.circle(surface, fill_color, (nx, ny), radius)
        pygame.draw.circle(surface, border_color, (nx, ny), radius, width=2)
        
        name_surf = fm.render(note.name, 'tiny', text_color)
        surface.blit(name_surf, (nx - name_surf.get_width() // 2, ny - name_surf.get_height() // 2))
