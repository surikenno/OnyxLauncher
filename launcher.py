import os
import sys
import json
import subprocess
import threading
import requests
import re
import customtkinter as ctk
import minecraft_launcher_lib

# --- STYL ONYX ---
COLOR_BG = "#0a0a0a"
COLOR_SIDEBAR = "#121212"
COLOR_ACCENT = "#1f1f1f"
COLOR_BUTTON = "#2a2a2a"
COLOR_TEXT = "#ffffff"
COLOR_LOGS = "#00ff00"

class OnyxLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Onyx Launcher - Mod Manager")
        self.geometry("1100x600")
        self.configure(fg_color=COLOR_BG)

        self.minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        self.mods_directory = os.path.join(self.minecraft_directory, "mods")
        if not os.path.exists(self.mods_directory): os.makedirs(self.mods_directory)
        
        self.settings_path = os.path.join(self.minecraft_directory, "onyx_settings.json")
        self.load_settings()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="ONYX", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=30)
        
        self.create_nav_btn("GRAJ", "play")
        self.create_nav_btn("MODY", "mods")
        self.create_nav_btn("WERSJE", "install")
        self.create_nav_btn("LOGI", "logs")
        self.create_nav_btn("USTAWIENIA", "settings")

        # Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)

        self.frame_play = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_mods_main = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_install = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_logs = ctk.CTkFrame(self.container, fg_color="transparent")
        self.frame_settings = ctk.CTkFrame(self.container, fg_color="transparent")

        self.setup_play_ui()
        self.setup_mods_ui()
        self.setup_install_ui()
        self.setup_logs_ui()
        self.setup_settings_ui()
        self.show_tab("play")

    def create_nav_btn(self, text, tab_name):
        ctk.CTkButton(self.sidebar, text=text, fg_color="transparent", height=45, 
                     command=lambda: self.show_tab(tab_name)).pack(pady=5, padx=15, fill="x")

    def show_tab(self, name):
        for f in [self.frame_play, self.frame_mods_main, self.frame_install, self.frame_logs, self.frame_settings]: f.pack_forget()
        if name == "play": 
            self.refresh_installed_list()
            self.frame_play.pack(fill="both", expand=True)
        elif name == "mods":
            self.frame_mods_main.pack(fill="both", expand=True)
            self.show_mod_subtab("pobierz")
        elif name == "install": self.frame_install.pack(fill="both", expand=True)
        elif name == "logs": self.frame_logs.pack(fill="both", expand=True)
        else: self.frame_settings.pack(fill="both", expand=True)

    # --- ZAKŁADKA MODY ---
    def setup_mods_ui(self):
        tab_nav = ctk.CTkFrame(self.frame_mods_main, fg_color="transparent")
        tab_nav.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(tab_nav, text="SZUKAJ NOWYCH", fg_color=COLOR_ACCENT, width=150, 
                     command=lambda: self.show_mod_subtab("pobierz")).pack(side="left", padx=5)
        ctk.CTkButton(tab_nav, text="MOJE MODY", fg_color=COLOR_ACCENT, width=150, 
                     command=lambda: self.show_mod_subtab("pobrane")).pack(side="left", padx=5)

        self.subframe_pobierz = ctk.CTkFrame(self.frame_mods_main, fg_color="transparent")
        self.subframe_pobrane = ctk.CTkFrame(self.frame_mods_main, fg_color="transparent")

        search_bar = ctk.CTkFrame(self.subframe_pobierz, fg_color="transparent")
        search_bar.pack(fill="x", pady=10)

        self.mod_search = ctk.CTkEntry(search_bar, placeholder_text="Szukaj moda...", width=400)
        self.mod_search.pack(side="left", padx=(0, 10))
        self.mod_search.bind("<Return>", lambda e: self.refresh_modrinth_view())

        all_mc_versions = [
            "1.21.1", "1.21", "1.20.6", "1.20.4", "1.20.2", "1.20.1", "1.20",
            "1.19.4", "1.19.3", "1.19.2", "1.19.1", "1.19",
            "1.18.2", "1.18.1", "1.18", "1.17.1", "1.16.5", "1.12.2"
        ]
        
        self.mod_version_filter = ctk.CTkOptionMenu(search_bar, values=all_mc_versions, width=120, 
                                                   command=lambda v: self.refresh_modrinth_view())
        self.mod_version_filter.set("1.21.1")
        self.mod_version_filter.pack(side="left")
        
        self.mods_scroll = ctk.CTkScrollableFrame(self.subframe_pobierz, fg_color=COLOR_SIDEBAR, width=750, height=350)
        self.mods_scroll.pack(fill="both", expand=True, pady=10)

        self.pobrane_scroll = ctk.CTkScrollableFrame(self.subframe_pobrane, fg_color=COLOR_SIDEBAR, width=750, height=350)
        self.pobrane_scroll.pack(fill="both", expand=True, pady=10)

    def refresh_modrinth_view(self):
        for w in self.mods_scroll.winfo_children(): w.destroy()
        loading = ctk.CTkLabel(self.mods_scroll, text="Przeszukiwanie Modrinth...")
        loading.pack(pady=20)
        threading.Thread(target=self.fetch_modrinth, args=(loading,), daemon=True).start()

    def fetch_modrinth(self, loading_lbl):
        query = self.mod_search.get().strip()
        version = self.mod_version_filter.get()
        url = f"https://api.modrinth.com/v2/search?limit=24&facets=[[\"versions:{version}\"],[\"project_type:mod\"]]"
        if query: url += f"&query={query}"
        else: url += "&index=downloads"

        try:
            res = requests.get(url, timeout=10).json()
            local_files = os.listdir(self.mods_directory)
            self.after(0, loading_lbl.destroy)
            for mod in res['hits']:
                self.after(0, lambda m=mod, v=version, lf=local_files: self.create_mod_card(m, v, lf))
        except Exception as e:
            self.after(0, lambda: self.log(f"Błąd API: {e}"))

    def create_mod_card(self, mod, ver, local_files):
        card = ctk.CTkFrame(self.mods_scroll, fg_color=COLOR_ACCENT)
        card.pack(fill="x", pady=2, padx=5)
        
        ctk.CTkLabel(card, text=mod['title'], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(card, text=f"by {mod['author']}", text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")
        
        is_installed = any(mod['slug'] in f.lower() or mod['title'].lower().replace(" ", "-") in f.lower() for f in local_files)
        
        btn_text = "ZAKTUALIZUJ" if is_installed else "POBIERZ"
        btn_color = "#3498db" if is_installed else COLOR_BUTTON

        btn = ctk.CTkButton(card, text=btn_text, width=110, height=30, fg_color=btn_color,
                            command=lambda: self.download_latest_for_ver(mod['project_id'], ver, is_installed))
        btn.pack(side="right", padx=15)

    def download_latest_for_ver(self, p_id, ver, updating=False):
        def task():
            try:
                v_res = requests.get(f"https://api.modrinth.com/v2/project/{p_id}/version?game_versions=[\"{ver}\"]", timeout=10).json()
                if not v_res:
                    self.log(f"Błąd: Brak moda dla wersji {ver}")
                    return
                
                target = v_res[0]['files'][0]
                filename = target['filename']
                file_path = os.path.join(self.mods_directory, filename)

                if os.path.exists(file_path): os.remove(file_path)

                self.log(f"Pobieranie: {filename}...")
                r = requests.get(target['url'], timeout=20)
                with open(file_path, 'wb') as f:
                    f.write(r.content)
                
                # --- AUTO FABRIC API CHECK ---
                if "fabric" in ver.lower() or "fabric" in filename.lower():
                    local_files = os.listdir(self.mods_directory)
                    if not any("fabric-api" in f.lower() for f in local_files) and "fabric-api" not in filename.lower():
                        self.log("Wykryto Fabric - pobieram wymagane Fabric API...")
                        self.download_latest_for_ver("P7dR8mSH", ver) # ID Modrinth dla Fabric API

                self.log("Zaktualizowano!" if updating else "Zainstalowano!")
                self.after(0, self.refresh_modrinth_view)
            except Exception as e: self.log(f"Błąd: {e}")
        threading.Thread(target=task, daemon=True).start()

    # --- START GRY ---
    def launch_task(self):
        v = self.installed_option.get()
        if v == "Brak wersji": return
        self.after(0, lambda: self.btn_launch.configure(state="disabled", text="W GRZE"))
        
        try:
            base_version = v.split("-")[0] if "-" in v else v 
            minecraft_launcher_lib.install.install_minecraft_version(base_version, self.minecraft_directory)
            minecraft_launcher_lib.install.install_minecraft_version(v, self.minecraft_directory)
            
            o = {"username": self.entry_nick.get(), "uuid": "0"*32, "token": "0",
                 "jvmArguments": [f"-Xmx{int(self.ram_slider.get())}G"], "launcherName": "Onyx"}
            
            cmd = minecraft_launcher_lib.command.get_minecraft_command(v, self.minecraft_directory, o)
            
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 cwd=self.minecraft_directory,
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            
            for line in p.stdout: self.after(0, lambda l=line.strip(): self.log(l))
        except Exception as e: self.log(f"BŁĄD: {e}")
        self.after(0, lambda: self.btn_launch.configure(state="normal", text="GRAJ"))

    # --- UI & SETTINGS ---
    def setup_play_ui(self):
        ctk.CTkLabel(self.frame_play, text="ONYX", font=ctk.CTkFont(size=42, weight="bold")).pack(pady=20)
        self.entry_nick = ctk.CTkEntry(self.frame_play, width=380, height=45, fg_color=COLOR_SIDEBAR)
        self.entry_nick.insert(0, self.settings.get("nick", "Gracz"))
        self.entry_nick.pack(pady=10)
        self.installed_option = ctk.CTkOptionMenu(self.frame_play, width=380, height=45, fg_color=COLOR_SIDEBAR)
        self.installed_option.pack(pady=10)
        self.btn_launch = ctk.CTkButton(self.frame_play, text="GRAJ", width=380, height=60, 
                                        fg_color="#ffffff", text_color="#000000", command=self.start_launch)
        self.btn_launch.pack(pady=30)

    def setup_settings_ui(self):
        # RAM INFO
        self.ram_label = ctk.CTkLabel(self.frame_settings, text=f"PRZYPISANY RAM: {self.settings.get('ram', 4)} GB", font=ctk.CTkFont(weight="bold"))
        self.ram_label.pack(pady=(20, 0))

        self.ram_slider = ctk.CTkSlider(self.frame_settings, from_=2, to=16, number_of_steps=14, command=self.update_ram_label)
        self.ram_slider.set(self.settings.get("ram", 4))
        self.ram_slider.pack(pady=10, padx=60, fill="x")
        
        ctk.CTkButton(self.frame_settings, text="FOLDER .MINECRAFT", command=lambda: os.startfile(self.minecraft_directory)).pack(pady=10)

    def update_ram_label(self, value):
        self.ram_label.configure(text=f"PRZYPISANY RAM: {int(value)} GB")
        self.save_settings()

    def start_launch(self):
        self.save_settings()
        threading.Thread(target=self.launch_task, daemon=True).start()

    def setup_install_ui(self):
        self.install_scroll = ctk.CTkScrollableFrame(self.frame_install, fg_color=COLOR_SIDEBAR, width=650, height=450)
        self.install_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        threading.Thread(target=self.load_mojang, daemon=True).start()

    def load_mojang(self):
        try:
            rel = [v["id"] for v in minecraft_launcher_lib.utils.get_version_list() if v["type"] == "release"][:20]
            for v in rel:
                f = ctk.CTkFrame(self.install_scroll, fg_color="transparent")
                f.pack(fill="x", pady=2)
                ctk.CTkLabel(f, text=v).pack(side="left", padx=20)
                ctk.CTkButton(f, text="POBIERZ", width=80, command=lambda x=v: self.install_v(x)).pack(side="right", padx=10)
        except: pass

    def install_v(self, v):
        def t():
            self.log(f"Instalacja Minecraft {v}...")
            minecraft_launcher_lib.install.install_minecraft_version(v, self.minecraft_directory)
            self.after(0, self.refresh_installed_list)
        threading.Thread(target=t, daemon=True).start()

    def setup_logs_ui(self):
        self.log_text = ctk.CTkTextbox(self.frame_logs, fg_color=COLOR_SIDEBAR, text_color=COLOR_LOGS, font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

    def log(self, m):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {m}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def load_settings(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f: self.settings = json.load(f)
            else: self.settings = {"nick": "Gracz", "ram": 4}
        except: self.settings = {"nick": "Gracz", "ram": 4}

    def save_settings(self):
        self.settings.update({
            "nick": self.entry_nick.get() if hasattr(self, 'entry_nick') else self.settings.get("nick"),
            "version": self.installed_option.get() if hasattr(self, 'installed_option') else self.settings.get("version"),
            "ram": int(self.ram_slider.get()) if hasattr(self, 'ram_slider') else self.settings.get("ram")
        })
        with open(self.settings_path, "w") as f: json.dump(self.settings, f)

    def refresh_installed_list(self):
        inst = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)]
        self.installed_option.configure(values=inst if inst else ["Brak wersji"])
        if inst:
            curr = self.settings.get("version", inst[0])
            self.installed_option.set(curr if curr in inst else inst[0])

    def refresh_local_mods(self):
        for w in self.pobrane_scroll.winfo_children(): w.destroy()
        files = [f for f in os.listdir(self.mods_directory) if f.endswith(".jar")]
        for file in files:
            f_row = ctk.CTkFrame(self.pobrane_scroll, fg_color=COLOR_ACCENT)
            f_row.pack(fill="x", pady=2, padx=5)
            ctk.CTkLabel(f_row, text=file).pack(side="left", padx=10)
            ctk.CTkButton(f_row, text="USUŃ", width=60, height=24, fg_color="#e74c3c", 
                        command=lambda p=file: self.delete_mod(p)).pack(side="right", padx=10)

    def delete_mod(self, name):
        try:
            os.remove(os.path.join(self.mods_directory, name))
            self.refresh_local_mods()
        except: pass

    def show_mod_subtab(self, sub):
        self.subframe_pobierz.pack_forget()
        self.subframe_pobrane.pack_forget()
        if sub == "pobierz":
            self.subframe_pobierz.pack(fill="both", expand=True)
            self.refresh_modrinth_view()
        else:
            self.subframe_pobrane.pack(fill="both", expand=True)
            self.refresh_local_mods()

if __name__ == "__main__":
    app = OnyxLauncher()
    app.mainloop()