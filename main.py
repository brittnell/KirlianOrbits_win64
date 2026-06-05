import pygame
import sys
import os
import math
import time

# Adjust import paths if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from midi_manager import MidiManager
from sequencer import Sequencer
from ui import (
    FontManager, Button, Slider, Dropdown, NoteSidebar, draw_clock_board,
    COLOR_BG, COLOR_PRIMARY, COLOR_PINK, COLOR_TEXT, COLOR_MUTED, COLOR_EMERALD, COLOR_RED, COLOR_WHITE
)

# Initial screen dimensions
WIDTH = 800
HEIGHT = 600

def resolve_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def main():
    global WIDTH, HEIGHT
    # Initialize Pygame
    pygame.init()
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    # Set brand new title caption!
    pygame.display.set_caption("Kirlian Orbits — Coronal MIDI Synchronizer")
    
    # Set custom window icon
    icon_path = resolve_path("icon.png")
    if os.path.exists(icon_path):
        try:
            icon_surf = pygame.image.load(icon_path)
            pygame.display.set_icon(icon_surf)
        except Exception:
            pass
    
    clock = pygame.time.Clock()
    
    # Initialize Core Engines
    fm = FontManager()
    midi_manager = MidiManager()
    sequencer = Sequencer()
    
    # State tracking
    selected_note = None
    dragged_note = None
    dragged_handle_idx = None
    is_fullscreen = False
    show_debug = False
    
    # Dynamic Callback for sidebar deletion
    def delete_active_note(note):
        nonlocal selected_note
        sequencer.remove_note(note)
        selected_note = None
        
    sidebar = NoteSidebar(WIDTH, HEIGHT, delete_active_note)
    
    # Define control bar callback actions
    def toggle_play():
        if sequencer.is_playing:
            sequencer.stop()
            midi_manager.panic()
            play_btn.text = "PLAY"
            play_btn.color = (50, 200, 100)
            play_btn.hover_color = (100, 230, 150)
        else:
            sequencer.start()
            play_btn.text = "PAUSE"
            play_btn.color = (255, 140, 0)
            play_btn.hover_color = (255, 180, 50)
            
    def clear_sequencer():
        nonlocal selected_note
        sequencer.clear_all()
        selected_note = None
        sidebar.set_note(None)
        midi_manager.panic()
        
    def change_bpm(val):
        sequencer.set_bpm(int(val))
        
    def toggle_line_spin():
        sequencer.is_line_spinning = not sequencer.is_line_spinning
        if sequencer.is_line_spinning:
            spin_btn.text = "SPIN: ON"
            spin_btn.color = COLOR_PRIMARY
            spin_btn.hover_color = (200, 170, 255)
        else:
            spin_btn.text = "SPIN: OFF"
            spin_btn.color = COLOR_MUTED
            spin_btn.hover_color = (160, 170, 180)
            sequencer.sweep_angle = 0.0
            
    def toggle_spin_direction():
        sequencer.line_spin_direction = -1 if sequencer.line_spin_direction == 1 else 1
        if sequencer.line_spin_direction == 1:
            dir_btn.text = "DIR: CW"
            dir_btn.color = COLOR_MUTED
            dir_btn.hover_color = (160, 170, 180)
        else:
            dir_btn.text = "DIR: CCW"
            dir_btn.color = COLOR_PINK
            dir_btn.hover_color = (255, 180, 220)
            
    def save_session_dialog():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Session files", "*.json"), ("All files", "*.*")],
            title="Save Kirlian Orbits Session"
        )
        root.destroy()
        if file_path:
            try:
                sequencer.save_to_json(file_path)
                midi_manager.status_message = "Session Saved Successfully"
            except Exception as e:
                midi_manager.status_message = f"Save Error: {str(e)[:25]}"
                
    def load_session_dialog():
        nonlocal selected_note
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON Session files", "*.json"), ("All files", "*.*")],
            title="Load Kirlian Orbits Session"
        )
        root.destroy()
        if file_path:
            try:
                selected_note = None
                sidebar.set_note(None)
                sequencer.load_from_json(file_path)
                bpm_slider.set_value(sequencer.bpm)
                if sequencer.line_spin_direction == 1:
                    dir_btn.text = "DIR: CW"
                    dir_btn.color = COLOR_MUTED
                else:
                    dir_btn.text = "DIR: CCW"
                    dir_btn.color = COLOR_PINK
                midi_manager.status_message = "Session Loaded Successfully"
            except Exception as e:
                midi_manager.status_message = f"Load Error: {str(e)[:25]}"

    def reset_orbits_and_sweep():
        sequencer.reset_orbits()
        midi_manager.panic()
        midi_manager.status_message = "Orbits & Sweep Reset"
        
    def straighten_spline_handles():
        sequencer.straighten_spline()
        midi_manager.status_message = "Spline Straightened"

    def select_midi_port(port_name):
        midi_manager.open_port(port_name)
        
    # Build Top Control Bar widgets
    midi_ports = midi_manager.available_ports if midi_manager.available_ports else ["No MIDI Ports"]
    default_port = midi_manager.port_name if midi_manager.port_name else (midi_ports[0] if midi_ports else "No MIDI Ports")
    
    # Sleek layout adjustment: moved dropdown and inserted SAVE/LOAD buttons next to it
    midi_dropdown = Dropdown(320, 15, 180, 28, midi_ports, default_port, "MIDI Output Route", callback=select_midi_port)
    save_btn = Button(195, 15, 55, 28, "SAVE", COLOR_MUTED, (70, 75, 100), save_session_dialog)
    load_btn = Button(255, 15, 55, 28, "LOAD", COLOR_MUTED, (70, 75, 100), load_session_dialog)
    
    play_btn = Button(20, 60, 55, 28, "PAUSE" if sequencer.is_playing else "PLAY", 
                      (50, 200, 100) if not sequencer.is_playing else (255, 140, 0),
                      (100, 230, 150) if not sequencer.is_playing else (255, 180, 50),
                      toggle_play)
                      
    clear_btn = Button(80, 60, 55, 28, "CLEAR", (150, 50, 50), (200, 80, 80), clear_sequencer)
    
    reset_btn = Button(140, 60, 55, 28, "RESET", COLOR_MUTED, (160, 170, 180), reset_orbits_and_sweep)
    
    bpm_slider = Slider(205, 65, 75, 18, 1, 1000, sequencer.bpm, "BPM", integer_only=True, callback=change_bpm)
    
    spin_btn = Button(290, 60, 65, 28, "SPIN: OFF", COLOR_MUTED, (160, 170, 180), toggle_line_spin)
    
    dir_btn = Button(360, 60, 55, 28, "DIR: CW", COLOR_MUTED, (160, 170, 180), toggle_spin_direction)
    
    straight_btn = Button(420, 60, 55, 28, "STRT", COLOR_MUTED, (160, 170, 180), straighten_spline_handles)
    
    top_bar_widgets = [play_btn, clear_btn, reset_btn, bpm_slider, spin_btn, dir_btn, straight_btn, save_btn, load_btn, midi_dropdown]
    
    # Primary application loop
    running = True
    while running:
        # Dynamic layout calculations
        clock_area_w = WIDTH - 280
        CLOCK_CENTER = (clock_area_w // 2, HEIGHT // 2 + 35)
        
        CLOCK_RADIUS = min(clock_area_w // 2 - 40, (HEIGHT - 115) // 2 - 25)
        CLOCK_RADIUS = max(100, CLOCK_RADIUS)
        
        sequencer.clock_radius = CLOCK_RADIUS
        
        # 1. Handle user inputs and events
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                break
                
            elif event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                
                sidebar.screen_w = WIDTH
                sidebar.screen_h = HEIGHT
                sidebar.set_note(selected_note)
                continue
                
            # A. Check dropdown open logic FIRST to capture clicks on its expanded options overlay
            if midi_dropdown.handle_event(event):
                continue
                
            # B. If sidebar is open and clicked, let it consume events
            if sidebar.is_visible():
                if sidebar.handle_event(event):
                    continue
                    
            # C. Process top bar controls (BPM slider, buttons, Line Spin toggle)
            top_bar_handled = False
            for widget in top_bar_widgets:
                if widget != midi_dropdown:
                    if widget.handle_event(event):
                        top_bar_handled = True
                        break
            if top_bar_handled:
                continue
                
            # D. Spline handles & Sequencer clicking, dragging and double-click logic
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                
                # Check if click is inside the left sequencer panel (4th attempt ugh)
                if mouse_pos[0] < clock_area_w and mouse_pos[1] > 110:
                    # I. Check if clicked a Spline Control Point Handle first
                    clicked_handle = None
                    
                    h1, h2, h3 = sequencer.handles
                    if sequencer.is_line_spinning:
                        ang = sequencer.sweep_angle
                        cos_a = math.cos(ang)
                        sin_a = math.sin(ang)
                        p1 = (h1[0] * cos_a - h1[1] * sin_a, h1[0] * sin_a + h1[1] * cos_a)
                        p2 = (h2[0] * cos_a - h2[1] * sin_a, h2[0] * sin_a + h2[1] * cos_a)
                        p3 = (h3[0] * cos_a - h3[1] * sin_a, h3[0] * sin_a + h3[1] * cos_a)
                    else:
                        p1, p2, p3 = h1, h2, h3
                        
                    ap1 = (CLOCK_CENTER[0] + p1[0], CLOCK_CENTER[1] + p1[1])
                    ap2 = (CLOCK_CENTER[0] + p2[0], CLOCK_CENTER[1] + p2[1])
                    ap3 = (CLOCK_CENTER[0] + p3[0], CLOCK_CENTER[1] + p3[1])
                    
                    handles_ap = [ap1, ap2, ap3]
                    for idx, ap in enumerate(handles_ap):
                        dist = math.sqrt((mouse_pos[0] - ap[0])**2 + (mouse_pos[1] - ap[1])**2)
                        if dist <= 12:
                            clicked_handle = idx
                            break
                            
                    if clicked_handle is not None:
                        dragged_handle_idx = clicked_handle
                        selected_note = None
                        sidebar.set_note(None)
                        continue
                        
                    # II. Check if clicked a note node
                    clicked_note = None
                    for note in sequencer.notes:
                        note.sync_cartesian(CLOCK_RADIUS)
                        nx = CLOCK_CENTER[0] + note.x
                        ny = CLOCK_CENTER[1] + note.y
                        dist = math.sqrt((mouse_pos[0] - nx)**2 + (mouse_pos[1] - ny)**2)
                        if dist <= note.radius + 4:
                            clicked_note = note
                            break
                            
                    if clicked_note:
                        selected_note = clicked_note
                        dragged_note = clicked_note
                        sidebar.set_note(clicked_note)
                    else:
                        if selected_note:
                            selected_note = None
                            sidebar.set_note(None)
                        else:
                            rx = mouse_pos[0] - CLOCK_CENTER[0]
                            ry = mouse_pos[1] - CLOCK_CENTER[1]
                            dist_to_center = math.sqrt(rx**2 + ry**2)
                            
                            if dist_to_center <= CLOCK_RADIUS + 20:
                                new_note = sequencer.add_note(rx, ry)
                                selected_note = new_note
                                sidebar.set_note(new_note)
                                
            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = event.pos
                
                # I. Handle Spline Handle Dragging with Spin-Correction
                if dragged_handle_idx is not None:
                    rx = mouse_pos[0] - CLOCK_CENTER[0]
                    ry = mouse_pos[1] - CLOCK_CENTER[1]
                    
                    dist = math.sqrt(rx**2 + ry**2)
                    if dist > CLOCK_RADIUS:
                        rx = (rx / dist) * CLOCK_RADIUS
                        ry = (ry / dist) * CLOCK_RADIUS
                        
                    if sequencer.is_line_spinning:
                        ang = -sequencer.sweep_angle
                        cos_a = math.cos(ang)
                        sin_a = math.sin(ang)
                        rx_base = rx * cos_a - ry * sin_a
                        ry_base = rx * sin_a + ry * cos_a
                    else:
                        rx_base = rx
                        ry_base = ry
                        
                    sequencer.handles[dragged_handle_idx] = [rx_base, ry_base]
                    
                # II. Handle Orbiting Note Dragging
                elif dragged_note:
                    rx = mouse_pos[0] - CLOCK_CENTER[0]
                    ry = mouse_pos[1] - CLOCK_CENTER[1]
                    
                    dist = math.sqrt(rx**2 + ry**2)
                    
                    dragged_note.norm_r = min(1.0, dist / CLOCK_RADIUS)
                    dragged_note.polar_angle = (math.atan2(ry, rx) + math.pi/2) % (2 * math.pi)
                    dragged_note.sync_cartesian(CLOCK_RADIUS)
                    
                    if dragged_note == selected_note:
                        sidebar.pitch_slider.set_value(dragged_note.midi_note)
                        sidebar.pitch_keyboard.set_value(dragged_note.midi_note)
                        
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragged_note = None
                dragged_handle_idx = None
                
            elif event.type == pygame.KEYDOWN:
                # Check for Ctrl + S or Ctrl + O 
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_CTRL):
                    if event.key == pygame.K_s:
                        save_session_dialog()
                        continue
                    elif event.key == pygame.K_o:
                        load_session_dialog()
                        continue
                        
                if event.key == pygame.K_SPACE:
                    toggle_play()
                elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                    if selected_note:
                        delete_active_note(selected_note)
                elif event.key == pygame.K_f or event.key == pygame.K_F11:
                    is_fullscreen = not is_fullscreen
                    if is_fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.RESIZABLE)
                    else:
                        screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
                        
                    WIDTH, HEIGHT = screen.get_size()
                    sidebar.screen_w = WIDTH
                    sidebar.screen_h = HEIGHT
                    sidebar.set_note(selected_note)
                elif event.key == pygame.K_d:
                    show_debug = not show_debug
                    
        # 2. Update states and clocks
        for note in sequencer.notes:
            note.sync_cartesian(CLOCK_RADIUS)
            
        sequencer.update(midi_manager)
        midi_manager.update()
        sidebar.update()
        
        # Update mouse hovers on top bar buttons
        m_pos = pygame.mouse.get_pos()
        for w in top_bar_widgets:
            if hasattr(w, 'check_hover'):
                w.check_hover(m_pos)
                
        # Update dropdown list options dynamically when clicked to catch hot-plugged devices!
        if midi_dropdown.is_open and pygame.time.get_ticks() % 60 == 0:
            midi_manager.refresh_ports()
            midi_dropdown.options = midi_manager.available_ports if midi_manager.available_ports else ["No MIDI Ports"]
            
        # 3. Draw screen graphics
        screen.fill(COLOR_BG)
        
        # A. Draw the clock board, tracks, control polygon, electric Bezier sweep arm, handles, and orbiting notes
        draw_clock_board(
            screen, CLOCK_CENTER, CLOCK_RADIUS, 
            sequencer.is_line_spinning, sequencer.sweep_angle, sequencer.handles,
            sequencer.notes, selected_note, fm
        )
        
        # B. Draw troubleshooting Debug Log overlay if toggled active
        if show_debug:
            debug_overlay = pygame.Surface((clock_area_w, HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(debug_overlay, (10, 11, 15, 235), (0, 0, clock_area_w, HEIGHT))
            screen.blit(debug_overlay, (0, 0))
            
            pygame.draw.line(screen, COLOR_BORDER, (clock_area_w, 0), (clock_area_w, HEIGHT), width=2)
            
            log_title = fm.render("SYSTEM DIAGNOSTICS & MIDI LOGGER", 'large', COLOR_PRIMARY)
            screen.blit(log_title, (30, 30))
            
            hint_txt1 = fm.render("exclusive-use locks: Close other DAWs/synthesizers on Windows if port fails.", 'tiny', COLOR_MUTED)
            screen.blit(hint_txt1, (30, 60))
            
            hint_txt2 = fm.render("MIDI concepts: This app is a transmitter (MIDI OUTPUT). It only lists outputs.", 'tiny', COLOR_MUTED)
            screen.blit(hint_txt2, (30, 78))
            
            hint_txt3 = fm.render("Physical keyboards (Inputs) do not expose outputs and will not appear.", 'tiny', COLOR_MUTED)
            screen.blit(hint_txt3, (30, 96))
            
            hint_txt4 = fm.render("Setup: Install loopMIDI (virtual cable) -> select in our app -> enable in DAW!", 'tiny', COLOR_EMERALD)
            screen.blit(hint_txt4, (30, 114))
            
            info_txt = fm.render(f"Device status: {midi_manager.status_message} | Active: {midi_manager.port_name}", 'small', COLOR_TEXT)
            screen.blit(info_txt, (30, 140))
            
            log_hdr = fm.render("TRANSFERRED PACKETS (LAST 13):", 'small', COLOR_PRIMARY)
            screen.blit(log_hdr, (30, 175))
            
            y_offset = 200
            if not midi_manager.logs:
                empty_surf = fm.render("No MIDI logs recorded. Press PLAY and trigger a note.", 'small', COLOR_MUTED)
                screen.blit(empty_surf, (30, y_offset))
            else:
                for entry in reversed(midi_manager.logs[-13:]):
                    log_color = COLOR_EMERALD if "Sent" in entry else (COLOR_PRIMARY if "Opened" in entry else COLOR_MUTED)
                    if "Error" in entry or "Failed" in entry:
                        log_color = COLOR_RED
                    entry_surf = fm.render(entry, 'small', log_color)
                    screen.blit(entry_surf, (30, y_offset))
                    y_offset += 24
                    
            help_hint = fm.render("Press 'D' key to close debug diagnostic log panel", 'tiny', COLOR_MUTED)
            screen.blit(help_hint, (30, HEIGHT - 30))
            
        # C. Draw top control bar background (solid bar separating controls from clock)
        pygame.draw.rect(screen, (22, 23, 31), (0, 0, WIDTH, 105))
        pygame.draw.line(screen, (35, 38, 55), (0, 105), (WIDTH, 105), width=2)
        
        # D. Draw brand title (No description/subtitle underneath!)
        title_surf = fm.render("KIRLIAN ORBITS", 'large', COLOR_PRIMARY)
        screen.blit(title_surf, (20, 10))
        
        # MIDI connection status diagnostics in Row 1 (Shifted up to y=38 to prevent overlapping y=60 buttons)
        status_lbl = fm.render("Status:", 'tiny', COLOR_MUTED)
        screen.blit(status_lbl, (20, 38))
        
        status_val = midi_manager.status_message
        if "Active" in status_val or "Ready" in status_val:
            status_color = COLOR_EMERALD
        elif "No Port" in status_val or "No MIDI" in status_val:
            status_color = COLOR_MUTED
        else:
            status_color = COLOR_RED
            
        status_val_surf = fm.render(status_val, 'tiny', status_color)
        screen.blit(status_val_surf, (65, 38))
        
        # Draw status hints at bottom-left
        if not show_debug:
            status_surf = fm.render("SPACE to Orbit | Warp Handles | Ctrl+S Save | Ctrl+O Load | D Logs | F11 Fullscreen | CLICK empty to Add", 'tiny', COLOR_MUTED)
            screen.blit(status_surf, (20, HEIGHT - 25))
            
        # E. Draw top bar control widgets (except dropdown overlay)
        for widget in top_bar_widgets:
            if widget != midi_dropdown:
                widget.draw(screen, fm)
                
        # F. Draw Note Editor sidebar panel
        sidebar.draw(screen, fm)
        
        # G. Draw MIDI port dropdown (placed on top of main widgets)
        midi_dropdown.draw(screen, fm)
        midi_dropdown.draw_options(screen, fm)
        
        # Blit display buffer
        pygame.display.flip()
        clock.tick(60)
        
    midi_manager.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
