import customtkinter as ctk
from customtkinter import CTkInputDialog
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import datetime
import time
import os
import re
import shutil
import subprocess
try:
    import winreg
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
from pydub import AudioSegment
from tkinter import messagebox, Canvas
from PIL import Image, ImageTk

class DubberApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Instance Variables ---
        self.is_recording = False
        self.audio_frames = []
        self.current_project_path = None
        self.segment_status = {}
        self.mic_devices = {}
        self.output_devices = {}
        self.mic_volume_control = None
        self.mic_volume_range_db = (-60.0, 0.0)
        self.currently_playing_info = {}
        self.last_interacted_segment_path = None
        self.playback_volume_db = 0.0
        self.record_start_time = None
        self.playback_stop_event = None
        self.animation_job_id = None
        self.final_mix_play_btn = None
        self.segment_counter = 0
        
        self.HOVER_COLOR = "#3a3a3a"
        self.PLAY_HIGHLIGHT_COLOR = "#1f538d"
        
        # --- Window Configuration ---
        self.title("Nexus Dubbing Studio")
        self.geometry("1280x800")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- Main Layout Configuration ---
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # --- Project Panel (Left) ---
        self.project_frame = ctk.CTkFrame(self)
        self.project_frame.grid(row=0, column=0, padx=(10,5), pady=10, sticky="new")
        project_label = ctk.CTkLabel(self.project_frame, text="Project Management", font=ctk.CTkFont(size=16, weight="bold"))
        project_label.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew")
        create_project_frame = ctk.CTkFrame(self.project_frame)
        create_project_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        create_project_frame.grid_columnconfigure(0, weight=1)
        self.project_name_entry = ctk.CTkEntry(create_project_frame, placeholder_text="Enter new project name...")
        self.project_name_entry.grid(row=0, column=0, padx=(5,2), pady=5, sticky="ew")
        self.create_project_button = ctk.CTkButton(create_project_frame, text="Create", width=70, command=self._create_project)
        self.create_project_button.grid(row=0, column=1, padx=(2,5), pady=5)
        self.open_folder_button = ctk.CTkButton(self.project_frame, text="Open Project Folder", command=self._open_project_folder, state="disabled")
        self.open_folder_button.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        existing_projects_label = ctk.CTkLabel(self.project_frame, text="Existing Projects")
        existing_projects_label.grid(row=3, column=0, padx=10, pady=(5,0), sticky="sw")
        self.project_list_frame = ctk.CTkScrollableFrame(self.project_frame)
        self.project_list_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")

        # --- Right Panel with TabView ---
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, padx=(5,10), pady=10, sticky="nsew")
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.current_project_label = ctk.CTkLabel(self.right_panel, text="No Project Selected", font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        self.current_project_label.grid(row=0, column=0, padx=5, pady=(0,5), sticky="ew")
        self.tab_view = ctk.CTkTabview(self.right_panel, fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self.tab_view.grid(row=1, column=0, sticky="nsew")
        self.segments_tab = self.tab_view.add("Segments")
        self.final_mix_tab = self.tab_view.add("Final Mix")
        self.tab_view.set("Segments")

        # --- Populate Segments Tab ---
        self.segments_tab.grid_rowconfigure(2, weight=1)
        self.segments_tab.grid_columnconfigure(0, weight=1)
        self.controls_frame = ctk.CTkFrame(self.segments_tab)
        self.controls_frame.grid(row=0, column=0, padx=0, pady=0, sticky="ew")
        
        # --- Input Controls Group ---
        input_frame = ctk.CTkFrame(self.controls_frame)
        input_frame.pack(fill="x", padx=10, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        
        mic_label = ctk.CTkLabel(input_frame, text="Input Device (Microphone)")
        mic_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5,0))
        self.mic_dropdown = ctk.CTkOptionMenu(input_frame, values=self._get_mic_display_names())
        self.mic_dropdown.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)
        
        self.input_volume_label = ctk.CTkLabel(input_frame, text="Input Volume (Recording):")
        self.input_volume_label.grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        self.input_volume_db_label = ctk.CTkLabel(input_frame, text="0.0 dB", width=50)
        self.input_volume_db_label.grid(row=2, column=1, sticky="e", padx=5, pady=(5,0))
        self.input_volume_slider = ctk.CTkSlider(input_frame, from_=0, to=45, command=self._update_input_volume)
        self.input_volume_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(0,5))
        
        self.timer_label = ctk.CTkLabel(self.controls_frame, text="00:00.0", font=ctk.CTkFont(family="Segoe UI", size=48, weight="bold"))
        self.timer_label.pack(pady=5)
        self.record_button = ctk.CTkButton(self.controls_frame, text="Record (R)", height=35, fg_color="#D32F2F", hover_color="#B71C1C", command=self.toggle_recording, state="disabled")
        self.record_button.pack(pady=5, padx=10, fill="x")

        # --- Output Controls Group ---
        output_frame = ctk.CTkFrame(self.controls_frame)
        output_frame.pack(fill="x", padx=10, pady=(5,10))
        output_frame.grid_columnconfigure(0, weight=1)

        output_device_label = ctk.CTkLabel(output_frame, text="Output Device (Playback)")
        output_device_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(5,0))
        self.output_device_dropdown = ctk.CTkOptionMenu(output_frame, values=self._get_output_device_names())
        self.output_device_dropdown.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5)
        
        self.output_volume_label = ctk.CTkLabel(output_frame, text="Output Volume (Playback):")
        self.output_volume_label.grid(row=2, column=0, sticky="w", padx=5, pady=(5,0))
        self.output_volume_db_label = ctk.CTkLabel(output_frame, text="0.0 dB", width=50)
        self.output_volume_db_label.grid(row=2, column=1, sticky="e", padx=5, pady=(5,0))
        self.output_volume_slider = ctk.CTkSlider(output_frame, from_=-24, to=45, command=self._update_output_volume)
        self.output_volume_slider.set(0)
        self.output_volume_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(0,5))
        
        list_controls_frame = ctk.CTkFrame(self.segments_tab)
        list_controls_frame.grid(row=1, column=0, padx=0, pady=5, sticky="ew")
        list_controls_frame.grid_columnconfigure((0,1,2), weight=1)
        self.approve_all_button = ctk.CTkButton(list_controls_frame, text="Approve All", command=self._toggle_approve_all, state="disabled")
        self.approve_all_button.grid(row=0, column=0, padx=5, sticky="ew")
        self.preview_all_button = ctk.CTkButton(list_controls_frame, text="Preview Sequence", command=self._preview_all_segments, state="disabled")
        self.preview_all_button.grid(row=0, column=1, padx=5, sticky="ew")
        self.merge_button = ctk.CTkButton(list_controls_frame, text="Merge Approved", command=self._merge_segments, state="disabled")
        self.merge_button.grid(row=0, column=2, padx=5, sticky="ew")
        self.delete_all_button = ctk.CTkButton(list_controls_frame, text="Delete All", fg_color="#D32F2F", hover_color="#B71C1C", command=self._delete_all_segments, state="disabled")
        self.delete_all_button.grid(row=0, column=3, padx=5)

        self.segments_frame = ctk.CTkScrollableFrame(self.segments_tab, label_text="Segment Bay")
        self.segments_frame.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
        
        self.status_label = ctk.CTkLabel(self, text="Welcome! Create or open a project to begin.", anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0,5), sticky="ew")
        
        self._populate_project_list()
        self._initialize_mic_volume()
        
        self.bind("<r>", lambda event: self.toggle_recording())
        self.bind("<R>", lambda event: self.toggle_recording())
        self.bind("<space>", lambda event: self._play_last_interacted())

    # --- DEVICE & VOLUME CONTROLS ---
    def _get_output_device_names(self):
        self.output_devices.clear()
        try:
            hostapis = sd.query_hostapis()
            mme_index = next(i for i, api in enumerate(hostapis) if 'MME' in api['name'])
            devices = sd.query_devices()
            for device in devices:
                if device['max_output_channels'] > 0 and device['hostapi'] == mme_index:
                    self.output_devices[device['name']] = device['index']
            if self.output_devices:
                return list(self.output_devices.keys())
        except (StopIteration, Exception):
            pass
        return ["No MME device found"]

    def _initialize_mic_volume(self):
        if not PYCAW_AVAILABLE:
            self.input_volume_slider.configure(state="disabled")
            self.input_volume_label.configure(text="Input Volume (pycaw not found)")
            self.input_volume_db_label.configure(text="N/A")
            return
        try:
            mic = AudioUtilities.GetMicrophone(AudioUtilities.GetDefaultAudioEndpoint(0, 1)) # eCapture
            self.mic_volume_control = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            min_db, max_db, _ = self.mic_volume_control.GetVolumeRange()
            self.mic_volume_range_db = (min_db, max_db)
            self.input_volume_slider.configure(from_=min_db, to=min(max_db, 45))
            current_db = self.mic_volume_control.GetMasterVolumeLevel()
            self.input_volume_slider.set(current_db)
            self.input_volume_db_label.configure(text=f"{current_db:.1f} dB")
        except Exception as e:
            print(f"Could not initialize microphone volume control: {e}")
            self.input_volume_slider.configure(state="disabled")
            self.input_volume_label.configure(text="Input Volume (Error)")
            self.input_volume_db_label.configure(text="N/A")
    
    def _update_input_volume(self, value):
        db_value = float(value)
        if self.mic_volume_control:
            min_db, max_db = self.mic_volume_range_db
            clamped_db = np.clip(db_value, min_db, max_db)
            try:
                self.mic_volume_control.SetMasterVolumeLevel(clamped_db, None)
                self.input_volume_db_label.configure(text=f"{clamped_db:.1f} dB")
            except Exception as e:
                print(f"Failed to set input volume: {e}")

    def _update_output_volume(self, value):
        self.playback_volume_db = float(value)
        self.output_volume_db_label.configure(text=f"{self.playback_volume_db:.1f} dB")
        
    def _play_audio_thread(self, filepath, stop_event):
        try:
            selected_device_name = self.output_device_dropdown.get()
            device_index = self.output_devices.get(selected_device_name)
            data, samplerate = sf.read(filepath, dtype='float32', always_2d=True)
            total_frames = len(data)
            current_frame = 0
            
            def finished_callback_wrapper():
                self.after(0, self._on_playback_finished)

            def playback_callback(outdata, frames, time, status):
                nonlocal current_frame
                chunk_size = min(total_frames - current_frame, frames)
                chunk = data[current_frame : current_frame + chunk_size]
                gain = 10 ** (self.playback_volume_db / 20.0)
                adjusted_chunk = np.clip(chunk * gain, -1.0, 1.0)
                outdata[:chunk_size] = adjusted_chunk
                if chunk_size < frames:
                    outdata[chunk_size:] = np.zeros((frames - chunk_size, 1), dtype='float32')
                    raise sd.CallbackStop
                current_frame += chunk_size
            
            with sd.OutputStream(samplerate=samplerate, channels=1, callback=playback_callback,
                                 device=device_index, finished_callback=finished_callback_wrapper):
                stop_event.wait()
        
        except Exception as e: 
            self.after(0, self._handle_error, "Playback Error", f"Could not play '{os.path.basename(filepath)}'.\nError: {e}")
            self.after(0, self._on_playback_finished)
            
    # --- The rest of the file is included below... ---
    def _update_status(self, message: str):
        self.status_label.configure(text=message)
        
    def _set_ui_enabled(self, enabled: bool, is_preview_playing=False):
        state = "normal" if enabled else "disabled"
        ui_buttons = [self.record_button, self.merge_button, self.create_project_button, 
                      self.open_folder_button, self.approve_all_button, self.delete_all_button]
        for btn in ui_buttons: btn.configure(state=state)
        
        self.project_name_entry.configure(state=state)
        self.output_volume_slider.configure(state=state)
        if PYCAW_AVAILABLE:
            self.input_volume_slider.configure(state=state)
        
        if not is_preview_playing:
             self.preview_all_button.configure(state=state)

        for child in self.project_list_frame.winfo_children():
            for btn in child.winfo_children():
                if isinstance(btn, ctk.CTkButton): btn.configure(state=state)
        for seg_info in self.segment_status.values():
            for widget in seg_info.get("interactive_widgets", []):
                widget.configure(state=state)
    
    def _handle_error(self, title: str, message: str):
        messagebox.showerror(title, message)
        
    def _on_segment_enter(self, main_widget):
        if self.currently_playing_info.get("widget") != main_widget:
            main_widget.configure(fg_color=self.HOVER_COLOR)

    def _on_segment_leave(self, main_widget):
        if self.currently_playing_info.get("widget") != main_widget:
            main_widget.configure(fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])

    def _bind_hover_events(self, widget_to_bind, main_target_widget):
        widget_to_bind.bind("<Enter>", lambda event, w=main_target_widget: self._on_segment_enter(w), add="+")
        widget_to_bind.bind("<Leave>", lambda event, w=main_target_widget: self._on_segment_leave(w), add="+")
        for child in widget_to_bind.winfo_children():
            self._bind_hover_events(child, main_target_widget)
            
    def _populate_project_list(self):
        for widget in self.project_list_frame.winfo_children(): widget.destroy()
        dirs = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith(('.', '__'))]
        for project_name in sorted(dirs):
            project_entry_frame = ctk.CTkFrame(self.project_list_frame)
            project_entry_frame.pack(fill="x", padx=0, pady=1)
            project_entry_frame.grid_columnconfigure(0, weight=1)
            open_btn = ctk.CTkButton(project_entry_frame, text=project_name, command=lambda p=project_name: self._open_project(p), anchor="w")
            open_btn.grid(row=0, column=0, padx=(0,2), pady=0, sticky="ew")
            rename_btn = ctk.CTkButton(project_entry_frame, text="Rename", width=70, command=lambda p=project_name: self._rename_project(p))
            rename_btn.grid(row=0, column=1, padx=2, pady=0)
            delete_btn = ctk.CTkButton(project_entry_frame, text="Delete", width=60, fg_color="#D32F2F", hover_color="#B71C1C", command=lambda p=project_name: self._delete_project(p))
            delete_btn.grid(row=0, column=2, padx=2, pady=0)

    def _create_project(self):
        project_name = self.project_name_entry.get().strip()
        if not project_name: return
        project_name = re.sub(r'[\\/*?:"<>|]', "", project_name)
        try:
            if not os.path.exists(project_name):
                os.makedirs(project_name)
                self.project_name_entry.delete(0, 'end')
                self._populate_project_list()
                self._open_project(project_name)
            else:
                messagebox.showwarning("Warning", f"A project named '{project_name}' already exists.")
        except OSError as e:
            self._handle_error("Creation Failed", f"Could not create project folder:\n{e}")

    def _rename_project(self, old_name):
        dialog = CTkInputDialog(text="Enter new project name:", title="Rename Project")
        new_name = dialog.get_input()
        if not new_name or new_name.strip() == "": return
        new_name = re.sub(r'[\\/*?:"<>|]', "", new_name.strip())
        if os.path.exists(new_name):
            messagebox.showerror("Error", f"A project named '{new_name}' already exists.")
            return
        try:
            os.rename(old_name, new_name)
            self._update_status(f"Renamed '{old_name}' to '{new_name}'")
            if self.current_project_path == old_name:
                self._open_project(new_name)
            self._populate_project_list()
        except OSError as e:
            self._handle_error("Rename Failed", f"Could not rename project: {e}")

    def _delete_project(self, project_name):
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete the project '{project_name}' and all its audio files?")
        if not confirm: return
        try:
            shutil.rmtree(project_name)
            self._update_status(f"Project '{project_name}' deleted.")
            if self.current_project_path == project_name:
                self.current_project_path = None
                self.title("Nexus Dubbing Studio")
                self.current_project_label.configure(text="No Project Selected")
                for widget in self.segments_frame.winfo_children(): widget.destroy()
                for widget in self.final_mix_tab.winfo_children(): widget.destroy()
                self.segment_status.clear()
                ui_buttons = [self.record_button, self.merge_button, self.preview_all_button, 
                              self.open_folder_button, self.approve_all_button, self.delete_all_button]
                for btn in ui_buttons: btn.configure(state="disabled")
            self._populate_project_list()
        except OSError as e:
            self._handle_error("Deletion Failed", f"Could not delete project: {e}")

    def _open_project(self, project_name):
        self.current_project_path = project_name
        self.title(f"Nexus Dubbing Studio - {project_name}")
        self._update_status(f"Project '{project_name}' opened.")
        self.current_project_label.configure(text=f"Current Project: {project_name}")
        self.segment_status.clear()
        self.segment_counter = 0
        
        ui_buttons = [self.record_button, self.merge_button, self.preview_all_button, 
                      self.open_folder_button, self.approve_all_button, self.delete_all_button]
        for btn in ui_buttons: btn.configure(state="normal")
        
        self._redraw_segment_list()
        self._load_final_mix_tab()
    
    def _open_project_folder(self):
        if self.current_project_path and os.path.exists(self.current_project_path): os.startfile(self.current_project_path)
            
    def _play_last_interacted(self):
        if self.last_interacted_segment_path: self._play_segment(self.last_interacted_segment_path)

    def _stop_playback(self):
        if self.playback_stop_event: self.playback_stop_event.set()

    def _play_segment(self, filepath, is_final_mix=False, is_preview=False):
        old_info = self.currently_playing_info.copy()
        if self.playback_stop_event: self.playback_stop_event.set()
        if self.animation_job_id: self.after_cancel(self.animation_job_id)
        self._reset_playback_ui(old_info)
        self.currently_playing_info.clear()
        self.last_interacted_segment_path = filepath
        try:
            with sf.SoundFile(filepath) as f:
                duration = len(f) / f.samplerate
        except Exception as e:
            self._handle_error("Playback Error", f"Could not read audio file: {e}")
            self._on_playback_finished()
            return
        play_button_to_update = None
        if is_final_mix or is_preview:
            play_button_to_update = self.preview_all_button if is_preview else self.final_mix_play_btn
            self.currently_playing_info = {"is_final_mix": is_final_mix, "is_preview": is_preview, "filepath": filepath}
        else:
            segment_data = self.segment_status.get(filepath, {})
            widget_to_play = segment_data.get('widget')
            if widget_to_play:
                widget_to_play.configure(fg_color=self.PLAY_HIGHLIGHT_COLOR)
                play_button_to_update = segment_data.get('play_btn')
                self.currently_playing_info = {
                    "widget": widget_to_play, "canvas": segment_data.get('canvas'),
                    "playhead": segment_data.get('playhead'), "canvas_width": segment_data.get('canvas_width', 0),
                    "start_time": time.perf_counter(), "duration": duration, "filepath": filepath,
                    "play_btn": play_button_to_update
                }
        if play_button_to_update:
            button_text = "■ Stop" if not is_preview else "Stop Preview"
            play_button_to_update.configure(text=button_text, command=self._stop_playback)
        self.playback_stop_event = threading.Event()
        threading.Thread(target=self._play_audio_thread, args=(filepath, self.playback_stop_event,), daemon=True).start()
        if self.currently_playing_info.get("canvas"):
            self._animation_loop()

    def _animation_loop(self):
        info = self.currently_playing_info
        if not info or not info.get("start_time"): return
        elapsed = time.perf_counter() - info['start_time']
        progress = elapsed / info['duration'] if info['duration'] > 0 else 1.0
        if progress < 1.0:
            self._update_playhead(progress)
            self.animation_job_id = self.after(16, self._animation_loop)
        else:
            self._update_playhead(1.0)

    def _update_playhead(self, progress):
        info = self.currently_playing_info
        if info.get('canvas'):
            canvas, playhead_id, width = info['canvas'], info['playhead'], info['canvas_width']
            x_pos = min(width - 4, progress * (width - 8) + 4)
            canvas.coords(playhead_id, x_pos - 4, (20/2)-4, x_pos + 4, (20/2)+4)

    def _on_playback_finished(self):
        self._reset_playback_ui(self.currently_playing_info)
        self.currently_playing_info.clear()

    def _reset_playback_ui(self, info):
        if self.animation_job_id:
            self.after_cancel(self.animation_job_id)
            self.animation_job_id = None
        if info.get('widget') and info.get('play_btn'):
            info['widget'].configure(fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
            info['play_btn'].configure(text="▶ Play", command=lambda p=info['filepath']: self._play_segment(p))
            self._update_playhead(0.0)
        if info.get('is_final_mix') and self.final_mix_play_btn:
            self.final_mix_play_btn.configure(text="▶ Play Final Mix", command=lambda p=self.final_mix_play_btn.filepath: self._play_segment(p, is_final_mix=True))
        self.preview_all_button.configure(text="Preview Sequence", command=self._preview_all_segments)
    
    def _preview_all_segments(self):
        all_segment_paths = sorted([path for path in self.segment_status.keys()])
        if not all_segment_paths:
            messagebox.showinfo("Nothing to Preview", "There are no segments to preview.")
            return
        self._set_ui_enabled(False, is_preview_playing=True)
        self.preview_all_button.configure(text="Generating...")
        self._update_status("Generating full sequence preview...")
        threading.Thread(target=self._preview_all_segments_thread, args=(all_segment_paths,), daemon=True).start()
    
    def _preview_all_segments_thread(self, segment_paths):
        try:
            preview_cache_path = os.path.join(self.current_project_path, ".preview")
            os.makedirs(preview_cache_path, exist_ok=True)
            temp_preview_path = os.path.join(preview_cache_path, "temp_preview.wav")
            combined = AudioSegment.empty()
            for path in segment_paths: combined += AudioSegment.from_wav(path)
            combined.export(temp_preview_path, format="wav")
            self.after(0, self._on_preview_generated, True, temp_preview_path)
        except Exception as e:
            self.after(0, self._on_preview_generated, False, str(e))
    
    def _on_preview_generated(self, success, result):
        if success:
            self._update_status("Playing full sequence preview...")
            self._set_ui_enabled(True, is_preview_playing=True) 
            self._play_segment(result, is_preview=True)
        else:
            self._set_ui_enabled(True)
            self.preview_all_button.configure(text="Preview Sequence")
            self._handle_error("Preview Error", f"Could not generate preview: {result}")
            self._update_status("Preview generation failed.")
            
    def _on_merge_complete(self, success: bool, result: str):
        self.merge_button.configure(text="Merge Approved")
        self._set_ui_enabled(True)
        if success:
            messagebox.showinfo("Success", f"Merged file saved as '{result}'.")
            self._update_status(f"Merge successful: {os.path.basename(result)}")
            self._load_final_mix_tab()
            self.tab_view.set("Final Mix")
        else:
            self._handle_error("Merge Error", f"An error occurred: {result}")
            self._update_status("Merge failed!")
    
    def _load_final_mix_tab(self):
        for widget in self.final_mix_tab.winfo_children(): widget.destroy()
        merged_file_path = os.path.join(self.current_project_path, "final_dub.wav")
        if os.path.exists(merged_file_path):
            try:
                with sf.SoundFile(merged_file_path) as f: duration = len(f) / f.samplerate
            except Exception: duration = 0.0
            mix_frame = ctk.CTkFrame(self.final_mix_tab)
            mix_frame.pack(fill="x", padx=10, pady=10)
            title_label = ctk.CTkLabel(mix_frame, text="Final Mix", font=ctk.CTkFont(size=16, weight="bold"))
            title_label.pack(pady=5)
            duration_label = ctk.CTkLabel(mix_frame, text=f"Duration: {duration:.1f}s", text_color="gray")
            duration_label.pack()
            canvas_width, canvas_height = 400, 20
            canvas = Canvas(mix_frame, width=canvas_width, height=canvas_height, bg="#2b2b2b", highlightthickness=0)
            canvas.pack(pady=10)
            canvas.create_line(4, canvas_height/2, canvas_width-4, canvas_height/2, fill="gray")
            controls_frame = ctk.CTkFrame(mix_frame, fg_color="transparent")
            controls_frame.pack(pady=10)
            self.final_mix_play_btn = ctk.CTkButton(controls_frame, text="▶ Play Final Mix", height=40, command=lambda p=merged_file_path: self._play_segment(p, is_final_mix=True))
            self.final_mix_play_btn.filepath = merged_file_path
            self.final_mix_play_btn.grid(row=0, column=0, padx=5)
            remerge_btn = ctk.CTkButton(controls_frame, text="Re-Merge", height=40, command=self._merge_segments)
            remerge_btn.grid(row=0, column=1, padx=5)
            delete_btn = ctk.CTkButton(controls_frame, text="🗑️ Delete", height=40, fg_color="#D32F2F", hover_color="#B71C1C", command=lambda p=merged_file_path: self._delete_final_mix(p))
            delete_btn.grid(row=0, column=2, padx=5)
        else:
            no_mix_label = ctk.CTkLabel(self.final_mix_tab, text="No final mix available.\nApprove and merge segments to create one.", font=ctk.CTkFont(size=14))
            no_mix_label.pack(expand=True)
    
    def _delete_final_mix(self, filepath):
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to permanently delete the final merged file?"):
            try:
                os.remove(filepath)
                self._update_status("Deleted final mix.")
                self._load_final_mix_tab()
            except Exception as e: self._handle_error("Error", f"Could not delete file: {e}")
    
    def _redraw_segment_list(self):
        for widget in self.segments_frame.winfo_children(): widget.destroy()
        filepaths = sorted(self.segment_status.keys(), reverse=True)
        for i, filepath in enumerate(filepaths):
            title = f"Segment {len(filepaths) - i}"
            self._create_and_pack_segment_widget(title, filepath)

    def _create_and_pack_segment_widget(self, title, filepath):
        segment_entry = ctk.CTkFrame(self.segments_frame, border_width=1, border_color="gray30")
        segment_entry.pack(fill="x", padx=5, pady=2)
        segment_entry.grid_columnconfigure(0, weight=1)
        info = self.segment_status[filepath]
        try:
            mtime = os.path.getmtime(filepath)
            timestamp_str = datetime.datetime.fromtimestamp(mtime).strftime('%d-%b-%Y %H:%M:%S')
            with sf.SoundFile(filepath) as f: duration = len(f) / f.samplerate
        except Exception: 
            duration, timestamp_str = 0.0, "N/A"
        left_panel = ctk.CTkFrame(segment_entry, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        title_label = ctk.CTkLabel(left_panel, text=title, anchor="w", font=ctk.CTkFont(weight="bold"))
        title_label.pack(fill="x")
        info_text = f"{duration:.1f}s | {timestamp_str}"
        duration_label = ctk.CTkLabel(left_panel, text=info_text, anchor="w", text_color="gray")
        duration_label.pack(fill="x", pady=(0, 5))
        canvas_width, canvas_height = 250, 20
        canvas = Canvas(left_panel, width=canvas_width, height=canvas_height, bg="#2b2b2b", highlightthickness=0)
        canvas.pack(fill="x", pady=2, anchor="w")
        canvas.create_line(4, canvas_height/2, canvas_width-4, canvas_height/2, fill="gray")
        playhead = canvas.create_oval(0, (canvas_height/2)-4, 8, (canvas_height/2)+4, fill="#d13535", outline="#d13535")
        controls_frame = ctk.CTkFrame(segment_entry, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="ns", padx=5, pady=5)
        approve_var = ctk.StringVar(value="on" if info.get("approved") else "off")
        approve_check = ctk.CTkCheckBox(controls_frame, text="Approve", variable=approve_var, onvalue="on", offvalue="off", command=lambda p=filepath: self._toggle_approve(p, approve_var))
        approve_check.pack(pady=2, padx=5, fill='x')
        play_btn = ctk.CTkButton(controls_frame, text="▶ Play", command=lambda p=filepath: self._play_segment(p))
        play_btn.pack(pady=2, padx=5, fill='x')
        delete_btn = ctk.CTkButton(controls_frame, text="🗑️ Delete", fg_color="#D32F2F", hover_color="#B71C1C", command=lambda p=filepath: self._delete_segment(p))
        delete_btn.pack(pady=2, padx=5, fill='x')
        interactive_widgets = [approve_check, play_btn, delete_btn]
        info.update({
            "widget": segment_entry, "approve_var": approve_var, "title": title,
            "interactive_widgets": interactive_widgets, "play_btn": play_btn,
            "canvas": canvas, "playhead": playhead, "canvas_width": canvas_width
        })
        self._bind_hover_events(segment_entry, segment_entry)
        
    def _toggle_approve_all(self):
        if not self.segment_status: return
        target_state = any(not info["approved"] for info in self.segment_status.values())
        for info in self.segment_status.values():
            info["approved"] = target_state
            info["approve_var"].set("on" if target_state else "off")
        self._update_status("Approved all segments." if target_state else "Deselected all segments.")
        
    def _delete_all_segments(self):
        if not self.segment_status: return
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete ALL {len(self.segment_status)} segments in this project?\n\nThis action cannot be undone."):
            paths_to_delete = list(self.segment_status.keys())
            for path in paths_to_delete:
                try: os.remove(path)
                except OSError as e: print(f"Could not delete file {path}: {e}")
            self.segment_status.clear()
            self._redraw_segment_list()
            self._update_status(f"Deleted all {len(paths_to_delete)} segments.")

    def _toggle_approve(self, filepath, var):
        if filepath not in self.segment_status: return
        self.segment_status[filepath]["approved"] = var.get() == "on"
    
    def _delete_segment(self, filepath):
        if filepath not in self.segment_status: return
        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete this segment?\n\n{os.path.basename(filepath)}?"):
            try:
                os.remove(filepath)
                del self.segment_status[filepath]
                self._redraw_segment_list()
                self._update_status(f"Deleted segment: {os.path.basename(filepath)}")
            except Exception as e: self._handle_error("Error", f"Could not delete file: {e}")
    
    def _merge_segments(self):
        approved_files = sorted([path for path, info in self.segment_status.items() if info["approved"]])
        if not approved_files:
            messagebox.showinfo("Nothing to Merge", "No segments have been approved.")
            return
        self._set_ui_enabled(False)
        self.merge_button.configure(text="Merging...")
        self._update_status("Merging segments...")
        threading.Thread(target=self._merge_segments_thread, args=(approved_files,), daemon=True).start()
    
    def _get_mic_display_names(self):
        self.mic_devices.clear()
        try:
            hostapis = sd.query_hostapis()
            mme_index = next(i for i, api in enumerate(hostapis) if 'MME' in api['name'])
        except StopIteration: return ["No MME microphone found"]
        devices = sd.query_devices()
        for device in devices:
            if device['max_input_channels'] > 0 and device['hostapi'] == mme_index: self.mic_devices[device['name']] = device['index']
        if self.mic_devices: return list(self.mic_devices.keys())
        else: return ["No MME microphone found"]
    
    def toggle_recording(self, event=None):
        if self.record_button.cget("state") == "disabled": return
        if self.is_recording:
            self.is_recording = False
            self.record_start_time = None
        else:
            if not self.mic_devices or self.mic_dropdown.get() not in self.mic_devices:
                messagebox.showerror("Error", "No valid microphone selected.")
                return
            self.is_recording = True
            self.record_start_time = datetime.datetime.now()
            self._update_timer()
            time_str = self.record_start_time.strftime("%H:%M:%S")
            self._update_status(f"● Recording started at {time_str}")
            self.record_button.configure(text="Stop (R)", fg_color="#388E3C", hover_color="#1B5E20")
            threading.Thread(target=self._record_thread, daemon=True).start()
    
    def _update_timer(self):
        if self.is_recording and self.record_start_time:
            delta = datetime.datetime.now() - self.record_start_time
            total_seconds = delta.total_seconds()
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            tenths = int((total_seconds * 10) % 10)
            self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}.{tenths}")
            self.after(100, self._update_timer)
    
    def _record_thread(self):
        self.audio_frames.clear()
        try:
            samplerate = 44100
            selected_device_name = self.mic_dropdown.get()
            selected_device_index = self.mic_devices[selected_device_name]
            def callback(indata, frames, time, status):
                if status: print(status)
                self.audio_frames.append(indata.copy())
            with sd.InputStream(device=selected_device_index, channels=1, samplerate=samplerate, callback=callback):
                while self.is_recording: sd.sleep(100)
            self.after(0, self._finalize_recording, samplerate)
        except Exception as e:
            self.is_recording = False
            self.after(0, self._reset_record_button)
            self.after(0, self._handle_error, "Recording Error", f"An audio device error occurred:\n{e}")
     
    def _reset_record_button(self):
        self.record_button.configure(text="Record (R)", fg_color="#D32F2F", hover_color="#B71C1C")
        self.timer_label.configure(text="00:00.0")
    
    def _merge_segments_thread(self, approved_files):
        try:
            if not approved_files:
                self.after(0, self._on_merge_complete, False, "No approved files to merge.")
                return
            combined_audio = AudioSegment.empty()
            for filepath in approved_files: combined_audio += AudioSegment.from_wav(filepath)
            output_filename = os.path.join(self.current_project_path, "final_dub.wav")
            combined_audio.export(output_filename, format="wav")
            self.after(0, self._on_merge_complete, True, output_filename)
        except Exception as e:
            self.after(0, self._on_merge_complete, False, str(e))

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    app = DubberApp()
    app.mainloop()